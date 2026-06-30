"""
Shared pytest fixtures for GNUS-POC test suite.

Provides reusable fixtures for:
- Temporary directory scaffolding
- Lightweight model paths for testing
- Sample chat messages
- Real tokenizer loading (session-scoped for efficiency)
"""

import sys
from pathlib import Path

import pytest

# Ensure gnus-poc root is on sys.path for all tests
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


@pytest.fixture
def tmp_project_root(tmp_path):
    """Create a temporary directory mimicking the gnus-poc structure."""
    root = tmp_path / "gnus_poc_test"
    root.mkdir()

    # Create essential subdirectories
    (root / "data").mkdir()
    (root / "data" / "analysis").mkdir()
    (root / "data" / "specialists").mkdir()
    (root / "models").mkdir()
    (root / "models" / "specialists_mlx").mkdir()
    (root / "training").mkdir()
    (root / "config").mkdir()
    (root / "artifacts").mkdir()

    return root


@pytest.fixture(scope="session")
def mock_model_path():
    """Return a lightweight HuggingFace model path suitable for testing.

    Uses Qwen2.5-0.5B-Instruct — a small model (~1GB) with a valid chat template.
    First download is cached by HuggingFace for subsequent test runs.
    """
    return "Qwen/Qwen2.5-0.5B-Instruct"


@pytest.fixture
def sample_messages():
    """Return standard chat messages for template testing."""
    return [
        {"role": "system", "content": "You are a test assistant."},
        {"role": "user", "content": "Hello, world!"},
    ]


@pytest.fixture(scope="session")
def real_tokenizer(mock_model_path):
    """Load the actual HuggingFace tokenizer for template validation.

    Session-scoped: loaded once per test session (model download on first use).
    Skips automatically if pytest is run with '-m \"not slow\"'.
    """
    try:
        from transformers import AutoTokenizer
    except ImportError:
        pytest.skip("transformers library not installed")

    try:
        tokenizer = AutoTokenizer.from_pretrained(
            mock_model_path,
            trust_remote_code=True,
        )
    except Exception as e:
        pytest.skip(f"Could not load tokenizer from {mock_model_path}: {e}")

    return tokenizer


# ---------------------------------------------------------------------------
# SGFP4 v2 test fixtures
# ---------------------------------------------------------------------------

SGFP4_MAGIC = b"SGF4"
SGFP4_VERSION = 0x02


@pytest.fixture
def valid_sgfp4_binary(tmp_path, tmp_project_root):
    """Create a valid SGFP4 v2 binary file with magic header in a quantize output dir."""
    niche = "code"
    fp4_dir = tmp_project_root / "models" / "specialists_mlx" / niche / "fp4"
    fp4_dir.mkdir(parents=True, exist_ok=True)

    # Build a minimal SGFP4 v2 binary: magic + version + some payload bytes
    payload = b"\x00" * 256
    binary = SGFP4_MAGIC + bytes([SGFP4_VERSION]) + payload

    sgfp4_path = fp4_dir / f"{niche}.sgfp4"
    sgfp4_path.write_bytes(binary)

    import hashlib
    file_hash = hashlib.sha256(binary).hexdigest()

    # Write manifest with matching SHA256
    manifest = fp4_dir / "manifest.json"
    manifest_data = {
        "model_name": "qwen3-code-specialist",
        "niche": niche,
        "base_model_ref": "mlx-community/Qwen3-30B-A3B-Instruct-2507-bf16",
        "adapter_ref": f"models/specialists_mlx/{niche}/adapter_model.safetensors",
        "quantization_params": {"target_bits": 4, "block_size": 64, "format": "SGFP4_v2"},
        "encoder_version": "sgfp4-v2-0.1.0",
        "timestamp_utc": "2026-06-27T00:00:00Z",
        "fp4_binary": {
            "path": str(sgfp4_path),
            "sha256": file_hash,
            "size_bytes": len(binary),
        },
    }
    import json
    manifest.write_text(json.dumps(manifest_data, indent=2))

    return fp4_dir


@pytest.fixture
def sgfp4_bad_magic(tmp_path, tmp_project_root):
    """Create an SGFP4 binary file with an invalid magic header."""
    niche = "code"
    fp4_dir = tmp_project_root / "models" / "specialists_mlx" / niche / "fp4"
    fp4_dir.mkdir(parents=True, exist_ok=True)

    # Bad magic: BAD4 instead of SGF4
    binary = b"BAD4" + bytes([SGFP4_VERSION]) + b"\x00" * 256
    sgfp4_path = fp4_dir / f"{niche}.sgfp4"
    sgfp4_path.write_bytes(binary)

    import hashlib
    file_hash = hashlib.sha256(binary).hexdigest()

    import json
    manifest = fp4_dir / "manifest.json"
    manifest_data = {
        "model_name": "qwen3-code-specialist",
        "niche": niche,
        "base_model_ref": "mlx-community/Qwen3-30B-A3B-Instruct-2507-bf16",
        "adapter_ref": f"models/specialists_mlx/{niche}/adapter_model.safetensors",
        "quantization_params": {"target_bits": 4},
        "encoder_version": "sgfp4-v2-0.1.0",
        "timestamp_utc": "2026-06-27T00:00:00Z",
        "fp4_binary": {"sha256": file_hash},
    }
    manifest.write_text(json.dumps(manifest_data, indent=2))

    return fp4_dir


