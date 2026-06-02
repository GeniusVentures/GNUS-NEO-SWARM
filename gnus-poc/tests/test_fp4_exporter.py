"""Tests for FP4 Ultra exporter."""

import struct

import numpy as np

from quantize.fp4_exporter import (
    FP4Exporter,
    MACROBLOCK_SIZE,
    PAYLOAD_BYTES,
    PAYLOAD_U32,
    MODE_FP4_AFFINE,
    MODE_T158_AFFINE,
)


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
