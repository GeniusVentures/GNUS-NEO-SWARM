"""FP4 Ultra binary exporter matching the FP4 Ultra spec (docs/fp4_ultra_spec_v0_2_adaptive_ascii.md).

Container layout: headers[B] | offsets[B] | codes_blob[B*2048]
- 64x64 macroblocks
- Fixed 2048-byte payload per block
- FP4_AFFINE (mode 0): 4-bit signed codes, 8 per uint32
- T158_AFFINE (mode 1): ternary as 2-bit symbols, 16 per uint32
- headers: packed half2 (fp16 scale | fp16 bias)
- offsets: (byte_offset & ~0xF) | flags4
"""

import json
import math
import struct
from pathlib import Path
from typing import Optional, Tuple

import numpy as np


MACROBLOCK_SIZE = 64
PAYLOAD_BYTES = 2048
PAYLOAD_U32 = PAYLOAD_BYTES // 4
ALIGNMENT = 16

MODE_FP4_AFFINE = 0
MODE_T158_AFFINE = 1


class FP4Exporter:
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
    ) -> Tuple[bytes, dict]:
        O, I = weights.shape
        tiles_y = math.ceil(O / MACROBLOCK_SIZE)
        tiles_x = math.ceil(I / MACROBLOCK_SIZE)
        B = tiles_y * tiles_x

        padded = np.zeros((tiles_y * MACROBLOCK_SIZE, tiles_x * MACROBLOCK_SIZE), dtype=np.float32)
        padded[:O, :I] = weights.astype(np.float32)

        headers = np.zeros(B, dtype=np.uint32)
        offsets = np.zeros(B, dtype=np.uint32)
        codes_blocks = []

        current_offset = 0
        for by in range(tiles_y):
            for bx in range(tiles_x):
                block_idx = by * tiles_x + bx
                block = padded[by * 64:(by + 1) * 64, bx * 64:(bx + 1) * 64]

                fp4_result = self._encode_fp4_affine(block)
                t158_result = self._encode_t158_affine(block)

                if prefer_ternary and t158_result["l2_error"] <= (1.0 + ternary_delta) * fp4_result["l2_error"]:
                    mode = MODE_T158_AFFINE
                    selected = t158_result
                else:
                    mode = MODE_FP4_AFFINE
                    selected = fp4_result

                scale = float(np.clip(selected["scale"], -65504, 65504))
                bias = float(np.clip(selected["bias"], -65504, 65504))
                headers[block_idx] = self._pack_half2(scale, bias)

                assert current_offset % ALIGNMENT == 0
                offsets[block_idx] = (current_offset & ~0xF) | (mode & 0xF)

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

    def _encode_fp4_affine(self, block: np.ndarray) -> dict:
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

    def _fit_affine(self, values: np.ndarray) -> Tuple[float, float]:
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
        bias = float(np.mean(values))
        centered = values - bias
        scale = max(1e-8, float(np.mean(np.abs(centered))))
        return scale, bias

    def _pack_half2(self, scale: float, bias: float) -> int:
        s_bits = self._float_to_half(scale)
        b_bits = self._float_to_half(bias)
        return (s_bits << 16) | b_bits

    def _float_to_half(self, value: float) -> int:
        packed, = struct.unpack("<H", struct.pack("<e", value))
        return packed

    def export_to_file(self, weights: np.ndarray, niche_name: str, output_dir: Optional[Path] = None):
        binary, stats = self.export_weights(weights, niche_name)
        if output_dir is None:
            output_dir = self._artifacts_dir / "fp4" / niche_name
        output_dir.mkdir(parents=True, exist_ok=True)

        bin_path = output_dir / f"{niche_name}.fp4"
        with bin_path.open("wb") as f:
            f.write(binary)

        stats_path = output_dir / f"{niche_name}_stats.json"
        with stats_path.open("w") as f:
            json.dump(stats, f, indent=2)

        return bin_path, stats
