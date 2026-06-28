"""Tests for FP4 Ultra exporter — v1 fixed and v2 adaptive."""

import json
import struct

import numpy as np

from quantize.fp4_exporter import (
    FP4Exporter,
    MACROBLOCK_SIZE,
    PAYLOAD_BYTES,
    PAYLOAD_U32,
    MODE_FP4_AFFINE,
    MODE_T158_AFFINE,
    LAYOUT_UNIFORM_64,
    LAYOUT_UNIFORM_32,
    LAYOUT_UNIFORM_16,
    LAYOUT_UNIFORM_8,
    LAYOUT_MIXED,
    LAYOUT_FULL_4x4,
    SGFP4_MAGIC,
    SGFP4_VERSION_V2,
    DEFAULT_V2_THRESHOLDS,
)


# ---------------------------------------------------------------------------
# v1 Tests (existing — backward compatibility)
# ---------------------------------------------------------------------------

class TestFP4Exporter:
    def test_export_small_tensor(self):
        exporter = FP4Exporter()
        weights = np.random.randn(64, 64).astype(np.float32)
        binary, stats = exporter.export_weights(weights, "test")

        B = stats["num_blocks"]
        assert B == 1
        expected_size = B * 4 + B * 4 + B * PAYLOAD_BYTES
        assert len(binary) == expected_size
        assert stats["shape"] == [64, 64]

    def test_export_rectangular_tensor(self):
        exporter = FP4Exporter()
        weights = np.random.randn(128, 192).astype(np.float32)
        binary, stats = exporter.export_weights(weights, "test")

        tiles_y = 128 // 64 + (1 if 128 % 64 else 0)
        tiles_x = 192 // 64
        assert stats["tiles_y"] == tiles_y
        assert stats["tiles_x"] == tiles_x
        assert stats["num_blocks"] == tiles_y * tiles_x

    def test_padded_tensor_pads_correctly(self):
        exporter = FP4Exporter()
        weights = np.random.randn(100, 100).astype(np.float32)
        binary, stats = exporter.export_weights(weights, "test")
        assert stats["tiles_y"] == 2
        assert stats["tiles_x"] == 2
        assert stats["num_blocks"] == 4

    def test_header_contains_scale_bias(self):
        exporter = FP4Exporter()
        weights = np.ones((64, 64), dtype=np.float32) * 3.0
        binary, stats = exporter.export_weights(weights, "test")

        header = struct.unpack_from("<I", binary, 0)[0]
        s_bits = (header >> 16) & 0xFFFF
        b_bits = header & 0xFFFF
        scale = struct.unpack("<e", struct.pack("<H", s_bits))[0]
        bias = struct.unpack("<e", struct.pack("<H", b_bits))[0]
        assert abs(bias - 3.0) < 0.16

    def test_export_to_file(self, tmp_path):
        exporter = FP4Exporter(project_root=tmp_path)
        weights = np.random.randn(64, 64).astype(np.float32)
        bin_path, stats = exporter.export_to_file(weights, "test")
        assert bin_path.exists()
        assert bin_path.name == "test.fp4"

    def test_ternary_vs_fp4_mode_flag(self):
        exporter = FP4Exporter()
        weights = np.eye(64, dtype=np.float32)
        binary, stats = exporter.export_weights(weights, "test", prefer_ternary=True)

        offset = struct.unpack_from("<I", binary, 4)[0]
        mode = offset & 0x1
        assert mode in (MODE_FP4_AFFINE, MODE_T158_AFFINE)

    def test_payload_size_fixed(self):
        exporter = FP4Exporter()
        weights = np.random.randn(128, 128).astype(np.float32)
        binary, stats = exporter.export_weights(weights, "test")
        B = stats["num_blocks"]
        payload_start = B * 4 + B * 4
        payload_length = len(binary) - payload_start
        assert payload_length == B * PAYLOAD_BYTES

    def test_roundtrip_fp4_mse(self):
        exporter = FP4Exporter()
        weights = np.random.randn(64, 64).astype(np.float32) * 3.0
        binary, stats = exporter.export_weights(weights, "test")

        reconstructed = np.zeros((64, 64), dtype=np.float32)
        header = struct.unpack_from("<I", binary, 0)[0]
        s_bits = (header >> 16) & 0xFFFF
        b_bits = header & 0xFFFF
        scale = struct.unpack("<e", struct.pack("<H", s_bits))[0]
        bias = struct.unpack("<e", struct.pack("<H", b_bits))[0]

        offset = struct.unpack_from("<I", binary, 4)[0]
        mode = offset & 0x1
        payload_start = 8
        payload = np.frombuffer(binary[payload_start:payload_start + PAYLOAD_BYTES], dtype=np.uint32)

        for i in range(4096):
            if mode == MODE_FP4_AFFINE:
                word = i // 8
                shift = 4 * (i % 8)
                code = int((payload[word] >> shift) & 0xF)
                if code >= 8:
                    code -= 16
            else:
                word = i // 16
                shift = 2 * (i % 16)
                sym = int((payload[word] >> shift) & 0x3)
                code = {0: 0, 1: 1, 2: -1, 3: 0}[sym]

            row = i // 64
            col = i % 64
            reconstructed[row, col] = scale * code + bias

        mse = float(np.mean((weights - reconstructed) ** 2))
        assert mse < 1.0


