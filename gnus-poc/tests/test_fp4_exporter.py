"""Tests for the SGFP4 v1 fixed and v2 adaptive exporters."""

import json
import struct

import numpy as np
import pytest

from quantize.fp4_exporter import (
    DEFAULT_V2_THRESHOLDS,
    LAYOUT_FULL_4x4,
    LAYOUT_MIXED,
    LAYOUT_UNIFORM_16,
    LAYOUT_UNIFORM_32,
    LAYOUT_UNIFORM_64,
    LAYOUT_UNIFORM_8,
    MACROBLOCK_SIZE,
    MODE_FP4_AFFINE,
    MODE_T158_AFFINE,
    PAYLOAD_BYTES,
    PAYLOAD_U32,
    FP4Exporter,
)
from quantize.sgfp4_decoder import SGFP4FormatError, _parse_split_map, decode_v1, decode_v2
from quantize.sgfp4_format import (
    ALIGNMENT,
    LEAF_RESERVED_MASK,
    SGFP4_MAGIC,
    SGFP4_VERSION_V2,
    UINT32_BYTES,
    V2_FIXED_HEADER_BYTES,
    align_up,
)


def _v2_record_region(binary: bytes):
    block_count = struct.unpack_from("<I", binary, 5)[0]
    table_end = V2_FIXED_HEADER_BYTES + UINT32_BYTES * block_count
    record_region = align_up(table_end)
    return block_count, table_end, record_region


def _first_leaf_header_position(binary: bytes, record_index: int = 0) -> int:
    block_count, _, record_region = _v2_record_region(binary)
    assert 0 <= record_index < block_count
    record_offset = struct.unpack_from(
        "<I",
        binary,
        V2_FIXED_HEADER_BYTES + UINT32_BYTES * record_index,
    )[0]
    record_base = record_region + record_offset
    layout = struct.unpack_from("<I", binary, record_base)[0] & 0x7
    return record_base + UINT32_BYTES + (12 if layout == LAYOUT_MIXED else 0)


class TestFP4Exporter:
    def test_export_small_tensor(self):
        exporter = FP4Exporter()
        weights = np.random.randn(64, 64).astype(np.float32)
        binary, stats = exporter.export_weights(weights, "test")
        block_count = stats["num_blocks"]
        assert block_count == 1
        assert len(binary) == block_count * (8 + PAYLOAD_BYTES)
        assert stats["shape"] == [64, 64]

    def test_export_rectangular_tensor(self):
        exporter = FP4Exporter()
        weights = np.random.randn(128, 192).astype(np.float32)
        _, stats = exporter.export_weights(weights, "test")
        assert stats["tiles_y"] == 2
        assert stats["tiles_x"] == 3
        assert stats["num_blocks"] == 6

    def test_padded_tensor_pads_correctly(self):
        exporter = FP4Exporter()
        weights = np.random.randn(100, 100).astype(np.float32)
        _, stats = exporter.export_weights(weights, "test")
        assert stats["tiles_y"] == 2
        assert stats["tiles_x"] == 2
        assert stats["num_blocks"] == 4

    def test_header_contains_scale_bias(self):
        exporter = FP4Exporter()
        weights = np.ones((64, 64), dtype=np.float32) * 3.0
        binary, _ = exporter.export_weights(weights, "test")
        header = struct.unpack_from("<I", binary, 0)[0]
        scale = struct.unpack("<e", struct.pack("<H", header >> 16))[0]
        bias = struct.unpack("<e", struct.pack("<H", header & 0xFFFF))[0]
        assert scale >= 0.0
        assert abs(bias - 3.0) < 0.16

    def test_export_to_file(self, tmp_path):
        exporter = FP4Exporter(project_root=tmp_path)
        weights = np.random.randn(64, 64).astype(np.float32)
        bin_path, _ = exporter.export_to_file(weights, "test")
        assert bin_path.exists()
        assert bin_path.name == "test.fp4"

    def test_ternary_vs_fp4_mode_flag(self):
        exporter = FP4Exporter()
        weights = np.eye(64, dtype=np.float32)
        binary, _ = exporter.export_weights(
            weights,
            "test",
            prefer_ternary=True,
        )
        offset = struct.unpack_from("<I", binary, 4)[0]
        assert (offset & 0x1) in (MODE_FP4_AFFINE, MODE_T158_AFFINE)

    def test_payload_size_fixed(self):
        exporter = FP4Exporter()
        weights = np.random.randn(128, 128).astype(np.float32)
        binary, stats = exporter.export_weights(weights, "test")
        block_count = stats["num_blocks"]
        payload_start = block_count * 8
        assert len(binary) - payload_start == block_count * PAYLOAD_BYTES

    def test_roundtrip_fp4_mse(self):
        exporter = FP4Exporter()
        weights = np.random.randn(64, 64).astype(np.float32) * 3.0
        binary, _ = exporter.export_weights(weights, "test")
        decoded = decode_v1(binary, 64, 64)
        mse = float(np.mean((weights - decoded) ** 2))
        assert mse < 1.0


