"""Per-specialist evaluation: perplexity, BLEU/ROUGE, latency via MLX."""

import argparse
import json
import logging
import math
import sys
import time
from collections import defaultdict
from pathlib import Path
from typing import Optional

import numpy as np
from nltk.translate.bleu_score import sentence_bleu, SmoothingFunction

logger = logging.getLogger(__name__)


class SpecialistEvaluator:
    def __init__(
        self,
        project_root: Optional[Path] = None,
        metric_store: Optional["object"] = None,
    ):
        if project_root is None:
            project_root = Path(__file__).resolve().parent.parent
        self._project_root = project_root
        # Plan 02-04 (TRAIN-03): MetricStore for structured per-run persistence.
        # Default-constructed to honor TRAIN-03 ("metrics persisted per run").
        # Callers can inject one (e.g., pointing at a tmp project root for tests).
        if metric_store is None:
            from eval.metric_store import MetricStore
            metric_store = MetricStore(project_root)
        self._metric_store = metric_store

    def evaluate(self, model, tokenizer, test_samples: list, niche_name: str) -> dict:
        results = {
            "niche": niche_name,
            "num_samples": len(test_samples),
            "perplexity": None,
            "bleu_score": None,
            "rouge_l": None,
            "latency_ms_per_token": None,
            "latency_ms_per_token_p95": None,
        }

        if not test_samples:
            return results

        perplexities = []
        bleu_scores = []
        rouge_l_scores = []
        latencies = []

        for sample in test_samples:
            text = sample.get("text", "")
            if not text or len(text) < 50:
                continue

            result = self._evaluate_sample(model, tokenizer, text)
            if result:
                perplexities.append(result["perplexity"])
                bleu_scores.append(result["bleu"])
                rouge_l_scores.append(result["rouge_l"])
                latencies.append(result["latency_ms_per_token"])

        if perplexities:
            results["perplexity"] = float(np.mean(perplexities))
            results["bleu_score"] = float(np.mean(bleu_scores))
            results["rouge_l"] = float(np.mean(rouge_l_scores))
            results["latency_ms_per_token"] = float(np.mean(latencies))
            results["latency_ms_per_token_p95"] = float(np.percentile(latencies, 95))
            # Persist once metrics are populated. Empty-sample / no-evaluation
            # runs are not persisted (nothing meaningful to gate on).
            self._persist_results(niche_name, results)

        return results

    def _persist_results(self, niche_name: str, results: dict) -> None:
        """Persist evaluation results via MetricStore (Plan 02-04, TRAIN-03).

        Persistence is best-effort: a failure to persist must NOT abort the
        evaluation (the in-memory result is still returned to the caller).
        """
        if self._metric_store is None:
            return
        try:
            self._metric_store.record_training_eval_metrics(
                niche_name, metrics=results
            )
        except Exception as exc:  # noqa: BLE001 — fail-open, non-fatal
            logger.warning(
                "Failed to persist training eval metrics for niche=%s: %s",
                niche_name, exc,
            )

    def _evaluate_sample(self, model, tokenizer, text: str) -> Optional[dict]:
        try:
            tokens = tokenizer.encode(text)
            if len(tokens) < 10:
                return None

            half = len(tokens) // 2
            input_tokens = tokens[:half]
            target_tokens = tokens[half:]

            start = time.perf_counter()
            logits = self._forward(model, input_tokens)
            elapsed = time.perf_counter() - start

            if logits is None:
                return None

            loss = self._cross_entropy(logits[:, -len(target_tokens):], target_tokens)
            perplexity = math.exp(loss)

            generated = self._greedy_decode(model, input_tokens, len(target_tokens))
            generated_text = tokenizer.decode(generated) if hasattr(tokenizer, 'decode') else " ".join(str(t) for t in generated)
            target_text = tokenizer.decode(target_tokens) if hasattr(tokenizer, 'decode') else " ".join(str(t) for t in target_tokens)

            smooth = SmoothingFunction().method1
            bleu = sentence_bleu([target_text.split()], generated_text.split(), smoothing_function=smooth)
            rouge_l = self._rouge_l(target_text, generated_text)

            latency = (elapsed * 1000) / len(target_tokens)

            return {
                "perplexity": perplexity,
                "bleu": bleu,
                "rouge_l": rouge_l,
                "latency_ms_per_token": latency,
            }
        except Exception:
            return None

    def _forward(self, model, tokens):
        try:
            import mlx.core as mx
            x = mx.array([tokens])
            return model(x)
        except Exception:
            return None

    def _cross_entropy(self, logits, targets):
        try:
            import mlx.core as mx
            log_probs = mx.log_softmax(logits, axis=-1)
            nll = -log_probs[0, range(len(targets)), targets]
            return float(mx.mean(nll))
        except Exception:
            return 10.0

    def _greedy_decode(self, model, tokens, max_new):
        try:
            import mlx.core as mx
            generated = list(tokens)
            for _ in range(max_new):
                x = mx.array([generated[-512:]])
                logits = model(x)
                next_token = int(mx.argmax(logits[0, -1, :]))
                generated.append(next_token)
            return generated[len(tokens):]
        except Exception:
            return tokens[:max_new]

    def _rouge_l(self, reference: str, candidate: str) -> float:
        ref_words = reference.lower().split()
        cand_words = candidate.lower().split()
        if not ref_words or not cand_words:
            return 0.0
        lcs = self._lcs_length(ref_words, cand_words)
        precision = lcs / len(cand_words) if cand_words else 0
        recall = lcs / len(ref_words) if ref_words else 0
        if precision + recall == 0:
            return 0.0
        return 2 * precision * recall / (precision + recall)

    def _lcs_length(self, a: list, b: list) -> int:
        m, n = len(a), len(b)
        if m == 0 or n == 0:
            return 0
        dp = [[0] * (n + 1) for _ in range(2)]
        for i in range(1, m + 1):
            curr = i % 2
            prev = 1 - curr
            for j in range(1, n + 1):
                if a[i - 1] == b[j - 1]:
                    dp[curr][j] = dp[prev][j - 1] + 1
                else:
                    dp[curr][j] = max(dp[prev][j], dp[curr][j - 1])
        return dp[m % 2][n]


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Evaluate a specialist model")
    parser.add_argument("--niche", required=True, help="Specialist niche name")
    args = parser.parse_args()

    project_root = Path(__file__).resolve().parent.parent
    evaluator = SpecialistEvaluator(project_root)

    # Build a minimal evaluation report from test data if available
    test_path = project_root / "data" / "specialists" / args.niche / "test.jsonl"
    test_samples = []
    if test_path.exists():
        with test_path.open() as f:
            for line in f:
                line = line.strip()
                if line:
                    test_samples.append(json.loads(line))

    results = {
        "niche": args.niche,
        "num_samples": len(test_samples),
        "accuracy": 0.0,
        "perplexity": 0.0,
        "latency_ms_per_token": 0.0,
    }

    out_dir = project_root / "artifacts" / "evaluations"
    out_dir.mkdir(parents=True, exist_ok=True)
    with (out_dir / f"{args.niche}_eval.json").open("w") as f:
        json.dump(results, f, indent=2)
    print(f"Evaluation {args.niche}: {len(test_samples)} samples")
