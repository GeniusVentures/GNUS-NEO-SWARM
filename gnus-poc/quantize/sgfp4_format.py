"""SGFP4 wire-format constants — single source of truth.

Every magic number used by the SGFP4 exporter and reference decoder is
named here exactly once, mirroring the SuperGenius coding standard's rule
against unnamed constants (std. §4.5). Names follow the Python/PEP 8
UPPER_CASE convention, which plays the role that k-prefixed compile-time
constants play in the C++ standard.

All values are normative, taken from "SGFP4: Adaptive Dual-Mode
Macroblock Quantization with GPU-Friendly Unpacking and Verifiable
Decode Semantics" (arXiv v2), sections 3.2, 4.2, 4.3, 6.1, 6.2.
"""

from enum import IntEnum


# ---------------------------------------------------------------------------
# Enumerations (std. §5.9: scoped enums over bare ints)
# ---------------------------------------------------------------------------

class CodeMode(IntEnum):
    """Per-block code mode (paper Sec 3.2)."""

    FP4_AFFINE = 0    # 4-bit signed two's-complement codes
    T158_AFFINE = 1   # ternary {-1, 0, +1} as 2-bit symbols


class Layout(IntEnum):
    """v2 superblock layout enumeration (paper Sec 6.2, Table 3)."""

    UNIFORM_64 = 0    # one 64x64 leaf
    UNIFORM_32 = 1    # four 32x32 leaves
    UNIFORM_16 = 2    # sixteen 16x16 leaves
    UNIFORM_8 = 3     # sixty-four 8x8 leaves
    MIXED = 4         # variable quadtree leaves; split map present
    FULL_4X4 = 5      # 256 4x4 leaves


# ---------------------------------------------------------------------------
# Tiling and payload geometry (Sec 3.1, 4.1)
# ---------------------------------------------------------------------------

MACROBLOCK_SIZE = 64        # external addressing unit, both profiles
PAYLOAD_BYTES = 2048        # v1 fixed payload per macroblock
PAYLOAD_U32 = PAYLOAD_BYTES // 4
ALIGNMENT = 16              # payload/record alignment, both profiles
UINT32_BYTES = 4
UINT32_BITS = 32

# ---------------------------------------------------------------------------
# Normative code packing (Sec 4.3, Eq. 3 and 4)
# ---------------------------------------------------------------------------

FP4_BITS_PER_CODE = 4
FP4_CODES_PER_WORD = UINT32_BITS // FP4_BITS_PER_CODE       # 8
FP4_NIBBLE_MASK = 0xF
FP4_SIGN_THRESHOLD = 8      # nibbles >= 8 map to code - 16
FP4_CODE_BIAS = 16          # two's-complement wrap for negative nibbles

T158_BITS_PER_CODE = 2
T158_CODES_PER_WORD = UINT32_BITS // T158_BITS_PER_CODE     # 16
T158_SYMBOL_MASK = 0x3
T158_SYMBOL_POS = 1         # 01 -> +1
T158_SYMBOL_NEG = 2         # 10 -> -1
# 00 -> 0; 11 is reserved and decodes as 0

T158_RESERVED_WORD_START = 256   # words 256..511 of a v1 T158 payload are 0

# ---------------------------------------------------------------------------
# v1 offset-word flags (Sec 4.2)
# ---------------------------------------------------------------------------

OFFSET_FLAG_MASK = 0xF          # low 4 bits of aligned offsets carry flags
OFFSET_MODE_MASK = 0x1          # bit 0: mode
OFFSET_RESERVED_MASK = 0xC      # bits 2-3: reserved, written 0

# ---------------------------------------------------------------------------
# Affine parameter packing (Sec 3.2) and v2 leaf-header flags (Sec 6.2, Eq. 6)
# ---------------------------------------------------------------------------

HALF_SHIFT = 16                 # S in upper 16 bits, beta in lower 16
HALF_MASK = 0xFFFF
FP16_MAX = 65504.0              # FP16 clip bound at encode time

LEAF_FLAG_MASK = 0xF            # low 4 bits of the packed word carry flags
LEAF_MODE_MASK = 0x1            # bit 0: mode
LEAF_RESERVED_MASK = 0xE        # bits 1-3: reserved, written 0
BETA_TRUNC_MASK = 0xFFF0        # decoder recovers beta = half(h & mask)
HEADER_CLEAR_FLAGS_MASK = 0xFFFFFFF0

# ---------------------------------------------------------------------------
# v2 framing (Sec 6.1)
# ---------------------------------------------------------------------------

SGFP4_MAGIC = b"SGF4"
SGFP4_VERSION_V2 = 0x02
V2_FIXED_HEADER_BYTES = 16      # magic(4) + version(1) + B(4) + pad(7)
V2_HEADER_PAD_BYTES = 7

# ---------------------------------------------------------------------------
# v2 record header (Sec 6.2)
# ---------------------------------------------------------------------------

SB_HEADER_LAYOUT_MASK = 0x7     # bits 0-2: layout enum
SB_HEADER_RESERVED_SHIFT = 3    # bits 3-31: reserved, written 0

SPLIT_MAP_BYTES = 12            # three little-endian uint32 words
SPLIT_MAP_WORDS = 3
SPLIT_MAP_MAX_BITS = 85         # 1 + 4 + 16 + 64 nodes of size >= 8
MIN_LEAF_SIZE = 4               # quadtree recursion floor; no bit below this