class TestFP4ExporterV2:
    def test_v2_binary_starts_with_magic(self):
        exporter = FP4Exporter()
        weights = np.random.randn(64, 64).astype(np.float32) * 0.1
        binary, _ = exporter.export_weights(weights, "test", adaptive=True)
        assert binary[:4] == SGFP4_MAGIC

    def test_v2_binary_has_version_byte(self):
        exporter = FP4Exporter()
        weights = np.random.randn(64, 64).astype(np.float32) * 0.1
        binary, _ = exporter.export_weights(weights, "test", adaptive=True)
        assert binary[4] == SGFP4_VERSION_V2

    def test_v2_binary_has_superblock_count(self):
        exporter = FP4Exporter()
        weights = np.random.randn(128, 128).astype(np.float32) * 0.1
        binary, _ = exporter.export_weights(weights, "test", adaptive=True)
        assert struct.unpack_from("<I", binary, 5)[0] == 4

    def test_v2_stats_has_effective_bpw(self):
        exporter = FP4Exporter()
        weights = np.random.randn(64, 64).astype(np.float32) * 0.1
        _, stats = exporter.export_weights(weights, "test", adaptive=True)
        assert 0.0 < stats["effective_bpw"] <= 32.0

    def test_v2_stats_has_layout_distribution(self):
        exporter = FP4Exporter()
        weights = np.random.randn(64, 64).astype(np.float32) * 0.5
        _, stats = exporter.export_weights(weights, "test", adaptive=True)
        assert all(index in stats["layout_distribution"] for index in range(6))
        assert sum(stats["layout_distribution"].values()) == stats["num_superblocks"]

    def test_v2_export_to_file_writes_sgfp4_extension(self, tmp_path):
        exporter = FP4Exporter(project_root=tmp_path)
        weights = np.random.randn(64, 64).astype(np.float32) * 0.1
        bin_path, _ = exporter.export_to_file(
            weights,
            "test",
            adaptive=True,
        )
        assert bin_path.name == "test.sgfp4"
        assert bin_path.exists()

    def test_v2_export_to_file_writes_manifest(self, tmp_path):
        exporter = FP4Exporter(project_root=tmp_path)
        weights = np.random.randn(64, 64).astype(np.float32) * 0.1
        bin_path, _ = exporter.export_to_file(
            weights,
            "code",
            adaptive=True,
            base_model="mlx-community/Qwen3-Coder-30B-A3B-Instruct-bf16",
        )
        manifest = json.loads((bin_path.parent / "manifest.json").read_text())
        assert "sha256" in manifest["fp4_binary"]
        assert manifest["niche"] == "code"

    def test_v2_vs_v1_different_output(self):
        exporter = FP4Exporter()
        weights = np.random.randn(64, 64).astype(np.float32) * 2.0
        v1_binary, _ = exporter.export_weights(weights, "test", adaptive=False)
        v2_binary, _ = exporter.export_weights(weights, "test", adaptive=True)
        assert v1_binary != v2_binary

    def test_v2_layout_constant_values(self):
        assert LAYOUT_UNIFORM_64 == 0
        assert LAYOUT_UNIFORM_32 == 1
        assert LAYOUT_UNIFORM_16 == 2
        assert LAYOUT_UNIFORM_8 == 3
        assert LAYOUT_MIXED == 4
        assert LAYOUT_FULL_4x4 == 5

    def test_payload_u32_helper(self):
        exporter = FP4Exporter()
        assert exporter._payload_u32(64, MODE_FP4_AFFINE) == 512
        assert exporter._payload_u32(64, MODE_T158_AFFINE) == 256
        assert exporter._payload_u32(32, MODE_FP4_AFFINE) == 128
        assert exporter._payload_u32(32, MODE_T158_AFFINE) == 64
        assert exporter._payload_u32(16, MODE_FP4_AFFINE) == 32
        assert exporter._payload_u32(16, MODE_T158_AFFINE) == 16
        assert exporter._payload_u32(8, MODE_FP4_AFFINE) == 8
        assert exporter._payload_u32(8, MODE_T158_AFFINE) == 4
        assert exporter._payload_u32(4, MODE_FP4_AFFINE) == 2
        assert exporter._payload_u32(4, MODE_T158_AFFINE) == 1

    def test_classify_layout_uniform_64(self):
        assert FP4Exporter._classify_layout(
            [{"size": 64, "y": 0, "x": 0}]
        ) == LAYOUT_UNIFORM_64

    def test_classify_layout_uniform_32(self):
        blocks = [
            {"size": 32, "y": 0, "x": 0},
            {"size": 32, "y": 0, "x": 32},
            {"size": 32, "y": 32, "x": 0},
            {"size": 32, "y": 32, "x": 32},
        ]
        assert FP4Exporter._classify_layout(blocks) == LAYOUT_UNIFORM_32

    def test_classify_layout_full_4x4(self):
        blocks = [
            {"size": 4, "y": y, "x": x}
            for y in range(0, 64, 4)
            for x in range(0, 64, 4)
        ]
        assert FP4Exporter._classify_layout(blocks) == LAYOUT_FULL_4x4

    def test_classify_layout_mixed(self):
        blocks = [
            {"size": 32, "y": 0, "x": 0},
            {"size": 16, "y": 32, "x": 0},
            {"size": 16, "y": 48, "x": 0},
        ]
        assert FP4Exporter._classify_layout(blocks) == LAYOUT_MIXED

    def test_v1_default_is_not_adaptive(self):
        exporter = FP4Exporter()
        weights = np.random.randn(64, 64).astype(np.float32) * 0.1
        binary, _ = exporter.export_weights(weights, "test")
        assert binary[:4] != SGFP4_MAGIC

    def test_v2_superblock_offset_table(self):
        exporter = FP4Exporter()
        weights = np.random.randn(128, 128).astype(np.float32) * 0.1
        binary, _ = exporter.export_weights(weights, "test", adaptive=True)
        block_count = struct.unpack_from("<I", binary, 5)[0]
        offsets = [
            struct.unpack_from(
                "<I",
                binary,
                V2_FIXED_HEADER_BYTES + UINT32_BYTES * index,
            )[0]
            for index in range(block_count)
        ]
        assert offsets == sorted(offsets)
        assert all(offset % ALIGNMENT == 0 for offset in offsets)

    def test_v2_encode_fp4_variable(self):
        exporter = FP4Exporter()
        for size in (4, 8, 16, 32, 64):
            region = np.random.randn(size, size).astype(np.float32) * 2.0
            result = exporter._encode_fp4_affine_variable(region)
            assert result["n_weights"] == size * size
            assert len(result["payload"]) == size * size // 8

    def test_v2_encode_t158_variable(self):
        exporter = FP4Exporter()
        for size in (4, 8, 16, 32, 64):
            region = np.random.randn(size, size).astype(np.float32)
            result = exporter._encode_t158_affine_variable(region)
            assert result["n_weights"] == size * size
            assert len(result["payload"]) == size * size // 16

    def test_backward_compatible_cli_default(self):
        assert MACROBLOCK_SIZE == 64
        assert PAYLOAD_BYTES == 2048
        assert MODE_FP4_AFFINE == 0
        assert MODE_T158_AFFINE == 1


