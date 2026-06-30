"""Encode-side Laplacian pyramid error analysis for weight quantization.

Per D-07: Laplacian pyramid analysis is encode-side only -- NOT decoded at runtime.
Separates low-frequency structure from high-frequency residual error,
preventing outliers from dominating per-block scale and making T158 more
viable on residuals near zero.

Adapts pyramid levels to block size (per RESEARCH.md Pitfall 2):
- 4x4 and 8x8 blocks: skip Laplacian entirely, use plain L2 (MSE)
- 16x16 blocks: 1 level
- 32x32 blocks: 2 levels
- 64x64 blocks: 3 levels

Uses scipy.ndimage.gaussian_filter for Gaussian smoothing with
configurable sigma and mode parameters.
"""

import numpy as np
from scipy.ndimage import gaussian_filter


# Per RESEARCH.md Pitfall 2: block-size to Laplacian level mapping
_BLOCK_SIZE_TO_LEVELS = {
    4: 0,
    8: 0,
    16: 1,
    32: 2,
    64: 3,
}


class LaplacianWeightedError:
    """Compute Laplacian pyramid-weighted error for encode-side block selection.

    Constructor kwargs (documented per RESEARCH.md Pattern 2 for tunability):
        sigma: Base sigma for Gaussian smoothing per level. Actual sigma per
               level is sigma * 2**level. Default: 2.0.
        mode:   Boundary handling mode passed to scipy.ndimage.gaussian_filter.
                Default: 'reflect'.
    """

    def __init__(self, sigma: float = 2.0, mode: str = "reflect"):
        self._sigma = sigma
        self._mode = mode

    def compute(
        self,
        original_2d: np.ndarray,
        reconstructed_2d: np.ndarray,
        block_size: int,
    ) -> float:
        """Compute Laplacian-weighted MSE between original and reconstructed.

        Args:
            original_2d: 2D numpy array of original float32 weights.
            reconstructed_2d: 2D numpy array of quantized+dequantized weights.
            block_size: Edge size of the block (4, 8, 16, 32, or 64).

        Returns:
            float: Laplacian-weighted MSE. For blocks <= 8x8, returns plain
                   MSE (Laplacian skipped per Pitfall 2).
        """
        levels = _BLOCK_SIZE_TO_LEVELS.get(block_size, 0)

        residual = (original_2d - reconstructed_2d).astype(np.float32)

        if levels == 0:
            # Small blocks: skip Laplacian, use plain MSE
            return float(np.mean(residual ** 2))

        smooth = original_2d.copy().astype(np.float32)
        total_error = 0.0
        weight_sum = 0.0

        for level in range(levels):
            sigma = self._sigma * (2.0 ** level)
            smooth_base = gaussian_filter(smooth, sigma=sigma, mode=self._mode)

            # Weight error by level importance: lower levels get higher weight
            level_weight = 1.0 / (2.0 ** level)
            level_error = float(np.mean(residual ** 2))
            total_error += level_weight * level_error
            weight_sum += level_weight

            # Downsample for next level
            if level < levels - 1:
                smooth = smooth_base[::2, ::2]
                if residual.shape[0] > 2:
                    residual = residual[::2, ::2]

        if weight_sum > 0.0:
            return total_error / weight_sum

        # Fallback: plain MSE
        return float(np.mean(residual ** 2))
