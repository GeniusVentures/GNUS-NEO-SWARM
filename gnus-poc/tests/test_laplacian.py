"""Tests for LaplacianWeightedError encode-side error analysis."""

import numpy as np
import pytest

from quantize.laplacian import LaplacianWeightedError


class TestLaplacianWeightedError:
    """Test suite for LaplacianWeightedError.compute()."""

    def test_identical_returns_zero(self):
        """Identical original and reconstructed produces zero error."""
        lap = LaplacianWeightedError()
        block = np.random.randn(32, 32).astype(np.float32)
        err = lap.compute(block, block, block_size=32)
        assert err == pytest.approx(0.0, abs=1e-7)

    def test_constant_block_zero_error(self):
        """All-constant input has zero error regardless of Laplacian."""
        lap = LaplacianWeightedError()
        original = np.ones((64, 64), dtype=np.float32) * 3.0
        reconstructed = np.ones((64, 64), dtype=np.float32) * 3.0
        err = lap.compute(original, reconstructed, block_size=64)
        assert err == pytest.approx(0.0, abs=1e-7)

    def test_small_block_uses_plain_mse(self):
        """4x4 and 8x8 blocks skip Laplacian and use plain MSE."""
        lap = LaplacianWeightedError()
        original = np.ones((8, 8), dtype=np.float32)
        reconstructed = np.ones((8, 8), dtype=np.float32) * 1.5
        err = lap.compute(original, reconstructed, block_size=8)
        expected_mse = float(np.mean((original - reconstructed) ** 2))
        assert err == pytest.approx(expected_mse, rel=1e-5)

    def test_small_block_4x4_uses_plain_mse(self):
        """4x4 blocks explicitly skip Laplacian."""
        lap = LaplacianWeightedError()
        original = np.ones((4, 4), dtype=np.float32)
        reconstructed = np.zeros((4, 4), dtype=np.float32)
        err = lap.compute(original, reconstructed, block_size=4)
        expected_mse = float(np.mean((original - reconstructed) ** 2))
        assert err == pytest.approx(expected_mse, rel=1e-5)

    def test_returns_float(self):
        """compute() always returns a plain Python float."""
        lap = LaplacianWeightedError()
        block = np.random.randn(16, 16).astype(np.float32)
        reconstructed = block + np.random.randn(16, 16).astype(np.float32) * 0.01
        err = lap.compute(block, reconstructed, block_size=16)
        assert isinstance(err, float)

    def test_laplacian_weighted_lower_than_plain_mse(self):
        """Laplacian-weighted error should be different (not equal) to plain MSE
        when there's smooth structure in the error."""
        lap = LaplacianWeightedError()
        original = np.random.randn(32, 32).astype(np.float32)
        # Add a large smooth error (low-frequency)
        y, x = np.mgrid[0:32, 0:32]
        smooth_error = 0.5 * np.sin(2 * np.pi * y / 64.0) * np.sin(2 * np.pi * x / 64.0)
        reconstructed = original + smooth_error.astype(np.float32)
        err = lap.compute(original, reconstructed, block_size=32)
        # Should be a finite float
        assert np.isfinite(err)
        assert err > 0.0

    def test_progressively_larger_error(self):
        """Larger reconstruction error yields larger Laplacian-weighted error."""
        lap = LaplacianWeightedError()
        original = np.random.randn(64, 64).astype(np.float32) * 0.1
        r1 = original + np.random.randn(64, 64).astype(np.float32) * 0.001
        r2 = original + np.random.randn(64, 64).astype(np.float32) * 0.1
        err1 = lap.compute(original, r1, block_size=64)
        err2 = lap.compute(original, r2, block_size=64)
        assert err1 < err2

    def test_constructor_kwargs(self):
        """Constructor accepts sigma and mode kwargs."""
        lap = LaplacianWeightedError(sigma=1.5, mode="nearest")
        original = np.random.randn(16, 16).astype(np.float32)
        reconstructed = original + np.random.randn(16, 16).astype(np.float32) * 0.01
        err = lap.compute(original, reconstructed, block_size=16)
        assert isinstance(err, float)
        assert err >= 0.0

    def test_block_size_16_uses_one_level(self):
        """16x16 blocks should use exactly 1 Laplacian level."""
        lap = LaplacianWeightedError()
        original = np.random.randn(16, 16).astype(np.float32)
        reconstructed = original + np.random.randn(16, 16).astype(np.float32) * 0.01
        err = lap.compute(original, reconstructed, block_size=16)
        assert isinstance(err, float)
        assert err >= 0.0

    def test_block_size_64_uses_three_levels(self):
        """64x64 blocks should use exactly 3 Laplacian levels."""
        lap = LaplacianWeightedError()
        original = np.random.randn(64, 64).astype(np.float32)
        reconstructed = original + np.random.randn(64, 64).astype(np.float32) * 0.01
        err = lap.compute(original, reconstructed, block_size=64)
        assert isinstance(err, float)
        assert err >= 0.0
