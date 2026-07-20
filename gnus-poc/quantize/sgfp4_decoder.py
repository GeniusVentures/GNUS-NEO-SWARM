"""Reference SGFP4 decoder — normative decode semantics.

Implements the closed decode specification of "SGFP4: Adaptive Dual-Mode
Macroblock Quantization with GPU-Friendly Unpacking and Verifiable Decode
Semantics" so that containers can be replayed bit-exactly by an independent
implementation (paper Sec 8 conformance-vector use case):

  - Sec 3.2  affine reconstruction w = S*c + beta; FP16 (S, beta) packed
             scale-in-high-halfword (packHalf2x16 order)
  - Sec 4    v1 profile: headers[B] | offsets[B] | 2048-byte payload blob;
             mode flag in bit 0 of the 16-byte-aligned offsets
  - Sec 4.3  normative code ordering (nibble i at bit 4*(i mod 8); ternary
             symbol i at bit 2*(i mod 16); 11 reserved -> 0)
  - Sec 6.1  v2 framing: 'SGF4' | 0x02 | B(u32) | 7B pad | record_offsets[B]
  - Sec 6.2  v2 record: sb_header | split map (MIXED) | block headers |
             pad | 16B-padded payloads; Eq (6) beta flag truncation

Decoders raise SGFP4FormatError on malformed streams.
"""

import math
import struct
from typing import List, Tuple

import numpy as np

MACROBLOCK_SIZE = 64
PAYLOAD_BYTES = 2048
PAYLOAD_U32 = PAYLOAD_BYTES // 4
ALIGNMENT = 16

MODE_FP4_AFFINE = 0
MODE_T158_AFFINE = 1

SGFP4_MAGIC = b"SGF4"
SGFP4_VERSION_V2 = 0x02

LAYOUT_UNIFORM_64 = 0
LAYOUT_UNIFORM_32 = 1
LAYOUT_UNIFORM_16 = 2
LAYOUT_UNIFORM_8 = 3
LAYOUT_MIXED = 4
LAYOUT_FULL_4x4 = 5

_LAYOUT_LEAF_SIZE = {
    LAYOUT_UNIFORM_64: 64,
    LAYOUT_UNIFORM_32: 32,
    LAYOUT_UNIFORM_16: 16,
    LAYOUT_UNIFORM_8: 8,
    LAYOUT_FULL_4x4: 4,
}


class SGFP4FormatError(ValueError):
    """Raised when a container violates the normative SGFP4 layout."""


def _half_from_bits(bits: int) -> float:
    return struct.unpack("<e", struct.pack("<H", bits & 0xFFFF))[0]


def int4_to_int(nib: int) -> int:
    """Two's-complement 4-bit code (paper Listing 1)."""
    nib &= 0xF
    return nib if nib < 8 else nib - 16


def sym2_to_ternary(sym: int) -> int:
    """2-bit ternary symbol map; 11 is reserved and decodes as 0."""
    sym &= 0x3
    if sym == 1:
        return 1
    if sym == 2:
        return -1
    return 0


def _decode_codes(words: np.ndarray, mode: int, n_weights: int) -> np.ndarray:
    """Normative code extraction (paper Sec 4.3, Eq. 3 and 4)."""
    codes = np.empty(n_weights, dtype=np.int32)
    if mode == MODE_FP4_AFFINE:
        for i in range(n_weights):
            codes[i] = int4_to_int(int(words[i >> 3] >> (4 * (i & 7))))
    else:
        for i in range(n_weights):
            codes[i] = sym2_to_ternary(int(words[i >> 4] >> (2 * (i & 15))))
    return codes


def decode_v1(binary: bytes, O: int, I: int) -> np.ndarray:
    """Decode a v1 fixed-payload container to a float32 (O, I) tensor.

    Args:
        binary: headers[B] | offsets[B] | codes blob (B*2048 bytes).
        O, I: unpadded tensor shape (carried by the model manifest).
    """
    binary = bytes(binary)
    ty = math.ceil(O / MACROBLOCK_SIZE)
    tx = math.ceil(I / MACROBLOCK_SIZE)
    B = ty * tx
    if len(binary) != 8 * B + B * PAYLOAD_BYTES:
        raise SGFP4FormatError(
            f"v1 stream is {len(binary)} bytes, expected {8 * B + B * PAYLOAD_BYTES}"
        )

    headers = np.frombuffer(binary, dtype=np.uint32, count=B, offset=0)
    offsets = np.frombuffer(binary, dtype=np.uint32, count=B, offset=4 * B)
    blob = binary[8 * B:]

    out = np.zeros((ty * MACROBLOCK_SIZE, tx * MACROBLOCK_SIZE), dtype=np.float32)
    for b in range(B):
        h = int(headers[b])
        S = _half_from_bits(h >> 16)
        beta = _half_from_bits(h & 0xFFFF)
        off = int(offsets[b])
        flags = off & 0xF
        base = off & ~0xF
        if flags & 0xC:
            raise SGFP4FormatError(
                f"block {b}: reserved offset flag bits 2-3 nonzero"
            )
        mode = flags & 0x1
        words = np.frombuffer(blob, dtype=np.uint32, count=PAYLOAD_U32, offset=base)
        codes = _decode_codes(words, mode, MACROBLOCK_SIZE * MACROBLOCK_SIZE)
        by, bx = divmod(b, tx)
        tile = (
            np.float32(S) * codes.astype(np.float32) + np.float32(beta)
        ).reshape(MACROBLOCK_SIZE, MACROBLOCK_SIZE)
        out[
            by * MACROBLOCK_SIZE:(by + 1) * MACROBLOCK_SIZE,
            bx * MACROBLOCK_SIZE:(bx + 1) * MACROBLOCK_SIZE,
        ] = tile
    return out[:O, :I]


