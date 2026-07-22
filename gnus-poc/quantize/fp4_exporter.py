"""FP4 Ultra binary exporter — SGFP4 v1 (fixed 64x64) and v2 (adaptive quadtree).

Container layout v1: headers[B] | offsets[B] | codes_blob[B*2048]
Container layout v2: magic[4] | version[1] | num_superblocks[4] | pad[7] |
                     superblock_offsets[B] | superblock_data[0..B-1]

v1 (fixed, backward compatible):
- 64x64 macroblocks
- Fixed 2048-byte payload per block
- FP4_AFFINE (mode 0): 4-bit signed codes, 8 per uint32
- T158_AFFINE (mode 1): ternary as 2-bit symbols, 16 per uint32

v2 (adaptive, SGFP4 v2):
- Variable block sizes 4x4..64x64 selected by quadtree + Laplacian error
- Layout enum per superblock (0-5) identifies block structure
- Variable payloads scale with block area
- Dual-mode per-block: FP4_AFFINE vs T158_AFFINE via error comparison
- 4-byte magic header (b'SGF4') + version byte (0x02) for format detection
- Superblock offset table for paging
- 16-byte payload alignment per block
- Manifest generation via ManifestBuilder
"""

import argparse
import json
import math
import struct
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import numpy as np

from quantize.sgfp4_format import (
    ALIGNMENT,
    FP16_MAX,
    HEADER_CLEAR_FLAGS_MASK,
    LEAF_ERROR_HINT_MASK,
    LEAF_MODE_MASK,
    MACROBLOCK_SIZE,
    MIN_LEAF_SIZE,
    OFFSET_FLAG_MASK,
    PAYLOAD_BYTES,
    PAYLOAD_U32,
    SB_HEADER_LAYOUT_MASK,
    SGFP4_MAGIC,
    SGFP4_VERSION_V2,
    SPLIT_MAP_BYTES,
    SPLIT_MAP_MAX_BITS,
    SPLIT_MAP_WORDS,
    UINT32_BITS,
    V2_HEADER_PAD_BYTES,
    CodeMode,
    Layout,
)


# ---------------------------------------------------------------------------
# Backward-compatible aliases (std. §4.1: scoped enums are the canonical
# names; plain-int aliases kept for existing callers and tests)
# ---------------------------------------------------------------------------

MODE_FP4_AFFINE = CodeMode.FP4_AFFINE
MODE_T158_AFFINE = CodeMode.T158_AFFINE

LAYOUT_UNIFORM_64 = Layout.UNIFORM_64
LAYOUT_UNIFORM_32 = Layout.UNIFORM_32
LAYOUT_UNIFORM_16 = Layout.UNIFORM_16
LAYOUT_UNIFORM_8 = Layout.UNIFORM_8
LAYOUT_MIXED = Layout.MIXED
LAYOUT_FULL_4x4 = Layout.FULL_4X4


def _zero_pad(data: bytes, alignment: int = ALIGNMENT) -> bytes:
    """Append zero bytes until len(data) is a multiple of alignment."""
    return data + b"\x00" * ((-len(data)) % alignment)

# Default v2 thresholds (per RESEARCH.md Pattern 4 / D-08)
DEFAULT_V2_THRESHOLDS = {
    64: {"max_mse": 0.01, "max_relative": 0.05},
    32: {"max_mse": 0.005, "max_relative": 0.03},
    16: {"max_mse": 0.002, "max_relative": 0.02},
    8:  {"max_mse": 0.001, "max_relative": 0.01},
    4:  {"max_mse": 0.0005, "max_relative": 0.005},
}


# ---------------------------------------------------------------------------
# FP4Exporter
# ---------------------------------------------------------------------------

