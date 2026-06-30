"""Logit-based knowledge distillation from teacher to student."""

import argparse
import hashlib
import json
import logging
import math
import re
import sys
from pathlib import Path
from typing import Optional

import numpy as np

logger = logging.getLogger(__name__)

# D-02 defaults for convergence thresholds. These are module-level constants so
# callers constructing a ConvergenceTracker can reference them without magic
# numbers.
DEFAULT_TARGET = 2.5
DEFAULT_WARNING = 3.0
DEFAULT_HARD_STOP = 5.0
DEFAULT_PATIENCE = 100
DEFAULT_MIN_DELTA = 0.01
DEFAULT_WINDOW_SIZE = 20

# DIST-03 default for the synthetic-quality minimum example length (in tokens).
DEFAULT_MIN_EXAMPLE_LENGTH = 50


class DistillationAbortedError(RuntimeError):
    """Raised when the convergence tracker reports a hard_stop (D-04)."""


def check_synthetic_quality(
    examples: list,
    min_length: int = DEFAULT_MIN_EXAMPLE_LENGTH,
) -> list:
    """Filter synthetic training examples by quality (DIST-03).

    Quality gates applied, in order:
        1. Non-empty / non-whitespace.
        2. Token count (``len(text.split())``) >= ``min_length``.
        3. Deduplication by normalized SHA256 (lowercased + whitespace-collapsed).

    Args:
        examples: Raw synthetic text examples.
        min_length: Minimum token count required to keep an example.

    Returns:
        Filtered list of accepted examples (order preserved).
    """
    accepted: list = []
    seen_hashes: set = set()
    for text in examples:
        if text is None:
            continue
        if not isinstance(text, str) or not text.strip():
            logger.warning("Filtered empty/whitespace synthetic example")
            continue
        if len(text.split()) < min_length:
            logger.warning(
                "Filtered synthetic example below min_length=%d", min_length
            )
            continue
        normalized = re.sub(r"\s+", " ", text.lower()).strip()
        digest = hashlib.sha256(normalized.encode("utf-8")).hexdigest()
        if digest in seen_hashes:
            logger.warning("Filtered duplicate synthetic example")
            continue
        seen_hashes.add(digest)
        accepted.append(text)
    return accepted


