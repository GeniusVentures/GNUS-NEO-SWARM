"""Pipeline runner — sequential DAG with subprocess execution and validated checkpoints.

Executes the 7-stage training/distillation pipeline for each specialist niche
via subprocess, capturing stdout/stderr and checking exit codes. Integrates
with CheckpointValidator for per-stage output validation before marking a
stage complete.
"""

from __future__ import annotations

import argparse
import logging
import subprocess
import sys
import time
import traceback
from pathlib import Path
from typing import Dict, List, NamedTuple, Optional

from pipeline.checkpoint import CheckpointValidator, StageValidationResult

logger = logging.getLogger(__name__)


class StageResult(NamedTuple):
    """Outcome of a single pipeline stage execution.

    Attributes:
        stage: Stage name (e.g., "train").
        niche: Specialist niche name (e.g., "code").
        success: Whether the stage completed successfully (exit 0).
        exit_code: Process exit code, or -1 if an exception occurred.
        stdout: Captured stdout from the subprocess.
        stderr: Captured stderr from the subprocess.
        attempts: Number of execution attempts (1 + retries).
    """

    stage: str
    niche: str
    success: bool
    exit_code: int
    stdout: str
    stderr: str
    attempts: int


#: Command-line argument templates keyed by stage name.
#: Each value is a list of argv entries; ``{niche}`` is replaced at runtime.
_STAGE_COMMANDS: Dict[str, List[str]] = {
    "data_prep": ["data/scripts/prepare_datasets.py", "--niche", "{niche}"],
    "synthetic_data": ["distill/synthetic.py", "--niche", "{niche}"],
    "dedup": ["training/dedup.py", "--niche", "{niche}"],
    "train": ["training/train_specialists_mlx.py", "--niche", "{niche}"],
    "evaluate": ["eval/evaluator.py", "--niche", "{niche}"],
    "distill": ["distill/distillation.py", "--niche", "{niche}"],
    "quantize": ["quantize/fp4_exporter.py", "--niche", "{niche}"],
}


