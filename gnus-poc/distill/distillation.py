"""Logit-based knowledge distillation from teacher to student."""

import argparse
import json
import math
import sys
from pathlib import Path
from typing import Optional

import numpy as np


class Distiller:
    def __init__(self, temperature: float = 2.0, alpha: float = 0.5):
        self._temperature = temperature
        self._alpha = alpha

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
    ) -> dict:
        if temperatures is None:
            temperatures = [1.0, 2.0, 4.0, 6.0, 8.0, 10.0]

        results = {}
        best_temp = temperatures[0]
        best_loss = float("inf")

        for temp in temperatures:
            self._temperature = temp
            loss = self.compute_distillation_loss(student_logits, teacher_logprobs, target_ids)
            results[str(temp)] = round(loss, 6)
            if loss < best_loss:
                best_loss = loss
                best_temp = temp

        return {
            "temperatures": results,
            "best_temperature": best_temp,
            "best_loss": round(best_loss, 6),
        }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run knowledge distillation for a specialist")
    parser.add_argument("--niche", required=True, help="Specialist niche name")
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
    print(f"Distillation {args.niche}: loss log written")