def _parse_split_map(buf: bytes) -> List[Tuple[int, int, int]]:
    """Rebuild leaf (y, x, size) list from a 12-byte split bitmap.

    Pre-order DFS, quadrant order TL, TR, BL, BR; one bit per node of
    size >= 8 (1 = split, 0 = leaf); 4x4 nodes contribute no bit.
    """
    if len(buf) < 12:
        raise SGFP4FormatError("split map truncated")
    w0, w1, w2 = struct.unpack_from("<3I", buf, 0)
    words = (w0, w1, w2)
    leaves: List[Tuple[int, int, int]] = []
    bitpos = [0]

    def walk(y: int, x: int, size: int):
        if size == 4:
            leaves.append((y, x, size))
            return
        k = bitpos[0]
        if k >= 85:
            raise SGFP4FormatError("split map overrun (>85 bits)")
        bitpos[0] += 1
        split = (words[k // 32] >> (k % 32)) & 1
        if split:
            half = size // 2
            for dy in (0, half):
                for dx in (0, half):
                    walk(y + dy, x + dx, half)
        else:
            leaves.append((y, x, size))

    walk(0, 0, MACROBLOCK_SIZE)
    return leaves


def decode_v2(binary: bytes, O: int, I: int) -> np.ndarray:
    """Decode a v2 quadtree-adaptive container to a float32 (O, I) tensor.

    Args:
        binary: self-framed v2 stream (paper Sec 6.1).
        O, I: unpadded tensor shape (carried by the model manifest).
    """
    binary = bytes(binary)
    if binary[:4] != SGFP4_MAGIC:
        raise SGFP4FormatError("bad magic")
    if binary[4] != SGFP4_VERSION_V2:
        raise SGFP4FormatError(f"bad version {binary[4]:#x}")
    B = struct.unpack_from("<I", binary, 5)[0]
    if binary[9:16] != b"\x00" * 7:
        raise SGFP4FormatError("missing 7-byte header pad (Sec 6.1)")
    rec_offs = [struct.unpack_from("<I", binary, 16 + 4 * i)[0] for i in range(B)]
    record_region = 16 + 4 * B

    ty = math.ceil(O / MACROBLOCK_SIZE)
    tx = math.ceil(I / MACROBLOCK_SIZE)
    if ty * tx != B:
        raise SGFP4FormatError(f"record count {B} != tiling {ty * tx}")

    out = np.zeros((ty * MACROBLOCK_SIZE, tx * MACROBLOCK_SIZE), dtype=np.float32)
    for b in range(B):
        if rec_offs[b] % ALIGNMENT != 0:
            raise SGFP4FormatError(
                f"record {b} offset {rec_offs[b]} not 16-byte aligned"
            )
        base = record_region + rec_offs[b]
        sb_header = struct.unpack_from("<I", binary, base)[0]
        layout = sb_header & 0x7
        if sb_header >> 3:
            raise SGFP4FormatError(f"record {b}: sb_header reserved bits set")
        pos = base + 4

        if layout == LAYOUT_MIXED:
            leaves = _parse_split_map(binary[pos:pos + 12])
            pos += 12
        elif layout in _LAYOUT_LEAF_SIZE:
            leaf = _LAYOUT_LEAF_SIZE[layout]
            # Uniform layouts: leaves in row-major raster order (Sec 6.2)
            leaves = [
                (ry, rx, leaf)
                for ry in range(0, MACROBLOCK_SIZE, leaf)
                for rx in range(0, MACROBLOCK_SIZE, leaf)
            ]
        else:
            raise SGFP4FormatError(f"record {b}: unknown layout {layout}")

        N = len(leaves)
        hdrs = [struct.unpack_from("<I", binary, pos + 4 * i)[0] for i in range(N)]
        pos += 4 * N
        hdr_pad = (-(pos - base)) % ALIGNMENT
        if binary[pos:pos + hdr_pad] != b"\x00" * hdr_pad:
            raise SGFP4FormatError(f"record {b}: header pad missing/nonzero")
        pos += hdr_pad

        by, bx = divmod(b, tx)
        for (y, x, size), h in zip(leaves, hdrs):
            S = _half_from_bits(h >> 16)
            beta = _half_from_bits(h & 0xFFF0)  # Eq (6): flag truncation
            flags = h & 0xF
            if flags & 0xE:
                raise SGFP4FormatError(
                    f"record {b} leaf ({y},{x}): reserved header flag bits set"
                )
            mode = flags & 0x1
            n_w = size * size
            n_words = n_w // 8 if mode == MODE_FP4_AFFINE else n_w // 16
            n_bytes = ((n_words * 4 + ALIGNMENT - 1) // ALIGNMENT) * ALIGNMENT
            words = np.frombuffer(binary, dtype=np.uint32, count=n_words, offset=pos)
            codes = _decode_codes(words, mode, n_w)
            tile = (
                np.float32(S) * codes.astype(np.float32) + np.float32(beta)
            ).reshape(size, size)
            out[by * MACROBLOCK_SIZE + y:by * MACROBLOCK_SIZE + y + size,
                bx * MACROBLOCK_SIZE + x:bx * MACROBLOCK_SIZE + x + size] = tile
            pos += n_bytes
    return out[:O, :I]
