"""Reference SGFP4 decoder implementing the normative decode semantics.

The decoder covers both SGFP4 profiles from the format specification:

* v1 fixed payload: ``headers[B] | offsets[B] | codes_blob[B*2048]``.
* v2 adaptive: ``SGF4 | 0x02 | B | pad0 | record_offsets[B] | pad1 |
  records``.

The v2 stream frames its record structure. The original tensor dimensions
``(O, I)`` are supplied by the enclosing model manifest and are required to
recover the macroblock grid and crop edge padding.
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
    T158_RESERVED_WORD_START,
    T158_SYMBOL_MASK,
    T158_SYMBOL_NEG,
    T158_SYMBOL_POS,
    UINT32_BITS,
    UINT32_BYTES,
    V2_FIXED_HEADER_BYTES,
    V2_HEADER_PAD_BYTES,
    CodeMode,
    Layout,
    align_up,
)


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
    """Decode one IEEE-754 binary16 value from its little-endian bit pattern."""
    return struct.unpack("<e", struct.pack("<H", bits & HALF_MASK))[0]


def int4_to_int(nib: int) -> int:
    """Decode a two's-complement 4-bit code."""
    nib &= FP4_NIBBLE_MASK
    return nib if nib < FP4_SIGN_THRESHOLD else nib - FP4_CODE_BIAS


def sym2_to_ternary(sym: int) -> int:
    """Decode a 2-bit ternary symbol; reserved ``11`` decodes as zero."""
    sym &= T158_SYMBOL_MASK
    if sym == T158_SYMBOL_POS:
        return 1
    if sym == T158_SYMBOL_NEG:
        return -1
    return 0


def _decode_codes(
    words: np.ndarray,
    mode: CodeMode,
    n_weights: int,
) -> np.ndarray:
    """Extract integer codes in the normative least-significant-bit order."""
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
    """Decode a v1 fixed-payload container to a float32 ``(O, I)`` tensor."""
    binary = bytes(binary)
    tiles_y = math.ceil(O / MACROBLOCK_SIZE)
    tiles_x = math.ceil(I / MACROBLOCK_SIZE)
    block_count = tiles_y * tiles_x
    expected_bytes = block_count * (2 * UINT32_BYTES + PAYLOAD_BYTES)
    if len(binary) != expected_bytes:
        raise SGFP4FormatError(
            f"v1 stream is {len(binary)} bytes, expected {expected_bytes}"
        )

    headers = np.frombuffer(
        binary,
        dtype="<u4",
        count=block_count,
        offset=0,
    )
    offsets = np.frombuffer(
        binary,
        dtype="<u4",
        count=block_count,
        offset=block_count * UINT32_BYTES,
    )
    blob = binary[block_count * 2 * UINT32_BYTES:]

    out = np.zeros(
        (tiles_y * MACROBLOCK_SIZE, tiles_x * MACROBLOCK_SIZE),
        dtype=np.float32,
    )
    for block_index in range(block_count):
        header = int(headers[block_index])
        scale = _half_from_bits(header >> HALF_SHIFT)
        bias = _half_from_bits(header & HALF_MASK)

        offset_word = int(offsets[block_index])
        flags = offset_word & OFFSET_FLAG_MASK
        base = offset_word & ~OFFSET_FLAG_MASK
        if (flags & OFFSET_RESERVED_MASK) != 0:
            raise SGFP4FormatError(
                f"block {block_index}: reserved offset flag bits 2-3 nonzero"
            )
        if base % ALIGNMENT != 0:
            raise SGFP4FormatError(
                f"block {block_index}: payload offset {base} is not aligned"
            )
        if base + PAYLOAD_BYTES > len(blob):
            raise SGFP4FormatError(f"block {block_index}: payload truncated")

        mode = CodeMode(flags & OFFSET_MODE_MASK)
        words = np.frombuffer(
            blob,
            dtype="<u4",
            count=PAYLOAD_U32,
            offset=base,
        )
        if (
            mode == CodeMode.T158_AFFINE
            and np.any(words[T158_RESERVED_WORD_START:] != 0)
        ):
            raise SGFP4FormatError(
                f"block {block_index}: reserved T158 payload tail is nonzero"
            )

        codes = _decode_codes(
            words,
            mode,
            MACROBLOCK_SIZE * MACROBLOCK_SIZE,
        )
        block_y, block_x = divmod(block_index, tiles_x)
        tile = (
            np.float32(scale) * codes.astype(np.float32) + np.float32(bias)
        ).reshape(MACROBLOCK_SIZE, MACROBLOCK_SIZE)
        out[
            block_y * MACROBLOCK_SIZE:(block_y + 1) * MACROBLOCK_SIZE,
            block_x * MACROBLOCK_SIZE:(block_x + 1) * MACROBLOCK_SIZE,
        ] = tile

    return out[:O, :I]


