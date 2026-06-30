"""Post-training adapter validation (Phase 2, Plan 02-03).

Multi-prong adapter validity check per decisions D-06 (held-out test set,
NOT training val_batches) and D-08 (three checks: loadability, validation
loss, behavioral difference; objective vs. subjective error tracking).

The validator is fail-open: MLX load failures and inference errors are
captured into the result dict rather than raised, so the pipeline runner
can branch on ``overall_valid`` and the status flags without a try/except
wrapper (T-02-10 mitigation). Logging is used in place of print() per
project convention.
"""

import logging
from pathlib import Path
from typing import Optional

from mlx_lm import utils as mlx_utils

logger = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).resolve().parent.parent

# Jaccard similarity at/above this value means the adapter behaves like the
# base model (no learned behavioral difference). Per D-08 / Pattern 2.
DEFAULT_BEHAVIORAL_DIFF_THRESHOLD = 0.95

# Number of test prompts used for the behavioral-difference inference check.
BEHAVIORAL_DIFF_SAMPLE_COUNT = 5


def validate_adapter(
    model_id: str,
    adapter_path: str,
    test_samples: list,
    loss_threshold: float,
    behavioral_diff_threshold: float = DEFAULT_BEHAVIORAL_DIFF_THRESHOLD,
) -> dict:
    """Run the multi-prong adapter validity check (D-06, D-08).

    Three checks run in sequence; each writes into the returned result dict:
      (a) Loadability -- ``mlx_utils.load(model_id, adapter_path=...)`` must
          succeed. On failure the function returns early with ``load_error``
          set and the remaining checks flagged invalid (T-02-10 mitigation).
      (b) Validation loss -- cross-entropy loss on the held-out test set must
          be <= ``loss_threshold``.
      (c) Behavioral difference -- token-level Jaccard similarity between base
          and adapter outputs on the first ``BEHAVIORAL_DIFF_SAMPLE_COUNT``
          samples must be < ``behavioral_diff_threshold``.

    Objective errors (wrong facts/code/math vs. a known label) are tracked
    separately from subjective differences (style/tone/phrasing with no
    ground truth). See D-08.

    Args:
        model_id: HuggingFace/MLX identifier of the base model.
        adapter_path: Filesystem path to the trained LoRA adapter directory.
        test_samples: Held-out test split (list of dicts with at least a
            ``text`` key; optional ``label``/``ground_truth`` for objective
            error tracking).
        loss_threshold: Max acceptable validation loss (per specialist, D-07).
        behavioral_diff_threshold: Jaccard similarity at or above which the
            adapter is considered behaviorally identical to the base model.

    Returns:
        dict with keys: loadable, load_error, validation_loss, loss_valid,
        jaccard_similarity, behavioral_diff, objective_errors,
        subjective_diffs, overall_valid.
    """
    result = {
        "loadable": False,
        "load_error": None,
        "validation_loss": None,
        "loss_valid": False,
        "jaccard_similarity": None,
        "behavioral_diff": False,
        "objective_errors": 0,
        "subjective_diffs": 0,
        "overall_valid": False,
    }

    # (a) Loadability check — fail-open on any exception (T-02-10).
    try:
        model, tokenizer = mlx_utils.load(model_id, adapter_path=adapter_path)
        result["loadable"] = True
    except Exception as exc:  # noqa: BLE001 — fail-open per threat model
        result["load_error"] = str(exc)
        logger.warning(
            "Adapter loadability check failed for %s: %s", adapter_path, exc
        )
        return result

    # (b) Validation loss check on held-out test set (D-06: NOT val_batches).
    validation_loss = _compute_validation_loss(model, tokenizer, test_samples)
    result["validation_loss"] = validation_loss
    result["loss_valid"] = (
        validation_loss is not None and validation_loss <= loss_threshold
    )

    # (c) Behavioral difference check (base vs. adapter on N prompts).
    base_model, _ = mlx_utils.load(model_id)  # no adapter
    diff_samples = test_samples[:BEHAVIORAL_DIFF_SAMPLE_COUNT]
    jaccard = _compute_jaccard_similarity(base_model, model, tokenizer, diff_samples)
    result["jaccard_similarity"] = jaccard
    result["behavioral_diff"] = (
        jaccard is not None and jaccard < behavioral_diff_threshold
    )

    # Objective vs. subjective error tracking (D-08).
    error_counts = _track_objective_errors(model, tokenizer, test_samples)
    result["objective_errors"] = error_counts["objective_errors"]
    result["subjective_diffs"] = error_counts["subjective_diffs"]

    result["overall_valid"] = all(
        [result["loadable"], result["loss_valid"], result["behavioral_diff"]]
    )
    return result


