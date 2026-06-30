# Phase 2: Training & Distillation Quality - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-06-21
**Phase:** 02-training-distillation-quality
**Areas discussed:** KD convergence & temperature sweeping, Training quality validation, Router rule design (GQHSM-compatible), Evaluation → training feedback

---

## KD Convergence & Temperature Sweeping

| Option | Description | Selected |
|--------|-------------|----------|
| Global distill_loss_target | Single threshold for all specialists | |
| Per-specialist distill_loss_target | Different thresholds per niche difficulty | ✓ |
| Hard stop only | Single threshold, training halts when exceeded | |
| Two-tier (warning + hard stop) | Warning logs and continues, hard stop halts | ✓ |

**User's choice:** Per-specialist thresholds. Two-tier stopping (warning + hard stop). Convergence definition and early stopping algorithm → researcher to find best practices from ML literature. Patience configurable per specialist. Temperature sweep produces per-specialist JSON analysis files with per-temperature convergence curves + best temperature.

**Notes:** User explicitly wants research-driven approach for convergence criteria and early stopping — not opinionated defaults.

---

## Training Quality Validation

| Option | Description | Selected |
|--------|-------------|----------|
| Reuse training val_batches | Use existing validation from training run | |
| Separate post-training validation | Independent pass on held-out test set | ✓ |
| Global validation threshold | Single threshold for all specialists | |
| Per-specialist validation threshold | Different thresholds per specialist | ✓ |
| Loss threshold only | Single metric for adapter validity | |
| Multi-prong (loadability + loss + behavioral) | Three checks for adapter quality | ✓ |

**User's choice:** Separate post-training validation pass for independent analysis. Per-specialist thresholds. Multi-prong validity: loadability, validation loss, behavioral change — with subjective differences (style/tone) treated differently from objective errors (facts/code).

**Notes:** User emphasized the separate validation pass enables analysis of "how to do better" — this is a learning feedback mechanism, not just a gate.

---

## Router Rule Design (GQHSM-Compatible)

| Option | Description | Selected |
|--------|-------------|----------|
| Direct GQHSM C++ integration | Wrap C++ library in Python | |
| Python-native + GQHSM-compatible JSON | Lightweight Python SM, JSON contract | ✓ |
| Simple if/else chain | Hardcoded classification logic | |
| Full state machine | States, transitions, triggers, guards | ✓ |
| No fallback | Single specialist selection per query | |
| Fallback chaining | Cascade through specialists on low confidence | ✓ |

**User's choice:** Python-native lightweight state machine consuming GQHSM-compatible JSON rule definitions. JSON is the compatibility contract — future C++ integration feeds same JSON to GQHSM directly. Rule types: keyword, regex, syntax density with priority ordering. Fallback chaining mirrors Phase 1 teacher cascade pattern.

**Notes:** GQHSM submodule already at repo root. User confirmed rule format with states and transitions. Side discussion on Python vs C++ GQHSM: agreed Python-native runtime is right for POC, JSON format provides future-proofing.

---

## Evaluation → Training Feedback

| Option | Description | Selected |
|--------|-------------|----------|
| Manual review only | Human checks all evaluation results | |
| Automatic gating only | Thresholds block pipeline automatically | |
| Automatic gating + parallel human review | Gates auto-block, severe outliers → human | ✓ |
| Static thresholds | Fixed per-metric thresholds | |
| LLM-adaptive thresholds | API can recursively update thresholds | ✓ |
| Variance from threshold | Outlier = deviation from fixed threshold | |
| Variance from prior run | Outlier = deviation from previous result | ✓ |
| Human review blocks pipeline | Review must complete before continuing | |
| Human review runs in parallel | Non-blocking, concurrent with pipeline | ✓ |

**User's choice:** Per-metric, per-specialist auto-gate thresholds. LLM API can recursively update thresholds adaptively. Variance from prior run triggers logging + parallel human review (non-blocking). Auto-gating blocks pipeline only after N configurable consecutive failures. Single failures log and continue.

**Notes:** User emphasized human review should not block — execute in parallel conversation. Only persistent degradation (N consecutive failures) triggers a block. This balances quality assurance with pipeline throughput.

---

## Claude's Discretion

- Lightweight Python state machine library choice (transitions, automaton, or custom)
- Convergence definition and early stopping algorithm implementation (after research)
- Default threshold values and patience defaults
- JSON rule file schema design (GQHSM-compatible subset)
- Adapter behavioral validation test design
- Evaluation metric persistence format and schema
- LLM-based threshold update mechanism and prompt design

## Deferred Ideas

- ML-based/learned router classification — Phase 2 is rules-based only
- Full autonomous threshold optimization without LLM — future enhancement
- Direct GQHSM C++ runtime integration — belongs to parent GNUS-NEO-SWARM C++ repo
- Full epistemic arbitration pipeline (Sanskrit, Kripke, hybrid frameworks) — parent C++ repo