def _parse_split_map(buf: bytes) -> List[Tuple[int, int, int]]:
    """Rebuild mixed-layout leaves from the normative 12-byte split map."""
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

    packed_bits = words[0] | (words[1] << 32) | (words[2] << 64)
    if (packed_bits >> bit_pos) != 0:
        raise SGFP4FormatError("split map has nonzero unused upper bits")

    return leaves


def _record_leaves(
    binary: bytes,
    layout: Layout,
    pos: int,
) -> Tuple[List[Tuple[int, int, int]], int]:
    """Resolve one record's leaf geometry and return the next header offset."""
    if layout == Layout.MIXED:
        leaves = _parse_split_map(binary[pos:pos + SPLIT_MAP_BYTES])
        return leaves, pos + SPLIT_MAP_BYTES
    if layout in _LAYOUT_LEAF_SIZE:
        leaf_size = _LAYOUT_LEAF_SIZE[layout]
        leaves = [
            (row, col, leaf_size)
            for row in range(0, MACROBLOCK_SIZE, leaf_size)
            for col in range(0, MACROBLOCK_SIZE, leaf_size)
        ]
        return leaves, pos
    raise SGFP4FormatError(f"unknown layout {int(layout)}")


def decode_v2(binary: bytes, O: int, I: int) -> np.ndarray:
    """Decode a v2 quadtree-adaptive container using manifest shape metadata."""
    binary = bytes(binary)
    if len(binary) < V2_FIXED_HEADER_BYTES:
        raise SGFP4FormatError("v2 fixed header truncated")
    if binary[:4] != SGFP4_MAGIC:
        raise SGFP4FormatError("bad magic")
    if binary[4] != SGFP4_VERSION_V2:
        raise SGFP4FormatError(f"bad version {binary[4]:#x}")

    block_count = struct.unpack_from("<I", binary, 5)[0]
    pad0 = binary[9:V2_FIXED_HEADER_BYTES]
    if pad0 != b"\x00" * V2_HEADER_PAD_BYTES:
        raise SGFP4FormatError("missing 7-byte header pad (Sec 6.1)")

    offset_table_start = V2_FIXED_HEADER_BYTES
    offset_table_end = offset_table_start + UINT32_BYTES * block_count
    if len(binary) < offset_table_end:
        raise SGFP4FormatError("record offset table truncated")

    record_offsets = [
        struct.unpack_from(
            "<I",
            binary,
            offset_table_start + UINT32_BYTES * index,
        )[0]
        for index in range(block_count)
    ]
    record_region = align_up(offset_table_end)
    pad1 = binary[offset_table_end:record_region]
    if pad1 != b"\x00" * (record_region - offset_table_end):
        raise SGFP4FormatError("offset-table pad missing or nonzero")
    if len(binary) < record_region:
        raise SGFP4FormatError("v2 record region truncated")

    tiles_y = math.ceil(O / MACROBLOCK_SIZE)
    tiles_x = math.ceil(I / MACROBLOCK_SIZE)
    expected_blocks = tiles_y * tiles_x
    if expected_blocks != block_count:
        raise SGFP4FormatError(
            f"record count {block_count} != tiling {expected_blocks}"
        )

    out = np.zeros(
        (tiles_y * MACROBLOCK_SIZE, tiles_x * MACROBLOCK_SIZE),
        dtype=np.float32,
    )
    previous_offset = -1
    for block_index, record_offset in enumerate(record_offsets):
        if record_offset % ALIGNMENT != 0:
            raise SGFP4FormatError(
                f"record {block_index} offset {record_offset} not 16-byte aligned"
            )
        if record_offset <= previous_offset:
            raise SGFP4FormatError("record offsets are not strictly increasing")
        previous_offset = record_offset

        base = record_region + record_offset
        if base + UINT32_BYTES > len(binary):
            raise SGFP4FormatError(f"record {block_index}: header truncated")

        sb_header = struct.unpack_from("<I", binary, base)[0]
        layout_value = sb_header & SB_HEADER_LAYOUT_MASK
        try:
            layout = Layout(layout_value)
        except ValueError as exc:
            raise SGFP4FormatError(
                f"record {block_index}: unknown layout {layout_value}"
            ) from exc
        if (sb_header >> SB_HEADER_RESERVED_SHIFT) != 0:
            raise SGFP4FormatError(
                f"record {block_index}: sb_header reserved bits set"
            )

        leaves, pos = _record_leaves(binary, layout, base + UINT32_BYTES)
        block_header_bytes = UINT32_BYTES * len(leaves)
        if pos + block_header_bytes > len(binary):
            raise SGFP4FormatError(
                f"record {block_index}: leaf header table truncated"
            )
        block_headers = [
            struct.unpack_from("<I", binary, pos + UINT32_BYTES * index)[0]
            for index in range(len(leaves))
        ]
        pos += block_header_bytes

        header_pad = (-(pos - base)) % ALIGNMENT
        if binary[pos:pos + header_pad] != b"\x00" * header_pad:
            raise SGFP4FormatError(
                f"record {block_index}: header pad missing or nonzero"
            )
        pos += header_pad

        block_y, block_x = divmod(block_index, tiles_x)
        for (y, x, size), header in zip(leaves, block_headers):
            scale = _half_from_bits(header >> HALF_SHIFT)
            bias = _half_from_bits(header & BETA_TRUNC_MASK)
            flags = header & LEAF_FLAG_MASK
            if (flags & LEAF_RESERVED_MASK) != 0:
                raise SGFP4FormatError(
                    f"record {block_index} leaf ({y},{x}): "
                    "reserved header flag bits set"
                )
            mode = CodeMode(flags & LEAF_MODE_MASK)

            n_weights = size * size
            if mode == CodeMode.FP4_AFFINE:
                n_words = n_weights // FP4_CODES_PER_WORD
            else:
                n_words = n_weights // T158_CODES_PER_WORD
            payload_bytes = n_words * UINT32_BYTES
            padded_bytes = align_up(payload_bytes)
            if pos + padded_bytes > len(binary):
                raise SGFP4FormatError(
                    f"record {block_index} leaf ({y},{x}): payload truncated"
                )

            words = np.frombuffer(
                binary,
                dtype="<u4",
                count=n_words,
                offset=pos,
            )
            payload_pad = binary[pos + payload_bytes:pos + padded_bytes]
            if payload_pad != b"\x00" * (padded_bytes - payload_bytes):
                raise SGFP4FormatError(
                    f"record {block_index} leaf ({y},{x}): "
                    "payload pad nonzero"
                )

            codes = _decode_codes(words, mode, n_weights)
            tile = (
                np.float32(scale) * codes.astype(np.float32) + np.float32(bias)
            ).reshape(size, size)
            out[
                block_y * MACROBLOCK_SIZE + y:
                block_y * MACROBLOCK_SIZE + y + size,
                block_x * MACROBLOCK_SIZE + x:
                block_x * MACROBLOCK_SIZE + x + size,
            ] = tile
            pos += padded_bytes

    return out[:O, :I]
