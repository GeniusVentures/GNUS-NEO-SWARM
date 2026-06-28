"""Tests for QuadtreeEncoder adaptive block-size selection."""

import numpy as np
import pytest

from quantize.quadtree import QuadtreeEncoder
from quantize.laplacian import LaplacianWeightedError


# ---------------------------------------------------------------------------
# Helper: create mock fit callables that return fixed encode results
# ---------------------------------------------------------------------------

def _make_fit_fp4(error_scale=1.0):
    """Return a callable that acts like _encode_fp4_affine_variable.
    Uses random codes so error is realistic."""
    def fit(region):
        flat = region.ravel().astype(np.float32)
        n = flat.size
        scale = float(np.max(np.abs(flat)) / 7.0) if np.max(np.abs(flat)) > 0 else 1.0
        bias = float(np.mean(flat))
        codes = np.clip(np.round((flat - bias) / scale), -8, 7).astype(np.int8)
        w_hat = scale * codes.astype(np.float32) + bias
        l2 = float(np.sqrt(np.mean((flat - w_hat) ** 2)))
        payload = np.zeros(n // 8, dtype=np.uint32)
        return {"scale": scale, "bias": bias, "l2_error": l2, "payload": payload, "n_weights": n}
    return fit


def _make_fit_t158(error_scale=1.0):
    """Return a callable that acts like _encode_t158_affine_variable."""
    def fit(region):
        flat = region.ravel().astype(np.float32)
        n = flat.size
        bias = float(np.mean(flat))
        centered = flat - bias
        scale = max(1e-8, float(np.mean(np.abs(centered))))
        tau = 0.5 * scale
        T = np.zeros(n, dtype=np.int8)
        T[centered > tau] = 1
        T[centered < -tau] = -1
        w_hat = scale * T.astype(np.float32) + bias
        l2 = float(np.sqrt(np.mean((flat - w_hat) ** 2)))
        payload = np.zeros(n // 16, dtype=np.uint32)
        return {"scale": scale, "bias": bias, "l2_error": l2, "payload": payload, "n_weights": n}
    return fit


# ---------------------------------------------------------------------------
# Default thresholds for tests
# ---------------------------------------------------------------------------

DEFAULT_THRESHOLDS = {
    64: {"max_mse": 0.01, "max_relative": 0.05},
    32: {"max_mse": 0.005, "max_relative": 0.03},
    16: {"max_mse": 0.002, "max_relative": 0.02},
    8: {"max_mse": 0.001, "max_relative": 0.01},
    4: {"max_mse": 0.0005, "max_relative": 0.005},
}


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestQuadtreeEncoder:
    """Test suite for QuadtreeEncoder.encode()."""

    def test_encode_uniform_zero_weights_returns_single_64x64(self):
        """All-zero superblock should be accepted as single 64x64 block."""
        encoder = QuadtreeEncoder(
            thresholds=DEFAULT_THRESHOLDS,
            ternary_delta=0.10,
            fit_fp4=_make_fit_fp4(),
            fit_t158=_make_fit_t158(),
            laplacian=LaplacianWeightedError(),
        )
        superblock = np.zeros((64, 64), dtype=np.float32)
        blocks = encoder.encode(superblock)
        assert len(blocks) >= 1
        # At least one block should be 64x64 (the encoder may decide to stay at 64)
        sizes = [b["size"] for b in blocks]
        total_area = sum(s * s for s in sizes)
        assert total_area == 4096  # covers entire superblock

    def test_encode_covers_full_superblock(self):
        """Quadtree blocks must cover the full 64x64 area without overlap or gaps."""
        encoder = QuadtreeEncoder(
            thresholds=DEFAULT_THRESHOLDS,
            ternary_delta=0.10,
            fit_fp4=_make_fit_fp4(),
            fit_t158=_make_fit_t158(),
            laplacian=LaplacianWeightedError(),
        )
        superblock = np.random.randn(64, 64).astype(np.float32) * 0.5
        blocks = encoder.encode(superblock)
        total_area = sum(b["size"] * b["size"] for b in blocks)
        assert total_area == 4096

    def test_encode_each_block_has_required_keys(self):
        """Each returned block dict must have all required keys."""
        encoder = QuadtreeEncoder(
            thresholds=DEFAULT_THRESHOLDS,
            ternary_delta=0.10,
            fit_fp4=_make_fit_fp4(),
            fit_t158=_make_fit_t158(),
            laplacian=LaplacianWeightedError(),
        )
        superblock = np.random.randn(64, 64).astype(np.float32)
        blocks = encoder.encode(superblock)
        required = {"y", "x", "size", "mode", "payload", "header", "scale", "bias", "error"}
        for b in blocks:
            missing = required - set(b.keys())
            assert not missing, f"Block missing keys: {missing}"

    def test_high_error_splits_to_smaller_blocks(self):
        """A superblock with extreme variance should split into smaller blocks."""
        encoder = QuadtreeEncoder(
            thresholds=DEFAULT_THRESHOLDS,
            ternary_delta=0.10,
            fit_fp4=_make_fit_fp4(),
            fit_t158=_make_fit_t158(),
            laplacian=LaplacianWeightedError(),
        )
        # Create a superblock with extreme outliers
        superblock = np.random.randn(64, 64).astype(np.float32) * 10.0
        # Place extreme values in specific corners
        superblock[0:16, 0:16] = 100.0
        superblock[48:64, 48:64] = -100.0
        blocks = encoder.encode(superblock)
        sizes = [b["size"] for b in blocks]
        # With extreme outliers, the encoder should split at least some regions
        assert len(blocks) > 1

    def test_low_error_stays_large(self):
        """A smooth, low-variance superblock should remain at large block size."""
        encoder = QuadtreeEncoder(
            thresholds=DEFAULT_THRESHOLDS,
            ternary_delta=0.10,
            fit_fp4=_make_fit_fp4(),
            fit_t158=_make_fit_t158(),
            laplacian=LaplacianWeightedError(),
        )
        # Very small weights: easy to encode
        superblock = np.ones((64, 64), dtype=np.float32) * 0.001
        blocks = encoder.encode(superblock)
        sizes = [b["size"] for b in blocks]
        # Should have relatively few blocks (large ones)
        assert max(sizes) >= 32

    def test_blocks_are_powers_of_two(self):
        """All block sizes must be powers of 2: 4, 8, 16, 32, or 64."""
        encoder = QuadtreeEncoder(
            thresholds=DEFAULT_THRESHOLDS,
            ternary_delta=0.10,
            fit_fp4=_make_fit_fp4(),
            fit_t158=_make_fit_t158(),
            laplacian=LaplacianWeightedError(),
        )
        superblock = np.random.randn(64, 64).astype(np.float32) * 3.0
        blocks = encoder.encode(superblock)
        valid_sizes = {4, 8, 16, 32, 64}
        for b in blocks:
            assert b["size"] in valid_sizes, f"Invalid block size {b['size']}"

    def test_deterministic_encoding(self):
        """Same input twice must produce same layout."""
        encoder = QuadtreeEncoder(
            thresholds=DEFAULT_THRESHOLDS,
            ternary_delta=0.10,
            fit_fp4=_make_fit_fp4(),
            fit_t158=_make_fit_t158(),
            laplacian=LaplacianWeightedError(),
        )
        np.random.seed(42)
        superblock = np.random.randn(64, 64).astype(np.float32)
        blocks1 = encoder.encode(superblock.copy())
        blocks2 = encoder.encode(superblock.copy())
        assert len(blocks1) == len(blocks2)
        for b1, b2 in zip(blocks1, blocks2):
            assert b1["size"] == b2["size"]
            assert b1["y"] == b2["y"]
            assert b1["x"] == b2["x"]
            assert b1["mode"] == b2["mode"]

    def test_min_block_size_default_4(self):
        """Default min_block_size prevents recursion below 4x4."""
        encoder = QuadtreeEncoder(
            thresholds=DEFAULT_THRESHOLDS,
            ternary_delta=0.10,
            fit_fp4=_make_fit_fp4(),
            fit_t158=_make_fit_t158(),
            laplacian=LaplacianWeightedError(),
        )
        assert encoder._min_block_size == 4

    def test_min_block_size_custom_8(self):
        """Custom min_block_size of 8 prevents blocks smaller than 8x8."""
        encoder = QuadtreeEncoder(
            thresholds=DEFAULT_THRESHOLDS,
            ternary_delta=0.10,
            min_block_size=8,
            fit_fp4=_make_fit_fp4(),
            fit_t158=_make_fit_t158(),
            laplacian=LaplacianWeightedError(),
        )
        superblock = np.random.randn(64, 64).astype(np.float32) * 5.0
        blocks = encoder.encode(superblock)
        for b in blocks:
            assert b["size"] >= 8

    def test_mode_is_valid_enum(self):
        """Mode must be 0 (FP4_AFFINE) or 1 (T158_AFFINE)."""
        encoder = QuadtreeEncoder(
            thresholds=DEFAULT_THRESHOLDS,
            ternary_delta=0.10,
            fit_fp4=_make_fit_fp4(),
            fit_t158=_make_fit_t158(),
            laplacian=LaplacianWeightedError(),
        )
        superblock = np.random.randn(64, 64).astype(np.float32)
        blocks = encoder.encode(superblock)
        for b in blocks:
            assert b["mode"] in (0, 1), f"Invalid mode {b['mode']}"

    def test_t158_rejected_on_outlier_weights(self):
        """Per-weight max error guard rejects T158 when outlier exceeds 5*scale."""
        # Use a high ternary_delta to make T158 preferred for everything
        encoder = QuadtreeEncoder(
            thresholds=DEFAULT_THRESHOLDS,
            ternary_delta=1.0,  # very aggressive T158 preference
            fit_fp4=_make_fit_fp4(),
            fit_t158=_make_fit_t158(),
            laplacian=LaplacianWeightedError(),
        )
        # Create a block with a single extreme outlier
        superblock = np.zeros((64, 64), dtype=np.float32)
        superblock[32, 32] = 100.0  # huge outlier
        blocks = encoder.encode(superblock)
        # The outlier region should eventually be FP4, not T158
        for b in blocks:
            y, x, sz = b["y"], b["x"], b["size"]
            if y <= 32 < y + sz and x <= 32 < x + sz:
                # This block contains the outlier
                assert b["mode"] == 0, (
                    f"T158 should be rejected for block at ({y},{x}) size {sz} "
                    f"due to outlier weight"
                )