class PipelineRunner:
    """Orchestrates the 7-stage pipeline for all specialist niches.

    Loads configuration from YAML, executes each stage via subprocess with
    stdout/stderr capture, validates outputs with CheckpointValidator, and
    supports --force and --from-stage flags for checkpoint control.
    """

    STAGES = [
        "data_prep",
        "synthetic_data",
        "dedup",
        "train",
        "evaluate",
        "distill",
        "quantize",
    ]

    # Defaults when config is missing or incomplete.
    _kDefaultRetryCount: int = 1
    _kDefaultBackoffSeconds: float = 5.0
    _kDefaultStageTimeout: int = 3600  # 1 hour per stage

    def __init__(
        self,
        project_root: Optional[Path] = None,
        config_path: Optional[Path] = None,
    ):
        """Initialize the pipeline runner.

        Args:
            project_root: Root directory of the gnus-poc project.
                Defaults to the parent of this file's directory.
            config_path: Path to ``pipeline.yaml``. Defaults to
                ``{project_root}/config/pipeline.yaml``.
        """
        if project_root is None:
            project_root = Path(__file__).resolve().parent.parent
        self._root: Path = project_root

        if config_path is None:
            config_path = project_root / "config" / "pipeline.yaml"
        self._config_path: Path = config_path

        # Load configuration.
        self._config: dict = {}
        self._stage_retry_count: int = self._kDefaultRetryCount
        self._stage_backoff_seconds: float = self._kDefaultBackoffSeconds
        self._load_config()

        # Checkpoint validator for output validation.
        self._checkpoint = CheckpointValidator(self._root)

    # ------------------------------------------------------------------
    # Configuration
    # ------------------------------------------------------------------

    def _load_config(self) -> None:
        """Load pipeline configuration from YAML file."""
        try:
            import yaml  # noqa: F811 — may be used by caller; imported here to avoid top-level dependency

            with self._config_path.open("r", encoding="utf-8") as f:
                self._config = yaml.safe_load(f) or {}
        except Exception as exc:
            logger.warning("Could not load config from %s: %s", self._config_path, exc)
            self._config = {}

        pipeline_cfg = self._config.get("pipeline", {})
        self._stage_retry_count = pipeline_cfg.get(
            "stage_retry_count", self._kDefaultRetryCount
        )
        self._stage_backoff_seconds = pipeline_cfg.get(
            "stage_backoff_seconds", self._kDefaultBackoffSeconds
        )

    # ------------------------------------------------------------------
    # Public entry point
    # ------------------------------------------------------------------

    def run(
        self,
        niche: Optional[str] = None,
        from_stage: Optional[str] = None,
        force: bool = False,
    ) -> None:
        """Run the pipeline for all niches (or a single niche).

        Args:
            niche: Run for a single specialist niche. If ``None``, runs for
                all niches listed in ``pipeline.yaml``.
            from_stage: Stage name to resume from (inclusive). Earlier stages
                are skipped if their checkpoints exist.
            force: If ``True``, clear all checkpoints and re-run every stage.
        """
        niches: List[str] = [niche] if niche else self._load_niches()
        start_idx: int = self._stage_index(from_stage) if from_stage else 0

        for n in niches:
            print(f"\n{'=' * 60}\nPipeline: {n.upper()}\n{'=' * 60}")

            # --force: clear all existing checkpoints for this niche.
            if force:
                self._checkpoint.clear_all_checkpoints(n)
                print(f"  [force] Cleared all checkpoints for {n}")

            niche_aborted = False
            for i in range(start_idx, len(self.STAGES)):
                stage = self.STAGES[i]

                # Skip if checkpoint exists and not forcing.
                if not force and self._is_complete(n, stage):
                    print(f"  [{stage}] Skipped (complete)")
                    continue

                result = self._run_stage(n, stage)

                if result.success:
                    # Validate outputs and mark checkpoint.
                    validation = self._checkpoint.validate_stage(n, stage)
                    passed_count = sum(
                        1 for c in validation.checks if c.get("passed", False)
                    )
                    total_count = len(validation.checks)
                    print(
                        f"  [{stage}] Checkpoint validation: {validation.passed} "
                        f"({passed_count}/{total_count} checks passed)"
                    )

                    if validation.passed:
                        self._checkpoint.mark_complete(n, stage, validation)
                    else:
                        print(f"  [{stage}] Validation FAILED — checkpoint not written")
                elif not result.success:
                    print(f"  [{stage}] FAILED — continuing to next niche")
                    # Per D-10: niche failure does not abort the entire pipeline.
                    # The niche_aborted flag below handles non-retryable errors.
                    # For stage execution failures (non-zero exit), continue to
                    # next stage in this niche — don't abort the niche.
                    pass

                # FileNotFoundError (script not found) is handled inside
                # _run_stage and returns success=False — the niche may be
                # partially aborted; subsequent stages will also fail. That's
                # acceptable — we continue to the next niche.
            # End stage loop
        # End niche loop

    # ------------------------------------------------------------------
    # Stage execution
    # ------------------------------------------------------------------

    def _run_stage(self, niche: str, stage: str) -> StageResult:
        """Execute a single pipeline stage for the given niche via subprocess.

        Handles retry, timeout, and per-D-10 error-type classification.
        """
        cmd = self._build_command(niche, stage)
        cmd_str = " ".join(cmd)
        print(f"  [{stage}] Executing: {cmd_str}")

        max_attempts = self._stage_retry_count + 1
        last_result: Optional[StageResult] = None

        for attempt in range(max_attempts):
            if attempt > 0:
                print(
                    f"  [{stage}] Retry {attempt}/{self._stage_retry_count}..."
                )
                time.sleep(self._stage_backoff_seconds)

            try:
                proc = subprocess.run(
                    cmd,
                    cwd=str(self._root),
                    capture_output=True,
                    text=True,
                    timeout=self._kDefaultStageTimeout,
                )

                result = StageResult(
                    stage=stage,
                    niche=niche,
                    success=(proc.returncode == 0),
                    exit_code=proc.returncode,
                    stdout=proc.stdout or "",
                    stderr=proc.stderr or "",
                    attempts=attempt + 1,
                )

                if result.success:
                    self._print_success_output(stage, result)
                    return result

                # Non-zero exit — print failure details.
                self._print_failure_output(stage, result)
                last_result = result
                # Fall through to retry loop.

            except subprocess.TimeoutExpired:
                print(f"  [{stage}] TIMEOUT after {self._kDefaultStageTimeout}s")
                last_result = StageResult(
                    stage=stage,
                    niche=niche,
                    success=False,
                    exit_code=-1,
                    stdout="",
                    stderr=f"Timeout after {self._kDefaultStageTimeout}s",
                    attempts=attempt + 1,
                )

            except FileNotFoundError:
                # Script not found — abort this niche entirely, but don't abort
                # the pipeline. Print a clear error and return failure.
                print(f"  [{stage}] Script not found: {cmd[1]}")
                return StageResult(
                    stage=stage,
                    niche=niche,
                    success=False,
                    exit_code=-1,
                    stdout="",
                    stderr=f"Script not found: {cmd[1]}",
                    attempts=attempt + 1,
                )

            except KeyboardInterrupt:
                # User abort — re-raise immediately.
                print(f"\n  [{stage}] Aborted by user")
                raise

            except Exception:
                # Unexpected exception — abort this niche, continue to next.
                print(f"  [{stage}] Unexpected error:")
                traceback.print_exc()
                return StageResult(
                    stage=stage,
                    niche=niche,
                    success=False,
                    exit_code=-1,
                    stdout="",
                    stderr=traceback.format_exc(),
                    attempts=attempt + 1,
                )

        # All attempts exhausted.
        return last_result if last_result is not None else StageResult(
            stage=stage,
            niche=niche,
            success=False,
            exit_code=-1,
            stdout="",
            stderr="No attempts executed",
            attempts=0,
        )

    def _build_command(self, niche: str, stage: str) -> List[str]:
        """Build the subprocess command list for a given niche and stage.

        Uses ``sys.executable`` for the Python interpreter so the same
        environment is used for subprocess stages.
        """
        if stage not in _STAGE_COMMANDS:
            raise ValueError(f"Unknown stage '{stage}'. Valid: {self.STAGES}")

        template = _STAGE_COMMANDS[stage]
        return [sys.executable] + [arg.replace("{niche}", niche) for arg in template]

    @staticmethod
    def _print_success_output(stage: str, result: StageResult) -> None:
        """Print a summary of successful stage output."""
        lines = result.stdout.strip().splitlines()
        print(f"  [{stage}] Complete (exit 0)")
        if lines:
            preview_lines = lines[:3]
            for line in preview_lines:
                truncated = line[:200] + ("..." if len(line) > 200 else "")
                print(f"    stdout: {truncated}")

    @staticmethod
    def _print_failure_output(stage: str, result: StageResult) -> None:
        """Print diagnostic information for a failed stage."""
        print(f"  [{stage}] FAILED (exit {result.exit_code})")
        stderr_lines = result.stderr.strip().splitlines()
        if stderr_lines:
            tail_lines = stderr_lines[-10:]
            for line in tail_lines:
                print(f"    stderr: {line}")

    # ------------------------------------------------------------------
    # Niche loading
    # ------------------------------------------------------------------

    def _load_niches(self) -> List[str]:
        """Load the list of specialist niches from configuration."""
        pipeline_cfg = self._config.get("pipeline", {})
        niches = pipeline_cfg.get("specialists", [])
        if isinstance(niches, list) and niches:
            return niches

        # Fallback to defaults.
        logger.warning("No specialists found in config; using defaults")
        return ["medical", "qa_technical", "code", "encyclopedic", "patents"]

    # ------------------------------------------------------------------
    # Stage index helper
    # ------------------------------------------------------------------

    def _stage_index(self, stage_name: str) -> int:
        """Return the zero-based index of *stage_name* in ``STAGES``.

        Returns 0 if the name is not found (treat unknown as start).
        """
        try:
            return self.STAGES.index(stage_name)
        except ValueError:
            return 0

    # ------------------------------------------------------------------
    # Checkpoint delegation
    # ------------------------------------------------------------------

    def _is_complete(self, niche: str, stage: str) -> bool:
        """Check whether a validated checkpoint exists for this niche/stage."""
        return self._checkpoint.is_complete(niche, stage)

    def _mark_complete(self, niche: str, stage: str) -> None:
        """Validate stage outputs and write a checkpoint file if they pass."""
        result = self._checkpoint.validate_stage(niche, stage)
        passed_count = sum(
            1 for c in result.checks if c.get("passed", False)
        )
        total_count = len(result.checks)
        print(
            f"  [{stage}] Checkpoint validation: {result.passed} "
            f"({passed_count}/{total_count} checks passed)"
        )
        if result.passed:
            self._checkpoint.mark_complete(niche, stage, result)


# ------------------------------------------------------------------
# CLI entry point
# ------------------------------------------------------------------


def main() -> None:
    """Parse command-line arguments and run the pipeline."""
    parser = argparse.ArgumentParser(
        description="GNUS-POC Pipeline Runner — execute the 7-stage training/distillation pipeline"
    )
    parser.add_argument(
        "--niche",
        type=str,
        default=None,
        help="Run for a single specialist niche (default: all from config)",
    )
    parser.add_argument(
        "--from-stage",
        type=str,
        default=None,
        help="Start execution from a specific stage name (e.g., train, evaluate)",
    )
    parser.add_argument(
        "--config",
        type=str,
        default=None,
        help="Path to pipeline config YAML (default: config/pipeline.yaml)",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        default=False,
        help="Force re-run all stages, clearing existing checkpoints",
    )
    args = parser.parse_args()

    config_path = Path(args.config) if args.config else None
    runner = PipelineRunner(config_path=config_path)
    runner.run(niche=args.niche, from_stage=args.from_stage, force=args.force)


if __name__ == "__main__":
    main()
