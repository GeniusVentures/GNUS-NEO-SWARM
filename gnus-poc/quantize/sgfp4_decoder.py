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

All wire-format constants come from quantize.sgfp4_format; this module
contains decode logic only. Decoders raise SGFP4FormatError on malformed
streams.
"""

import math
import struct
from typing import List, Tuple

import numpy as np

from quantize.sgfp4_format import (
    ALIGNMENT,
    BETA_TRUNC_MASK,
    FP4_BITS_PER_CODE,
    FP4_CODE_BIAS,
    FP4_CODES_PER_WORD,
    FP4_NIBBLE_MASK,
    FP4_SIGN_THRESHOLD,
    HALF_MASK,
    HALF_SHIFT,
    LEAF_FLAG_MASK,
    LEAF_MODE_MASK,
    LEAF_RESERVED_MASK,
    MACROBLOCK_SIZE,
    MIN_LEAF_SIZE,
    OFFSET_FLAG_MASK,
    OFFSET_MODE_MASK,
    OFFSET_RESERVED_MASK,
    PAYLOAD_BYTES,
    PAYLOAD_U32,
    SB_HEADER_LAYOUT_MASK,
    SB_HEADER_RESERVED_SHIFT,
    SGFP4_MAGIC,
    SGFP4_VERSION_V2,
    SPLIT_MAP_BYTES,
    SPLIT_MAP_MAX_BITS,
    T158_BITS_PER_CODE,
    T158_CODES_PER_WORD,
    T158_SYMBOL_MASK,
    T158_SYMBOL_NEG,
    T158_SYMBOL_POS,
    UINT32_BITS,
    V2_FIXED_HEADER_BYTES,
    V2_HEADER_PAD_BYTES,
    CodeMode,
    Layout,
)

# Uniform layouts imply both the leaf geometry and the leaf count
_LAYOUT_LEAF_SIZE = {
    Layout.UNIFORM_64: 64,
    Layout.UNIFORM_32: 32,
    Layout.UNIFORM_16: 16,
    Layout.UNIFORM_8: 8,
    Layout.FULL_4X4: 4,
}


class SGFP4FormatError(ValueError):
    """Raised when a container violates the normative SGFP4 layout."""


def _half_from_bits(bits: int) -> float:
    return struct.unpack("<e", struct.pack("<H", bits & HALF_MASK))[0]


def int4_to_int(nib: int) -> int:
    """Two's-complement 4-bit code (paper Sec 4.3, Listing 1)."""
    nib &= FP4_NIBBLE_MASK
    return nib if nib < FP4_SIGN_THRESHOLD else nib - FP4_CODE_BIAS


def sym2_to_ternary(sym: int) -> int:
    """2-bit ternary symbol map; 11 is reserved and decodes as 0."""
    sym &= T158_SYMBOL_MASK
    if sym == T158_SYMBOL_POS:
        return 1
    if sym == T158_SYMBOL_NEG:
        return -1
    return 0


