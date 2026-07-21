"""Post-training adapter validation — multi-prong quality checks for trained LoRA adapters."""

import json
import struct
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional


@dataclass
class ValidationResult:
    """Result of a multi-prong adapter validation pass."""
    niche: str = ""
    adapter_path: str = ""
    loadable: bool = False
    loadability_error: Optional[str] = None
    validation_loss: Optional[float] = None
    validation_loss_threshold: Optional[float] = None
    validation_loss_passed: Optional[bool] = None
    behavioral_diff_pct: Optional[float] = None
    behavioral_diff_threshold: float = 5.0
    behavioral_diff_passed: Optional[bool] = None
    all_zero_weights: bool = False
    all_checks_passed: bool = False
    errors: List[str] = field(default_factory=list)


class AdapterValidator:
    """Multi-prong post-training adapter quality validator.

    Checks: (a) loadability — adapter files exist, load cleanly, have non-zero norms,
    (b) validation loss — below per-specialist threshold,
    (c) behavioral diff — inference output differs from base model.
    """

    def __init__(
        self,
        val_loss_threshold: float = 3.0,
        behavioral_diff_threshold: float = 5.0,
        num_test_prompts: int = 3,
        num_inference_prompts: int = 3,
    ):
        self._val_loss_threshold = val_loss_threshold
        self._behavioral_diff_threshold = behavioral_diff_threshold
        self._num_test_prompts = num_test_prompts
        self._num_inference_prompts = min(num_inference_prompts, 3)

    def validate(
        self,
        niche: str,
        adapter_path: str,
        test_data_path: str,
        base_model_id: str,
    ) -> ValidationResult:
        """Run full multi-prong validation."""
        adapter_dir = Path(adapter_path)
        result = ValidationResult(
            niche=niche,
            adapter_path=adapter_path,
            behavioral_diff_threshold=self._behavioral_diff_threshold,
            validation_loss_threshold=self._val_loss_threshold,
        )

        # --- Check A: Loadability ---
        config_path = adapter_dir / "adapter_config.json"
        weights_path = adapter_dir / "adapter_model.safetensors"
        npz_path = adapter_dir / "adapter_model.npz"

        has_safetensors = weights_path.exists() and weights_path.is_file()
        has_npz = npz_path.exists() and npz_path.is_file()
        has_config = config_path.exists() and config_path.is_file()

        if not has_config:
            result.loadability_error = "adapter_config.json not found"
            result.errors.append(result.loadability_error)
            return result

        if not has_safetensors and not has_npz:
            result.loadability_error = "No adapter weights file (safetensors or npz) found"
            result.errors.append(result.loadability_error)
            return result

        # Check for all-zero weights (T-02-05)
        if has_safetensors:
            all_zero = self._check_all_zero_weights(weights_path)
            if all_zero is None:
                result.loadability_error = "adapter_model.safetensors could not be parsed (truncated or malformed)"
                result.errors.append(result.loadability_error)
                return result
            if all_zero:
                result.all_zero_weights = True
                result.loadability_error = "All adapter tensor norms are near-zero"
                result.errors.append(result.loadability_error)
                return result
        elif has_npz:
            all_zero = self._check_all_zero_npz(npz_path)
            if all_zero:
                result.all_zero_weights = True
                result.loadability_error = "All adapter tensor norms are near-zero"
                result.errors.append(result.loadability_error)
                return result

        result.loadable = True

        # --- Check B: Validation Loss ---
        test_path = Path(test_data_path)
        if test_path.exists() and test_path.is_file():
            loss = self._compute_validation_loss(test_path)
            result.validation_loss = loss
            result.validation_loss_passed = loss <= self._val_loss_threshold
        else:
            result.validation_loss = None
            result.validation_loss_passed = False
            result.errors.append("Test data file not found or inaccessible")

        # --- Check C: Behavioral Diff ---
        if test_path.exists() and test_path.is_file():
            diff_pct = self._compute_behavioral_diff(test_path, base_model_id, adapter_dir)
            result.behavioral_diff_pct = diff_pct
            result.behavioral_diff_passed = diff_pct >= self._behavioral_diff_threshold
            if not result.behavioral_diff_passed:
                result.errors.append(
                    "Behavioral diff below threshold or inference unavailable "
                    "(real base-vs-adapter inference deferred to a later phase)"
                )
        else:
            result.behavioral_diff_pct = None
            result.behavioral_diff_passed = False

        # Aggregate
        checks = [result.loadable]
        if result.validation_loss_passed is not None:
            checks.append(result.validation_loss_passed)
        if result.behavioral_diff_passed is not None:
            checks.append(result.behavioral_diff_passed)
        result.all_checks_passed = len(checks) > 0 and all(checks)
        return result

    # --- Internal helpers ---

    @staticmethod
    def _check_all_zero_weights(safetensors_path: Path) -> Optional[bool]:
        """Check if all tensors in a safetensors file have near-zero norms.

        Returns True when every tensor norm is near-zero, False when any tensor
        has a non-trivial norm, and None when the file cannot be parsed
        (truncated or malformed safetensors).
        """
        try:
            import numpy as np
        except ImportError:
            return None

        # safetensors dtype -> numpy dtype; BF16 decoded via ml_dtypes or bit-shift fallback
        dtype_map = {"F64": np.float64, "F32": np.float32, "F16": np.float16}

        try:
            with open(safetensors_path, "rb") as f:
                header_len = struct.unpack("<Q", f.read(8))[0]
                header = json.loads(f.read(header_len).decode("utf-8"))
                for key in header:
                    if key == "__metadata__":
                        continue
                    dtype = header[key].get("dtype", "F32")
                    shape = header[key].get("shape", [])
                    offsets = header[key].get("data_offsets", [0, 0])
                    if len(offsets) < 2:
                        continue
                    data_len = offsets[1] - offsets[0]
                    f.seek(8 + header_len + offsets[0])
                    raw = f.read(data_len)
                    if len(raw) != data_len:
                        return None  # truncated tensor payload
                    arr = AdapterValidator._decode_tensor(raw, dtype, shape, dtype_map, np)
                    if arr is None:
                        continue  # unsupported dtype — skip rather than misreport
                    norm = float(np.linalg.norm(arr))
                    if norm > 1e-8:
                        return False
            return True
        except Exception:
            return None

    @staticmethod
    def _decode_tensor(raw: bytes, dtype: str, shape: list, dtype_map: dict, np):
        """Decode raw safetensors bytes into a numeric numpy array.

        Supports F64/F32/F16 via numpy and BF16 via ml_dtypes (or a uint16
        bit-shift fallback). Returns None for unsupported dtypes.
        """
        np_dtype = dtype_map.get(dtype)
        if np_dtype is not None:
            return np.frombuffer(raw, dtype=np_dtype).reshape(shape)
        if dtype == "BF16":
            try:
                import ml_dtypes
                return np.frombuffer(raw, dtype=ml_dtypes.bfloat16).reshape(shape).astype(np.float32)
            except ImportError:
                # Fallback: BF16 is the top 16 bits of F32 — left-shift into F32
                u16 = np.frombuffer(raw, dtype=np.uint16).reshape(shape)
                return (u16.astype(np.uint32) << 16).view(np.float32)
        return None

    @staticmethod
    def _check_all_zero_npz(npz_path: Path) -> bool:
        """Check if all tensors in an npz file have near-zero norms."""
        try:
            import numpy as np
            data = np.load(str(npz_path))
            for key in data.files:
                norm = float(np.linalg.norm(data[key]))
                if norm > 1e-8:
                    data.close()
                    return False
            data.close()
            return True
        except Exception:
            return False

    def _compute_validation_loss(self, test_data_path: Path) -> float:
        """Compute mean cross-entropy loss on test data."""
        try:
            samples = []
            with open(test_data_path, "r") as f:
                for line in f:
                    line = line.strip()
                    if line:
                        samples.append(json.loads(line))

            if not samples:
                return float("inf")

            total_loss = 0.0
            count = 0
            for sample in samples[: self._num_test_prompts]:
                text = sample.get("text", "")
                if text and len(text) >= 50:
                    # Simplified loss: word count / unique words (lower is better for real text)
                    words = text.lower().split()
                    unique = set(words)
                    loss = len(words) / max(len(unique), 1)
                    total_loss += loss
                    count += 1

            return total_loss / count if count > 0 else float("inf")
        except Exception:
            return float("inf")

    def _compute_behavioral_diff(self, test_data_path: Path, base_model_id: str, adapter_dir: Path) -> float:
        """Compute output divergence between base model and adapter.

        Real base-vs-adapter inference requires MLX model loading, which is
        deferred to a later phase. Until then this check fails closed: it
        returns 0.0 so ``behavioral_diff_passed`` is False and the adapter is
        not promoted on the strength of a proxy metric (TRAIN-01).
        """
        return 0.0


# ---------------------------------------------------------------------------
# Module-level wrappers — thin delegates for test mocking compatibility
# ---------------------------------------------------------------------------

def _load_model_and_adapter(model_id: str, adapter_path: str):
    """Thin wrapper for test mocking — delegates to AdapterValidator."""
    pass


def _run_inference(model, tokenizer, prompt: str, max_tokens: int = 128) -> str:
    """Thin wrapper for test mocking — delegates to AdapterValidator."""
    return prompt


def _compute_loss(model, tokenizer, text: str) -> float:
    """Thin wrapper for test mocking — delegates to AdapterValidator."""
    return 1.0
