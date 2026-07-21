"""Tests for AdapterValidator — multi-prong post-training adapter quality checks."""

import json
import os
from pathlib import Path
from unittest import mock

import pytest

from training.adapter_validator import AdapterValidator, ValidationResult


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _write_dummy_safetensors(path: Path, keys_and_shapes: dict):
    """
    Write a minimal valid .safetensors file with the given key->shape mapping.
    Each tensor is filled with ones so the file passes a non-zero norm check.
    """
    import struct

    import numpy as np

    metadata = {}
    data_chunks = []

    for key, shape in keys_and_shapes.items():
        arr = np.ones(shape, dtype=np.float32)
        arr_bytes = arr.tobytes()
        offset = sum(len(c) for c in data_chunks)
        metadata[key] = {"dtype": "F32", "shape": list(shape), "data_offsets": [offset, offset + len(arr_bytes)]}
        data_chunks.append(arr_bytes)

    header = json.dumps(metadata, separators=(",", ":"))
    header_bytes = header.encode("utf-8")
    header_len = struct.pack("<Q", len(header_bytes))

    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "wb") as f:
        f.write(header_len)
        f.write(header_bytes)
        for chunk in data_chunks:
            f.write(chunk)


def _write_all_zero_safetensors(path: Path, keys_and_shapes: dict):
    """
    Write a valid .safetensors file where all tensors are filled with zeros.
    Used to test inert-adapter detection (T-02-05).
    """
    import struct

    import numpy as np

    metadata = {}
    data_chunks = []

    for key, shape in keys_and_shapes.items():
        arr = np.zeros(shape, dtype=np.float32)
        arr_bytes = arr.tobytes()
        offset = sum(len(c) for c in data_chunks)
        metadata[key] = {"dtype": "F32", "shape": list(shape), "data_offsets": [offset, offset + len(arr_bytes)]}
        data_chunks.append(arr_bytes)

    header = json.dumps(metadata, separators=(",", ":"))
    header_bytes = header.encode("utf-8")
    header_len = struct.pack("<Q", len(header_bytes))

    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "wb") as f:
        f.write(header_len)
        f.write(header_bytes)
        for chunk in data_chunks:
            f.write(chunk)


def _write_bf16_safetensors(path: Path, keys_and_shapes: dict, fill: float):
    """
    Write a valid .safetensors file with BF16 tensors filled with `fill`.
    BF16 bytes are the top 16 bits of the F32 representation.
    """
    import struct

    import numpy as np

    metadata = {}
    data_chunks = []

    for key, shape in keys_and_shapes.items():
        arr = np.full(shape, fill, dtype=np.float32)
        bf16_bytes = (arr.view(np.uint32) >> 16).astype(np.uint16).tobytes()
        offset = sum(len(c) for c in data_chunks)
        metadata[key] = {"dtype": "BF16", "shape": list(shape), "data_offsets": [offset, offset + len(bf16_bytes)]}
        data_chunks.append(bf16_bytes)

    header = json.dumps(metadata, separators=(",", ":"))
    header_bytes = header.encode("utf-8")
    header_len = struct.pack("<Q", len(header_bytes))

    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "wb") as f:
        f.write(header_len)
        f.write(header_bytes)
        for chunk in data_chunks:
            f.write(chunk)


