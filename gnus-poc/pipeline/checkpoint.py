"""Checkpoint validator — per-stage output validation for pipeline resume.

Replaces empty .done marker files with validated JSON checkpoints that verify
stage output quality before marking a stage complete.
"""

from __future__ import annotations

import hashlib
import json
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


@dataclass
class StageValidationResult:
    """Result of validating a pipeline stage's outputs.

    Attributes:
        stage: Stage name (e.g., "train").
        niche: Specialist niche name (e.g., "code").
        passed: Whether all checks passed.
        checks: List of per-check results, each with ``name``, ``passed``, ``detail``.
        completed_at: ISO 8601 timestamp set when checkpoint is written.
    """

    stage: str
    niche: str
    passed: bool = False
    checks: List[Dict[str, Any]] = field(default_factory=list)
    completed_at: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to a JSON-compatible dictionary."""
        return {
            "stage": self.stage,
            "niche": self.niche,
            "passed": self.passed,
            "checks": self.checks,
            "completed_at": self.completed_at,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "StageValidationResult":
        """Deserialize from a JSON-compatible dictionary."""
        return cls(
            stage=data.get("stage", ""),
            niche=data.get("niche", ""),
            passed=data.get("passed", False),
            checks=data.get("checks", []),
            completed_at=data.get("completed_at"),
        )


class CheckpointValidator:
    """Validates pipeline stage outputs before marking a stage complete.

    Each stage has specific validation checks (per D-15) that verify output
    files exist, contain expected data, and meet quality thresholds.
    """

    #: Minimum number of lines required in synthetic data JSONL output.
    _kMinSyntheticRowCount: int = 10

    #: Expected magic header for SGFP4 v2 binary files.
    _kSgfp4Magic: bytes = b"SGF4"

    #: Expected SGFP4 v2 version byte.
    _kSgfp4Version: int = 0x02

    #: Required fields in quantization manifest.json (QUANT-03).
    _kQuantManifestRequiredFields: tuple = (
        "model_name",
        "niche",
        "base_model_ref",
        "adapter_ref",
        "quantization_params",
        "encoder_version",
        "timestamp_utc",
    )

    #: Chunk size for SHA256 streaming hash computation (64 KiB).
    _kSha256ChunkSize: int = 65536

    #: Stages recognized by the pipeline (mirrors PipelineRunner.STAGES).
    STAGES = [
        "data_prep",
        "synthetic_data",
        "dedup",
        "train",
        "evaluate",
        "distill",
        "quantize",
    ]

    def __init__(self, project_root: Path):
        """Initialize the validator.

        Args:
            project_root: Root directory of the gnus-poc project.
        """
        self._root = project_root

    # ------------------------------------------------------------------
    # Path helpers
    # ------------------------------------------------------------------

    @property
    def checkpoint_dir(self) -> Path:
        """Directory where validated checkpoint JSON files are stored."""
        return self._root / "artifacts" / ".checkpoints"

    def checkpoint_path(self, niche: str, stage: str) -> Path:
        """Return the JSON checkpoint file path for a niche/stage pair."""
        return self.checkpoint_dir / niche / f"{stage}.json"

    # ------------------------------------------------------------------
    # Per-stage validation
    # ------------------------------------------------------------------

    def validate_stage(self, niche: str, stage: str) -> StageValidationResult:
        """Run all validation checks for a given niche and stage.

        Args:
            niche: Specialist niche name (e.g., "code").
            stage: Pipeline stage name (e.g., "train").

        Returns:
            StageValidationResult with per-check details.

        Raises:
            ValueError: If *stage* is not one of the known pipeline stages.
        """
        if stage not in self.STAGES:
            raise ValueError(
                f"Unknown stage '{stage}'. Valid: {self.STAGES}"
            )

        method_name = f"_validate_{stage}"
        validator = getattr(self, method_name, None)
        if validator is None:
            raise ValueError(
                f"No validation method for stage '{stage}'"
            )

        checks: List[Dict[str, Any]] = validator(niche)
        passed = all(c.get("passed", False) for c in checks)
        return StageValidationResult(
            stage=stage,
            niche=niche,
            passed=passed,
            checks=checks,
        )

    # -- data_prep -------------------------------------------------------

    def _validate_data_prep(self, niche: str) -> List[Dict[str, Any]]:
        """Validate data_prep stage: dataset directory has non-init files."""
        checks: List[Dict[str, Any]] = []
        data_dir = self._root / "data" / "specialists" / niche

        # Check 1: directory exists
        if not data_dir.exists() or not data_dir.is_dir():
            checks.append({
                "name": "directory_exists",
                "passed": False,
                "detail": f"Directory not found: {data_dir}",
            })
            return checks

        checks.append({
            "name": "directory_exists",
            "passed": True,
            "detail": f"Directory exists: {data_dir}",
        })

        # Check 2: contains at least one non-__init__.py file
        non_init_files = [
            f for f in data_dir.iterdir()
            if f.is_file() and f.name != "__init__.py"
        ]
        if len(non_init_files) == 0:
            checks.append({
                "name": "has_data_files",
                "passed": False,
                "detail": f"No non-__init__.py files found in {data_dir}",
            })
        else:
            checks.append({
                "name": "has_data_files",
                "passed": True,
                "detail": f"Found {len(non_init_files)} data file(s)",
            })

        return checks

    # -- synthetic_data --------------------------------------------------

    def _validate_synthetic_data(self, niche: str) -> List[Dict[str, Any]]:
        """Validate synthetic_data stage: JSONL with minimum rows, valid JSON."""
        checks: List[Dict[str, Any]] = []
        jsonl_path = self._root / "artifacts" / "synthetic" / f"{niche}.jsonl"

        # Check 1: file exists
        if not jsonl_path.exists() or not jsonl_path.is_file():
            checks.append({
                "name": "jsonl_exists",
                "passed": False,
                "detail": f"File not found: {jsonl_path}",
            })
            return checks

        checks.append({
            "name": "jsonl_exists",
            "passed": True,
            "detail": f"File exists: {jsonl_path}",
        })

        # Check 2: read lines and validate each is valid, non-empty JSON
        try:
            lines = jsonl_path.read_text(encoding="utf-8").strip().splitlines()
        except OSError as exc:
            checks.append({
                "name": "jsonl_readable",
                "passed": False,
                "detail": f"Could not read file: {exc}",
            })
            return checks

        valid_count = 0
        empty_count = 0
        for i, line in enumerate(lines):
            stripped = line.strip()
            if not stripped:
                empty_count += 1
                continue
            try:
                parsed = json.loads(stripped)
            except json.JSONDecodeError as exc:
                checks.append({
                    "name": "valid_json_lines",
                    "passed": False,
                    "detail": f"Line {i + 1} is not valid JSON: {exc}",
                })
                return checks
            # Check that parsed content is not empty/whitespace-only
            if isinstance(parsed, dict) and all(
                isinstance(v, str) and not v.strip() for v in parsed.values()
            ):
                empty_count += 1
                continue
            if isinstance(parsed, str) and not parsed.strip():
                empty_count += 1
                continue
            valid_count += 1

        checks.append({
            "name": "valid_json_lines",
            "passed": True,
            "detail": f"{valid_count} valid non-empty JSON lines out of {len(lines)} total",
        })

        # Check 3: minimum row count
        min_rows = self._kMinSyntheticRowCount
        if valid_count < min_rows:
            checks.append({
                "name": "min_row_count",
                "passed": False,
                "detail": f"Only {valid_count} rows; minimum required is {min_rows}",
            })
        else:
            checks.append({
                "name": "min_row_count",
                "passed": True,
                "detail": f"{valid_count} rows >= {min_rows} minimum",
            })

        return checks

    # -- dedup -----------------------------------------------------------

    def _validate_dedup(self, niche: str) -> List[Dict[str, Any]]:
        """Validate dedup stage: hash file and dedup log exist."""
        checks: List[Dict[str, Any]] = []
        dedup_dir = self._root / "artifacts" / "dedup"

        # Check 1: hash file exists (try .json then .txt)
        hash_json = dedup_dir / f"{niche}_hashes.json"
        hash_txt = dedup_dir / f"{niche}_hashes.txt"
        hash_found = None
        if hash_json.exists() and hash_json.is_file():
            hash_found = hash_json
        elif hash_txt.exists() and hash_txt.is_file():
            hash_found = hash_txt

        if hash_found is None:
            checks.append({
                "name": "hash_file_exists",
                "passed": False,
                "detail": f"No hash file found: {hash_json} or {hash_txt}",
            })
        else:
            checks.append({
                "name": "hash_file_exists",
                "passed": True,
                "detail": f"Hash file found: {hash_found}",
            })

        # Check 2: dedup log exists with valid removed_count
        log_path = dedup_dir / f"{niche}_dedup_log.json"
        if not log_path.exists() or not log_path.is_file():
            checks.append({
                "name": "dedup_log_exists",
                "passed": False,
                "detail": f"Dedup log not found: {log_path}",
            })
            return checks

        try:
            log_data = json.loads(log_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            checks.append({
                "name": "dedup_log_valid",
                "passed": False,
                "detail": f"Could not read dedup log: {exc}",
            })
            return checks

        removed_count = log_data.get("removed_count", -1)
        if removed_count < 0:
            checks.append({
                "name": "removed_count_valid",
                "passed": False,
                "detail": f"removed_count is missing or negative: {removed_count}",
            })
        else:
            checks.append({
                "name": "removed_count_valid",
                "passed": True,
                "detail": f"removed_count = {removed_count}",
            })

        return checks

    # -- train -----------------------------------------------------------

    def _validate_train(self, niche: str) -> List[Dict[str, Any]]:
        """Validate train stage: adapter weights, config, and metadata exist."""
        checks: List[Dict[str, Any]] = []
        model_dir = self._root / "models" / "specialists_mlx" / niche

        # Check 1: adapter_config.json
        adapter_config = model_dir / "adapter_config.json"
        if not adapter_config.exists() or not adapter_config.is_file():
            checks.append({
                "name": "adapter_config_exists",
                "passed": False,
                "detail": f"Not found: {adapter_config}",
            })
        else:
            checks.append({
                "name": "adapter_config_exists",
                "passed": True,
                "detail": f"Found: {adapter_config}",
            })

        # Check 2: adapter_model.safetensors (or .npz fallback)
        safetensors = model_dir / "adapter_model.safetensors"
        npz = model_dir / "adapter_model.npz"
        if safetensors.exists() and safetensors.is_file():
            checks.append({
                "name": "adapter_weights_exist",
                "passed": True,
                "detail": f"Found: {safetensors}",
            })
        elif npz.exists() and npz.is_file():
            checks.append({
                "name": "adapter_weights_exist",
                "passed": True,
                "detail": f"Found (npz fallback): {npz}",
            })
        else:
            checks.append({
                "name": "adapter_weights_exist",
                "passed": False,
                "detail": f"Neither {safetensors} nor {npz} found",
            })

        # Check 3: training_metadata.json with status field
        meta_path = model_dir / "training_metadata.json"
        if not meta_path.exists() or not meta_path.is_file():
            checks.append({
                "name": "training_metadata_exists",
                "passed": False,
                "detail": f"Not found: {meta_path}",
            })
            return checks

        try:
            meta = json.loads(meta_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            checks.append({
                "name": "training_metadata_valid",
                "passed": False,
                "detail": f"Could not read/parse metadata: {exc}",
            })
            return checks

        if meta.get("status") != "complete":
            checks.append({
                "name": "metadata_status_complete",
                "passed": False,
                "detail": f"training_metadata.json status must be 'complete', got '{meta.get('status')}'",
            })
        else:
            checks.append({
                "name": "metadata_status_complete",
                "passed": True,
                "detail": "Training status is 'complete'",
            })

        return checks

    # -- evaluate --------------------------------------------------------

    def _validate_evaluate(self, niche: str) -> List[Dict[str, Any]]:
        """Validate evaluate stage: evaluation JSON with required metrics."""
        checks: List[Dict[str, Any]] = []
        eval_dir = self._root / "artifacts" / "evaluations"

        # Check 1: at least one evaluation JSON file exists
        eval_files = list(eval_dir.glob(f"{niche}_*.json"))
        if len(eval_files) == 0:
            checks.append({
                "name": "eval_file_exists",
                "passed": False,
                "detail": f"No evaluation files matching {niche}_*.json in {eval_dir}",
            })
            return checks

        # Use the first matching file
        eval_file = eval_files[0]
        checks.append({
            "name": "eval_file_exists",
            "passed": True,
            "detail": f"Found: {eval_file}",
        })

        # Check 2: file contains JSON with required metric keys
        try:
            eval_data = json.loads(eval_file.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            checks.append({
                "name": "eval_json_valid",
                "passed": False,
                "detail": f"Could not read/parse {eval_file}: {exc}",
            })
            return checks

        required_keys = ["accuracy", "perplexity", "latency"]
        missing_keys = [k for k in required_keys if k not in eval_data]
        if missing_keys:
            checks.append({
                "name": "eval_required_metrics",
                "passed": False,
                "detail": f"Missing required metrics: {missing_keys}",
            })
        else:
            checks.append({
                "name": "eval_required_metrics",
                "passed": True,
                "detail": f"All required metrics present: accuracy={eval_data.get('accuracy')}, "
                          f"perplexity={eval_data.get('perplexity')}, latency={eval_data.get('latency')}",
            })

        return checks

    # -- distill ---------------------------------------------------------

    def _validate_distill(self, niche: str) -> List[Dict[str, Any]]:
        """Validate distill stage: loss log exists with non-increasing trend."""
        checks: List[Dict[str, Any]] = []
        loss_path = self._root / "artifacts" / "distill" / f"{niche}_loss.json"

        # Check 1: loss file exists
        if not loss_path.exists() or not loss_path.is_file():
            checks.append({
                "name": "loss_file_exists",
                "passed": False,
                "detail": f"Not found: {loss_path}",
            })
            return checks

        checks.append({
            "name": "loss_file_exists",
            "passed": True,
            "detail": f"Found: {loss_path}",
        })

        # Check 2: loss values form a non-increasing trend
        try:
            loss_data = json.loads(loss_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            checks.append({
                "name": "loss_file_valid",
                "passed": False,
                "detail": f"Could not read/parse loss file: {exc}",
            })
            return checks

        # Extract loss values — support {"losses": [...]} or direct list
        if isinstance(loss_data, dict):
            losses = loss_data.get("losses", loss_data.get("loss", []))
        elif isinstance(loss_data, list):
            losses = loss_data
        else:
            checks.append({
                "name": "loss_trend_decreasing",
                "passed": False,
                "detail": f"Loss data is not a list or dict with 'losses' key",
            })
            return checks

        if len(losses) < 2:
            checks.append({
                "name": "loss_trend_decreasing",
                "passed": True,
                "detail": f"Only {len(losses)} data point(s); trend cannot be verified",
            })
            return checks

        # Allow up to 10% of steps to increase by <= 5% each
        increase_count = 0
        significant_increase_count = 0
        max_allowed_increases = max(1, int(len(losses) * 0.10))

        for i in range(1, len(losses)):
            prev_val = losses[i - 1]
            curr_val = losses[i]
            if curr_val > prev_val:
                increase_count += 1
                # Check if increase is > 5% of previous value
                if prev_val > 0 and (curr_val - prev_val) / prev_val > 0.05:
                    significant_increase_count += 1

        if significant_increase_count > 0:
            checks.append({
                "name": "loss_trend_decreasing",
                "passed": False,
                "detail": f"{significant_increase_count} step(s) increased by more than 5% "
                          f"(out of {increase_count} total increases in {len(losses)} steps)",
            })
        elif increase_count > max_allowed_increases:
            checks.append({
                "name": "loss_trend_decreasing",
                "passed": False,
                "detail": f"{increase_count} increases exceed the {max_allowed_increases} allowed "
                          f"(10% of {len(losses)} steps)",
            })
        else:
            checks.append({
                "name": "loss_trend_decreasing",
                "passed": True,
                "detail": f"Non-increasing trend confirmed: {increase_count} allowable increase(s) "
                          f"in {len(losses)} steps",
            })

        return checks

    # -- quantize --------------------------------------------------------

    def _validate_quantize(self, niche: str) -> List[Dict[str, Any]]:
        """Validate quantize stage: FP4 export files, manifest, and SGFP4 v2 artifacts.

        Checks:
        1. fp4_dir_exists — the fp4 output directory exists
        2. fp4_weights_exist — at least one .npz, .safetensors, or .sgfp4 file
        3. manifest_exists — manifest.json exists
        4. sgfp4_binary_exists — the {niche}.sgfp4 v2 binary exists (warning if missing)
        5. magic_header_valid — .sgfp4 file starts with b'SGF4' + 0x02
        6. manifest_sha256_valid — manifest fp4_binary.sha256 matches .sgfp4 file hash
        7. manifest_required_fields — QUANT-03 required fields present in manifest
        """
        checks: List[Dict[str, Any]] = []
        fp4_dir = self._root / "models" / "specialists_mlx" / niche / "fp4"

        # Check 1: fp4 directory exists
        if not fp4_dir.exists() or not fp4_dir.is_dir():
            checks.append({
                "name": "fp4_dir_exists",
                "passed": False,
                "detail": f"Directory not found: {fp4_dir}",
            })
            return checks

        checks.append({
            "name": "fp4_dir_exists",
            "passed": True,
            "detail": f"Directory exists: {fp4_dir}",
        })

        # Check 2: at least one .npz, .safetensors, or .sgfp4 file
        weight_files = (
            list(fp4_dir.glob("*.npz"))
            + list(fp4_dir.glob("*.safetensors"))
            + list(fp4_dir.glob("*.sgfp4"))
        )
        if len(weight_files) == 0:
            checks.append({
                "name": "fp4_weights_exist",
                "passed": False,
                "detail": f"No .npz, .safetensors, or .sgfp4 files in {fp4_dir}",
            })
        else:
            checks.append({
                "name": "fp4_weights_exist",
                "passed": True,
                "detail": f"Found {len(weight_files)} weight file(s): "
                          f"{[f.name for f in weight_files]}",
            })

        # Check 3: manifest.json exists
        manifest = fp4_dir / "manifest.json"
        manifest_exists = manifest.exists() and manifest.is_file()
        if not manifest_exists:
            checks.append({
                "name": "manifest_exists",
                "passed": False,
                "detail": f"Not found: {manifest}",
            })
        else:
            checks.append({
                "name": "manifest_exists",
                "passed": True,
                "detail": f"Found: {manifest}",
            })

        # --- SGFP4 v2 checks (additive; v1-only output still passes) ---------

        # Check 4: sgfp4 binary existence (v2-specific)
        sgfp4_path = fp4_dir / f"{niche}.sgfp4"
        sgfp4_exists = sgfp4_path.exists() and sgfp4_path.is_file()
        if sgfp4_exists:
            checks.append({
                "name": "sgfp4_binary_exists",
                "passed": True,
                "detail": f"Found: {sgfp4_path}",
            })
        else:
            # Not a failure — v1 .fp4 files are still valid quantize output
            checks.append({
                "name": "sgfp4_binary_exists",
                "passed": True,
                "detail": "No .sgfp4 v2 binary found (v1-only export is valid)",
            })

        # Check 5: magic header validation (only if .sgfp4 exists)
        if sgfp4_exists:
            self._check_sgfp4_magic_header(checks, sgfp4_path)

        # Check 6: manifest SHA256 validation (if manifest and .sgfp4 both exist)
        if manifest_exists and sgfp4_exists:
            self._check_manifest_sha256(checks, manifest, sgfp4_path)

        # Check 7: manifest required fields (if manifest exists)
        if manifest_exists:
            self._check_manifest_required_fields(checks, manifest)

        return checks

    def _check_sgfp4_magic_header(
        self,
        checks: List[Dict[str, Any]],
        sgfp4_path: Path,
    ) -> None:
        """Validate the SGFP4 v2 magic header (b'SGF4' + 0x02)."""
        try:
            with open(sgfp4_path, "rb") as fh:
                header_bytes = fh.read(5)
        except OSError as exc:
            checks.append({
                "name": "magic_header_valid",
                "passed": False,
                "detail": f"Could not read {sgfp4_path}: {exc}",
            })
            return

        if len(header_bytes) < 5:
            checks.append({
                "name": "magic_header_valid",
                "passed": False,
                "detail": f"File too short for SGFP4 header: {len(header_bytes)} bytes",
            })
            return

        actual_magic = header_bytes[:4]
        actual_version = header_bytes[4]

        if actual_magic != self._kSgfp4Magic:
            checks.append({
                "name": "magic_header_valid",
                "passed": False,
                "detail": f"Expected magic b'SGF4', got {actual_magic}",
            })
            return

        if actual_version != self._kSgfp4Version:
            checks.append({
                "name": "magic_header_valid",
                "passed": False,
                "detail": f"Expected version 0x02, got {actual_version:#04x}",
            })
            return

        checks.append({
            "name": "magic_header_valid",
            "passed": True,
            "detail": "Magic SGF4 + version 0x02",
        })

    def _check_manifest_sha256(
        self,
        checks: List[Dict[str, Any]],
        manifest_path: Path,
        sgfp4_path: Path,
    ) -> None:
        """Verify manifest fp4_binary.sha256 matches the .sgfp4 file content hash."""
        # Read manifest
        try:
            manifest_data = json.loads(manifest_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            checks.append({
                "name": "manifest_sha256_valid",
                "passed": False,
                "detail": f"Could not read manifest: {exc}",
            })
            return

        fp4_binary = manifest_data.get("fp4_binary")
        if not isinstance(fp4_binary, dict):
            checks.append({
                "name": "manifest_sha256_valid",
                "passed": True,
                "detail": "No fp4_binary object in manifest (backward compatible)",
            })
            return

        manifest_hash = fp4_binary.get("sha256")
        if manifest_hash is None:
            checks.append({
                "name": "manifest_sha256_valid",
                "passed": True,
                "detail": "No sha256 field in manifest fp4_binary (backward compatible)",
            })
            return

        # Compute SHA256 of .sgfp4 binary (streaming, 64 KiB chunks)
        try:
            file_hash = self._file_sha256(sgfp4_path)
        except OSError as exc:
            checks.append({
                "name": "manifest_sha256_valid",
                "passed": False,
                "detail": f"Could not hash {sgfp4_path}: {exc}",
            })
            return

        if file_hash == manifest_hash:
            checks.append({
                "name": "manifest_sha256_valid",
                "passed": True,
                "detail": "SHA256 matches",
            })
        else:
            checks.append({
                "name": "manifest_sha256_valid",
                "passed": False,
                "detail": f"Manifest SHA256 {manifest_hash} does not match file SHA256 {file_hash}",
            })

    def _check_manifest_required_fields(
        self,
        checks: List[Dict[str, Any]],
        manifest_path: Path,
    ) -> None:
        """Validate QUANT-03 required fields in manifest.json."""
        try:
            manifest_data = json.loads(manifest_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            checks.append({
                "name": "manifest_required_fields",
                "passed": False,
                "detail": f"Could not read manifest: {exc}",
            })
            return

        missing_fields = [
            field for field in self._kQuantManifestRequiredFields
            if field not in manifest_data
        ]

        if missing_fields:
            checks.append({
                "name": "manifest_required_fields",
                "passed": False,
                "detail": f"Missing required fields: {missing_fields}",
            })
        else:
            checks.append({
                "name": "manifest_required_fields",
                "passed": True,
                "detail": f"All {len(self._kQuantManifestRequiredFields)} required fields present",
            })

    @staticmethod
    def _file_sha256(file_path: Path) -> str:
        """Compute the SHA256 hex digest of a file (streaming, 64 KiB chunks)."""
        sha = hashlib.sha256()
        with open(file_path, "rb") as fh:
            while True:
                chunk = fh.read(CheckpointValidator._kSha256ChunkSize)
                if not chunk:
                    break
                sha.update(chunk)
        return sha.hexdigest()

    # ------------------------------------------------------------------
    # Checkpoint lifecycle (read / write / clear)
    # ------------------------------------------------------------------

    def is_complete(self, niche: str, stage: str) -> bool:
        """Check if a validated checkpoint exists for the given niche/stage.

        Returns ``True`` only when a JSON checkpoint file exists and its
        ``passed`` field is ``true``.
        """
        path = self.checkpoint_path(niche, stage)
        if not path.exists() or not path.is_file():
            return False

        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            logger.warning("Could not read checkpoint %s: %s", path, exc)
            return False

        result = StageValidationResult.from_dict(data)
        return result.passed

    def mark_complete(
        self,
        niche: str,
        stage: str,
        result: StageValidationResult,
    ) -> None:
        """Write a validated checkpoint file to disk.

        Sets *result.completed_at* to the current UTC timestamp and writes
        the JSON to ``artifacts/.checkpoints/{niche}/{stage}.json``.

        Raises:
            OSError: If the checkpoint cannot be written (disk full, etc.).
        """
        result.completed_at = datetime.now(timezone.utc).isoformat()
        path = self.checkpoint_path(niche, stage)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps(result.to_dict(), indent=2, ensure_ascii=False),
            encoding="utf-8",
        )

    def clear_checkpoint(self, niche: str, stage: str) -> None:
        """Remove the checkpoint file for a single niche/stage, if it exists."""
        path = self.checkpoint_path(niche, stage)
        try:
            if path.exists():
                path.unlink()
        except OSError as exc:
            logger.warning("Could not clear checkpoint %s: %s", path, exc)

    def clear_all_checkpoints(self, niche: str) -> None:
        """Remove all checkpoint files for a given niche (used by --force)."""
        niche_dir = self.checkpoint_dir / niche
        if not niche_dir.exists() or not niche_dir.is_dir():
            return

        for child in niche_dir.iterdir():
            try:
                if child.is_file():
                    child.unlink()
            except OSError as exc:
                logger.warning(
                    "Could not clear checkpoint %s: %s", child, exc
                )

        # Try to remove the niche directory if empty
        try:
            niche_dir.rmdir()
        except OSError:
            pass