class Distiller:
    def __init__(
        self,
        temperature: float = 2.0,
        alpha: float = 0.5,
        convergence_tracker: Optional["object"] = None,
    ):
        self._temperature = temperature
        self._alpha = alpha
        self._tracker = convergence_tracker

    def compute_distillation_loss(
        self,
        student_logits: np.ndarray,
        teacher_logprobs: list,
        target_ids: list,
    ) -> float:
        if student_logits is None or not teacher_logprobs:
            return float("inf")

        ce_loss = self._cross_entropy_loss(student_logits, target_ids)
        kd_loss = self._kl_divergence_loss(student_logits, teacher_logprobs)
        return self._alpha * kd_loss + (1.0 - self._alpha) * ce_loss

    def _cross_entropy_loss(self, logits: np.ndarray, target_ids: list) -> float:
        logits = np.atleast_2d(logits)
        if logits.shape[0] != len(target_ids):
            return float("inf")

        logits_scaled = logits / self._temperature
        log_probs = logits_scaled - np.log(np.sum(np.exp(logits_scaled), axis=-1, keepdims=True))
        loss = 0.0
        for i, t in enumerate(target_ids):
            if 0 <= t < log_probs.shape[1]:
                loss += log_probs[i, t]
        return -loss / len(target_ids)

    def _kl_divergence_loss(self, student_logits: np.ndarray, teacher_logprobs: list) -> float:
        student_logits = np.atleast_2d(student_logits)
        student_scaled = student_logits / self._temperature
        student_log_probs = student_scaled - np.log(np.sum(np.exp(student_scaled), axis=-1, keepdims=True))

        seq_len = min(len(student_log_probs), len(teacher_logprobs))
        loss = 0.0
        for i in range(seq_len):
            t_logprobs = teacher_logprobs[i]
            if isinstance(t_logprobs, dict):
                t_probs = {int(k): math.exp(v) for k, v in t_logprobs.items()}
            elif isinstance(t_logprobs, list):
                vocab_size = student_log_probs.shape[1]
                t_probs = dict(enumerate(t_logprobs[:vocab_size]))
            else:
                continue
            for token_id, prob in t_probs.items():
                if 0 <= token_id < student_log_probs.shape[1]:
                    loss += prob * (math.log(max(prob, 1e-10)) - student_log_probs[i, token_id])
        return loss / seq_len if seq_len > 0 else 0.0

    def sweep_temperature(
        self,
        student_logits: np.ndarray,
        teacher_logprobs: list,
        target_ids: list,
        temperatures: Optional[list] = None,
        niche: Optional[str] = None,
        output_dir: Optional[object] = None,
    ) -> dict:
        if temperatures is None:
            temperatures = [1.0, 2.0, 4.0, 6.0, 8.0, 10.0]

        results = {}
        best_temp = temperatures[0]
        best_loss = float("inf")

        for temp in temperatures:
            self._temperature = temp
            loss = self.compute_distillation_loss(student_logits, teacher_logprobs, target_ids)
            # A single-step sweep has no convergence history; expose the same
            # shape as a multi-step sweep so consumers do not need a second
            # parser. converged_at_step is None because there was no tracker.
            results[str(temp)] = {
                "loss": round(loss, 6),
                "final_loss": round(loss, 6),
                "losses": [round(loss, 6)],
                "converged_at_step": getattr(self._tracker, "converged_at_step", None)
                if self._tracker is not None
                else None,
            }
            if loss < best_loss:
                best_loss = loss
                best_temp = temp

        sweep_result = {
            "temperatures": results,
            "best_temperature": best_temp,
            "best_loss": round(best_loss, 6),
        }

        # D-05: structured JSON output to artifacts/sweeps/{niche}_sweep.json.
        if output_dir is not None and niche is not None:
            out_dir = Path(output_dir)
            out_dir.mkdir(parents=True, exist_ok=True)
            # Sanitize the niche name so it cannot traverse directories
            # (T-02-02 mitigation). Keep it filesystem-safe.
            safe_niche = re.sub(r"[^A-Za-z0-9._-]", "_", niche)
            sweep_file = out_dir / f"{safe_niche}_sweep.json"
            payload = {
                "niche": niche,
                "best_temperature": sweep_result["best_temperature"],
                "temperatures": sweep_result["temperatures"],
            }
            with sweep_file.open("w") as f:
                json.dump(payload, f, indent=2)
            logger.info("Wrote temperature sweep JSON to %s", sweep_file)

        return sweep_result

    def run_distillation(self, batches: list) -> list:
        """Run the distillation loop over a list of training batches.

        Each batch is a ``(student_logits, teacher_logprobs, target_ids)``
        tuple. When a ConvergenceTracker is attached (``self._tracker``) each
        loss is fed to the tracker and the loop reacts to its status:

            ``continue``   — keep training.
            ``warning``    — log and keep training.
            ``converged``  — log and return early.
            ``early_stop`` — log and return early.
            ``hard_stop``  — log an error and raise DistillationAbortedError.

        When no tracker is attached the loop computes a loss for every batch
        (backward compatible with the pre-convergence Distiller).

        Args:
            batches: List of ``(student_logits, teacher_logprobs, target_ids)``.

        Returns:
            List of per-batch loss values (possibly truncated by early stop).
        """
        losses: list = []
        for step, (student_logits, teacher_logprobs, target_ids) in enumerate(batches):
            loss = self.compute_distillation_loss(
                student_logits, teacher_logprobs, target_ids
            )
            losses.append(loss)

            if self._tracker is None:
                continue

            status = self._tracker.step(loss, step)
            if status == "continue":
                continue
            elif status == "warning":
                logger.warning(
                    "Distillation warning at step %d: loss=%.6f", step, loss
                )
            elif status == "converged":
                logger.info(
                    "Distillation converged at step %d: loss=%.6f", step, loss
                )
                return losses
            elif status == "early_stop":
                logger.info(
                    "Distillation early-stopped at step %d (plateau): loss=%.6f",
                    step, loss,
                )
                return losses
            elif status == "hard_stop":
                logger.error(
                    "Distillation hard-stop at step %d: loss=%.6f exceeds threshold",
                    step, loss,
                )
                raise DistillationAbortedError(
                    f"Hard-stop threshold exceeded at step {step} (loss={loss:.6f})"
                )
        return losses


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run knowledge distillation for a specialist")
    parser.add_argument("--niche", required=True, help="Specialist niche name")
    parser.add_argument(
        "--sweep-output-dir",
        default=None,
        help="Directory for structured temperature sweep JSON (default: artifacts/sweeps/)",
    )
    args = parser.parse_args()

    project_root = Path(__file__).resolve().parent.parent
    distiller = Distiller()

    # Produce a minimal loss log — real loss computation requires model + data
    loss_log = {
        "niche": args.niche,
        "losses": [float("inf")],
        "note": "Placeholder — run with model and tokenizer for real KD loss",
    }

    out_dir = project_root / "artifacts" / "distill"
    out_dir.mkdir(parents=True, exist_ok=True)
    with (out_dir / f"{args.niche}_loss.json").open("w") as f:
        json.dump(loss_log, f, indent=2)

    # D-05: when a sweep output dir is requested, ensure the structured sweep
    # directory exists so downstream tooling can find {niche}_sweep.json.
    sweep_dir = args.sweep_output_dir or str(project_root / "artifacts" / "sweeps")
    Path(sweep_dir).mkdir(parents=True, exist_ok=True)
    print(f"Distillation {args.niche}: loss log written (sweep dir: {sweep_dir})")
