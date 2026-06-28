"""Quadtree adaptive block-size encoder for SGFP4 v2.

Per D-01: Full quadtree implementation. Encode tries largest block first
(64x64), measures Laplacian-weighted error, splits into 4 children if error
exceeds configurable threshold, recurses down to min_block_size (default 4x4).

The encoder is designed to be consumed by FP4Exporter. It accepts callable
hooks for FP4_AFFINE and T158_AFFINE fitting, keeping the quadtree logic
independent of the specific encode implementation.

Dual-mode selection per D-04: prefer T158 when t158_error <= (1.0 + delta) * fp4_error.
Per-weight max error guard per RESEARCH.md Pitfall 4: if any individual weight
reconstruction error exceeds 5 * scale, reject T158 and force FP4_AFFINE.

Hysteresis per RESEARCH.md Pitfall 1: if parent block was accepted, require child
error to be <= threshold * 0.8 (20% improvement) before splitting. Allow 10% slack
(accept if error <= threshold * 1.1) when min_block_size not yet reached.

Max recursion depth = 4 levels (64->32->16->8->4). Raises ValueError if exceeded.
"""

from typing import Callable, Dict, List

import numpy as np


# Maximum recursion depth (64 -> 32 -> 16 -> 8 -> 4)
_kMaxRecursionDepth = 4

# Per RESEARCH.md Pitfall 4: per-weight max error guard for T158
_kT158MaxPerWeightErrorScale = 5.0

# Hysteresis constants per RESEARCH.md Pitfall 1
_kHysteresisImprovement = 0.8   # 20% improvement required for child split
_kHysteresisSlack = 1.1         # 10% slack before forcing split


