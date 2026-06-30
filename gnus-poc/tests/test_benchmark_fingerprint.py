"""Tests for reproducibility fingerprint module (Plan 04-03 Task 1, D-02)."""

import hashlib
import json
from pathlib import Path
from unittest.mock import patch

import pytest

from eval.benchmark_fingerprint import (
    compute_fingerprint,
    fingerprints_match,
    fingerprint_hash,
    validate_fingerprint,
)


REQUIRED_FIELDS = [
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
]


def _write_manifest(path: Path, payload: dict) -> Path:
    """Write a manifest JSON file to a path; returns the path."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        json.dump(payload, f, sort_keys=True)
    return path


def _expected_sha256_bytes(raw_bytes: bytes) -> str:
    return hashlib.sha256(raw_bytes).hexdigest()


class TestComputeFingerprint:
    def test_returns_all_eleven_required_fields(self, tmp_path):
        """D-02: compute_fingerprint returns dict with all 11 required fields."""
        model_manifest = _write_manifest(tmp_path / "model.json", {"weights": "abc"})
        sgfp4_manifest = _write_manifest(tmp_path / "sgfp4.json", {"quant": "def"})

        with patch("eval.benchmark_fingerprint._harness_version", return_value="0.4.12"):
            fp = compute_fingerprint(
                task_name="medmcqa",
                fewshot_seed=42,
                prompt_template="Q: {question}\nA:",
                model_manifest_path=model_manifest,
                sgfp4_manifest_path=sgfp4_manifest,
                generation_params={"temperature": 0.0, "do_sample": False},
            )

        for field in REQUIRED_FIELDS:
            assert field in fp, f"missing required field: {field}"
        # Nullable revision fields may legitimately be None per D-02
        non_nullable = [f for f in REQUIRED_FIELDS if f not in ("task_revision", "dataset_revision")]
        for field in non_nullable:
            assert fp[field] is not None, f"field {field} is None"

        assert fp["task_name"] == "medmcqa"
        assert fp["fewshot_seed"] == 42

    def test_prompt_hash_is_deterministic_sha256(self, tmp_path):
        """prompt_hash: same template produces same SHA256 across calls."""
        model_manifest = _write_manifest(tmp_path / "model.json", {"a": 1})
        sgfp4_manifest = _write_manifest(tmp_path / "sgfp4.json", {"b": 2})
        template = "Q: {question}\nA:"

        with patch("eval.benchmark_fingerprint._harness_version", return_value="0.4.12"):
            fp_a = compute_fingerprint(
                task_name="humaneval",
                fewshot_seed=0,
                prompt_template=template,
                model_manifest_path=model_manifest,
                sgfp4_manifest_path=sgfp4_manifest,
                generation_params={},
            )
            fp_b = compute_fingerprint(
                task_name="humaneval",
                fewshot_seed=0,
                prompt_template=template,
                model_manifest_path=model_manifest,
                sgfp4_manifest_path=sgfp4_manifest,
                generation_params={},
            )

        assert fp_a["prompt_hash"] == fp_b["prompt_hash"]
        # SHA256 hex digests are 64 chars
        assert len(fp_a["prompt_hash"]) == 64

    def test_model_manifest_sha256_missing_raises(self, tmp_path):
        """model_manifest_sha256: missing manifest file raises FileNotFoundError."""
        sgfp4_manifest = _write_manifest(tmp_path / "sgfp4.json", {"b": 2})
        with patch("eval.benchmark_fingerprint._harness_version", return_value="0.4.12"):
            with pytest.raises(FileNotFoundError):
                compute_fingerprint(
                    task_name="medmcqa",
                    fewshot_seed=1,
                    prompt_template="x",
                    model_manifest_path=tmp_path / "nonexistent_model.json",
                    sgfp4_manifest_path=sgfp4_manifest,
                    generation_params={},
                )

    def test_sgfp4_manifest_sha256_missing_raises(self, tmp_path):
        """sgfp4_manifest_sha256: missing manifest file raises FileNotFoundError."""
        model_manifest = _write_manifest(tmp_path / "model.json", {"a": 1})
        with patch("eval.benchmark_fingerprint._harness_version", return_value="0.4.12"):
            with pytest.raises(FileNotFoundError):
                compute_fingerprint(
                    task_name="medmcqa",
                    fewshot_seed=1,
                    prompt_template="x",
                    model_manifest_path=model_manifest,
                    sgfp4_manifest_path=tmp_path / "nonexistent_sgfp4.json",
                    generation_params={},
                )


class TestValidateFingerprint:
    def test_valid_fingerprint_returns_true_empty_missing(self, tmp_path):
        """validate_fingerprint: complete 11-field fingerprint -> (True, [])."""
        model_manifest = _write_manifest(tmp_path / "model.json", {"a": 1})
        sgfp4_manifest = _write_manifest(tmp_path / "sgfp4.json", {"b": 2})
        with patch("eval.benchmark_fingerprint._harness_version", return_value="0.4.12"):
            fp = compute_fingerprint(
                task_name="medmcqa",
                fewshot_seed=42,
                prompt_template="x",
                model_manifest_path=model_manifest,
                sgfp4_manifest_path=sgfp4_manifest,
                generation_params={},
            )
        is_valid, missing = validate_fingerprint(fp)
        assert is_valid is True
        assert missing == []

    def test_incomplete_fingerprint_returns_false_with_missing(self):
        """validate_fingerprint: incomplete dict -> (False, [missing field names])."""
        incomplete = {
            "harness_commit": "0.4.12",
            "task_name": "medmcqa",
            # missing 9 fields
        }
        is_valid, missing = validate_fingerprint(incomplete)
        assert is_valid is False
        # 11 required fields - 2 present (harness_commit, task_name) = 9 missing
        assert len(missing) == 9
        assert "prompt_hash" in missing


class TestFingerprintHash:
    def test_deterministic_sorted_keys(self, tmp_path):
        """fingerprint_hash: deterministic SHA256 of sorted-keys JSON."""
        model_manifest = _write_manifest(tmp_path / "model.json", {"a": 1})
        sgfp4_manifest = _write_manifest(tmp_path / "sgfp4.json", {"b": 2})
        with patch("eval.benchmark_fingerprint._harness_version", return_value="0.4.12"):
            fp = compute_fingerprint(
                task_name="medmcqa",
                fewshot_seed=42,
                prompt_template="x",
                model_manifest_path=model_manifest,
                sgfp4_manifest_path=sgfp4_manifest,
                generation_params={"temperature": 0.0},
            )
        h1 = fingerprint_hash(fp)
        h2 = fingerprint_hash(fp)
        assert h1 == h2
        assert len(h1) == 64

    def test_different_fingerprints_different_hashes(self, tmp_path):
        """fingerprint_hash: different fingerprints produce different hashes."""
        model_manifest = _write_manifest(tmp_path / "model.json", {"a": 1})
        sgfp4_manifest = _write_manifest(tmp_path / "sgfp4.json", {"b": 2})
        with patch("eval.benchmark_fingerprint._harness_version", return_value="0.4.12"):
            fp_a = compute_fingerprint(
                task_name="medmcqa",
                fewshot_seed=1,
                prompt_template="x",
                model_manifest_path=model_manifest,
                sgfp4_manifest_path=sgfp4_manifest,
                generation_params={},
            )
            fp_b = compute_fingerprint(
                task_name="humaneval",  # different task
                fewshot_seed=1,
                prompt_template="x",
                model_manifest_path=model_manifest,
                sgfp4_manifest_path=sgfp4_manifest,
                generation_params={},
            )
        assert fingerprint_hash(fp_a) != fingerprint_hash(fp_b)


class TestFingerprintsMatch:
    def test_identical_hashes_match(self, tmp_path):
        """fingerprints_match: identical fingerprints -> True."""
        model_manifest = _write_manifest(tmp_path / "model.json", {"a": 1})
        sgfp4_manifest = _write_manifest(tmp_path / "sgfp4.json", {"b": 2})
        with patch("eval.benchmark_fingerprint._harness_version", return_value="0.4.12"):
            fp_a = compute_fingerprint(
                task_name="medmcqa",
                fewshot_seed=42,
                prompt_template="x",
                model_manifest_path=model_manifest,
                sgfp4_manifest_path=sgfp4_manifest,
                generation_params={},
            )
        fp_b = dict(fp_a)
        assert fingerprints_match(fp_a, fp_b) is True

    def test_different_hashes_do_not_match(self, tmp_path):
        """fingerprints_match: differing fingerprints -> False."""
        model_manifest = _write_manifest(tmp_path / "model.json", {"a": 1})
        sgfp4_manifest = _write_manifest(tmp_path / "sgfp4.json", {"b": 2})
        with patch("eval.benchmark_fingerprint._harness_version", return_value="0.4.12"):
            fp_a = compute_fingerprint(
                task_name="medmcqa",
                fewshot_seed=1,
                prompt_template="x",
                model_manifest_path=model_manifest,
                sgfp4_manifest_path=sgfp4_manifest,
                generation_params={},
            )
            fp_b = compute_fingerprint(
                task_name="medmcqa",
                fewshot_seed=999,  # different seed
                prompt_template="x",
                model_manifest_path=model_manifest,
                sgfp4_manifest_path=sgfp4_manifest,
                generation_params={},
            )
        assert fingerprints_match(fp_a, fp_b) is False
