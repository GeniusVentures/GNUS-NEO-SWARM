"""Tests for CheckpointValidator, including SGFP4 v2 quantize stage validation."""

import json
import os
from pathlib import Path

import pytest

from pipeline.checkpoint import CheckpointValidator, StageValidationResult


class TestCheckpointValidatorBasic:
    """Basic lifecycle tests for CheckpointValidator."""

    def test_stage_validation_result_roundtrip(self):
        result = StageValidationResult(
            stage="quantize",
            niche="code",
            passed=True,
            checks=[
                {"name": "fp4_dir_exists", "passed": True, "detail": "ok"},
            ],
            completed_at="2026-01-01T00:00:00Z",
        )
        d = result.to_dict()
        restored = StageValidationResult.from_dict(d)
        assert restored.stage == "quantize"
        assert restored.niche == "code"
        assert restored.passed is True
        assert len(restored.checks) == 1

    def test_unknown_stage_raises(self, tmp_project_root):
        validator = CheckpointValidator(tmp_project_root)
        with pytest.raises(ValueError, match="Unknown stage"):
            validator.validate_stage("code", "nonexistent_stage")


class TestCheckpointValidatorCheckpointLifecycle:
    """Tests for checkpoint read/write/clear."""

    def test_mark_and_is_complete(self, tmp_project_root):
        validator = CheckpointValidator(tmp_project_root)
        niche = "code"
        stage = "quantize"

        result = StageValidationResult(
            stage=stage,
            niche=niche,
            passed=True,
            checks=[{"name": "check1", "passed": True, "detail": "ok"}],
        )
        validator.mark_complete(niche, stage, result)

        assert validator.is_complete(niche, stage) is True

    def test_clear_checkpoint(self, tmp_project_root):
        validator = CheckpointValidator(tmp_project_root)
        niche = "code"
        stage = "quantize"

        result = StageValidationResult(
            stage=stage,
            niche=niche,
            passed=True,
            checks=[{"name": "check1", "passed": True, "detail": "ok"}],
        )
        validator.mark_complete(niche, stage, result)
        assert validator.is_complete(niche, stage) is True

        validator.clear_checkpoint(niche, stage)
        assert validator.is_complete(niche, stage) is False

    def test_clear_all_checkpoints(self, tmp_project_root):
        validator = CheckpointValidator(tmp_project_root)
        niche = "code"

        for stage in ["data_prep", "train"]:
            result = StageValidationResult(
                stage=stage,
                niche=niche,
                passed=True,
                checks=[{"name": "check1", "passed": True, "detail": "ok"}],
            )
            validator.mark_complete(niche, stage, result)

        # Mark a second niche to ensure only the target is cleared
        result2 = StageValidationResult(
            stage="train",
            niche="medical",
            passed=True,
            checks=[{"name": "check1", "passed": True, "detail": "ok"}],
        )
        validator.mark_complete("medical", "train", result2)

        assert validator.is_complete(niche, "train") is True
        validator.clear_all_checkpoints(niche)
        assert validator.is_complete(niche, "data_prep") is False
        assert validator.is_complete(niche, "train") is False

        # Other niche untouched
        assert validator.is_complete("medical", "train") is True