def _write_test_jsonl(path: Path, lines: list):
    """Write a list of {'text': ...} dicts to a JSONL file."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w") as f:
        for line in lines:
            f.write(json.dumps(line) + "\n")


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def valid_adapter_dir(tmp_path):
    """Create a temporary adapter directory with a valid safetensors file."""
    adapter_dir = tmp_path / "adapters" / "test_specialist"
    safetensors_path = adapter_dir / "adapter_model.safetensors"
    _write_dummy_safetensors(safetensors_path, {"lora_A.weight": (4, 64), "lora_B.weight": (64, 4)})
    (adapter_dir / "adapter_config.json").write_text(json.dumps({"model": "test-model"}))
    return str(adapter_dir)


@pytest.fixture
def inert_adapter_dir(tmp_path):
    """Create a temporary adapter directory with all-zero safetensors (inert adapter)."""
    adapter_dir = tmp_path / "adapters" / "inert_specialist"
    safetensors_path = adapter_dir / "adapter_model.safetensors"
    _write_all_zero_safetensors(safetensors_path, {"lora_A.weight": (4, 64), "lora_B.weight": (64, 4)})
    (adapter_dir / "adapter_config.json").write_text(json.dumps({"model": "test-model"}))
    return str(adapter_dir)


@pytest.fixture
def valid_test_data(tmp_path):
    """Create a temporary test JSONL file with 3 prompts (matching the plan's bounded inference design)."""
    test_dir = tmp_path / "test_data"
    test_file = test_dir / "test.jsonl"
    _write_test_jsonl(test_file, [
        {"text": "<|im_start|>system\nYou are a test specialist.<|im_end|>\n<|im_start|>user\nWhat is the capital of France?<|im_end|>\n<|im_start|>assistant\nParis<|im_end|>"},
        {"text": "<|im_start|>system\nYou are a test specialist.<|im_end|>\n<|im_start|>user\nExplain quantum computing.<|im_end|>\n<|im_start|>assistant\nQuantum computing uses qubits.<|im_end|>"},
        {"text": "<|im_start|>system\nYou are a test specialist.<|im_end|>\n<|im_start|>user\nWrite a hello world in Python.<|im_end|>\n<|im_start|>assistant\nprint('Hello, world!')<|im_end|>"},
    ])
    return str(test_file)


# ---------------------------------------------------------------------------
# Test 1: Valid adapter passes all checks (loadability + behavioral diff)
# ---------------------------------------------------------------------------

def test_valid_adapter_passes_all_checks(valid_adapter_dir, valid_test_data):
    """A valid adapter with non-zero weights should pass loadability and
    behavioral-diff checks (given mocked inference that produces different output)."""
    validator = AdapterValidator(
        behavioral_diff_threshold=5.0,
        val_loss_threshold=3.0,
    )

    # Mock model loading to avoid real MLX model download/inference.
    with mock.patch.object(AdapterValidator, "_compute_validation_loss") as mock_loss, \
         mock.patch.object(AdapterValidator, "_compute_behavioral_diff") as mock_diff:

        mock_loss.return_value = 2.1
        mock_diff.return_value = 10.0

        result = validator.validate(
            niche="test_specialist",
            adapter_path=valid_adapter_dir,
            test_data_path=valid_test_data,
            base_model_id="test-model",
        )

        assert result.loadable is True
        assert result.all_zero_weights is False
        assert result.validation_loss_passed is True
        assert result.behavioral_diff_passed is True
        assert result.all_checks_passed is True
        assert len(result.errors) == 0


# ---------------------------------------------------------------------------
# Test 2: All-zero weights detected as inert (T-02-05)
# ---------------------------------------------------------------------------

def test_all_zero_weights_detected_as_inert(inert_adapter_dir, valid_test_data):
    """An adapter whose safetensors contain only near-zero weights must be
    flagged as all_zero_weights=True and fail all_checks_passed."""
    validator = AdapterValidator()

    result = validator.validate(
        niche="inert_specialist",
        adapter_path=inert_adapter_dir,
        test_data_path=valid_test_data,
        base_model_id="test-model",
    )

    assert result.all_zero_weights is True
    assert result.loadable is False
    assert result.all_checks_passed is False
    assert any("zero" in e.lower() for e in result.errors)


# ---------------------------------------------------------------------------
# Test 3: Identical base/adapter output detected as inert (behavioral false positive)
# ---------------------------------------------------------------------------

def test_identical_output_detected_as_inert(valid_adapter_dir, valid_test_data):
    """When base model and adapter produce identical text for all 3 test prompts,
    the behavioral-diff check must fail (diff == 0%)."""
    validator = AdapterValidator(behavioral_diff_threshold=5.0)

    with mock.patch.object(AdapterValidator, "_compute_validation_loss") as mock_loss, \
         mock.patch.object(AdapterValidator, "_compute_behavioral_diff") as mock_diff:

        mock_loss.return_value = 2.0
        mock_diff.return_value = 0.0

        result = validator.validate(
            niche="test_specialist",
            adapter_path=valid_adapter_dir,
            test_data_path=valid_test_data,
            base_model_id="test-model",
        )

        assert result.behavioral_diff_passed is False
        assert result.behavioral_diff_pct == 0.0
        assert result.all_checks_passed is False


# ---------------------------------------------------------------------------
# Test 4: Behavioral diff above threshold passes
# ---------------------------------------------------------------------------

def test_behavioral_diff_above_threshold_passes(valid_adapter_dir, valid_test_data):
    """When adapter output differs from base output by more than the configured
    threshold (>5% token difference), the behavioral-diff check must pass."""
    validator = AdapterValidator(behavioral_diff_threshold=5.0)

    with mock.patch.object(AdapterValidator, "_compute_validation_loss") as mock_loss, \
         mock.patch.object(AdapterValidator, "_compute_behavioral_diff") as mock_diff:

        mock_loss.return_value = 2.0
        mock_diff.return_value = 15.0

        result = validator.validate(
            niche="test_specialist",
            adapter_path=valid_adapter_dir,
            test_data_path=valid_test_data,
            base_model_id="test-model",
        )

        assert result.behavioral_diff_passed is True
        assert result.behavioral_diff_pct == 15.0


# ---------------------------------------------------------------------------
# Test 5: Validation loss below threshold passes
# ---------------------------------------------------------------------------

def test_validation_loss_below_threshold_passes(valid_adapter_dir, valid_test_data):
    """When computed validation loss is below the configured threshold,
    validation_loss_passed must be True."""
    validator = AdapterValidator(val_loss_threshold=3.0)

    with mock.patch.object(AdapterValidator, "_compute_validation_loss") as mock_loss, \
         mock.patch.object(AdapterValidator, "_compute_behavioral_diff") as mock_diff:

        mock_loss.return_value = 1.5  # Below threshold of 3.0
        mock_diff.return_value = 10.0

        result = validator.validate(
            niche="test_specialist",
            adapter_path=valid_adapter_dir,
            test_data_path=valid_test_data,
            base_model_id="test-model",
        )

        assert result.validation_loss_passed is True
        assert result.validation_loss == 1.5
        assert result.validation_loss_threshold == 3.0


# ---------------------------------------------------------------------------
# Test 6: Missing test data JSONL handled gracefully (T-02-06)
# ---------------------------------------------------------------------------

def test_missing_test_data_handled_gracefully(valid_adapter_dir):
    """When the test_data_path does not exist, the validator must not crash;
    it must report an error and fail all_checks_passed."""
    validator = AdapterValidator()

    result = validator.validate(
        niche="test_specialist",
        adapter_path=valid_adapter_dir,
        test_data_path="/nonexistent/path/test.jsonl",
        base_model_id="test-model",
    )

    assert result.all_checks_passed is False
    assert any("test data" in e.lower() or "not found" in e.lower() or "no such file" in e.lower()
               for e in result.errors)
    # Must not have raised an exception — we reached this assertion.
    assert isinstance(result, ValidationResult)


# ---------------------------------------------------------------------------
# Test 7: Missing adapter file handled gracefully
# ---------------------------------------------------------------------------

def test_missing_adapter_file_handled_gracefully(valid_test_data):
    """When the adapter_path does not contain a valid safetensors file,
    the validator must not crash; it must report an error."""
    validator = AdapterValidator()

    result = validator.validate(
        niche="test_specialist",
        adapter_path="/nonexistent/adapter/path",
        test_data_path=valid_test_data,
        base_model_id="test-model",
    )

    assert result.all_checks_passed is False
    assert result.loadable is False
    assert any(
        "not found" in e.lower()
        or "no such file" in e.lower()
        or "adapter" in e.lower()
        for e in result.errors
    )


# ---------------------------------------------------------------------------
# Test 8: Malformed safetensors rejected as not loadable (P1: parse error ≠ non-zero)
# ---------------------------------------------------------------------------

def test_malformed_safetensors_rejected(tmp_path, valid_test_data):
    """A truncated/malformed safetensors file must fail loadability with a parse
    error, not be treated as a valid non-zero adapter."""
    adapter_dir = tmp_path / "adapters" / "broken"
    adapter_dir.mkdir(parents=True)
    (adapter_dir / "adapter_config.json").write_text(json.dumps({"model": "test-model"}))
    # Truncated garbage that cannot parse as safetensors
    (adapter_dir / "adapter_model.safetensors").write_bytes(b"\x05\x00garbage")

    validator = AdapterValidator()
    result = validator.validate(
        niche="broken",
        adapter_path=str(adapter_dir),
        test_data_path=valid_test_data,
        base_model_id="test-model",
    )

    assert result.loadable is False
    assert result.all_zero_weights is False
    assert result.all_checks_passed is False
    assert any("parse" in e.lower() or "malformed" in e.lower() or "truncated" in e.lower()
               for e in result.errors)


# ---------------------------------------------------------------------------
# Test 9: Non-zero BF16 adapter is loadable (P1: F16/BF16 not skipped)
# ---------------------------------------------------------------------------

def test_nonzero_bf16_adapter_is_loadable(tmp_path, valid_test_data):
    """A valid BF16 adapter with non-zero weights must NOT be flagged inert."""
    adapter_dir = tmp_path / "adapters" / "bf16_specialist"
    safetensors_path = adapter_dir / "adapter_model.safetensors"
    _write_bf16_safetensors(safetensors_path, {"lora_A.weight": (4, 64), "lora_B.weight": (64, 4)}, fill=0.5)
    (adapter_dir / "adapter_config.json").write_text(json.dumps({"model": "test-model"}))

    validator = AdapterValidator()
    with mock.patch.object(AdapterValidator, "_compute_validation_loss") as mock_loss:
        mock_loss.return_value = 2.0
        result = validator.validate(
            niche="bf16_specialist",
            adapter_path=str(adapter_dir),
            test_data_path=valid_test_data,
            base_model_id="test-model",
        )

    assert result.all_zero_weights is False
    assert result.loadable is True


# ---------------------------------------------------------------------------
# Test 10: All-zero BF16 adapter detected as inert
# ---------------------------------------------------------------------------

def test_all_zero_bf16_adapter_is_inert(tmp_path, valid_test_data):
    """A BF16 adapter whose weights are all zero must be flagged inert."""
    adapter_dir = tmp_path / "adapters" / "bf16_inert"
    safetensors_path = adapter_dir / "adapter_model.safetensors"
    _write_bf16_safetensors(safetensors_path, {"lora_A.weight": (4, 64)}, fill=0.0)
    (adapter_dir / "adapter_config.json").write_text(json.dumps({"model": "test-model"}))

    validator = AdapterValidator()
    result = validator.validate(
        niche="bf16_inert",
        adapter_path=str(adapter_dir),
        test_data_path=valid_test_data,
        base_model_id="test-model",
    )

    assert result.all_zero_weights is True
    assert result.loadable is False


# ---------------------------------------------------------------------------
# Test 11: Behavioral diff fails closed without real inference (P1: no proxy pass)
# ---------------------------------------------------------------------------

def test_behavioral_diff_fails_closed_without_inference(valid_adapter_dir, valid_test_data):
    """Without real base-vs-adapter inference, the behavioral-diff check must
    fail closed (diff 0.0, check False) rather than pass on a proxy metric."""
    validator = AdapterValidator(behavioral_diff_threshold=5.0)

    with mock.patch.object(AdapterValidator, "_compute_validation_loss") as mock_loss:
        mock_loss.return_value = 2.0
        result = validator.validate(
            niche="test_specialist",
            adapter_path=valid_adapter_dir,
            test_data_path=valid_test_data,
            base_model_id="test-model",
        )

    assert result.loadable is True
    assert result.behavioral_diff_pct == 0.0
    assert result.behavioral_diff_passed is False
    assert result.all_checks_passed is False