def _decode_codes(words: np.ndarray, mode: CodeMode, n_weights: int) -> np.ndarray:
    """Normative code extraction (paper Sec 4.3, Eq. 3 and 4)."""
    codes = np.empty(n_weights, dtype=np.int32)
    if mode == CodeMode.FP4_AFFINE:
        for i in range(n_weights):
            word = words[i // FP4_CODES_PER_WORD]
            shift = FP4_BITS_PER_CODE * (i % FP4_CODES_PER_WORD)
            codes[i] = int4_to_int(int(word >> shift))
    else:
        for i in range(n_weights):
            word = words[i // T158_CODES_PER_WORD]
            shift = T158_BITS_PER_CODE * (i % T158_CODES_PER_WORD)
            codes[i] = sym2_to_ternary(int(word >> shift))
    return codes


def decode_v1(binary: bytes, O: int, I: int) -> np.ndarray:
    """Decode a v1 fixed-payload container to a float32 (O, I) tensor.

    Args:
        binary: headers[B] | offsets[B] | codes blob (B*2048 bytes).
        O: unpadded output-channel count (carried by the model manifest).
        I: unpadded input-channel count.

    Returns:
        Decoded float32 array of shape (O, I).

    Raises:
        SGFP4FormatError: on size mismatches or reserved-bit violations.
    """
    binary = bytes(binary)
    tiles_y = math.ceil(O / MACROBLOCK_SIZE)
    tiles_x = math.ceil(I / MACROBLOCK_SIZE)
    B = tiles_y * tiles_x
    expected_bytes = B * 8 + B * PAYLOAD_BYTES  # headers + offsets + blob
    if len(binary) != expected_bytes:
        raise SGFP4FormatError(
            f"v1 stream is {len(binary)} bytes, expected {expected_bytes}"
        )

    headers = np.frombuffer(binary, dtype=np.uint32, count=B, offset=0)
    offsets = np.frombuffer(binary, dtype=np.uint32, count=B, offset=B * 4)
    blob = binary[B * 8:]

    out = np.zeros(
        (tiles_y * MACROBLOCK_SIZE, tiles_x * MACROBLOCK_SIZE), dtype=np.float32
    )
    for b in range(B):
        header = int(headers[b])
        scale = _half_from_bits(header >> HALF_SHIFT)
        bias = _half_from_bits(header & HALF_MASK)

        offset_word = int(offsets[b])
        flags = offset_word & OFFSET_FLAG_MASK
        base = offset_word & ~OFFSET_FLAG_MASK
        if (flags & OFFSET_RESERVED_MASK) != 0:
            raise SGFP4FormatError(
                f"block {b}: reserved offset flag bits 2-3 nonzero"
            )
        mode = CodeMode(flags & OFFSET_MODE_MASK)

        words = np.frombuffer(blob, dtype=np.uint32, count=PAYLOAD_U32, offset=base)
        codes = _decode_codes(words, mode, MACROBLOCK_SIZE * MACROBLOCK_SIZE)

        by, bx = divmod(b, tiles_x)
        tile = (
            np.float32(scale) * codes.astype(np.float32) + np.float32(bias)
        ).reshape(MACROBLOCK_SIZE, MACROBLOCK_SIZE)
        out[
            by * MACROBLOCK_SIZE:(by + 1) * MACROBLOCK_SIZE,
            bx * MACROBLOCK_SIZE:(bx + 1) * MACROBLOCK_SIZE,
        ] = tile
    return out[:O, :I]


def _parse_split_map(buf: bytes) -> List[Tuple[int, int, int]]:
    """Rebuild leaf (y, x, size) list from a 12-byte split bitmap.

    Pre-order DFS, quadrant order TL, TR, BL, BR; one bit per node of
    size >= 8 (1 = split, 0 = leaf); 4x4 nodes contribute no bit
    (paper Sec 6.2).
    """
    if len(buf) < SPLIT_MAP_BYTES:
        raise SGFP4FormatError("split map truncated")
    words = struct.unpack_from("<3I", buf, 0)
    leaves: List[Tuple[int, int, int]] = []
    bit_pos = 0

    def walk(y: int, x: int, size: int) -> None:
        nonlocal bit_pos
        if size == MIN_LEAF_SIZE:
            leaves.append((y, x, size))
            return
        if bit_pos >= SPLIT_MAP_MAX_BITS:
            raise SGFP4FormatError(
                f"split map overrun (>{SPLIT_MAP_MAX_BITS} bits)"
            )
        word_index = bit_pos // UINT32_BITS
        bit_index = bit_pos % UINT32_BITS
        bit_pos += 1
        split = (words[word_index] >> bit_index) & 0x1
        if split != 0:
            half = size // 2
            for dy in (0, half):
                for dx in (0, half):
                    walk(y + dy, x + dx, half)
        else:
            leaves.append((y, x, size))

    walk(0, 0, MACROBLOCK_SIZE)
    return leaves


def _record_leaves(
    binary: bytes, layout: Layout, pos: int
) -> Tuple[List[Tuple[int, int, int]], int]:
    """Resolve the leaf list of one v2 record per paper Sec 6.2.

    Uniform layouts imply row-major raster order; LAYOUT_MIXED consumes a
    12-byte split map and yields leaves in pre-order DFS order.

    Returns:
        (leaves, new_pos): leaf (y, x, size) list and the offset just past
        the split map (unchanged for uniform layouts).
    """
    if layout == Layout.MIXED:
        leaves = _parse_split_map(binary[pos:pos + SPLIT_MAP_BYTES])
        return leaves, pos + SPLIT_MAP_BYTES
    if layout in _LAYOUT_LEAF_SIZE:
        leaf_size = _LAYOUT_LEAF_SIZE[layout]
        leaves = [
            (ry, rx, leaf_size)
            for ry in range(0, MACROBLOCK_SIZE, leaf_size)
            for rx in range(0, MACROBLOCK_SIZE, leaf_size)
        ]
        return leaves, pos
    raise SGFP4FormatError(f"unknown layout {int(layout)}")


def decode_v2(binary: bytes, O: int, I: int) -> np.ndarray:
    """Decode a v2 quadtree-adaptive container to a float32 (O, I) tensor.

    Args:
        binary: self-framed v2 stream (paper Sec 6.1).
        O: unpadded output-channel count (carried by the model manifest).
        I: unpadded input-channel count.

    Returns:
        Decoded float32 array of shape (O, I).

    Raises:
        SGFP4FormatError: on framing, alignment, or reserved-bit violations.
    """
    binary = bytes(binary)
    if binary[:4] != SGFP4_MAGIC:
        raise SGFP4FormatError("bad magic")
    if binary[4] != SGFP4_VERSION_V2:
        raise SGFP4FormatError(f"bad version {binary[4]:#x}")
    B = struct.unpack_from("<I", binary, 5)[0]
    pad = binary[9:V2_FIXED_HEADER_BYTES]
    if pad != b"\x00" * V2_HEADER_PAD_BYTES:
        raise SGFP4FormatError("missing 7-byte header pad (Sec 6.1)")
    rec_offs = [
        struct.unpack_from("<I", binary, V2_FIXED_HEADER_BYTES + 4 * i)[0]
        for i in range(B)
    ]
    record_region = V2_FIXED_HEADER_BYTES + 4 * B

    tiles_y = math.ceil(O / MACROBLOCK_SIZE)
    tiles_x = math.ceil(I / MACROBLOCK_SIZE)
    if tiles_y * tiles_x != B:
        raise SGFP4FormatError(f"record count {B} != tiling {tiles_y * tiles_x}")

    out = np.zeros(
        (tiles_y * MACROBLOCK_SIZE, tiles_x * MACROBLOCK_SIZE), dtype=np.float32
    )
    for b in range(B):
        if rec_offs[b] % ALIGNMENT != 0:
            raise SGFP4FormatError(
                f"record {b} offset {rec_offs[b]} not 16-byte aligned"
            )
        base = record_region + rec_offs[b]
        sb_header = struct.unpack_from("<I", binary, base)[0]
        layout = Layout(sb_header & SB_HEADER_LAYOUT_MASK)
        if (sb_header >> SB_HEADER_RESERVED_SHIFT) != 0:
            raise SGFP4FormatError(f"record {b}: sb_header reserved bits set")

        leaves, pos = _record_leaves(binary, layout, base + 4)

        block_headers = [
            struct.unpack_from("<I", binary, pos + 4 * i)[0]
            for i in range(len(leaves))
        ]
        pos += 4 * len(leaves)
        header_pad = (-(pos - base)) % ALIGNMENT
        if binary[pos:pos + header_pad] != b"\x00" * header_pad:
            raise SGFP4FormatError(f"record {b}: header pad missing/nonzero")
        pos += header_pad

        by, bx = divmod(b, tiles_x)
        for (y, x, size), header in zip(leaves, block_headers):
            scale = _half_from_bits(header >> HALF_SHIFT)
            bias = _half_from_bits(header & BETA_TRUNC_MASK)  # Eq (6)
            flags = header & LEAF_FLAG_MASK
            if (flags & LEAF_RESERVED_MASK) != 0:
                raise SGFP4FormatError(
                    f"record {b} leaf ({y},{x}): reserved header flag bits set"
                )
            mode = CodeMode(flags & LEAF_MODE_MASK)

            n_weights = size * size
            if mode == CodeMode.FP4_AFFINE:
                n_words = n_weights // FP4_CODES_PER_WORD
            else:
                n_words = n_weights // T158_CODES_PER_WORD
            payload_bytes = n_words * 4
            n_bytes = payload_bytes + (-payload_bytes) % ALIGNMENT
            words = np.frombuffer(
                binary, dtype=np.uint32, count=n_words, offset=pos
            )
            codes = _decode_codes(words, mode, n_weights)
            tile = (
                np.float32(scale) * codes.astype(np.float32) + np.float32(bias)
            ).reshape(size, size)
            out[
                by * MACROBLOCK_SIZE + y:by * MACROBLOCK_SIZE + y + size,
                bx * MACROBLOCK_SIZE + x:bx * MACROBLOCK_SIZE + x + size,
            ] = tile
            pos += n_bytes
    return out[:O, :I]
