"""Adaptive quadtree leaf selection for the SGFP4 v2 encoder.

The encoder tries the largest region first, compares FP4_AFFINE and
T158_AFFINE reconstruction error, and splits regions that fail the configured
absolute or relative error gates. Laplacian-pyramid weighting is encode-side
policy only. The returned ``error_hint`` field is an internal diagnostic and is
not serialized into the v2 leaf-header flags.
"""

from typing import Callable, Dict, List

import numpy as np

from quantize.sgfp4_format import CodeMode


_kMaxRecursionDepth = 4
_kT158MaxPerWeightErrorScale = 5.0
_kHysteresisImprovement = 0.8
_kHysteresisSlack = 1.1
_kRelativeEpsilon = 1e-12


class QuadtreeEncoder:
    """Encode one 64x64 macroblock into adaptive square leaves."""

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
        """Return a deterministic, complete leaf cover for a 64x64 macroblock."""
        if superblock_64x64.shape != (64, 64):
            raise ValueError(
                f"superblock must be 64x64, got {superblock_64x64.shape}"
            )
        if not np.isfinite(superblock_64x64).all():
            raise ValueError("superblock contains NaN or Inf values")
        if self._min_block_size not in (4, 8, 16, 32, 64):
            raise ValueError(
                "min_block_size must be one of 4, 8, 16, 32, or 64"
            )

        return self._try_block(
            superblock_64x64,
            0,
            0,
            64,
            parent_accepted=False,
        )

    def _try_block(
        self,
        superblock: np.ndarray,
        y: int,
        x: int,
        size: int,
        parent_accepted: bool,
        depth: int = 0,
    ) -> List[dict]:
        """Recursively accept or split one square region."""
        if depth > _kMaxRecursionDepth:
            raise ValueError(
                f"Max recursion depth {_kMaxRecursionDepth} exceeded at "
                f"block ({y}, {x}) size {size}. This should never happen "
                f"with min_block_size={self._min_block_size}."
            )

        region = superblock[y:y + size, x:x + size]
        threshold = self._thresholds.get(
            size,
            self._thresholds.get(
                self._min_block_size,
                {"max_mse": 0.0005},
            ),
        )

        fp4_result = self._fit_fp4(region)
        t158_result = self._fit_t158(region)

        fp4_reconstructed = self._reconstruct(
            region,
            fp4_result,
            mode=CodeMode.FP4_AFFINE,
        )
        t158_reconstructed = self._reconstruct(
            region,
            t158_result,
            mode=CodeMode.T158_AFFINE,
        )

        fp4_error = self._laplacian.compute(
            region,
            fp4_reconstructed,
            block_size=size,
        )
        t158_error = self._laplacian.compute(
            region,
            t158_reconstructed,
            block_size=size,
        )

        t158_preferred = (
            t158_error <= (1.0 + self._ternary_delta) * fp4_error
        )
        if t158_preferred and self._t158_has_outlier(region, t158_result):
            t158_preferred = False

        if t158_preferred:
            selected = t158_result
            selected_error = t158_error
            mode = CodeMode.T158_AFFINE
        else:
            selected = fp4_result
            selected_error = fp4_error
            mode = CodeMode.FP4_AFFINE

        max_mse = threshold.get("max_mse", 0.0005)
        max_relative = threshold.get("max_relative")
        gate_error = self._combined_gate_error(
            region,
            selected_error,
            max_mse,
            max_relative,
        )

        effective_threshold = max_mse
        if parent_accepted:
            effective_threshold *= _kHysteresisImprovement

        accept = gate_error <= effective_threshold
        if not accept and size > self._min_block_size:
            accept = gate_error <= max_mse * _kHysteresisSlack
        if size <= self._min_block_size:
            accept = True

        if accept:
            scale = float(np.clip(selected["scale"], -65504, 65504))
            bias = float(np.clip(selected["bias"], -65504, 65504))
            return [{
                "y": y,
                "x": x,
                "size": size,
                "mode": mode,
                "payload": selected["payload"],
                "header": 0,
                "scale": scale,
                "bias": bias,
                "error": selected_error,
                "error_hint": 1 if size >= 16 else 0,
            }]

        half = size // 2
        results: List[dict] = []
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

    @staticmethod
    def _combined_gate_error(
        region: np.ndarray,
        selected_error: float,
        max_mse: float,
        max_relative,
    ) -> float:
        """Apply both absolute and relative gates on one comparable scale."""
        if max_relative is None or max_relative <= 0.0:
            return selected_error

        signal_power = float(np.mean(region.astype(np.float64) ** 2))
        if signal_power <= _kRelativeEpsilon:
            return selected_error

        relative_equivalent = max_mse * (
            (selected_error / signal_power) / max_relative
        )
        return max(selected_error, relative_equivalent)

    @staticmethod
    def _reconstruct(
        region: np.ndarray,
        result: dict,
        mode: CodeMode = CodeMode.FP4_AFFINE,
    ) -> np.ndarray:
        """Reconstruct a candidate using its own normative codebook."""
        flat = region.ravel().astype(np.float32)
        scale = result["scale"]
        bias = result["bias"]

        if mode == CodeMode.T158_AFFINE:
            centered = flat - bias
            threshold = 0.5 * scale
            codes = np.zeros(flat.size, dtype=np.int8)
            codes[centered > threshold] = 1
            codes[centered < -threshold] = -1
        else:
            codes = np.clip(
                np.round((flat - bias) / scale),
                -8,
                7,
            ).astype(np.int8)

        return (
            scale * codes.astype(np.float32) + bias
        ).reshape(region.shape)

    @staticmethod
    def _t158_has_outlier(region: np.ndarray, t158_result: dict) -> bool:
        """Return true when ternary reconstruction violates the outlier veto."""
        flat = region.ravel().astype(np.float32)
        scale = t158_result["scale"]
        bias = t158_result["bias"]
        centered = flat - bias
        threshold = 0.5 * scale
        codes = np.zeros(flat.size, dtype=np.int8)
        codes[centered > threshold] = 1
        codes[centered < -threshold] = -1
        reconstructed = scale * codes.astype(np.float32) + bias
        maximum_error = float(np.max(np.abs(flat - reconstructed)))
        return maximum_error > _kT158MaxPerWeightErrorScale * scale
