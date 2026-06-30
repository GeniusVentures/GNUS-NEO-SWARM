"""Reproducibility fingerprint for canonical benchmark runs (Plan 04-03 Task 1, D-02).

Implements D-02: every canonical benchmark run records an 11-field fingerprint that
identifies the exact harness, prompt, dataset, decoding, and manifest state of the run.
Without this, trend analysis across runs is meaningless -- score drift from unrecorded
prompt or generation-parameter changes cannot be distinguished from real model regressions.

The fingerprint is intentionally lightweight and stdlib-only (hashlib + json + importlib).
All field values are simple scalars/dicts/strings so the fingerprint is JSON-serializable
and stable across processes (sort_keys=True in fingerprint_hash).
"""

import hashlib
import importlib.metadata
import json
import re
from pathlib import Path
from typing import Optional

REQUIRED_FIELDS = (
    "harness_commit",
    "task_name",
    "task_revision",
    "dataset_revision",
    "prompt_hash",
    "fewshot_seed",
    "chat_template_hash",
    "answer_extraction",
    "generation_params",
    "model_manifest_sha256",
    "sgfp4_manifest_sha256",
)

# T-04-15 mitigation: cap manifest read size to guard against unbounded reads.
# Manifest files are small (<1KB) in normal operation; 10 MB is a hard safety ceiling.
_K_MAX_MANIFEST_BYTES = 10 * 1024 * 1024

_WHITESPACE_RE = re.compile(r"\s+")


def _harness_version() -> str:
    """Return the lm-eval-harness package version, or 'unknown' if not installed.

    Wrapped as a module-level function so tests can patch it without depending on
    lm-eval being installed in the test environment.
    """
    try:
        return importlib.metadata.version("lm_eval")
    except importlib.metadata.PackageNotFoundError:
        return "unknown"


def _sha256_file(path: Path) -> str:
    """SHA256 hex digest of a manifest file's binary contents.

    T-04-15 mitigation: enforces a maximum read size to prevent unbounded reads
    on an attacker-supplied path.

    Args:
        path: Path to the manifest file.

    Returns:
        Lowercase hex SHA256 digest string.

    Raises:
        FileNotFoundError: If the path does not exist.
    """
    if not path.exists():
        raise FileNotFoundError(f"manifest file not found: {path}")

    digest = hashlib.sha256()
    with path.open("rb") as f:
        read_bytes = 0
        while True:
            chunk = f.read(65536)
            if not chunk:
                break
            read_bytes += len(chunk)
            if read_bytes > _K_MAX_MANIFEST_BYTES:
                raise ValueError(
                    f"manifest file exceeds {_K_MAX_MANIFEST_BYTES} bytes: {path}"
                )
            digest.update(chunk)
    return digest.hexdigest()


def _sha256_str(value: str) -> str:
    """SHA256 hex digest of a string with whitespace normalized before hashing.

    Whitespace normalization makes the hash resilient to incidental indentation /
    trailing-newline differences that do not change prompt semantics.
    """
    normalized = _WHITESPACE_RE.sub(" ", value).strip()
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def compute_fingerprint(
    task_name: str,
    fewshot_seed: int,
    prompt_template: str,
    model_manifest_path: Path,
    sgfp4_manifest_path: Path,
    generation_params: dict,
    task_revision: Optional[str] = None,
    dataset_revision: Optional[str] = None,
    chat_template: Optional[str] = None,
    answer_extraction: str = "default",
) -> dict:
    """Compute the 11-field reproducibility fingerprint per D-02.

    Args:
        task_name: lm-eval task identifier (e.g. ``medmcqa``).
        fewshot_seed: Integer seed for deterministic few-shot sampling.
        prompt_template: Rendered prompt template string.
        model_manifest_path: Path to the model manifest JSON file (Phase 3 output).
        sgfp4_manifest_path: Path to the SGFP4 quantization manifest JSON file.
        generation_params: Dict of decoding parameters
            (``temperature``, ``do_sample``, ``max_gen_toks``, ``top_p``).
        task_revision: Optional pinned lm-eval task revision; ``None`` if not pinned.
        dataset_revision: Optional pinned dataset revision; ``None`` if not pinned.
        chat_template: Optional chat template string; ``None`` -> hash is ``"none"``.
        answer_extraction: Answer extraction mode (default ``"default"``).

    Returns:
        Dict with all 11 D-02 fingerprint fields populated.
    """
    chat_template_hash = (
        _sha256_str(chat_template) if chat_template is not None else "none"
    )

    return {
        "harness_commit": _harness_version(),
        "task_name": task_name,
        "task_revision": task_revision,
        "dataset_revision": dataset_revision,
        "prompt_hash": _sha256_str(prompt_template),
        "fewshot_seed": int(fewshot_seed),
        "chat_template_hash": chat_template_hash,
        "answer_extraction": answer_extraction,
        "generation_params": dict(generation_params),
        "model_manifest_sha256": _sha256_file(Path(model_manifest_path)),
        "sgfp4_manifest_sha256": _sha256_file(Path(sgfp4_manifest_path)),
    }


# Per D-02 these revision fields are explicitly nullable (``None`` when a
# benchmark task/dataset revision is not pinned). They must be present in a
# valid fingerprint, but a ``None`` value is acceptable.
_NULLABLE_FIELDS = frozenset({"task_revision", "dataset_revision"})


def validate_fingerprint(fp: dict) -> tuple:
    """Validate that a fingerprint dict contains all 11 D-02 fields.

    Presence check only; field types are not validated. The two revision
    fields (``task_revision``, ``dataset_revision``) are explicitly nullable
    per D-02 -- a ``None`` value is valid for them but the key must be present.
    All other fields must be present and non-None.

    Args:
        fp: Fingerprint dict to validate.

    Returns:
        Tuple of ``(is_valid: bool, missing_fields: list[str])``.
    """
    missing = []
    for field in REQUIRED_FIELDS:
        if field not in fp:
            missing.append(field)
            continue
        if field in _NULLABLE_FIELDS:
            continue
        if fp[field] is None:
            missing.append(field)
    return (len(missing) == 0, missing)


def fingerprint_hash(fp: dict) -> str:
    """SHA256 hex digest of the fingerprint dict (sorted keys for determinism).

    Args:
        fp: Fingerprint dict.

    Returns:
        Lowercase 64-character hex digest.
    """
    return hashlib.sha256(
        json.dumps(fp, sort_keys=True, default=str).encode("utf-8")
    ).hexdigest()


def fingerprints_match(fp_a: dict, fp_b: dict) -> bool:
    """Return True when two fingerprints share an identical fingerprint_hash.

    Args:
        fp_a: First fingerprint dict.
        fp_b: Second fingerprint dict.

    Returns:
        True iff fingerprint_hash(fp_a) == fingerprint_hash(fp_b).
    """
    return fingerprint_hash(fp_a) == fingerprint_hash(fp_b)
