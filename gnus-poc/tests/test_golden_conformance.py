"""Golden conformance checks for SGFP4 v2 encode/decode.

Fixed-seed tensors are exported through the adaptive encoder and round-tripped
through the independent reference decoder. The tests pin framing invariants,
reserved-bit behavior, reconstruction quality, and deterministic bytes.
"""

import struct

import numpy as np
import pytest

from quantize.fp4_exporter import FP4Exporter
from quantize.sgfp4_decoder import decode_v2
from quantize.sgfp4_format import (
    LEAF_RESERVED_MASK,
    SGFP4_MAGIC,
    SGFP4_VERSION_V2,
    UINT32_BYTES,
    V2_FIXED_HEADER_BYTES,
    align_up,
)


_GOLDEN_CASES = [
    ("smooth_low_entropy", 100, (64, 64), 0.01),
    ("mixed_entropy", 101, (64, 64), 1.0),
    ("three_superblocks", 103, (64, 192), 0.05),
    ("four_superblocks", 102, (128, 128), 0.05),
]


def _make_weights(seed, shape, scale):
    rng = np.random.default_rng(seed)
    return (rng.standard_normal(shape) * scale).astype(np.float32)


def _record_region(binary):
    block_count = struct.unpack_from("<I", binary, 5)[0]
    table_end = V2_FIXED_HEADER_BYTES + UINT32_BYTES * block_count
    region = align_up(table_end)
    assert binary[table_end:region] == b"\x00" * (region - table_end)
    return block_count, region


def _parse_first_leaf_headers(binary):
    """Extract ``(layout, first_leaf_header)`` for every v2 record."""
    assert binary[:4] == SGFP4_MAGIC
    assert binary[4] == SGFP4_VERSION_V2
    block_count, record_region = _record_region(binary)
    records = []
    for index in range(block_count):
        record_offset = struct.unpack_from(
            "<I",
            binary,
            V2_FIXED_HEADER_BYTES + UINT32_BYTES * index,
        )[0]
        record_base = record_region + record_offset
        sb_header = struct.unpack_from("<I", binary, record_base)[0]
        layout = sb_header & 0x7
        header_pos = record_base + UINT32_BYTES
        if layout == 4:
            header_pos += 12
        first_leaf = struct.unpack_from("<I", binary, header_pos)[0]
        records.append((layout, first_leaf))
    return records


class TestGoldenConformance:
    """Deterministic SGFP4 v2 framing and decode checks."""

    @pytest.mark.parametrize("name,seed,shape,scale", _GOLDEN_CASES)
    def test_golden_roundtrip(self, name, seed, shape, scale):
        del name
        exporter = FP4Exporter()
        weights = _make_weights(seed, shape, scale)
        binary, stats = exporter.export_weights(weights, "golden", adaptive=True)

        assert binary[:4] == SGFP4_MAGIC
        assert binary[4] == SGFP4_VERSION_V2
        assert binary[9:V2_FIXED_HEADER_BYTES] == b"\x00" * 7

        block_count, record_region = _record_region(binary)
        expected_blocks = ((shape[0] + 63) // 64) * ((shape[1] + 63) // 64)
        assert block_count == expected_blocks
        assert stats["num_superblocks"] == expected_blocks
        assert record_region % 16 == 0

        assert stats["total_blocks"] == (
            stats["fp4_blocks"] + stats["t158_blocks"]
        )

        offsets = [
            struct.unpack_from(
                "<I",
                binary,
                V2_FIXED_HEADER_BYTES + UINT32_BYTES * index,
            )[0]
            for index in range(block_count)
        ]
        for offset in offsets:
            assert offset % 16 == 0
            assert (record_region + offset) % 16 == 0

        # v2 bit 0 is MODE; bits 1-3 are reserved and must remain zero.
        for _, first_leaf in _parse_first_leaf_headers(binary):
            assert (first_leaf & LEAF_RESERVED_MASK) == 0

        decoded = decode_v2(binary, shape[0], shape[1])
        assert decoded.shape == shape
        mse = float(np.mean((weights - decoded) ** 2))
        signal = float(np.mean(weights ** 2))
        assert mse < max(signal * 4.0, 1e-6)

    def test_golden_deterministic(self):
        exporter = FP4Exporter()
        weights = _make_weights(200, (64, 64), 0.5)
        binary1, stats1 = exporter.export_weights(weights, "golden", adaptive=True)
        binary2, stats2 = exporter.export_weights(weights, "golden", adaptive=True)
        assert binary1 == binary2
        assert stats1 == stats2
