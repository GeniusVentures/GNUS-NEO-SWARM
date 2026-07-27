"""SGFP4 v1 fixed-payload and v2 adaptive-quadtree exporter.

Container layout v1::

    headers[B] | offsets[B] | codes_blob[B * 2048]

Container layout v2::

    magic[4] | version[1] | B[4] | pad0[7] | record_offsets[B] |
    pad1[0..12] | records[0..B-1]

For v2, ``pad1`` aligns the record-region base to 16 bytes. Record offsets
are relative to that aligned base. Each record and each leaf payload is also
zero-padded to a 16-byte multiple.
"""

import argparse
import json
import math
import struct
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import numpy as np

from quantize.sgfp4_format import (
    ALIGNMENT,
    FP16_MAX,
    HEADER_CLEAR_FLAGS_MASK,
    LEAF_MODE_MASK,
    MACROBLOCK_SIZE,
    MIN_LEAF_SIZE,
    OFFSET_FLAG_MASK,
    PAYLOAD_BYTES,
    PAYLOAD_U32,
    SB_HEADER_LAYOUT_MASK,
    SGFP4_MAGIC,
    SGFP4_VERSION_V2,
    SPLIT_MAP_MAX_BITS,
    SPLIT_MAP_WORDS,
    UINT32_BITS,
    V2_HEADER_PAD_BYTES,
    CodeMode,
    Layout,
)


# Backward-compatible aliases used by existing callers and tests.
MODE_FP4_AFFINE = CodeMode.FP4_AFFINE
MODE_T158_AFFINE = CodeMode.T158_AFFINE

LAYOUT_UNIFORM_64 = Layout.UNIFORM_64
LAYOUT_UNIFORM_32 = Layout.UNIFORM_32
LAYOUT_UNIFORM_16 = Layout.UNIFORM_16
LAYOUT_UNIFORM_8 = Layout.UNIFORM_8
LAYOUT_MIXED = Layout.MIXED
LAYOUT_FULL_4x4 = Layout.FULL_4X4


def _zero_pad(data: bytes, alignment: int = ALIGNMENT) -> bytes:
    """Append zero bytes until ``len(data)`` is a multiple of alignment."""
    if alignment <= 0:
        raise ValueError("alignment must be positive")
    return data + b"\x00" * ((-len(data)) % alignment)


DEFAULT_V2_THRESHOLDS = {
    64: {"max_mse": 0.01, "max_relative": 0.05},
    32: {"max_mse": 0.005, "max_relative": 0.03},
    16: {"max_mse": 0.002, "max_relative": 0.02},
    8: {"max_mse": 0.001, "max_relative": 0.01},
    4: {"max_mse": 0.0005, "max_relative": 0.005},
}