def _compute_validation_loss(model, tokenizer, test_samples: list) -> Optional[float]:
    """Mean cross-entropy loss over the held-out test set.

    Uses the SpecialistEvaluator pattern (forward pass per sample, average
    perplexity-derived loss). Returns None if no sample yields a usable
    loss so the caller can record the missing metric without crashing.
    """
    import mlx.core as mx
    from mlx.nn import loss as mlx_loss

    if not test_samples:
        return None

    losses = []
    for sample in test_samples:
        text = sample.get("text", "")
        if not text:
            continue
        try:
            tokens = tokenizer.encode(text)
            if len(tokens) < 2:
                continue
            inputs = mx.array(tokens[:-1])
            targets = mx.array(tokens[1:])
            logits = model(inputs[None])
            loss_val = mlx_loss.cross_entropy(logits[0], targets)
            losses.append(float(loss_val))
        except Exception as exc:  # noqa: BLE001 — skip bad sample (T-02-11)
            logger.debug("Skipping sample for loss computation: %s", exc)
            continue

    if not losses:
        return None
    return sum(losses) / len(losses)


def _compute_jaccard_similarity(
    base_model, adapter_model, tokenizer, samples: list
) -> Optional[float]:
    """Token-level Jaccard similarity between base and adapter outputs.

    Runs generation on each sample with both models, tokenizes the outputs
    into token sets, and averages the pairwise Jaccard index. Returns None
    if no sample produces a comparable output pair.
    """
    from mlx_lm import generate

    if not samples:
        return None

    similarities = []
    for sample in samples:
        prompt = sample.get("text", "")
        if not prompt:
            continue
        try:
            base_out = generate(base_model, tokenizer, prompt=prompt, max_tokens=32)
            adapter_out = generate(
                adapter_model, tokenizer, prompt=prompt, max_tokens=32
            )
            base_tokens = set(tokenizer.encode(base_out))
            adapter_tokens = set(tokenizer.encode(adapter_out))
            if not base_tokens and not adapter_tokens:
                continue
            union = base_tokens | adapter_tokens
            if not union:
                continue
            intersection = base_tokens & adapter_tokens
            similarities.append(len(intersection) / len(union))
        except Exception as exc:  # noqa: BLE001 — skip bad sample (T-02-10)
            logger.debug("Skipping sample for Jaccard computation: %s", exc)
            continue

    if not similarities:
        return None
    return sum(similarities) / len(similarities)


def _track_objective_errors(adapter_model, tokenizer, test_samples: list) -> dict:
    """Count objective errors vs. subjective differences (D-08).

    Objective errors: a sample carries a ``label`` or ``ground_truth`` key and
    the adapter output does not match it (wrong facts/code/math).
    Subjective differences: outputs differ but no ground truth is available
    to verify (style/tone/phrasing).

    Args:
        adapter_model: The LoRA-adapted model.
        tokenizer: The model tokenizer.
        test_samples: Held-out test split; samples may optionally carry a
            ``label`` or ``ground_truth`` key.

    Returns:
        dict with keys ``objective_errors`` and ``subjective_diffs``.
    """
    from mlx_lm import generate

    objective_errors = 0
    subjective_diffs = 0

    for sample in test_samples:
        prompt = sample.get("text", "")
        if not prompt:
            continue
        ground_truth = sample.get("label", sample.get("ground_truth"))
        try:
            output = generate(
                adapter_model, tokenizer, prompt=prompt, max_tokens=32
            )
        except Exception as exc:  # noqa: BLE001 — skip bad sample (T-02-10)
            logger.debug("Skipping sample for objective error tracking: %s", exc)
            continue

        if ground_truth is not None:
            if str(ground_truth).strip() not in output:
                objective_errors += 1
        else:
            # No ground truth — any non-empty output is a subjective signal.
            if output.strip():
                subjective_diffs += 1

    return {"objective_errors": objective_errors, "subjective_diffs": subjective_diffs}
