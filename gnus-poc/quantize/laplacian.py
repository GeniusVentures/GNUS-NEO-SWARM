"""Encode-side Laplacian-pyramid error analysis for SGFP4 quantization.

The pyramid is an encoder policy only. It affects block and mode selection but
is not serialized into v2 leaf flags and adds no runtime decode work.

The number of levels adapts to leaf size:

* 4x4 and 8x8: plain MSE
* 16x16: one level
* 32x32: two levels
* 64x64: three levels
"""

import numpy as np
from scipy.ndimage import gaussian_filter


_BLOCK_SIZE_TO_LEVELS = {
    4: 0,
    8: 0,
    16: 1,
    32: 2,
    64: 3,
}


def pyramid_levels_for_size(block_size: int) -> int:
    """Return the configured encode-side pyramid depth for a leaf size."""
    return _BLOCK_SIZE_TO_LEVELS.get(block_size, 0)


class LaplacianWeightedError:
    """Compute encode-side Laplacian-pyramid reconstruction error."""

    def __init__(self, sigma: float = 2.0, mode: str = "reflect"):
        self._sigma = sigma
        self._mode = mode

    def compute(
        self,
        original_2d: np.ndarray,
        reconstructed_2d: np.ndarray,
        block_size: int,
    ) -> float:
        """Return weighted reconstruction MSE for the selected leaf size."""
        levels = pyramid_levels_for_size(block_size)
        residual = (original_2d - reconstructed_2d).astype(np.float32)

        if levels == 0:
            return float(np.mean(residual ** 2))

        smooth = residual.copy()
        total_error = 0.0
        weight_sum = 0.0

        for level in range(levels):
            sigma = self._sigma * (2.0 ** level)
            smooth_base = gaussian_filter(
                smooth,
                sigma=sigma,
                mode=self._mode,
            )
            band = smooth - smooth_base
            level_weight = 1.0 / (2.0 ** level)
            total_error += level_weight * float(np.mean(band ** 2))
            weight_sum += level_weight

            if level < levels - 1:
                smooth = smooth_base[::2, ::2]

        if weight_sum > 0.0:
            return total_error / weight_sum
        return float(np.mean(residual ** 2))