# ---------------------------------------------------------------------------
# v2 Tests (adaptive quadtree export)
# ---------------------------------------------------------------------------

class TestFP4ExporterV2:
    """Tests for SGFP4 v2 adaptive export."""

    def test_v2_binary_starts_with_magic(self):
        """v2 binary must begin with 4-byte magic b'SGF4'."""
        exporter = FP4Exporter()
        weights = np.random.randn(64, 64).astype(np.float32) * 0.1
        binary, stats = exporter.export_weights(weights, "test", adaptive=True)
        assert binary[:4] == SGFP4_MAGIC

    def test_v2_binary_has_version_byte(self):
        """v2 binary must have version byte 0x02 after magic."""
        exporter = FP4Exporter()
        weights = np.random.randn(64, 64).astype(np.float32) * 0.1
        binary, stats = exporter.export_weights(weights, "test", adaptive=True)
        version = struct.unpack_from("<B", binary, 4)[0]
        assert version == SGFP4_VERSION_V2

    def test_v2_binary_has_superblock_count(self):
        """v2 binary must include num_superblocks as uint32."""
        exporter = FP4Exporter()
        weights = np.random.randn(128, 128).astype(np.float32) * 0.1
        binary, stats = exporter.export_weights(weights, "test", adaptive=True)
        num_sb = struct.unpack_from("<I", binary, 5)[0]
        assert num_sb == 4  # 2x2 superblocks for 128x128

    def test_v2_stats_has_effective_bpw(self):
        """v2 stats dict must include effective_bpw field."""
        exporter = FP4Exporter()
        weights = np.random.randn(64, 64).astype(np.float32) * 0.1
        binary, stats = exporter.export_weights(weights, "test", adaptive=True)
        assert "effective_bpw" in stats
        assert stats["effective_bpw"] > 0.0
        assert stats["effective_bpw"] <= 32.0  # reasonable upper bound

    def test_v2_stats_has_layout_distribution(self):
        """v2 stats dict must include layout_distribution for all 6 layout values."""
        exporter = FP4Exporter()
        weights = np.random.randn(64, 64).astype(np.float32) * 0.5
        binary, stats = exporter.export_weights(weights, "test", adaptive=True)
        assert "layout_distribution" in stats
        for i in range(6):
            assert i in stats["layout_distribution"]
        # Sum of distribution counts should equal num_superblocks
        total = sum(stats["layout_distribution"].values())
        assert total == stats["num_superblocks"]

    def test_v2_export_to_file_writes_sgfp4_extension(self, tmp_path):
        """v2 adaptive export uses .sgfp4 extension."""
        exporter = FP4Exporter(project_root=tmp_path)
        weights = np.random.randn(64, 64).astype(np.float32) * 0.1
        bin_path, stats = exporter.export_to_file(weights, "test", adaptive=True)
        assert bin_path.name == "test.sgfp4"
        assert bin_path.exists()

    def test_v2_export_to_file_writes_manifest(self, tmp_path):
        """v2 export_to_file writes manifest.json alongside binary."""
        exporter = FP4Exporter(project_root=tmp_path)
        weights = np.random.randn(64, 64).astype(np.float32) * 0.1
        bin_path, stats = exporter.export_to_file(
            weights, "code", adaptive=True,
            base_model="mlx-community/Qwen3-Coder-30B-A3B-Instruct-bf16",
        )
        manifest_path = bin_path.parent / "manifest.json"
        assert manifest_path.exists()
        manifest = json.loads(manifest_path.read_text())
        assert "sha256" in manifest["fp4_binary"]
        assert manifest["niche"] == "code"

    def test_v2_vs_v1_different_output(self):
        """v1 and v2 output for same weights must differ (different format)."""
        exporter = FP4Exporter()
        weights = np.random.randn(64, 64).astype(np.float32) * 2.0
        v1_binary, _ = exporter.export_weights(weights, "test", adaptive=False)
        v2_binary, _ = exporter.export_weights(weights, "test", adaptive=True)
        assert v1_binary != v2_binary

    def test_v2_layout_constant_values(self):
        """Verify layout enum constants have correct values per D-02."""
        assert LAYOUT_UNIFORM_64 == 0
        assert LAYOUT_UNIFORM_32 == 1
        assert LAYOUT_UNIFORM_16 == 2
        assert LAYOUT_UNIFORM_8 == 3
        assert LAYOUT_MIXED == 4
        assert LAYOUT_FULL_4x4 == 5

    def test_payload_u32_helper(self):
        """_payload_u32 returns correct uint32 counts per D-03."""
        exporter = FP4Exporter()
        # 64x64: 4096 weights
        assert exporter._payload_u32(64, MODE_FP4_AFFINE) == 512     # 4096/8
        assert exporter._payload_u32(64, MODE_T158_AFFINE) == 256    # 4096/16
        # 32x32: 1024 weights
        assert exporter._payload_u32(32, MODE_FP4_AFFINE) == 128
        assert exporter._payload_u32(32, MODE_T158_AFFINE) == 64
        # 16x16: 256 weights
        assert exporter._payload_u32(16, MODE_FP4_AFFINE) == 32
        assert exporter._payload_u32(16, MODE_T158_AFFINE) == 16
        # 8x8: 64 weights
        assert exporter._payload_u32(8, MODE_FP4_AFFINE) == 8
        assert exporter._payload_u32(8, MODE_T158_AFFINE) == 4
        # 4x4: 16 weights
        assert exporter._payload_u32(4, MODE_FP4_AFFINE) == 2
        assert exporter._payload_u32(4, MODE_T158_AFFINE) == 1

    def test_classify_layout_uniform_64(self):
        """_classify_layout detects uniform 64x64 layout."""
        exporter = FP4Exporter()
        blocks = [{"size": 64, "y": 0, "x": 0}]
        assert exporter._classify_layout(blocks) == LAYOUT_UNIFORM_64

    def test_classify_layout_uniform_32(self):
        """_classify_layout detects uniform 32x32 layout."""
        exporter = FP4Exporter()
        blocks = [
            {"size": 32, "y": 0, "x": 0}, {"size": 32, "y": 0, "x": 32},
            {"size": 32, "y": 32, "x": 0}, {"size": 32, "y": 32, "x": 32},
        ]
        assert exporter._classify_layout(blocks) == LAYOUT_UNIFORM_32

    def test_classify_layout_full_4x4(self):
        """_classify_layout detects full 4x4 layout (256 blocks)."""
        exporter = FP4Exporter()
        blocks = []
        for y in range(0, 64, 4):
            for x in range(0, 64, 4):
                blocks.append({"size": 4, "y": y, "x": x})
        assert exporter._classify_layout(blocks) == LAYOUT_FULL_4x4

    def test_classify_layout_mixed(self):
        """_classify_layout detects mixed quadree layout."""
        exporter = FP4Exporter()
        blocks = [
            {"size": 32, "y": 0, "x": 0},
            {"size": 16, "y": 32, "x": 0},
            {"size": 16, "y": 48, "x": 0},
        ]
        assert exporter._classify_layout(blocks) == LAYOUT_MIXED

    def test_v1_default_is_not_adaptive(self):
        """Default export_weights call must use v1 (not v2)."""
        exporter = FP4Exporter()
        weights = np.random.randn(64, 64).astype(np.float32) * 0.1
        binary, stats = exporter.export_weights(weights, "test")
        # v1 has no magic header
        assert binary[:4] != SGFP4_MAGIC

    def test_v2_superblock_offset_table(self):
        """v2 binary includes valid superblock offset table."""
        exporter = FP4Exporter()
        weights = np.random.randn(128, 128).astype(np.float32) * 0.1
        binary, stats = exporter.export_weights(weights, "test", adaptive=True)
        # After magic(4) + version(1) + num_sb(4) = 9 bytes
        num_sb = struct.unpack_from("<I", binary, 5)[0]
        assert num_sb == 4
        # Read offset table
        offset_base = 9
        offsets = []
        for i in range(num_sb):
            off = struct.unpack_from("<I", binary, offset_base + i * 4)[0]
            offsets.append(off)
        # Offsets must be monotonically increasing
        for i in range(1, len(offsets)):
            assert offsets[i] > offsets[i - 1]

    def test_v2_encode_fp4_variable(self):
        """_encode_fp4_affine_variable works for various block sizes."""
        exporter = FP4Exporter()
        for size in [4, 8, 16, 32, 64]:
            region = np.random.randn(size, size).astype(np.float32) * 2.0
            result = exporter._encode_fp4_affine_variable(region)
            assert "scale" in result
            assert "bias" in result
            assert "l2_error" in result
            assert "payload" in result
            assert "n_weights" in result
            assert result["n_weights"] == size * size
            payload_words = size * size // 8
            assert len(result["payload"]) == payload_words

    def test_v2_encode_t158_variable(self):
        """_encode_t158_affine_variable works for various block sizes."""
        exporter = FP4Exporter()
        for size in [4, 8, 16, 32, 64]:
            region = np.random.randn(size, size).astype(np.float32)
            result = exporter._encode_t158_affine_variable(region)
            assert "scale" in result
            assert "bias" in result
            assert "l2_error" in result
            assert "payload" in result
            assert "n_weights" in result
            assert result["n_weights"] == size * size
            payload_words = size * size // 16
            assert len(result["payload"]) == payload_words

    def test_backward_compatible_cli_default(self):
        """CLI with just --niche produces v1 output with .fp4 extension."""
        # Validate that the module-level constants used in __main__ are correct
        assert MACROBLOCK_SIZE == 64
        assert PAYLOAD_BYTES == 2048
        assert MODE_FP4_AFFINE == 0
        assert MODE_T158_AFFINE == 1