class TestQuantizeValidationSgfp4V2:
    """SGFP4 v2 quantize stage validation tests."""

    def test_valid_sgfp4_v2_passes_all_checks(self, tmp_project_root, valid_sgfp4_binary):
        """Full SGFP4 v2 output with valid magic, SHA256 match, and all required fields."""
        validator = CheckpointValidator(tmp_project_root)
        result = validator.validate_stage("code", "quantize")

        assert result.passed is True

        checks_by_name = {c["name"]: c for c in result.checks}
        assert len(checks_by_name) == 7

        assert checks_by_name["fp4_dir_exists"]["passed"] is True
        assert checks_by_name["fp4_weights_exist"]["passed"] is True
        assert checks_by_name["manifest_exists"]["passed"] is True
        assert checks_by_name["sgfp4_binary_exists"]["passed"] is True
        assert checks_by_name["magic_header_valid"]["passed"] is True
        assert checks_by_name["manifest_sha256_valid"]["passed"] is True
        assert checks_by_name["manifest_required_fields"]["passed"] is True

    def test_magic_header_mismatch_detected(self, tmp_project_root, sgfp4_bad_magic):
        """Bad magic (b'BAD4' instead of b'SGF4') produces a failed check."""
        validator = CheckpointValidator(tmp_project_root)
        result = validator.validate_stage("code", "quantize")

        checks_by_name = {c["name"]: c for c in result.checks}
        assert checks_by_name["magic_header_valid"]["passed"] is False
        assert "SGF4" in checks_by_name["magic_header_valid"]["detail"]

    def test_sha256_mismatch_detected(self, tmp_project_root, sgfp4_sha256_mismatch):
        """Mismatched manifest SHA256 vs binary SHA256 produces failed check."""
        validator = CheckpointValidator(tmp_project_root)
        result = validator.validate_stage("code", "quantize")

        checks_by_name = {c["name"]: c for c in result.checks}
        assert checks_by_name["manifest_sha256_valid"]["passed"] is False
        assert "does not match" in checks_by_name["manifest_sha256_valid"]["detail"]

    def test_missing_sha256_in_manifest_passes(self, tmp_project_root, sgfp4_manifest_no_sha256):
        """Manifest without fp4_binary key is backward compatible (passes)."""
        validator = CheckpointValidator(tmp_project_root)
        result = validator.validate_stage("code", "quantize")

        checks_by_name = {c["name"]: c for c in result.checks}
        assert checks_by_name["manifest_sha256_valid"]["passed"] is True
        assert "No sha256" in checks_by_name["manifest_sha256_valid"]["detail"]

    def test_v1_only_passes_validation(self, tmp_project_root, sgfp4_v1_only):
        """v1-only output (no .sgfp4) still passes validation."""
        validator = CheckpointValidator(tmp_project_root)
        result = validator.validate_stage("code", "quantize")

        checks_by_name = {c["name"]: c for c in result.checks}
        assert checks_by_name["fp4_dir_exists"]["passed"] is True
        assert checks_by_name["fp4_weights_exist"]["passed"] is True
        assert checks_by_name["sgfp4_binary_exists"]["passed"] is True  # passes as warning
        assert "v1-only" in checks_by_name["sgfp4_binary_exists"]["detail"]

        # Should still pass overall (v1 is valid)
        assert result.passed is True

    def test_missing_required_manifest_fields(self, tmp_project_root, sgfp4_missing_fields):
        """Missing QUANT-03 required fields (adapter_ref, encoder_version) produces failed check."""
        validator = CheckpointValidator(tmp_project_root)
        result = validator.validate_stage("code", "quantize")

        checks_by_name = {c["name"]: c for c in result.checks}
        assert checks_by_name["manifest_required_fields"]["passed"] is False
        assert "adapter_ref" in checks_by_name["manifest_required_fields"]["detail"]
        assert "encoder_version" in checks_by_name["manifest_required_fields"]["detail"]

    def test_validation_readonly_does_not_modify_fs(self, tmp_project_root, valid_sgfp4_binary):
        """Validation must not modify the filesystem — read-only check."""
        # Record state before validation
        fp4_dir = valid_sgfp4_binary
        mtimes_before = {}
        for f in fp4_dir.iterdir():
            mtimes_before[f.name] = f.stat().st_mtime

        validator = CheckpointValidator(tmp_project_root)
        validator.validate_stage("code", "quantize")

        # Verify nothing changed
        for f in fp4_dir.iterdir():
            assert f.stat().st_mtime == mtimes_before[f.name], (
                f"File {f.name} was modified by validation"
            )
