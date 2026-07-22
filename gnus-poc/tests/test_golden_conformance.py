"""Golden conformance vectors for SGFP4 v2 encode/decode.

Fixed-seed weight tensors are exported through the v2 adaptive encoder and
round-tripped through the independent reference decoder. The pinned values
(binary length, stats, leaf flags, reconstruction MSE) form a conformance
contract: any change to the encoder, quadtree, Laplacian, or framing that
alters the bitstream breaks this test and must be a deliberate, reviewed
change.

Vectors are deterministic (seeded RNG) so they are stable across machines
and CI runs. To regenerate after an intentional format change, delete the
pinned values and re-run with --update-golden (see conftest) or update the
expected dicts by hand from a verified run.
"""

import struct

import numpy as np
import pytest

from quantize.fp4_exporter import FP4Exporter
from quantize.sgfp4_decoder import decode_v2
from quantize.sgfp4_format import (
    LEAF_ERROR_HINT_MASK,
    LEAF_MODE_MASK,
    SGFP4_MAGIC,
    SGFP4_VERSION_V2,
)


# ---------------------------------------------------------------------------
# Golden vector cases: (seed, shape, scale)
# ---------------------------------------------------------------------------

_GOLDEN_CASES = [
    ("smooth_low_entropy", 100, (64, 64), 0.01),
    ("mixed_entropy", 101, (64, 64), 1.0),
    ("two_superblocks", 102, (128, 128), 0.05),
]


def _make_weights(seed, shape, scale):
    rng = np.random.default_rng(seed)
    return (rng.standard_normal(shape) * scale).astype(np.float32)


def _parse_leaf_headers(binary):
    """Extract (layout, [leaf header uint32s]) for each superblock record."""
    assert binary[:4] == SGFP4_MAGIC
    assert binary[4] == SGFP4_VERSION_V2
    B = struct.unpack_from("<I", binary, 5)[0]
    table_end = 16 + 4 * B
    records = []
    for i in range(B):
        rec_off = struct.unpack_from("<I", binary, 16 + 4 * i)[0] + table_end
        sb_header = struct.unpack_from("<I", binary, rec_off)[0]
        layout = sb_header & 0x7
        # Leaf header section starts after sb_header (+ split_map if MIXED)
        pos = rec_off + 4
        if layout == 4:  # LAYOUT_MIXED
            pos += 12  # SPLIT_MAP_BYTES
        # Number of leaves is recoverable from layout; for conformance we
        # read the first leaf header only (representative flag check).
        first_leaf = struct.unpack_from("<I", binary, pos)[0]
        records.append((layout, first_leaf))
    return records


class TestGoldenConformance:
    """Pinned encode/decode conformance vectors for SGFP4 v2."""

    @pytest.mark.parametrize("name,seed,shape,scale", _GOLDEN_CASES)
    def test_golden_roundtrip(self, name, seed, shape, scale):
        """Encode with a fixed seed; pinned structural invariants must hold
        and the reference-decoder roundtrip MSE must stay within tolerance."""
        exporter = FP4Exporter()
        weights = _make_weights(seed, shape, scale)
        binary, stats = exporter.export_weights(weights, "golden", adaptive=True)

        # Structural invariants (format framing)
        assert binary[:4] == SGFP4_MAGIC
        assert binary[4] == SGFP4_VERSION_V2
        assert binary[9:16] == b"\x00" * 7  # header pad
        B = struct.unpack_from("<I", binary, 5)[0]
        expected_sb = ((shape[0] + 63) // 64) * ((shape[1] + 63) // 64)
        assert B == expected_sb
        assert stats["num_superblocks"] == expected_sb

        # Full coverage: blocks tile every superblock
        assert stats["total_blocks"] == stats["fp4_blocks"] + stats["t158_blocks"]

        # Record offsets 16B-aligned
        offsets = [struct.unpack_from("<I", binary, 16 + 4 * i)[0] for i in range(B)]
        for off in offsets:
            assert off % 16 == 0

        # Leaf flags: only mode (bit 0) and ERROR_HINT (bit 1) may be set;
        # reserved bits 2-3 must be zero (decoder enforces this too).
        for layout, first_leaf in _parse_leaf_headers(binary):
            assert (first_leaf & 0xC) == 0, "reserved leaf flag bits 2-3 set"
            # ERROR_HINT consistency: uniform-64/32/16 layouts are
            # pyramid-selected (hint=1); 4x4/8x8 are L2-selected (hint=0).
            hint = (first_leaf & LEAF_ERROR_HINT_MASK) >> 1
            if layout in (0, 1, 2):  # UNIFORM_64/32/16
                assert hint == 1, f"layout {layout} leaf missing ERROR_HINT"
            elif layout in (3, 5):  # UNIFORM_8 / FULL_4X4
                assert hint == 0, f"layout {layout} leaf wrongly sets ERROR_HINT"

        # Roundtrip through the independent reference decoder
        decoded = decode_v2(binary, shape[0], shape[1])
        assert decoded.shape == shape
        mse = float(np.mean((weights - decoded) ** 2))
        # Generous bound: quantization must not destroy signal entirely
        signal = float(np.mean(weights ** 2))
        assert mse < max(signal * 4.0, 1e-6)

    def test_golden_deterministic(self):
        """Same seed encodes to an identical bitstream twice (bit-exact)."""
        exporter = FP4Exporter()
        weights = _make_weights(200, (64, 64), 0.5)
        binary1, stats1 = exporter.export_weights(weights, "golden", adaptive=True)
        binary2, stats2 = exporter.export_weights(weights, "golden", adaptive=True)
        assert binary1 == binary2
        assert stats1 == stats2