class TestFP4ExporterThreatModel:
    def test_sgfp4_magic_is_constant(self):
        assert SGFP4_MAGIC == b"SGF4"
        assert len(SGFP4_MAGIC) == 4

    def test_sgfp4_version_is_v2(self):
        assert SGFP4_VERSION_V2 == 0x02

    def test_v2_stats_has_no_weight_values(self):
        exporter = FP4Exporter()
        weights = np.random.randn(64, 64).astype(np.float32)
        _, stats = exporter.export_weights(weights, "test", adaptive=True)
        assert "shape" in stats
        assert "num_superblocks" in stats
        assert "effective_bpw" in stats
        assert "layout_distribution" in stats
        assert "weights" not in stats
        assert "values" not in stats

    def test_default_thresholds_all_positive(self):
        for size, threshold in DEFAULT_V2_THRESHOLDS.items():
            assert threshold["max_mse"] > 0.0, size
            assert threshold["max_relative"] > 0.0, size

    def test_superblock_header_layout_reserved(self):
        for layout_value in range(6):
            assert np.uint32(layout_value & 0x7) < 8


class TestV2SpecConformance:
    @pytest.mark.parametrize(
        "shape,expected_blocks",
        [
            ((64, 64), 1),
            ((64, 128), 2),
            ((64, 192), 3),
            ((128, 128), 4),
            ((64, 320), 5),
        ],
    )
    def test_v2_offset_table_and_record_region_alignment(
        self,
        shape,
        expected_blocks,
    ):
        exporter = FP4Exporter()
        rng = np.random.default_rng(expected_blocks)
        weights = (rng.standard_normal(shape) * 0.05).astype(np.float32)
        binary, _ = exporter.export_weights(weights, "test", adaptive=True)

        assert binary[9:V2_FIXED_HEADER_BYTES] == b"\x00" * 7
        block_count, table_end, record_region = _v2_record_region(binary)
        assert block_count == expected_blocks
        assert record_region == align_up(16 + 4 * block_count)
        assert record_region % ALIGNMENT == 0
        assert binary[table_end:record_region] == b"\x00" * (
            record_region - table_end
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
            assert offset % ALIGNMENT == 0
            assert (record_region + offset) % ALIGNMENT == 0

        ends = offsets[1:] + [len(binary) - record_region]
        for offset, end in zip(offsets, ends):
            assert (end - offset) % ALIGNMENT == 0

    def test_v2_reference_decoder_roundtrip_uniform(self):
        exporter = FP4Exporter()
        rng = np.random.default_rng(2)
        weights = (rng.standard_normal((128, 128)) * 0.05).astype(np.float32)
        binary, _ = exporter.export_weights(weights, "test", adaptive=True)
        decoded = decode_v2(binary, 128, 128)
        assert float(np.mean((weights - decoded) ** 2)) < 0.01

    def test_v2_offset_table_pad_must_be_zero(self):
        exporter = FP4Exporter()
        weights = np.zeros((64, 64), dtype=np.float32)
        binary, _ = exporter.export_weights(weights, "test", adaptive=True)
        _, table_end, record_region = _v2_record_region(binary)
        assert record_region > table_end

        corrupted = bytearray(binary)
        corrupted[table_end] = 1
        with pytest.raises(SGFP4FormatError, match="offset-table pad"):
            decode_v2(bytes(corrupted), 64, 64)

    def test_v2_leaf_bits_1_through_3_are_zero(self):
        exporter = FP4Exporter()
        weights = np.zeros((64, 64), dtype=np.float32)
        binary, _ = exporter.export_weights(weights, "test", adaptive=True)
        header_pos = _first_leaf_header_position(binary)
        header = struct.unpack_from("<I", binary, header_pos)[0]
        assert (header & LEAF_RESERVED_MASK) == 0

    def test_v2_decoder_rejects_reserved_leaf_bit(self):
        exporter = FP4Exporter()
        weights = np.zeros((64, 64), dtype=np.float32)
        binary, _ = exporter.export_weights(weights, "test", adaptive=True)
        header_pos = _first_leaf_header_position(binary)

        corrupted = bytearray(binary)
        header = struct.unpack_from("<I", corrupted, header_pos)[0]
        struct.pack_into("<I", corrupted, header_pos, header | 0x2)
        with pytest.raises(SGFP4FormatError, match="reserved header flag"):
            decode_v2(bytes(corrupted), 64, 64)

    def test_v2_uniform_16_raster_order_roundtrip(self):
        exporter = FP4Exporter()
        rng = np.random.default_rng(3)
        weights = (rng.standard_normal((64, 64)) * 2.0).astype(np.float32)
        binary, stats = exporter.export_weights(
            weights,
            "test",
            adaptive=True,
            thresholds={
                64: {"max_mse": 0.0, "max_relative": 0.0},
                32: {"max_mse": 0.0, "max_relative": 0.0},
            },
            min_block_size=16,
        )
        assert stats["layout_distribution"][LAYOUT_UNIFORM_16] == 1
        decoded = decode_v2(binary, 64, 64)
        assert float(np.mean((weights - decoded) ** 2)) < 1.0

    def test_v2_mixed_layout_roundtrip_via_split_map(self):
        exporter = FP4Exporter()
        rng = np.random.default_rng(4)
        weights = (rng.standard_normal((64, 64)) * 0.01).astype(np.float32)
        weights[:32, :32] = rng.standard_normal((32, 32)).astype(np.float32)
        thresholds = {
            size: {"max_mse": 1e-4, "max_relative": 1.0}
            for size in (64, 32, 16, 8, 4)
        }
        binary, stats = exporter.export_weights(
            weights,
            "test",
            adaptive=True,
            thresholds=thresholds,
        )
        assert stats["layout_distribution"][LAYOUT_MIXED] == 1
        decoded = decode_v2(binary, 64, 64)
        assert float(np.mean((weights - decoded) ** 2)) < 1.0

    def test_build_split_map_known_tree(self):
        blocks = [
            {"y": 0, "x": 0, "size": 32},
            {"y": 0, "x": 32, "size": 32},
            {"y": 32, "x": 0, "size": 16},
            {"y": 32, "x": 16, "size": 16},
            {"y": 48, "x": 0, "size": 16},
            {"y": 48, "x": 16, "size": 16},
            {"y": 32, "x": 32, "size": 32},
        ]
        split_map = FP4Exporter._build_split_map(blocks)
        assert len(split_map) == 12
        word0, word1, word2 = struct.unpack("<3I", split_map)
        assert word0 == (1 << 0) | (1 << 3)
        assert word1 == 0 and word2 == 0
        assert _parse_split_map(split_map) == [
            (block["y"], block["x"], block["size"])
            for block in blocks
        ]