class FP4Exporter:
    """Export two-dimensional weight tensors to SGFP4 v1 or v2."""

    def __init__(self, project_root: Optional[Path] = None):
        if project_root is None:
            project_root = Path(__file__).resolve().parent.parent
        self._root = project_root
        self._artifacts_dir = project_root / "artifacts"

    def export_weights(
        self,
        weights: np.ndarray,
        niche_name: str,
        prefer_ternary: bool = False,
        ternary_delta: float = 0.10,
        adaptive: bool = False,
        thresholds: Optional[Dict[int, Dict[str, float]]] = None,
        min_block_size: int = 4,
        laplacian_levels: int = 3,
    ) -> Tuple[bytes, dict]:
        """Export a two-dimensional float weight tensor.

        ``adaptive=False`` selects the v1 fixed-payload profile.
        ``adaptive=True`` selects the v2 quadtree-adaptive profile.
        """
        if weights.ndim != 2:
            raise ValueError("weights must be a two-dimensional array")

        if adaptive:
            return self._export_v2_adaptive(
                weights,
                niche_name,
                prefer_ternary=prefer_ternary,
                ternary_delta=ternary_delta,
                thresholds=thresholds,
                min_block_size=min_block_size,
                laplacian_levels=laplacian_levels,
            )

        return self._export_v1_fixed(
            weights,
            niche_name,
            prefer_ternary=prefer_ternary,
            ternary_delta=ternary_delta,
        )

    def export_to_file(
        self,
        weights: np.ndarray,
        niche_name: str,
        output_dir: Optional[Path] = None,
        adaptive: bool = False,
        thresholds: Optional[Dict[int, Dict[str, float]]] = None,
        min_block_size: int = 4,
        laplacian_levels: int = 3,
        base_model: str = "",
        training_metadata: Optional[dict] = None,
        **kwargs,
    ):
        """Export weights to disk and write stats and, for v2, a manifest."""
        binary, stats = self.export_weights(
            weights,
            niche_name,
            adaptive=adaptive,
            thresholds=thresholds,
            min_block_size=min_block_size,
            laplacian_levels=laplacian_levels,
            **kwargs,
        )

        if output_dir is None:
            output_dir = self._artifacts_dir / "fp4" / niche_name
        output_dir.mkdir(parents=True, exist_ok=True)

        extension = ".sgfp4" if adaptive else ".fp4"
        bin_path = output_dir / f"{niche_name}{extension}"
        bin_path.write_bytes(binary)

        stats_path = output_dir / f"{niche_name}_stats.json"
        stats_path.write_text(json.dumps(stats, indent=2))

        if adaptive:
            self._write_manifest(
                niche_name=niche_name,
                bin_path=bin_path,
                stats=stats,
                base_model=base_model,
                training_metadata=training_metadata or {},
                output_dir=output_dir,
            )

        return bin_path, stats

    # ------------------------------------------------------------------
    # v1 fixed-payload profile
    # ------------------------------------------------------------------

    def _export_v1_fixed(
        self,
        weights: np.ndarray,
        niche_name: str,
        prefer_ternary: bool = False,
        ternary_delta: float = 0.10,
    ) -> Tuple[bytes, dict]:
        """Export the v1 fixed 64x64 profile."""
        del niche_name
        output_count, input_count = weights.shape
        tiles_y = math.ceil(output_count / MACROBLOCK_SIZE)
        tiles_x = math.ceil(input_count / MACROBLOCK_SIZE)
        block_count = tiles_y * tiles_x

        padded = np.zeros(
            (tiles_y * MACROBLOCK_SIZE, tiles_x * MACROBLOCK_SIZE),
            dtype=np.float32,
        )
        padded[:output_count, :input_count] = weights.astype(np.float32)

        headers = np.zeros(block_count, dtype="<u4")
        offsets = np.zeros(block_count, dtype="<u4")
        code_blocks = []

        current_offset = 0
        for block_y in range(tiles_y):
            for block_x in range(tiles_x):
                block_index = block_y * tiles_x + block_x
                block = padded[
                    block_y * MACROBLOCK_SIZE:(block_y + 1) * MACROBLOCK_SIZE,
                    block_x * MACROBLOCK_SIZE:(block_x + 1) * MACROBLOCK_SIZE,
                ]

                fp4_result = self._encode_fp4_affine(block)
                t158_result = self._encode_t158_affine(block)
                if (
                    prefer_ternary
                    and t158_result["l2_error"]
                    <= (1.0 + ternary_delta) * fp4_result["l2_error"]
                ):
                    mode = MODE_T158_AFFINE
                    selected = t158_result
                else:
                    mode = MODE_FP4_AFFINE
                    selected = fp4_result

                scale = float(np.clip(selected["scale"], -FP16_MAX, FP16_MAX))
                bias = float(np.clip(selected["bias"], -FP16_MAX, FP16_MAX))
                headers[block_index] = self._pack_half2(scale, bias)

                if current_offset % ALIGNMENT != 0:
                    raise AssertionError("v1 payload offset is not aligned")
                offsets[block_index] = (
                    (current_offset & ~OFFSET_FLAG_MASK)
                    | (int(mode) & OFFSET_FLAG_MASK)
                )

                block_payload = selected["payload"]
                if len(block_payload) != PAYLOAD_U32:
                    raise AssertionError("v1 payload has the wrong size")
                code_blocks.append(block_payload.astype("<u4", copy=False))
                current_offset += PAYLOAD_BYTES

        codes_blob = b"".join(block.tobytes() for block in code_blocks)
        fp4_blocks = sum(1 for word in offsets if (int(word) & 0x1) == 0)
        t158_blocks = block_count - fp4_blocks

        stats = {
            "shape": [output_count, input_count],
            "num_blocks": block_count,
            "tiles_y": tiles_y,
            "tiles_x": tiles_x,
            "total_bytes": len(codes_blob) + block_count * 8,
            "fp4_blocks": fp4_blocks,
            "t158_blocks": t158_blocks,
        }
        return headers.tobytes() + offsets.tobytes() + codes_blob, stats

    # ------------------------------------------------------------------
    # v2 quadtree-adaptive profile
    # ------------------------------------------------------------------

    def _export_v2_adaptive(
        self,
        weights: np.ndarray,
        niche_name: str,
        prefer_ternary: bool = False,
        ternary_delta: float = 0.10,
        thresholds: Optional[Dict[int, Dict[str, float]]] = None,
        min_block_size: int = 4,
        laplacian_levels: int = 3,
    ) -> Tuple[bytes, dict]:
        """Export the SGFP4 v2 quadtree-adaptive profile.

        The framing is::

            SGF4 | 0x02 | B | pad0 | offsets[B] | pad1 | records

        ``pad1`` is zero-filled so the record-region base is
        ``align16(16 + 4*B)``. Offsets remain relative to that base.
        """
        del niche_name, prefer_ternary, laplacian_levels
        output_count, input_count = weights.shape
        tiles_y = math.ceil(output_count / MACROBLOCK_SIZE)
        tiles_x = math.ceil(input_count / MACROBLOCK_SIZE)
        block_count = tiles_y * tiles_x

        padded = np.zeros(
            (tiles_y * MACROBLOCK_SIZE, tiles_x * MACROBLOCK_SIZE),
            dtype=np.float32,
        )
        padded[:output_count, :input_count] = weights.astype(np.float32)

        if thresholds is None:
            thresholds = DEFAULT_V2_THRESHOLDS

        from quantize.laplacian import LaplacianWeightedError
        from quantize.quadtree import QuadtreeEncoder

        laplacian = LaplacianWeightedError()
        superblock_layouts = []
        total_fp4_blocks = 0
        total_t158_blocks = 0

        for block_y in range(tiles_y):
            for block_x in range(tiles_x):
                superblock = padded[
                    block_y * MACROBLOCK_SIZE:(block_y + 1) * MACROBLOCK_SIZE,
                    block_x * MACROBLOCK_SIZE:(block_x + 1) * MACROBLOCK_SIZE,
                ]
                encoder = QuadtreeEncoder(
                    thresholds=thresholds,
                    ternary_delta=ternary_delta,
                    fit_fp4=self._encode_fp4_affine_variable,
                    fit_t158=self._encode_t158_affine_variable,
                    laplacian=laplacian,
                    min_block_size=min_block_size,
                )
                blocks = encoder.encode(superblock)
                layout = self._classify_layout(blocks)
                superblock_layouts.append((layout, blocks))

                for block in blocks:
                    if block["mode"] == MODE_FP4_AFFINE:
                        total_fp4_blocks += 1
                    else:
                        total_t158_blocks += 1

        record_chunks = []
        record_offsets = np.zeros(block_count, dtype="<u4")
        current_offset = 0

        for index, (layout, blocks) in enumerate(superblock_layouts):
            if layout == Layout.MIXED:
                split_map = self._build_split_map(blocks)
            else:
                split_map = b""
                blocks = sorted(blocks, key=lambda block: (block["y"], block["x"]))

            sb_header = struct.pack("<I", int(layout) & SB_HEADER_LAYOUT_MASK)
            leaf_headers = []
            for block in blocks:
                packed = self._pack_half2(
                    float(np.clip(block["scale"], -FP16_MAX, FP16_MAX)),
                    float(np.clip(block["bias"], -FP16_MAX, FP16_MAX)),
                )
                # v2 bit 0 is MODE. Bits 1-3 are reserved and remain zero.
                flags = int(block["mode"]) & LEAF_MODE_MASK
                leaf_headers.append(
                    struct.pack(
                        "<I",
                        (int(packed) & HEADER_CLEAR_FLAGS_MASK) | flags,
                    )
                )

            header_section = _zero_pad(
                sb_header + split_map + b"".join(leaf_headers)
            )
            payload_chunks = [
                _zero_pad(
                    block["payload"].astype("<u4", copy=False).tobytes()
                )
                for block in blocks
            ]
            record = _zero_pad(header_section + b"".join(payload_chunks))

            if current_offset % ALIGNMENT != 0:
                raise AssertionError("v2 record offset is not aligned")
            record_offsets[index] = current_offset
            record_chunks.append(record)
            current_offset += len(record)

        framing = (
            SGFP4_MAGIC
            + struct.pack("<B", SGFP4_VERSION_V2)
            + struct.pack("<I", block_count)
            + b"\x00" * V2_HEADER_PAD_BYTES
            + record_offsets.tobytes()
        )
        framing = _zero_pad(framing)
        binary = framing + b"".join(record_chunks)

        total_weights = int(output_count * input_count)
        total_bits = len(binary) * 8
        effective_bpw = total_bits / total_weights if total_weights > 0 else 0.0
        layout_distribution = {value: 0 for value in range(6)}
        for layout, _ in superblock_layouts:
            layout_distribution[int(layout)] += 1

        stats = {
            "shape": [output_count, input_count],
            "num_superblocks": block_count,
            "tiles_y": tiles_y,
            "tiles_x": tiles_x,
            "total_bytes": len(binary),
            "fp4_blocks": total_fp4_blocks,
            "t158_blocks": total_t158_blocks,
            "total_blocks": total_fp4_blocks + total_t158_blocks,
            "effective_bpw": round(effective_bpw, 4),
            "layout_distribution": layout_distribution,
        }
        return binary, stats

    # ------------------------------------------------------------------
    # Code fitting and packing
    # ------------------------------------------------------------------

    def _encode_fp4_affine(self, block: np.ndarray) -> dict:
        """Encode one v1 64x64 block in FP4_AFFINE mode."""
        flat = block.ravel().astype(np.float32)
        scale, bias = self._fit_affine(flat)
        codes = np.clip(
            np.round((flat - bias) / scale),
            -8,
            7,
        ).astype(np.int8)
        reconstructed = scale * codes.astype(np.float32) + bias
        l2_error = float(np.sqrt(np.mean((flat - reconstructed) ** 2)))

        payload = np.zeros(PAYLOAD_U32, dtype="<u4")
        for index in range(4096):
            code = int(codes[index]) & 0xF
            word = index // 8
            shift = 4 * (index % 8)
            payload[word] |= np.uint32(code) << np.uint32(shift)
        return {
            "scale": scale,
            "bias": bias,
            "l2_error": l2_error,
            "payload": payload,
        }

    def _encode_t158_affine(self, block: np.ndarray) -> dict:
        """Encode one v1 64x64 block in T158_AFFINE mode."""
        flat = block.ravel().astype(np.float32)
        scale, bias = self._fit_ternary(flat)
        ternary = self._ternary_codes(flat, scale, bias)
        reconstructed = scale * ternary.astype(np.float32) + bias
        l2_error = float(np.sqrt(np.mean((flat - reconstructed) ** 2)))

        payload = np.zeros(PAYLOAD_U32, dtype="<u4")
        self._pack_ternary_codes(ternary, payload)
        return {
            "scale": scale,
            "bias": bias,
            "l2_error": l2_error,
            "payload": payload,
        }

    def _encode_fp4_affine_variable(self, region: np.ndarray) -> dict:
        """Encode a square v2 leaf in FP4_AFFINE mode."""
        flat = region.ravel().astype(np.float32)
        n_weights = flat.size
        scale, bias = self._fit_affine(flat)
        codes = np.clip(
            np.round((flat - bias) / scale),
            -8,
            7,
        ).astype(np.int8)
        reconstructed = scale * codes.astype(np.float32) + bias
        l2_error = float(np.sqrt(np.mean((flat - reconstructed) ** 2)))

        payload = np.zeros(n_weights // 8, dtype="<u4")
        for index in range(n_weights):
            code = int(codes[index]) & 0xF
            word = index // 8
            shift = 4 * (index % 8)
            payload[word] |= np.uint32(code) << np.uint32(shift)
        return {
            "scale": scale,
            "bias": bias,
            "l2_error": l2_error,
            "payload": payload,
            "n_weights": n_weights,
        }

    def _encode_t158_affine_variable(self, region: np.ndarray) -> dict:
        """Encode a square v2 leaf in T158_AFFINE mode."""
        flat = region.ravel().astype(np.float32)
        n_weights = flat.size
        scale, bias = self._fit_ternary(flat)
        ternary = self._ternary_codes(flat, scale, bias)
        reconstructed = scale * ternary.astype(np.float32) + bias
        l2_error = float(np.sqrt(np.mean((flat - reconstructed) ** 2)))

        payload = np.zeros(n_weights // 16, dtype="<u4")
        self._pack_ternary_codes(ternary, payload)
        return {
            "scale": scale,
            "bias": bias,
            "l2_error": l2_error,
            "payload": payload,
            "n_weights": n_weights,
        }

    @staticmethod
    def _ternary_codes(
        values: np.ndarray,
        scale: float,
        bias: float,
    ) -> np.ndarray:
        centered = values - bias
        threshold = 0.5 * scale
        codes = np.zeros(values.size, dtype=np.int8)
        codes[centered > threshold] = 1
        codes[centered < -threshold] = -1
        return codes

    @staticmethod
    def _pack_ternary_codes(codes: np.ndarray, payload: np.ndarray) -> None:
        for index, value in enumerate(codes):
            ternary = int(value)
            bits = 0 if ternary == 0 else (1 if ternary == 1 else 2)
            word = index // 16
            shift = 2 * (index % 16)
            payload[word] |= np.uint32(bits) << np.uint32(shift)

    def _fit_affine(self, values: np.ndarray) -> Tuple[float, float]:
        """Fit scale and bias using the exemplary 16-candidate search."""
        absolute_maximum = float(np.max(np.abs(values)))
        initial_scale = absolute_maximum / 7.0 if absolute_maximum > 0 else 1.0
        bias = float(np.mean(values))
        best_error = float("inf")
        best_scale = initial_scale

        for multiplier in np.logspace(np.log10(0.5), np.log10(1.5), 16):
            scale = initial_scale * multiplier
            codes = np.clip(
                np.round((values - bias) / scale),
                -8,
                7,
            ).astype(np.int8)
            reconstructed = scale * codes.astype(np.float32) + bias
            error = float(np.mean((values - reconstructed) ** 2))
            if error < best_error:
                best_error = error
                best_scale = scale
        return best_scale, bias

    @staticmethod
    def _fit_ternary(values: np.ndarray) -> Tuple[float, float]:
        """Fit the exemplary affine ternary scale and bias."""
        bias = float(np.mean(values))
        centered = values - bias
        scale = max(1e-8, float(np.mean(np.abs(centered))))
        return scale, bias

    def _pack_half2(self, scale: float, bias: float) -> int:
        """Pack FP16 scale in the upper half and FP16 bias in the lower."""
        scale_bits = self._float_to_half(scale)
        bias_bits = self._float_to_half(bias)
        return (scale_bits << 16) | bias_bits

    @staticmethod
    def _float_to_half(value: float) -> int:
        """Convert a Python float to its IEEE-754 binary16 bit pattern."""
        packed, = struct.unpack("<H", struct.pack("<e", value))
        return packed

    # ------------------------------------------------------------------
    # v2 layout helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _payload_u32(size: int, mode: int) -> int:
        """Return the active uint32 payload words for one square leaf."""
        n_weights = size * size
        if mode == MODE_FP4_AFFINE:
            return n_weights // 8
        return n_weights // 16

    @staticmethod
    def _classify_layout(blocks: List[dict]) -> Layout:
        """Classify a quadtree leaf set into the v2 layout enumeration."""
        sizes = [block["size"] for block in blocks]
        unique_sizes = set(sizes)
        if len(unique_sizes) == 1:
            size = sizes[0]
            expected_count = (MACROBLOCK_SIZE // size) ** 2
            if len(blocks) == expected_count:
                if size == 64:
                    return Layout.UNIFORM_64
                if size == 32:
                    return Layout.UNIFORM_32
                if size == 16:
                    return Layout.UNIFORM_16
                if size == 8:
                    return Layout.UNIFORM_8
                if size == MIN_LEAF_SIZE:
                    return Layout.FULL_4X4
        return Layout.MIXED

    @staticmethod
    def _build_split_map(blocks: List[dict]) -> bytes:
        """Serialize a mixed quadtree as three little-endian uint32 words."""
        bits: List[int] = []
        leaf_index = 0

        def walk(y: int, x: int, size: int) -> None:
            nonlocal leaf_index
            if leaf_index >= len(blocks):
                raise AssertionError("split map exhausted the leaf list")
            block = blocks[leaf_index]
            if size == MIN_LEAF_SIZE:
                expected = (y, x, MIN_LEAF_SIZE)
                actual = (block["y"], block["x"], block["size"])
                if actual != expected:
                    raise AssertionError(
                        f"split-map walk expected leaf {expected}, got {actual}"
                    )
                leaf_index += 1
                return

            if (block["y"], block["x"], block["size"]) == (y, x, size):
                bits.append(0)
                leaf_index += 1
                return

            bits.append(1)
            half = size // 2
            for dy in (0, half):
                for dx in (0, half):
                    walk(y + dy, x + dx, half)

        walk(0, 0, MACROBLOCK_SIZE)
        if leaf_index != len(blocks):
            raise AssertionError(
                f"split map consumed {leaf_index} of {len(blocks)} leaves"
            )
        if len(bits) > SPLIT_MAP_MAX_BITS:
            raise AssertionError(
                f"split map needs {len(bits)} bits; maximum is {SPLIT_MAP_MAX_BITS}"
            )

        words = [0] * SPLIT_MAP_WORDS
        for bit_index, bit in enumerate(bits):
            if bit != 0:
                words[bit_index // UINT32_BITS] |= 1 << (bit_index % UINT32_BITS)
        return struct.pack("<3I", *words)

    # ------------------------------------------------------------------
    # Manifest generation
    # ------------------------------------------------------------------

    def _write_manifest(
        self,
        niche_name: str,
        bin_path: Path,
        stats: dict,
        base_model: str,
        training_metadata: dict,
        output_dir: Path,
    ):
        from quantize.manifest import ManifestBuilder

        builder = ManifestBuilder(project_root=self._root)
        manifest = builder.build(
            niche_name=niche_name,
            base_model=base_model or "",
            training_metadata=training_metadata,
            fp4_bin_path=bin_path,
            fp4_stats=stats,
        )
        (output_dir / "manifest.json").write_text(json.dumps(manifest, indent=2))
        builder.save(manifest, niche_name)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Export specialist weights to SGFP4 v1 or v2"
    )
    parser.add_argument("--niche", required=True, help="Specialist niche name")
    parser.add_argument(
        "--adaptive",
        action="store_true",
        help="Use SGFP4 v2 adaptive quadtree export",
    )
    args = parser.parse_args()

    project_root = Path(__file__).resolve().parent.parent
    exporter = FP4Exporter(project_root)
    dummy_weights = np.random.randn(512, 512).astype(np.float32) * 0.01
    output_dir = project_root / "models" / "specialists_mlx" / args.niche / "fp4"

    if args.adaptive:
        bin_path, stats = exporter.export_to_file(
            dummy_weights,
            args.niche,
            output_dir,
            adaptive=True,
        )
        print(
            f"SGFP4 v2 export {args.niche}: {bin_path} "
            f"({stats['total_bytes']} bytes, {stats['effective_bpw']} bpw)"
        )
    else:
        bin_path, stats = exporter.export_to_file(
            dummy_weights,
            args.niche,
            output_dir,
        )
        manifest = {
            "model_name": args.niche,
            "niche": args.niche,
            "base_model_ref": "",
            "adapter_ref": "",
            "quantization_params": {"format": "fp4_ultra"},
            "encoder_version": "0.1.0",
            "timestamp_utc": "",
        }
        (output_dir / "manifest.json").write_text(json.dumps(manifest, indent=2))
        print(f"FP4 export {args.niche}: {bin_path} ({stats['total_bytes']} bytes)")