class QuadtreeEncoder:
    """Encode a 64x64 superblock into variable-sized blocks using quadtree recursion.

    Constructor args:
        thresholds: Dict mapping block_size (int) -> {"max_mse": float, "max_relative": float}.
                    Thresholds per block size for split decisions.
        ternary_delta: D-04 delta value for T158 preference:
                       prefer T158 when t158_err <= (1.0 + delta) * fp4_err.
        min_block_size: Minimum block edge size. Must be in {4, 8, 16, 32, 64}.
                        Default: 4.
        fit_fp4: Callable(region: np.ndarray) -> dict.
                 Must return {scale, bias, l2_error, payload, n_weights}.
        fit_t158: Callable(region: np.ndarray) -> dict.
                  Must return {scale, bias, l2_error, payload, n_weights}.
        laplacian: LaplacianWeightedError instance for error computation.
    """

    def __init__(
        self,
        thresholds: Dict[int, Dict[str, float]],
        ternary_delta: float,
        fit_fp4: Callable,
        fit_t158: Callable,
        laplacian,
        min_block_size: int = 4,
    ):
        self._thresholds = thresholds
        self._ternary_delta = ternary_delta
        self._fit_fp4 = fit_fp4
        self._fit_t158 = fit_t158
        self._laplacian = laplacian
        self._min_block_size = min_block_size

    def encode(self, superblock_64x64: np.ndarray) -> List[dict]:
        """Encode a 64x64 superblock into a list of block dicts.

        Each dict contains: {y, x, size, mode, payload, header, scale, bias, error}.

        Args:
            superblock_64x64: 2D numpy array of shape (64, 64), float32.

        Returns:
            List of dict, one per leaf block. Blocks cover the full 64x64 area
            without overlap or gaps.
        """
        # T-03-01: Validate tensor dimensions
        if superblock_64x64.shape != (64, 64):
            raise ValueError(
                f"superblock must be 64x64, got {superblock_64x64.shape}"
            )
        if not np.isfinite(superblock_64x64).all():
            raise ValueError("superblock contains NaN or Inf values")

        return self._try_block(superblock_64x64, 0, 0, 64, parent_accepted=False)

    def _try_block(
        self,
        superblock: np.ndarray,
        y: int,
        x: int,
        size: int,
        parent_accepted: bool,
        depth: int = 0,
    ) -> List[dict]:
        """Recursive quadtree encode. Returns list of block dicts.

        Args:
            superblock: The full 64x64 superblock array.
            y: Top-left row of this block.
            x: Top-left column of this block.
            size: Edge size of this block (power of 2).
            parent_accepted: Whether the parent block was accepted
                             (used for hysteresis).
            depth: Current recursion depth.

        Returns:
            List of dict, one per leaf block.
        """
        # T-03-01: enforce max recursion depth
        if depth > _kMaxRecursionDepth:
            raise ValueError(
                f"Max recursion depth {_kMaxRecursionDepth} exceeded at "
                f"block ({y}, {x}) size {size}. This should never happen "
                f"with min_block_size={self._min_block_size}."
            )

        region = superblock[y:y + size, x:x + size]
        threshold = self._thresholds.get(
            size, self._thresholds.get(self._min_block_size, {"max_mse": 0.0005})
        )

        # Fit both modes
        fp4_result = self._fit_fp4(region)
        t158_result = self._fit_t158(region)

        # Compute Laplacian-weighted error for both modes
        fp4_reconstructed = self._reconstruct(region, fp4_result)
        t158_reconstructed = self._reconstruct(region, t158_result)

        fp4_error = self._laplacian.compute(region, fp4_reconstructed, block_size=size)
        t158_error = self._laplacian.compute(region, t158_reconstructed, block_size=size)

        # D-04: dual-mode selection
        t158_preferred = t158_error <= (1.0 + self._ternary_delta) * fp4_error

        if t158_preferred:
            # Per RESEARCH.md Pitfall 4: per-weight max error guard
            if self._t158_has_outlier(region, t158_result):
                t158_preferred = False

        if t158_preferred:
            selected = t158_result
            selected_error = t158_error
            mode = 1  # MODE_T158_AFFINE
        else:
            selected = fp4_result
            selected_error = fp4_error
            mode = 0  # MODE_FP4_AFFINE

        max_mse = threshold.get("max_mse", 0.0005)

        # Apply hysteresis
        effective_threshold = max_mse
        if parent_accepted:
            effective_threshold = max_mse * _kHysteresisImprovement

        # Accept block if error within threshold or at minimum block size
        accept = selected_error <= effective_threshold

        if not accept and size > self._min_block_size:
            # Check hysteresis slack: accept if within 10% of threshold
            if selected_error <= max_mse * _kHysteresisSlack:
                accept = True

        if size <= self._min_block_size:
            accept = True

        if accept:
            # Compute header: packed half2 (scale << 16 | bias)
            # The header packing is done by the exporter; store raw values here
            scale = float(np.clip(selected["scale"], -65504, 65504))
            bias = float(np.clip(selected["bias"], -65504, 65504))
            return [{
                "y": y,
                "x": x,
                "size": size,
                "mode": mode,
                "payload": selected["payload"],
                "header": 0,  # Packed by exporter later
                "scale": scale,
                "bias": bias,
                "error": selected_error,
            }]

        # Split into 4 children
        half = size // 2
        results = []
        for dy in (0, half):
            for dx in (0, half):
                results.extend(
                    self._try_block(
                        superblock,
                        y + dy,
                        x + dx,
                        half,
                        parent_accepted=accept,
                        depth=depth + 1,
                    )
                )
        return results

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _reconstruct(region: np.ndarray, result: dict) -> np.ndarray:
        """Reconstruct a region from encode result for error computation."""
        flat = region.ravel().astype(np.float32)
        n = flat.size
        scale = result["scale"]
        bias = result["bias"]
        # Reconstruct using same method as encode
        codes = np.clip(np.round((flat - bias) / scale), -8, 7).astype(np.int8)
        return (scale * codes.astype(np.float32) + bias).reshape(region.shape)

    @staticmethod
    def _t158_has_outlier(region: np.ndarray, t158_result: dict) -> bool:
        """Check if any individual weight error exceeds kT158MaxPerWeightErrorScale * scale."""
        flat = region.ravel().astype(np.float32)
        scale = t158_result["scale"]
        bias = t158_result["bias"]
        centered = flat - bias
        tau = 0.5 * scale
        T = np.zeros(flat.size, dtype=np.int8)
        T[centered > tau] = 1
        T[centered < -tau] = -1
        w_hat = scale * T.astype(np.float32) + bias
        errors = np.abs(flat - w_hat)
        max_error = float(np.max(errors))
        return max_error > _kT158MaxPerWeightErrorScale * scale