class FP4Exporter:
    """SGFP4 weight exporter with v1 fixed and v2 adaptive modes.

    Constructor args:
        project_root: Path to the gnus-poc project root. Defaults to parent of
                      this file if None.
    """

    def __init__(self, project_root: Optional[Path] = None):
        if project_root is None:
            project_root = Path(__file__).resolve().parent.parent
        self._root = project_root
        self._artifacts_dir = project_root / "artifacts"

    # ==================================================================
    # Public API
    # ==================================================================

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
        """Export weight tensor to SGFP4 binary.

        Args:
            weights: 2D float32 numpy array of shape (O, I).
            niche_name: Specialist niche name (e.g. "code", "medical").
            prefer_ternary: Prefer T158_AFFINE even in v1 mode.
            ternary_delta: D-04 delta for T158 preference.
            adaptive: If True, use SGFP4 v2 adaptive quadtree export.
                      If False (default), use v1 fixed 64x64 export.
            thresholds: Per-block-size error thresholds (v2 only).
            min_block_size: Minimum block edge size for quadtree (v2 only).
            laplacian_levels: Max Laplacian pyramid levels (v2 only).

        Returns:
            Tuple of (binary bytes, stats dict).
        """
        if adaptive:
            return self._export_v2_adaptive(
                weights, niche_name,
                prefer_ternary=prefer_ternary,
                ternary_delta=ternary_delta,
                thresholds=thresholds,
                min_block_size=min_block_size,
                laplacian_levels=laplacian_levels,
            )
        else:
            return self._export_v1_fixed(
                weights, niche_name,
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
        """Export weights to file, optionally with manifest (v2).

        Args:
            weights: 2D float32 numpy array.
            niche_name: Specialist niche name.
            output_dir: Target directory (default: artifacts/fp4/{niche}).
            adaptive: Use v2 adaptive export if True.
            thresholds: Per-block-size error thresholds (v2 only).
            min_block_size: Minimum block edge size (v2 only).
            laplacian_levels: Max Laplacian pyramid levels (v2 only).
            base_model: Base model reference for manifest (v2 only).
            training_metadata: Training metadata dict for manifest (v2 only).
            **kwargs: Additional arguments passed to export_weights.

        Returns:
            Tuple of (bin_path, stats).
        """
        binary, stats = self.export_weights(
            weights, niche_name,
            adaptive=adaptive,
            thresholds=thresholds,
            min_block_size=min_block_size,
            laplacian_levels=laplacian_levels,
            **kwargs,
        )

        if output_dir is None:
            output_dir = self._artifacts_dir / "fp4" / niche_name
        output_dir.mkdir(parents=True, exist_ok=True)

        if adaptive:
            ext = ".sgfp4"
        else:
            ext = ".fp4"

        bin_path = output_dir / f"{niche_name}{ext}"
        with bin_path.open("wb") as f:
            f.write(binary)

        # Write stats JSON
        stats_path = output_dir / f"{niche_name}_stats.json"
        with stats_path.open("w") as f:
            json.dump(stats, f, indent=2)

        # v2: write manifest via ManifestBuilder (D-10)
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

    # ==================================================================
    # v1 fixed export (preserved for backward compatibility)
    # ==================================================================

    def _export_v1_fixed(
        self,
        weights: np.ndarray,
        niche_name: str,
        prefer_ternary: bool = False,
        ternary_delta: float = 0.10,
    ) -> Tuple[bytes, dict]:
        """v1 fixed 64x64 export — identical to pre-upgrade behavior."""
        O, I = weights.shape
        tiles_y = math.ceil(O / MACROBLOCK_SIZE)
        tiles_x = math.ceil(I / MACROBLOCK_SIZE)
        B = tiles_y * tiles_x

        padded = np.zeros(
            (tiles_y * MACROBLOCK_SIZE, tiles_x * MACROBLOCK_SIZE),
            dtype=np.float32,
        )
        padded[:O, :I] = weights.astype(np.float32)

        headers = np.zeros(B, dtype=np.uint32)
        offsets = np.zeros(B, dtype=np.uint32)
        codes_blocks = []

        current_offset = 0
        for by in range(tiles_y):
            for bx in range(tiles_x):
                block_idx = by * tiles_x + bx
                block = padded[
                    by * 64:(by + 1) * 64,
                    bx * 64:(bx + 1) * 64,
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
                headers[block_idx] = self._pack_half2(scale, bias)

                assert current_offset % ALIGNMENT == 0
                offsets[block_idx] = (
                    (current_offset & ~OFFSET_FLAG_MASK)
                    | (int(mode) & OFFSET_FLAG_MASK)
                )

                block_payload = selected["payload"]
                assert len(block_payload) == PAYLOAD_U32
                codes_blocks.append(block_payload)
                current_offset += PAYLOAD_BYTES

        codes_blob = b"".join(b.tobytes() for b in codes_blocks)

        stats = {
            "shape": [O, I],
            "num_blocks": B,
            "tiles_y": tiles_y,
            "tiles_x": tiles_x,
            "total_bytes": len(codes_blob) + B * 4 + B * 4,
            "fp4_blocks": 0,
            "t158_blocks": 0,
        }

        for b in range(B):
            if offsets[b] & 0x1:
                stats["t158_blocks"] += 1
            else:
                stats["fp4_blocks"] += 1

        return (
            headers.tobytes() + offsets.tobytes() + codes_blob,
            stats,
        )

    # ==================================================================
    # v2 adaptive export
    # ==================================================================

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
        """SGFP4 v2 adaptive quadtree export.

        Binary format (paper Sec 6.1):
            magic[4] | version[1] | num_superblocks[4] | pad[7] |
            superblock_offsets[B] | superblock_data[0..B-1]

        Each superblock record (paper Sec 6.2), 16-byte aligned and zero
        padded to a 16-byte multiple:
            sb_header[4] | split_map[12] (LAYOUT_MIXED only) |
            block_headers[N*4] | pad[0-15] | payloads[N] (each 16B-padded)

        Leaf storage order: row-major raster for uniform layouts; pre-order
        DFS (matching the split map) for LAYOUT_MIXED.
        """
        O, I = weights.shape
        tiles_y = math.ceil(O / MACROBLOCK_SIZE)
        tiles_x = math.ceil(I / MACROBLOCK_SIZE)
        B = tiles_y * tiles_x

        padded = np.zeros(
            (tiles_y * MACROBLOCK_SIZE, tiles_x * MACROBLOCK_SIZE),
            dtype=np.float32,
        )
        padded[:O, :I] = weights.astype(np.float32)

        # Use default thresholds if none provided
        if thresholds is None:
            thresholds = DEFAULT_V2_THRESHOLDS

        # Import v2 modules (lazy to avoid circular imports at module level)
        from quantize.laplacian import LaplacianWeightedError
        from quantize.quadtree import QuadtreeEncoder

        laplacian = LaplacianWeightedError()

        # Encode each superblock into variable-sized blocks
        superblock_layouts = []  # List of (layout_enum, blocks)
        total_fp4_blocks = 0
        total_t158_blocks = 0

        for by in range(tiles_y):
            for bx in range(tiles_x):
                superblock = padded[
                    by * 64:(by + 1) * 64,
                    bx * 64:(bx + 1) * 64,
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

                for blk in blocks:
                    if blk["mode"] == MODE_FP4_AFFINE:
                        total_fp4_blocks += 1
                    else:
                        total_t158_blocks += 1

        # Serialize superblocks
        superblock_data_chunks = []
        superblock_offsets = np.zeros(B, dtype=np.uint32)
        current_offset = 0

        for idx, (layout, blocks) in enumerate(superblock_layouts):
            # Leaf storage order (paper Sec 6.2): uniform layouts are stored
            # in row-major raster order of the tile grid; LAYOUT_MIXED keeps
            # the pre-order DFS order that matches the split map.
            if layout == Layout.MIXED:
                split_map = self._build_split_map(blocks)
            else:
                split_map = b""
                blocks = sorted(blocks, key=lambda b: (b["y"], b["x"]))

            # Superblock header: uint32 with layout enum + reserved
            sb_header = np.uint32(int(layout) & SB_HEADER_LAYOUT_MASK)

            # Per-block headers
            block_headers = []
            for blk in blocks:
                bh = self._pack_half2(
                    float(np.clip(blk["scale"], -FP16_MAX, FP16_MAX)),
                    float(np.clip(blk["bias"], -FP16_MAX, FP16_MAX)),
                )
                # 4 LSB offset flags:
                #   bit 0 = mode (FP4=0, T158=1)
                #   bit 1 = ERROR_HINT (0 = L2-selected, 1 = Pyramid-selected)
                #   bits 2-3 = reserved (0)
                flags = int(blk["mode"]) & LEAF_MODE_MASK
                if blk.get("error_hint", 0):
                    flags |= LEAF_ERROR_HINT_MASK
                bh = np.uint32((int(bh) & HEADER_CLEAR_FLAGS_MASK) | flags)
                block_headers.append(bh)

            # Header section: sb_header | split_map | block_headers, then
            # zero pad to a 16-byte boundary so payloads (and therefore all
            # absolute addresses) stay aligned (paper Sec 6.2)
            header_section = _zero_pad(
                sb_header.tobytes()
                + split_map
                + b"".join(bh.tobytes() for bh in block_headers)
            )

            # Per-block payloads with 16-byte alignment per RESEARCH.md Pitfall 3
            payload_chunks = [
                _zero_pad(blk["payload"].tobytes()) for blk in blocks
            ]

            # Assemble superblock data; pad record to a 16-byte multiple so
            # every record offset stays 16-byte aligned (paper Sec 6.1)
            sb_data = _zero_pad(header_section + b"".join(payload_chunks))

            superblock_offsets[idx] = current_offset
            superblock_data_chunks.append(sb_data)
            current_offset += len(sb_data)

        # Assemble full binary: magic | version | B | 7B pad to 16-byte
        # boundary | offset table | records (paper Sec 6.1)
        binary = (
            SGFP4_MAGIC
            + struct.pack("<B", SGFP4_VERSION_V2)
            + struct.pack("<I", B)
            + b"\x00" * V2_HEADER_PAD_BYTES
            + superblock_offsets.tobytes()
            + b"".join(superblock_data_chunks)
        )

        # Compute layout distribution
        layout_distribution = {i: 0 for i in range(6)}
        for layout, _ in superblock_layouts:
            layout_distribution[layout] += 1

        # Compute effective bitrate
        total_weights = int(O * I)
        total_bits = len(binary) * 8
        effective_bpw = total_bits / total_weights if total_weights > 0 else 0.0

        stats = {
            "shape": [O, I],
            "num_superblocks": B,
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

    # ==================================================================
    # Encode helpers
    # ==================================================================

    def _encode_fp4_affine(self, block: np.ndarray) -> dict:
        """v1: encode a 64x64 block in FP4_AFFINE mode (4096 weights)."""
        flat = block.ravel().astype(np.float32)
        scale, bias = self._fit_affine(flat)

        codes = np.clip(np.round((flat - bias) / scale), -8, 7).astype(np.int8)
        w_hat = scale * codes.astype(np.float32) + bias
        l2 = float(np.sqrt(np.mean((flat - w_hat) ** 2)))

        payload = np.zeros(PAYLOAD_U32, dtype=np.uint32)
        for i in range(4096):
            code = int(codes[i]) & 0xF
            word = i // 8
            shift = 4 * (i % 8)
            payload[word] |= np.uint32(code) << np.uint32(shift)

        return {"scale": scale, "bias": bias, "l2_error": l2, "payload": payload}

    def _encode_t158_affine(self, block: np.ndarray) -> dict:
        """v1: encode a 64x64 block in T158_AFFINE mode (4096 weights)."""
        flat = block.ravel().astype(np.float32)
        scale, bias = self._fit_ternary(flat)

        centered = flat - bias
        tau = 0.5 * scale
        T = np.zeros(4096, dtype=np.int8)
        T[centered > tau] = 1
        T[centered < -tau] = -1

        w_hat = scale * T.astype(np.float32) + bias
        l2 = float(np.sqrt(np.mean((flat - w_hat) ** 2)))

        payload = np.zeros(PAYLOAD_U32, dtype=np.uint32)
        for i in range(4096):
            t = int(T[i])
            if t == 0:
                bits = 0
            elif t == 1:
                bits = 1
            else:
                bits = 2
            word = i // 16
            shift = 2 * (i % 16)
            payload[word] |= np.uint32(bits) << np.uint32(shift)

        return {"scale": scale, "bias": bias, "l2_error": l2, "payload": payload}

    def _encode_fp4_affine_variable(self, region: np.ndarray) -> dict:
        """v2: encode a variable-sized region in FP4_AFFINE mode.

        Args:
            region: 2D numpy array of any NxN size, float32.

        Returns:
            dict with keys: scale, bias, l2_error, payload, n_weights.
        """
        flat = region.ravel().astype(np.float32)
        n_weights = flat.size
        n_payload_u32 = n_weights // 8

        scale, bias = self._fit_affine(flat)

        codes = np.clip(np.round((flat - bias) / scale), -8, 7).astype(np.int8)
        w_hat = scale * codes.astype(np.float32) + bias
        l2 = float(np.sqrt(np.mean((flat - w_hat) ** 2)))

        payload = np.zeros(n_payload_u32, dtype=np.uint32)
        for i in range(n_weights):
            code = int(codes[i]) & 0xF
            word = i // 8
            shift = 4 * (i % 8)
            payload[word] |= np.uint32(code) << np.uint32(shift)

        return {
            "scale": scale,
            "bias": bias,
            "l2_error": l2,
            "payload": payload,
            "n_weights": n_weights,
        }

    def _encode_t158_affine_variable(self, region: np.ndarray) -> dict:
        """v2: encode a variable-sized region in T158_AFFINE mode.

        Args:
            region: 2D numpy array of any NxN size, float32.

        Returns:
            dict with keys: scale, bias, l2_error, payload, n_weights.
        """
        flat = region.ravel().astype(np.float32)
        n_weights = flat.size
        n_payload_u32 = n_weights // 16

        scale, bias = self._fit_ternary(flat)

        centered = flat - bias
        tau = 0.5 * scale
        T = np.zeros(n_weights, dtype=np.int8)
        T[centered > tau] = 1
        T[centered < -tau] = -1

        w_hat = scale * T.astype(np.float32) + bias
        l2 = float(np.sqrt(np.mean((flat - w_hat) ** 2)))

        payload = np.zeros(n_payload_u32, dtype=np.uint32)
        for i in range(n_weights):
            t = int(T[i])
            if t == 0:
                bits = 0
            elif t == 1:
                bits = 1
            else:
                bits = 2
            word = i // 16
            shift = 2 * (i % 16)
            payload[word] |= np.uint32(bits) << np.uint32(shift)

        return {
            "scale": scale,
            "bias": bias,
            "l2_error": l2,
            "payload": payload,
            "n_weights": n_weights,
        }

    # ==================================================================
    # Fitting helpers (shared between v1 and v2)
    # ==================================================================

    def _fit_affine(self, values: np.ndarray) -> Tuple[float, float]:
        """Fit affine scale and bias for FP4 encoding (16-candidate search)."""
        abs_max = float(np.max(np.abs(values)))
        scale = abs_max / 7.0 if abs_max > 0 else 1.0
        bias = float(np.mean(values))
        best_err = float("inf")
        best_scale = scale

        for mult in np.logspace(np.log10(0.5), np.log10(1.5), 16):
            s = scale * mult
            codes = np.clip(np.round((values - bias) / s), -8, 7).astype(np.int8)
            w_hat = s * codes.astype(np.float32) + bias
            err = float(np.mean((values - w_hat) ** 2))
            if err < best_err:
                best_err = err
                best_scale = s

        return best_scale, bias

    def _fit_ternary(self, values: np.ndarray) -> Tuple[float, float]:
        """Fit scale and bias for T158 ternary encoding."""
        bias = float(np.mean(values))
        centered = values - bias
        scale = max(1e-8, float(np.mean(np.abs(centered))))
        return scale, bias

    # ==================================================================
    # Packing helpers
    # ==================================================================

    def _pack_half2(self, scale: float, bias: float) -> int:
        """Pack two FP16 values into a uint32: scale in upper 16 bits, bias in lower."""
        s_bits = self._float_to_half(scale)
        b_bits = self._float_to_half(bias)
        return (s_bits << 16) | b_bits

    @staticmethod
    def _float_to_half(value: float) -> int:
        """Convert float to IEEE 754 half-precision bits via struct."""
        packed, = struct.unpack("<H", struct.pack("<e", value))
        return packed

    # ==================================================================
    # v2 helpers
    # ==================================================================

    @staticmethod
    def _payload_u32(size: int, mode: int) -> int:
        """Return number of uint32 words for a block payload (D-03).

        Args:
            size: Block edge size (4, 8, 16, 32, or 64).
            mode: MODE_FP4_AFFINE (0) or MODE_T158_AFFINE (1).

        Returns:
            Number of uint32 words in payload.
        """
        n_weights = size * size
        if mode == MODE_FP4_AFFINE:
            return n_weights // 8
        else:
            return n_weights // 16

    @staticmethod
    def _classify_layout(blocks: List[dict]) -> Layout:
        """Classify superblock layout from quadtree output blocks (D-02).

        Args:
            blocks: List of block dicts from QuadtreeEncoder.encode().

        Returns:
            Layout enum member.
        """
        sizes = [b["size"] for b in blocks]
        unique_sizes = set(sizes)

        if len(unique_sizes) == 1:
            size = sizes[0]
            expected_count = (MACROBLOCK_SIZE // size) * (MACROBLOCK_SIZE // size)
            if len(blocks) != expected_count:
                # All same size but wrong count — treat as mixed
                return Layout.MIXED

            if size == 64:
                return Layout.UNIFORM_64
            elif size == 32:
                return Layout.UNIFORM_32
            elif size == 16:
                return Layout.UNIFORM_16
            elif size == 8:
                return Layout.UNIFORM_8
            elif size == MIN_LEAF_SIZE:
                return Layout.FULL_4X4

        return Layout.MIXED

    @staticmethod
    def _build_split_map(blocks: List[dict]) -> bytes:
        """Serialize the quadtree structure as a 12-byte split bitmap.

        Per paper Sec 6.2: visiting nodes in pre-order DFS with quadrant
        order TL, TR, BL, BR, one bit per node of size >= 8 records whether
        that node is split (1) or a leaf (0). Nodes of size 4 cannot split
        and contribute no bit. Bit k of the map is bit (k mod 32) of word
        floor(k/32); upper bits are zero.

        Args:
            blocks: Leaf block dicts (with y, x, size) in pre-order DFS
                    order, as emitted by QuadtreeEncoder.encode().

        Returns:
            12 bytes: three little-endian uint32 words.
        """
        bits: List[int] = []
        leaf_index = 0

        def walk(y: int, x: int, size: int) -> None:
            nonlocal leaf_index
            blk = blocks[leaf_index]
            if size == MIN_LEAF_SIZE:
                # 4x4 nodes cannot split and contribute no bit; the leaf
                # must be here.
                assert (blk["y"], blk["x"], blk["size"]) == (y, x, MIN_LEAF_SIZE), (
                    f"split-map walk expected 4x4 leaf at ({y},{x}), got {blk}"
                )
                leaf_index += 1
                return
            if (blk["y"], blk["x"], blk["size"]) == (y, x, size):
                bits.append(0)  # leaf
                leaf_index += 1
                return
            bits.append(1)  # split
            half = size // 2
            for dy in (0, half):
                for dx in (0, half):
                    walk(y + dy, x + dx, half)

        walk(0, 0, MACROBLOCK_SIZE)
        assert leaf_index == len(blocks), (
            f"split map consumed {leaf_index} of {len(blocks)} leaves"
        )
        assert len(bits) <= SPLIT_MAP_MAX_BITS, (
            f"split map needs {len(bits)} bits (max {SPLIT_MAP_MAX_BITS})"
        )

        words = [0] * SPLIT_MAP_WORDS
        for k, bit in enumerate(bits):
            if bit != 0:
                words[k // UINT32_BITS] |= 1 << (k % UINT32_BITS)
        return struct.pack("<3I", *words)

    # ==================================================================
    # Manifest generation (v2 only)
    # ==================================================================

    def _write_manifest(
        self,
        niche_name: str,
        bin_path: Path,
        stats: dict,
        base_model: str,
        training_metadata: dict,
        output_dir: Path,
    ):
        """Write manifest.json using ManifestBuilder (D-10)."""
        from quantize.manifest import ManifestBuilder

        builder = ManifestBuilder(project_root=self._root)
        manifest = builder.build(
            niche_name=niche_name,
            base_model=base_model or "",
            training_metadata=training_metadata,
            fp4_bin_path=bin_path,
            fp4_stats=stats,
        )

        # Write manifest alongside binary in output_dir
        manifest_path = output_dir / "manifest.json"
        with manifest_path.open("w") as f:
            json.dump(manifest, f, indent=2)

        # Also save to artifacts/manifests/ per ManifestBuilder convention
        builder.save(manifest, niche_name)


# ---------------------------------------------------------------------------
# CLI entry point (backward compatible with v1)
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Export specialist weights to FP4 Ultra format (v1 or v2)"
    )
    parser.add_argument("--niche", required=True, help="Specialist niche name")
    parser.add_argument(
        "--adaptive", action="store_true",
        help="Use SGFP4 v2 adaptive quadtree export",
    )
    args = parser.parse_args()

    project_root = Path(__file__).resolve().parent.parent
    exporter = FP4Exporter(project_root)

    # Placeholder export — real export requires adapter weights from training
    dummy_weights = np.random.randn(512, 512).astype(np.float32) * 0.01
    output_dir = project_root / "models" / "specialists_mlx" / args.niche / "fp4"

    if args.adaptive:
        bin_path, stats = exporter.export_to_file(
            dummy_weights, args.niche, output_dir,
            adaptive=True,
        )
        print(
            f"SGFP4 v2 export {args.niche}: {bin_path} ({stats['total_bytes']} bytes, "
            f"{stats.get('effective_bpw', 'N/A')} bpw)"
        )
    else:
        bin_path, stats = exporter.export_to_file(dummy_weights, args.niche, output_dir)
        manifest = {
            "model_name": args.niche,
            "niche": args.niche,
            "base_model_ref": "",
            "adapter_ref": "",
            "quantization_params": {"format": "fp4_ultra"},
            "encoder_version": "0.1.0",
            "timestamp_utc": "",
        }
        with (output_dir / "manifest.json").open("w") as f:
            json.dump(manifest, f, indent=2)
        print(f"FP4 export {args.niche}: {bin_path} ({stats['total_bytes']} bytes)")