@pytest.fixture
def sgfp4_sha256_mismatch(tmp_path, tmp_project_root):
    """Create an SGFP4 v2 binary + manifest with mismatched SHA256."""
    niche = "code"
    fp4_dir = tmp_project_root / "models" / "specialists_mlx" / niche / "fp4"
    fp4_dir.mkdir(parents=True, exist_ok=True)

    binary = SGFP4_MAGIC + bytes([SGFP4_VERSION]) + b"\x00" * 256
    sgfp4_path = fp4_dir / f"{niche}.sgfp4"
    sgfp4_path.write_bytes(binary)

    import json
    manifest = fp4_dir / "manifest.json"
    manifest_data = {
        "model_name": "qwen3-code-specialist",
        "niche": niche,
        "base_model_ref": "mlx-community/Qwen3-30B-A3B-Instruct-2507-bf16",
        "adapter_ref": f"models/specialists_mlx/{niche}/adapter_model.safetensors",
        "quantization_params": {"target_bits": 4},
        "encoder_version": "sgfp4-v2-0.1.0",
        "timestamp_utc": "2026-06-27T00:00:00Z",
        # Deliberately wrong SHA256
        "fp4_binary": {"sha256": "0" * 64},
    }
    manifest.write_text(json.dumps(manifest_data, indent=2))

    return fp4_dir


@pytest.fixture
def sgfp4_manifest_no_sha256(tmp_path, tmp_project_root):
    """Create an SGFP4 v2 binary + manifest with fp4_binary but no sha256 field (backward compat)."""
    niche = "code"
    fp4_dir = tmp_project_root / "models" / "specialists_mlx" / niche / "fp4"
    fp4_dir.mkdir(parents=True, exist_ok=True)

    binary = SGFP4_MAGIC + bytes([SGFP4_VERSION]) + b"\x00" * 256
    sgfp4_path = fp4_dir / f"{niche}.sgfp4"
    sgfp4_path.write_bytes(binary)

    import json
    manifest = fp4_dir / "manifest.json"
    manifest_data = {
        "model_name": "qwen3-code-specialist",
        "niche": niche,
        "base_model_ref": "mlx-community/Qwen3-30B-A3B-Instruct-2507-bf16",
        "adapter_ref": f"models/specialists_mlx/{niche}/adapter_model.safetensors",
        "quantization_params": {"target_bits": 4},
        "encoder_version": "sgfp4-v1-0.1.0",
        "timestamp_utc": "2026-06-27T00:00:00Z",
        "fp4_binary": {"path": str(sgfp4_path)},
        # fp4_binary exists but sha256 is missing — v1 backward compat
    }
    manifest.write_text(json.dumps(manifest_data, indent=2))

    return fp4_dir


@pytest.fixture
def sgfp4_v1_only(tmp_path, tmp_project_root):
    """Create a v1-only quantize output (no .sgfp4 binary)."""
    niche = "code"
    fp4_dir = tmp_project_root / "models" / "specialists_mlx" / niche / "fp4"
    fp4_dir.mkdir(parents=True, exist_ok=True)

    # Create a dummy .npz file (v1 artifact)
    npz_path = fp4_dir / f"{niche}_w1.npz"
    npz_path.write_bytes(b"\x00" * 128)

    # Minimal manifest
    import json
    manifest = fp4_dir / "manifest.json"
    manifest_data = {
        "model_name": "qwen3-code-specialist",
        "niche": niche,
        "base_model_ref": "mlx-community/Qwen3-30B-A3B-Instruct-2507-bf16",
        "adapter_ref": f"models/specialists_mlx/{niche}/adapter_model.safetensors",
        "quantization_params": {"target_bits": 4},
        "encoder_version": "sgfp4-v1-0.1.0",
        "timestamp_utc": "2026-06-27T00:00:00Z",
    }
    manifest.write_text(json.dumps(manifest_data, indent=2))

    return fp4_dir


@pytest.fixture
def sgfp4_missing_fields(tmp_path, tmp_project_root):
    """Create an SGFP4 v2 output with missing QUANT-03 required fields in manifest."""
    niche = "code"
    fp4_dir = tmp_project_root / "models" / "specialists_mlx" / niche / "fp4"
    fp4_dir.mkdir(parents=True, exist_ok=True)

    binary = SGFP4_MAGIC + bytes([SGFP4_VERSION]) + b"\x00" * 256
    sgfp4_path = fp4_dir / f"{niche}.sgfp4"
    sgfp4_path.write_bytes(binary)

    import hashlib
    file_hash = hashlib.sha256(binary).hexdigest()

    import json
    manifest = fp4_dir / "manifest.json"
    # Missing adapter_ref and encoder_version
    manifest_data = {
        "model_name": "qwen3-code-specialist",
        "niche": niche,
        "base_model_ref": "mlx-community/Qwen3-30B-A3B-Instruct-2507-bf16",
        "quantization_params": {"target_bits": 4},
        "timestamp_utc": "2026-06-27T00:00:00Z",
        "fp4_binary": {"sha256": file_hash},
    }
    manifest.write_text(json.dumps(manifest_data, indent=2))

    return fp4_dir