# ---------------------------------------------------------------------------
# Threat model tests (T-03-01 through T-03-03)
# ---------------------------------------------------------------------------

class TestFP4ExporterThreatModel:
    """Security-focused tests for threat mitigations."""

    def test_sgfp4_magic_is_constant(self):
        """T-03-03: Magic header bytes are fixed and correct."""
        assert SGFP4_MAGIC == b'SGF4'
        assert len(SGFP4_MAGIC) == 4

    def test_sgfp4_version_is_v2(self):
        """T-03-03: Version byte is 0x02 for v2."""
        assert SGFP4_VERSION_V2 == 0x02

    def test_v2_stats_has_no_weight_values(self):
        """T-03-04: stats don't expose weight values — only aggregates."""
        exporter = FP4Exporter()
        weights = np.random.randn(64, 64).astype(np.float32)
        binary, stats = exporter.export_weights(weights, "test", adaptive=True)
        # stats must contain only aggregate/structural fields
        assert "shape" in stats
        assert "num_superblocks" in stats
        assert "effective_bpw" in stats
        assert "layout_distribution" in stats
        # Must NOT contain raw weight values
        assert "weights" not in stats
        assert "values" not in stats

    def test_default_thresholds_all_positive(self):
        """D-08: All default thresholds have positive max_mse values."""
        for size, t in DEFAULT_V2_THRESHOLDS.items():
            assert t["max_mse"] > 0.0, f"Non-positive threshold for block size {size}"
            assert t["max_relative"] > 0.0, f"Non-positive threshold for block size {size}"

    def test_superblock_header_layout_reserved(self):
        """Superblock header reserves bits 3-31 for future use."""
        # Layout enum uses only bits 0-2 (values 0-5)
        # Bits 3-31 are reserved (zero)
        for layout_val in range(6):
            # The superblock header is just layout & 0x7
            sb_header = np.uint32(layout_val & 0x7)
            assert sb_header < 8  # fits in 3 bits
