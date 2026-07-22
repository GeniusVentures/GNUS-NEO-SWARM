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

Spec conformance: the residual pyramid is a true Laplacian pyramid -- each
level is Gaussian-filtered BEFORE decimation (anti-aliasing), and each
level's error is measured on the Laplacian band (smooth - smooth_base),
not on the raw residual reused at every level.
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


def pyramid_levels_for_size(block_size: int) -> int:
    """Return the number of Laplacian pyramid levels used for a block size.

    0 means the block's error was computed with plain L2 (MSE); >0 means
    the Laplacian pyramid selected the block. Used for the SGFP4 v2 leaf
    ERROR_HINT flag (paper: 0 = L2-selected, 1 = Pyramid-selected).
    """
    return _BLOCK_SIZE_TO_LEVELS.get(block_size, 0)


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

        smooth = residual.copy()
        total_error = 0.0
        weight_sum = 0.0

        for level in range(levels):
            sigma = self._sigma * (2.0 ** level)
            # Gaussian pre-filter before decimation (anti-aliasing) -- without
            # this the pyramid aliases and is not a true Laplacian pyramid.
            smooth_base = gaussian_filter(smooth, sigma=sigma, mode=self._mode)

            # Laplacian band for this level: high-frequency detail removed by
            # the Gaussian. Band MSE measures the error energy at this scale.
            band = smooth - smooth_base

            # Weight error by level importance: lower levels get higher weight
            level_weight = 1.0 / (2.0 ** level)
            level_error = float(np.mean(band ** 2))
            total_error += level_weight * level_error
            weight_sum += level_weight

            # Decimate the filtered base for the next level
            if level < levels - 1:
                smooth = smooth_base[::2, ::2]

        if weight_sum > 0.0:
            return total_error / weight_sum

        # Fallback: plain MSE
        return float(np.mean(residual ** 2))
