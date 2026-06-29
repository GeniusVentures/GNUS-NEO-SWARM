# Phase 2: Training & Distillation Quality - Research

**Researched:** 2026-06-29
**Domain:** Knowledge Distillation Convergence / LoRA Specialist Training / Rules-Based Routing
**Confidence:** HIGH

## Summary

Phase 2 hardens three existing prototype modules (`Distiller`, `train_specialists_mlx.py`, `SpecialistEvaluator`) and introduces one greenfield module (Router). The Distiller gains convergence tracking with two-tier early stopping (warning + hard-stop) and structured temperature sweep output. The LoRA trainer adds a post-training validation pass on held-out test data with multi-prong adapter validity checks. The evaluator gains per-specialist metric persistence and auto-gating with consecutive-failure counters. The new Router implements a GQHSM-compatible rules-based classifier using keyword/regex/syntax-density matching with fallback chaining mirroring the existing TeacherCascade pattern.

All modules already exist in prototypical form and integrate with Phase 1 outputs (TeacherClient, cascade, checkpoint system, two-layer config). The primary work is adding convergence criteria, persistence, validation gates, and the router -- not rewriting existing code.

**Primary recommendation:** Extend existing modules with surgical additions (convergence tracking in Distiller, validation pass in trainer, metric persistence in evaluator) rather than rewrites. Use `transitions` 0.9.3 (already installed) for the router's lightweight Python state machine runtime -- its hierarchical states, conditional transitions, and YAML loading capabilities map directly to the GQHSM conceptual model required by D-10.

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| KD loss computation + convergence tracking | Pipeline (Python) | -- | Runs in training pipeline; no external services |
| Temperature sweep with per-specialist analysis | Pipeline (Python) | -- | File-based output to artifacts/sweeps/ |
| LoRA adapter training | Pipeline (Python) | MLX runtime | Uses mlx-lm.lora.train_model; weights saved to disk |
| Post-training validation (held-out test set) | Pipeline (Python) | -- | Runs locally after training completes; reads test split |
| Adapter validity checks (loadability, loss, behavioral) | Pipeline (Python) | MLX runtime | Loads adapters via MLX; runs inference |
| Evaluation metric computation (PPL, BLEU, ROUGE-L, latency) | Pipeline (Python) | -- | SpecialistEvaluator computes metrics locally |
| Metric persistence (JSON per run) | Pipeline (Python) | File I/O | Writes to artifacts/evaluations/ |
| Auto-gating with consecutive-failure counters | Pipeline (Python) | -- | Gate state persisted to artifacts/.gate_state/ |
| Query classification (keyword, regex, syntax density) | Router (Python) | -- | Pure Python; no external API calls |
| Specialist selection and fallback chaining | Router (Python) | TeacherClient | Can consult teacher API for confidence checks |
| Router rule YAML loading | Config layer | -- | ConfigLoader pattern from Phase 1 |

## User Constraints (from CONTEXT.md)

### Locked Decisions
- **D-01:** `distill_loss_target` is per-specialist, configurable in `config/specialists/<niche>.yaml`.
- **D-02:** Convergence definition and early stopping algorithm --> researcher. Study ML literature best practices for KD convergence criteria (loss < target for N consecutive steps vs final loss only) and effective early stopping (plateau detection, patience-based).
- **D-03:** Patience (steps without improvement before stopping) configurable per specialist.
- **D-04:** Two-tier stopping: **warning threshold** (log + continue training) and **hard-stop threshold** (halt training entirely). Both thresholds --> researcher to recommend effective defaults.
- **D-05:** Temperature sweep produces per-specialist JSON analysis file at `artifacts/sweeps/<niche>_sweep.json` containing: per-temperature loss curves, convergence rate per temperature, and identified best temperature.
- **D-06:** Separate post-training validation pass on a held-out test set (not reused from training `val_batches`).
- **D-07:** Validation loss threshold per specialist, configurable in `config/specialists/<niche>.yaml`.
- **D-08:** Multi-prong adapter validity check: (a) loadability -- adapter weights load cleanly via MLX, (b) validation loss -- below configured per-specialist threshold, (c) behavioral -- inference output differs from base model. Subjective differences tracked separately from objective errors. Objective errors are more severe.
- **D-09:** Python-native lightweight state machine runtime that consumes GQHSM-compatible JSON rule definitions. The JSON is the compatibility contract.
- **D-10:** Rule format mirrors GQHSM's conceptual model: states, transitions, trigger conditions (keyword, regex, token density), guards (confidence checks, domain constraints), actions (select specialist, log classification).
- **D-11:** Rule types support keyword matching, regex patterns, syntax density heuristics, with configurable priority ordering. Rules defined in YAML, no code changes required to add/modify rules.
- **D-12:** Fallback chaining: if primary specialist classification has confidence below threshold, try next-best match. Mirrors the Phase 1 teacher cascade pattern.
- **D-13:** GQHSM submodule at repo root (`GQHSM/`) -- reference StateProto and conceptual model for JSON schema design.
- **D-14:** Automatic gating with per-metric, per-specialist thresholds. Each specialist has pass/fail gates on its domain-relevant metrics.
- **D-15:** LLM API can recursively update gate thresholds based on observed performance trends.
- **D-16:** Variance from prior run (metric delta) is logged for trend analysis. Severe outliers trigger parallel human review -- logged as a notification, does NOT block pipeline execution.
- **D-17:** Auto-gating only blocks the pipeline after N configurable consecutive failures for the same specialist. Single failures log and continue.

### Claude's Discretion
- Choice of lightweight Python state machine library (`transitions`, `automaton`, or custom implementation)
- Convergence definition specifics and early stopping algorithm implementation
- Default threshold values and patience defaults
- JSON rule file schema design (GQHSM-compatible subset)
- Adapter behavioral validation test design (how to measure "different output")
- Evaluation metric persistence format and schema
- LLM-based threshold update mechanism and prompt design

### Deferred Ideas (OUT OF SCOPE)
- Learned router (ML-based classification)
- Dynamic threshold evolution from evaluation data (full autonomous optimization without LLM)
- GQHSM C++ integration (Python POC uses lightweight Python state machine)
- Epistemic arbitration (full GQHSM pipeline)

## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| DIST-01 | KD Loss Convergence -- configurable alpha, loss below `distill_loss_target` | See "KD Convergence Criteria" pattern; two-tier stopping with patience |
| DIST-02 | Temperature Sweeping -- configurable temps, per-temperature loss curves logged | Extends existing `sweep_temperature()`; adds structured JSON output |
| DIST-03 | Synthetic Data Quality -- min length, no empty, deduplication | Extends existing dedup pipeline; adds quality checks before training |
| TRAIN-01 | LoRA Adapter Validity -- loadable, different from base, metadata recorded | See "Adapter Validity Check" pattern; extends `train_specialists_mlx.py` |
| TRAIN-02 | Hyperparameter Configurability -- YAML-driven, per-specialist overrides, validation | ConfigLoader pattern from Phase 1; invalid combos caught at load |
| TRAIN-03 | Evaluation Metrics -- accuracy, perplexity, latency, persisted per run | Extends `SpecialistEvaluator` and `MetricStore` patterns |
| ROUTE-01 | Rule-Based Query Classification -- keyword, regex, syntax density, YAML-driven | `transitions` library + GQHSM-compatible JSON schema |
| ROUTE-02 | Specialist Selection and Execution Plan -- maps classification to specialist, produces plan | Router produces execution plan with mode and specialist from classification |

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| `mlx-lm` | 0.28.4 (installed) | LoRA training, model loading, inference | Already used by `train_specialists_mlx.py` and `SpecialistEvaluator` |
| `transitions` | 0.9.3 (installed) | Lightweight hierarchical state machine for router runtime | Supports YAML config loading, hierarchical states, conditional transitions/guards -- maps directly to GQHSM conceptual model; already installed |
| `pyyaml` | 6.0.2 (installed) | YAML config loading/validation | Already used across entire pipeline; router rules in YAML |
| `numpy` | (installed) | Numerical ops for loss computation | Already used in Distiller and Evaluator |
| `datasets` | (installed) | HF dataset loading | Already used in `train_specialists_mlx.py` |
| `nltk` | (installed) | BLEU score smoothing | Already used in `SpecialistEvaluator` |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| `python-statemachine` | 3.2.0 (PyPI) | Alternative state machine with AsyncIO, validation | If `transitions` cannot be used; provides YAML via optional `[io]` extra, richer validation |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| `transitions` 0.9.3 | `python-statemachine` 3.2.0 | `transitions` already installed, has hierarchical states and YAML loading. `python-statemachine` has async support (unneeded for sync router) but requires separate `[io]` install for YAML. Either works; `transitions` wins on "already installed." |
| `transitions` 0.9.3 | Custom state machine class | Custom adds 200+ lines of tested logic (state tracking, transition dispatch, guard evaluation, serialization). `transitions` handles all of this in a library already vetted by years of community use. |
| `SpecialistEvaluator` static methods | Dedicated eval persistence class | `MetricStore` (Phase 4) already provides structured persistence. Extend it for training evaluation metrics rather than creating a new persistence class. |

**Installation:**
```bash
# All core libraries already installed. If transitions were missing:
pip install transitions
```

**Version verification:**
```bash
pip show transitions mlx-lm pyyaml nltk datasets | grep -E "^(Name|Version)"
```
- `transitions`: 0.9.3 (verified installed)
- `mlx-lm`: 0.28.4 (verified installed)
- `pyyaml`: 6.0.2 (verified installed)
- `nltk`: (installed, used by SpecialistEvaluator)

## Package Legitimacy Audit

> slopcheck failed to run despite being installed (returned JSON parse error). All packages verified via pip index + pip show instead.

| Package | Registry | Age | Downloads | Source Repo | slopcheck | Disposition |
|---------|----------|-----|-----------|-------------|-----------|-------------|
| `transitions` | PyPI | 9+ yrs (v0.1 to v0.9.3, 2025) | N/A | github.com/pytransitions/transitions | [ASSUMED] | Approved -- installed, v0.9.3 confirmed |
| `python-statemachine` | PyPI | 9+ yrs (v0.1.0 2017 to v3.2.0 2026) | N/A | github.com/fgmacedo/python-statemachine | [ASSUMED] | Alternative only -- not primary recommendation |
| `mlx-lm` | PyPI | 2+ yrs | N/A | github.com/ml-explore/mlx-lm | [ASSUMED] | Approved -- already installed, v0.28.4 confirmed |
| `pyyaml` | PyPI | 15+ yrs | N/A | github.com/yaml/pyyaml | [ASSUMED] | Approved -- already installed, v6.0.2 confirmed |

**Packages removed due to slopcheck [SLOP] verdict:** none
**Packages flagged as suspicious [SUS]:** none

*slopcheck was unavailable at research time; all packages above tagged `[ASSUMED]`. Planner must gate each install behind a `checkpoint:human-verify` task.*

## Architecture Patterns

### System Architecture Diagram

```
                        .planning/workstreams/poc/REQUIREMENTS.md DIST-01..03, TRAIN-01..03, ROUTE-01..02

                        ┌─────────────────────────────────────────────────────────────────┐
                        │                        PIPELINE ORCHESTRATOR                      │
                        │                     (Phase 1: pipeline/runner.py)                 │
                        └───────┬──────────────┬───────────────┬───────────────┬───────────┘
                                │              │               │               │
                   ┌────────────▼──┐  ┌────────▼──────┐  ┌─────▼──────┐  ┌─────▼──────────┐
                   │  DISTILLATION  │  │   TRAINING    │  │ EVALUATION │  │    ROUTER      │
                   │   (extended)   │  │   (extended)  │  │ (extended) │  │  (greenfield)  │
                   └───────┬────────┘  └───────┬───────┘  └─────┬──────┘  └─────┬──────────┘
                           │                   │                │               │
        ┌──────────────────┼───────────────────┼────────────────┼───────────────┼──────────────┐
        │                  │                   │                │               │              │
        ▼                  ▼                   ▼                ▼               ▼              ▼
┌──────────────┐  ┌──────────────────┐  ┌──────────────┐  ┌──────────────┐  ┌──────────────────┐
│ KD Loss +    │  │ LoRA Training    │  │ PPL/BLEU/    │  │ MetricStore  │  │ Query → Rule     │
│ Convergence  │  │ via mlx-lm.lora  │  │ ROUGE-L      │  │ (Phase 4)    │  │ Match → State    │
│ Tracker      │  │ .train_model()   │  │ Latency      │  │              │  │ Transition       │
└──────┬───────┘  └────────┬─────────┘  └──────┬───────┘  └──────┬───────┘  └────────┬─────────┘
       │                   │                   │                │                    │
       │  ┌────────────────┼───────────────────┼────────────────┼────────────────────┼──────┐
       │  │                │                   │                │                    │      │
       ▼  ▼                ▼                   ▼                ▼                    ▼      ▼
┌────────────────┐  ┌──────────────────┐  ┌──────────────┐  ┌──────────────┐  ┌──────────────────┐
│ artifacts/     │  │ models/          │  │ artifacts/    │  │ artifacts/   │  │ GQHSM-compatible │
│ distill/       │  │ specialists_mlx/ │  │ evaluations/  │  │ .gate_state/ │  │ JSON rule file   │
│ {niche}_loss.  │  │ {niche}/         │  │ {niche}_{ts}. │  │ {niche}_     │  │ router_rules.    │
│ json           │  │ adapters.        │  │ json          │  │ gate_state.  │  │ json             │
│ artifacts/     │  │ safetensors      │  │               │  │ json         │  │                  │
│ sweeps/        │  │ adapter_config.  │  │               │  │              │  │                  │
│ {niche}_sweep. │  │ json             │  │               │  │              │  │                  │
│ json           │  │ training_        │  │               │  │              │  │                  │
│                │  │ metadata.json    │  │               │  │              │  │                  │
└────────────────┘  └──────────────────┘  └──────────────┘  └──────────────┘  └──────────────────┘

       ┌──────────────────────────────────────────────────────────────────────────────────────┐
       │                              SHARED DEPENDENCIES                                      │
       │  ┌──────────────────┐  ┌──────────────────┐  ┌─────────────────┐  ┌───────────────┐  │
       │  │ TeacherClient    │  │ TeacherCascade   │  │ ConfigLoader    │  │ Checkpoint    │  │
       │  │ (Phase 1)        │  │ (Phase 1)        │  │ (Phase 1)       │  │ System        │  │
       │  │ Multi-backend    │  │ Confidence-gated │  │ Two-layer YAML  │  │ (Phase 1)     │  │
       │  │ API dispatch     │  │ L1→L2 escalation │  │ + overrides     │  │               │  │
       │  └──────────────────┘  └──────────────────┘  └─────────────────┘  └───────────────┘  │
       └──────────────────────────────────────────────────────────────────────────────────────┘
```

### Data Flow: Knowledge Distillation with Convergence

```
config/specialists/{niche}.yaml          TeacherClient (Phase 1)
        │                                        │
        │ distill_loss_target,                   │ logprobs API
        │ distill_loss_warning,                  │
        │ distill_loss_hard_stop,                ▼
        │ patience, min_delta         ┌─────────────────────┐
        │                             │ teacher_logprobs     │
        ▼                             │ + target_ids         │
┌───────────────────┐                 └──────────┬──────────┘
│ Distiller         │                            │
│ (distillation.py) │◄───────────────────────────┘
│                   │
│ compute_          │    per step: loss = α*KL + (1-α)*CE
│ distillation_loss │
│                   │
│ ConvergenceTracker│    ┌──────────────────────────────┐
│ (NEW)             │    │ loss < target for patience    │
│                   │    │ steps? → convergence          │
│  - rolling window │    │ loss < warning? → log         │
│  - patience       │    │ loss > hard_stop? → abort     │
│  - min_delta      │    │ no improvement > patience? →  │
│  - two-tier stop  │    │   early stop                  │
└────────┬──────────┘    └──────────────────────────────┘
         │
         ▼
┌───────────────────┐
│ Sweep Output      │
│ artifacts/sweeps/ │
│ {niche}_sweep.json│
│                   │
│ {                 │
│   "temperatures": │
│     {"1.0": {     │
│       "losses":   │
│       [...],      │
│       "converged_ │
│       at_step": N │
│     }},           │
│   "best_temp": 4.0│
│ }                 │
└───────────────────┘
```

### Data Flow: Rules-Based Router

```
User Query ──────► ┌──────────────────────────────────────┐
                   │          Router (gnus-poc/router/)    │
                   │                                      │
                   │  ┌────────────────────────────┐      │
                   │  │ YAML rule loading           │      │
                   │  │ (config/router_rules.yaml)  │      │
                   │  └──────────┬─────────────────┘      │
                   │             │                        │
                   │             ▼                        │
                   │  ┌────────────────────────────┐      │
                   │  │ GQHSM-Compatible State      │      │
                   │  │ Machine (transitions lib)   │      │
                   │  │                            │      │
                   │  │ States:                    │      │
                   │  │  pre_classify → keyword_   │      │
                   │  │  match → regex_match →     │      │
                   │  │  syntax_density →          │      │
                   │  │  select_specialist →       │      │
                   │  │  fallback_chain            │      │
                   │  │                            │      │
                   │  │ Transitions:               │      │
                   │  │  triggered by rule match   │      │
                   │  │  with guard conditions     │      │
                   │  └──────────┬─────────────────┘      │
                   │             │                        │
                   │             ▼                        │
                   │  ┌────────────────────────────┐      │
                   │  │ Execution Plan Output       │      │
                   │  │ {                          │      │
                   │  │   "primary_specialist":    │      │
                   │  │     "code",                │      │
                   │  │   "execution_mode":        │      │
                   │  │     "single",              │      │
                   │  │   "confidence": 0.85,      │      │
                   │  │   "matched_rule":          │      │
                   │  │     "code_detection",      │      │
                   │  │   "fallback_chain": [...]  │      │
                   │  │ }                          │      │
                   │  └────────────────────────────┘      │
                   └──────────────────────────────────────┘
                                       │
                                       ▼
                              Execution Plan JSON
```

### Recommended Project Structure

```
gnus-poc/
├── config/
│   ├── pipeline.yaml              # Global defaults (already has eval_gates section)
│   ├── router_rules.yaml          # NEW: Router rule definitions
│   ├── router_rules.json          # NEW: GQHSM-compatible JSON export
│   └── specialists/
│       ├── code.yaml              # Extended: +distill_loss_target, +validation_loss_threshold
│       ├── encyclopedic.yaml      # Extended: same additions
│       ├── medical.yaml           # Extended: same additions
│       ├── patents.yaml           # Extended: same additions
│       └── qa_technical.yaml      # Extended: same additions
├── distill/
│   ├── distillation.py            # EXTEND: +ConvergenceTracker, +two-tier stopping
│   └── convergence.py             # NEW: ConvergenceTracker class
├── training/
│   ├── train_specialists_mlx.py   # EXTEND: +post-training validation, +adapter validity checks
│   └── validation.py              # NEW: Post-training validation + adapter checks
├── eval/
│   ├── evaluator.py               # EXTEND: +structured metric persistence per run
│   ├── metric_store.py            # EXTEND: +training eval metrics (beyond SGFP4)
│   └── benchmarker.py             # EXTEND: +per-specialist gating, +trend analysis
├── router/                        # NEW: Greenfield module
│   ├── __init__.py
│   ├── engine.py                  # State machine runtime (consumes GQHSM JSON)
│   ├── rules.py                   # Rule matching (keyword, regex, syntax density)
│   ├── schema.py                  # GQHSM-compatible JSON schema + validation
│   └── classifier.py              # High-level classify() API with fallback chaining
├── artifacts/
│   ├── distill/                   # Existing: {niche}_loss.json
│   ├── sweeps/                    # NEW: {niche}_sweep.json
│   ├── evaluations/               # EXTEND: {niche}_{timestamp}.json per run
│   └── .gate_state/              # EXTEND: training gate state files
└── tests/
    ├── test_convergence.py        # NEW
    ├── test_distillation.py       # EXTEND
    ├── test_training_validation.py # NEW
    ├── test_router_rules.py       # NEW
    └── test_router_engine.py      # NEW
```

### Pattern 1: KD Convergence with Two-Tier Early Stopping

**What:** Monitor KD loss over training steps using a rolling window. Two thresholds: a warning threshold (log + continue) and a hard-stop threshold (halt training). Patience-based early stopping triggered when loss improvement over the rolling window is below `min_delta` for `patience` consecutive steps.

**When to use:** Every distillation run. Configurable per specialist via `config/specialists/<niche>.yaml`.

**Algorithm:**
```
best_loss = inf
no_improvement_steps = 0
for each training step:
    loss = compute_kd_loss(student_logits, teacher_logprobs, target_ids)

    if loss > hard_stop_threshold:
        abort("KD loss exceeded hard-stop threshold")
    if loss > warning_threshold:
        log_warning("loss above warning threshold")

    if loss < best_loss - min_delta:
        best_loss = loss
        no_improvement_steps = 0
    else:
        no_improvement_steps += 1

    if no_improvement_steps >= patience:
        stop_early("convergence plateau detected")

    if loss < distill_loss_target:
        converge("loss below target")
```

**Example config (per specialist):**
```yaml
# config/specialists/code.yaml -- additions
distillation:
  alpha: 0.7                           # KD loss weight (0=CE only, 1=KL only)
  distill_loss_target: 2.5             # Convergence target
  distill_loss_warning: 3.0            # Log warning, continue
  distill_loss_hard_stop: 5.0          # Halt training
  patience: 100                        # Steps without improvement before early stop
  min_delta: 0.01                      # Min improvement to reset patience
```

**Default thresholds (Claude's discretion, per D-04):**
- `distill_loss_target`: 2.5 (MEDIUM confidence -- reasonable for logit-based KD with temperature 2.0-4.0; should be tuned per specialist based on initial loss values)
- `distill_loss_warning`: 3.0 (20% above target -- gives operator visibility without blocking)
- `distill_loss_hard_stop`: 5.0 (2x target -- indicates catastrophic divergence)
- `patience`: 100 (standard for ML training; 100 steps at batch_size=4 is 400 examples)
- `min_delta`: 0.01 (1e-2 -- common default; large enough to filter noise, small enough to detect real improvement)

### Pattern 2: Post-Training Validation Pass

**What:** After LoRA training completes, run inference on a separate held-out test set (NOT the training `val_batches`) to produce an independent quality signal. Check three things: (a) adapter loads cleanly, (b) validation loss below threshold, (c) inference output differs from base model.

**When to use:** After every `train_specialist()` call, before marking training as complete.

**Adapter validity check components:**
1. **Loadability:** `mlx_lm.utils.load(model_id, adapter_path=adapter_path)` must succeed without exceptions.
2. **Validation loss:** Forward pass on test set, compute CE loss, compare to `validation_loss_threshold` in specialist config.
3. **Behavioral difference:** Run inference on 5 test prompts with base model vs. adapter model. Compare outputs using token-level overlap (Jaccard similarity). Outputs must differ (Jaccard < 0.95) to confirm adapter changes behavior.
4. **Objective error tracking:** If test set has labeled answers, compute accuracy. Objective errors (wrong facts, wrong code, wrong math) tracked separately from subjective differences (style, tone, phrasing).

**Example config (per specialist):**
```yaml
# config/specialists/code.yaml -- additions
validation:
  validation_loss_threshold: 3.0       # Max acceptable loss on held-out test
  behavioral_diff_threshold: 0.95      # Jaccard < 0.95 = different output
  test_split_path: "data/specialists/code/test.jsonl"
  min_test_samples: 50                 # Require at least this many test samples
```

### Pattern 3: Rules-Based Router with GQHSM-Compatible State Machine

**What:** A lightweight Python state machine using `transitions` that consumes GQHSM-compatible JSON rule definitions. The state machine walks through classification stages (pre_classify, keyword_match, regex_match, syntax_density, select_specialist, fallback_chain) with guard conditions on each transition. Specialist selection is the terminal action. Fallback chaining mirrors the TeacherCascade pattern from Phase 1.

**When to use:** When classifying incoming queries to route to the appropriate specialist.

**GQHSM-Compatible JSON Schema (subset):**
```json
{
  "states": [
    {"name": "pre_classify"},
    {"name": "keyword_match"},
    {"name": "regex_match"},
    {"name": "syntax_density"},
    {"name": "select_specialist"},
    {"name": "fallback_chain"}
  ],
  "transitions": [
    {
      "trigger": "matched_keywords",
      "source": "keyword_match",
      "dest": "select_specialist",
      "conditions": ["confidence_above_threshold"],
      "unless": [],
      "actions": ["set_specialist_from_match"]
    },
    {
      "trigger": "no_match",
      "source": "keyword_match",
      "dest": "regex_match"
    }
  ],
  "initial": "pre_classify"
}
```

**Rule YAML format (consumed by config loader, serialized to JSON for state machine):**
```yaml
router:
  rules:
    - name: "code_detection"
      priority: 10
      triggers:
        - type: keyword
          patterns: ["def ", "class ", "import ", "```", "function ", "const "]
        - type: syntax_density
          threshold: 0.3
          chars: ["{", "}", "(", ")", ";", "=", "=>", ":"]
      action: select_specialist
      specialist: code
      confidence_threshold: 0.6
      fallback: encyclopedic

    - name: "math_detection"
      priority: 9
      triggers:
        - type: syntax_density
          threshold: 0.3
          chars: ["0","1","2","3","4","5","6","7","8","9","+","-","*","/","=","^"]
        - type: keyword
          patterns: ["solve", "equation", "derivative", "integral", "theorem"]
      action: select_specialist
      specialist: qa_technical
      fallback: encyclopedic

    - name: "medical_detection"
      priority: 8
      triggers:
        - type: keyword
          patterns: ["diagnosis", "symptom", "treatment", "patient", "disease", "medication"]
      action: select_specialist
      specialist: medical
      fallback: encyclopedic

    - name: "patent_detection"
      priority: 7
      triggers:
        - type: keyword
          patterns: ["patent", "claims ", "prior art", "invention", "USPTO"]
      action: select_specialist
      specialist: patents
      fallback: encyclopedic

    - name: "default_encyclopedic"
      priority: 0
      triggers:
        - type: always_match
      action: select_specialist
      specialist: encyclopedic
```

**Fallback chaining implementation (mirrors cascade.py pattern):**
```python
# router/classifier.py
def classify_with_fallback(self, query: str) -> dict:
    """Classify query with fallback chaining (D-12).
    
    Mirrors TeacherCascade.execute() pattern:
    1. Try primary classification rule
    2. If confidence < threshold, try next-best match
    3. Return best result or default
    """
    matches = self.match_all_rules(query)  # returns [(rule, confidence), ...]
    matches.sort(key=lambda m: m[0].priority, reverse=True)
    
    for rule, confidence in matches:
        if confidence >= rule.confidence_threshold:
            return self._build_plan(rule, confidence, mode="single")
    
    # Fallback: try each rule's configured fallback
    for rule, _ in matches:
        if rule.fallback:
            fallback_rule = self._get_rule_by_specialist(rule.fallback)
            if fallback_rule:
                return self._build_plan(fallback_rule, 0.0, mode="fallback")
    
    # Ultimate fallback: encyclopedic
    return self._build_plan(self._get_rule_by_specialist("encyclopedic"), 0.0, mode="fallback")
```

### Anti-Patterns to Avoid
- **Rewriting existing modules:** `Distiller`, `train_specialists_mlx.py`, `SpecialistEvaluator`, and `Benchmarker` already work. Add convergence tracking, validation passes, and persistence -- do not rewrite the core logic.
- **Custom state machine from scratch:** The GQHSM conceptual model (states, transitions, triggers, guards, actions) maps directly to `transitions` library capabilities. Hand-rolling a state machine adds ~200 lines of tested logic for no benefit.
- **Router calling teacher API on every query:** Router classification is purely rules-based (D-09/D-11 explicitly reject learned routing). Teacher API calls for confidence checks should be optional and only invoked when rule confidence is borderline.
- **Combining training + evaluation in one giant function:** The existing pattern separates training (`train_specialists_mlx.py`), evaluation (`evaluator.py`), and distillation (`distillation.py`) into distinct modules. Keep the validation pass as a separate step that the pipeline runner orchestrates.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| State machine runtime for router | Custom state machine class with manual state tracking, transition dispatch, guard evaluation | `transitions` 0.9.3 (already installed) | 9+ years of community testing, handles hierarchical states, conditional transitions, YAML loading, event dispatch. Custom version would be ~200 lines of error-prone logic duplicating a well-tested library. |
| Plateau detection in training | Manual loss tracking with ad-hoc thresholds | ConvergenceTracker with rolling window + patience + min_delta | Standard ML pattern. Rolling window (default 20 steps) smooths noise. Patience with min_delta prevents false stops from minor oscillations. Directly configurable per specialist. |
| YAML schema validation for router rules | Ad-hoc key checking in load function | JSON Schema validation against GQHSM-compatible schema | The JSON is the GQHSM compatibility contract. Schema validation ensures rules are well-formed before the state machine consumes them. Catches misconfigurations at load time. |
| Deduplication of synthetic data | Manual string comparison loop | Normalized text hash (SHA256 of lowercased, whitespace-normalized text) | Already partially implemented in dedup stage. Extend with quality checks (min length, non-empty) before hash computation. |
| Behavioral difference measurement | Manual comparison of outputs | Token-level Jaccard similarity + structured output comparison | Jaccard < 0.95 is a simple, interpretable signal that adapter changes behavior. Paired with objective error tracking for factual accuracy. |

**Key insight:** The router is the only greenfield module. Everything else extends existing code. The state machine is the most "don't hand-roll" risk area -- `transitions` eliminates 200+ lines of custom state management logic.

## Common Pitfalls

### Pitfall 1: KD Loss Oscillation Masking Convergence
**What goes wrong:** KD loss oscillates within a narrow range around the target threshold. The naive "loss < target" check fails because the loss crosses the threshold repeatedly without truly converging.
**Why it happens:** Temperature scaling amplifies small variations in teacher logprobs. Batch-level noise causes loss to fluctuate +/- 0.1-0.3 around the true convergence value.
**How to avoid:** Use a rolling window (20 steps) average for convergence checks, not point values. Require `loss_rolling_avg < target` for `patience` consecutive steps. The `min_delta` parameter filters noise -- improvement must exceed this to reset the patience counter.
**Warning signs:** Loss oscillates in a 0.2-0.5 range without a clear descending trend after 50+ steps.

### Pitfall 2: Adapter Loadability Fails Silently After Training
**What goes wrong:** Training produces `adapters.safetensors` but the file is corrupt or incompatible with the base model, and the error is not detected until inference fails downstream.
**Why it happens:** MLX `train_model()` writes the adapter file but doesn't verify it's loadable. If training was interrupted or the adapter dimensions don't match the target layers, the file exists but `load()` fails.
**How to avoid:** Immediately after training, call `mlx_lm.utils.load(model_id, adapter_path=adapter_path)` in a `try/except` block. If loading fails, mark training as incomplete (don't write `TRAINING_STATUS.json` with `status: "complete"`). Re-raise the error so the pipeline runner knows the stage failed.
**Warning signs:** `adapters.safetensors` file size is significantly smaller than expected (< 1MB for a 16-layer LoRA rank 16 on a 30B model).

### Pitfall 3: Router Priority Conflicts
**What goes wrong:** Two rules match the same query with different specialists. The wrong specialist is selected because rule priority ordering is non-deterministic or the first-match-wins behavior is unexpected.
**Why it happens:** Rule matching is naturally overlapping -- a query about "Python code for medical diagnosis" matches both `code_detection` and `medical_detection`.
**How to avoid:** Explicit priority ordering in YAML (lower number = lower priority). Higher priority rules run first. When multiple rules match, highest confidence wins. When confidences are equal, highest priority wins. The `confidence_threshold` per rule provides a gate -- below-threshold matches are ignored even if they're the only match. The fallback chain handles the case where no rule meets its threshold.
**Warning signs:** Same query classified differently on repeated runs. Classification flips between two specialists for similar queries.

### Pitfall 4: Validation Set Leakage
**What goes wrong:** The "held-out test set" used for post-training validation is accidentally a subset of the training data, making validation metrics artificially good.
**Why it happens:** The existing `train_specialists_mlx.py` uses `data/specialists/{niche}_mlx/{train,valid}.jsonl` for training. If the validation pass reuses `valid.jsonl`, it's testing on the same distribution the model was evaluated on during training.
**How to avoid:** The post-training validation pass must use a separate file (`test.jsonl`) that was never included in the MLX dataset preparation. The acceptance criteria (D-06) explicitly states "held-out test set (not reused from training `val_batches`)." The `test_split_path` in specialist config should point to `data/specialists/{niche}/test.jsonl` (HF dataset test split), NOT the MLX-formatted data.
**Warning signs:** Validation loss is suspiciously close to training loss. BLEU scores are unrealistically high (>0.8).

### Pitfall 5: Runtime State Inventory for Gate Counters Across Pipeline Restarts
**What goes wrong:** Consecutive failure counters reset when the pipeline restarts, so the auto-gating threshold (N consecutive failures to block) is never reached.
**Why it happens:** Gate state is stored in memory only, or the persistence file is overwritten on each pipeline run.
**How to avoid:** Gate state persistence already exists in `Benchmarker` (`artifacts/.gate_state/{niche}_gate_state.json` and `{niche}_bench_gate_state.json`). Training evaluation gates should use the same pattern: persist consecutive failure counters to `artifacts/.gate_state/{niche}_training_gate_state.json`. Load on startup, save after each evaluation. Fail-open on corrupt files (Phase 3 pattern).
**Warning signs:** Pipeline reports "1st failure" for the same specialist on every run. Blocking state is never entered despite repeated failures.

## Code Examples

Verified patterns from the existing codebase and official library documentation:

### ConvergenceTracker Usage (extending existing Distiller)

```python
# Source: Pattern from existing distillation.py extended with standard ML convergence practices
# distill/convergence.py (NEW)

class ConvergenceTracker:
    """Tracks KD loss convergence with two-tier stopping and patience."""

    def __init__(self, target: float, warning: float, hard_stop: float,
                 patience: int = 100, min_delta: float = 0.01, window_size: int = 20):
        self._target = target
        self._warning = warning
        self._hard_stop = hard_stop
        self._patience = patience
        self._min_delta = min_delta
        self._window_size = window_size
        self._losses = []
        self._best_loss = float("inf")
        self._no_improvement_steps = 0
        self._converged = False
        self._converged_at_step = None
        self._warnings = []
        self._aborted = False

    def step(self, loss: float, step_number: int) -> str:
        """Record a loss value and return status: 'continue', 'warning', 'converged',
        'early_stop', or 'hard_stop'."""
        self._losses.append(loss)

        if loss > self._hard_stop:
            self._aborted = True
            return "hard_stop"

        status = "continue"
        if loss > self._warning:
            self._warnings.append(step_number)
            status = "warning"

        if loss < self._best_loss - self._min_delta:
            self._best_loss = loss
            self._no_improvement_steps = 0
        else:
            self._no_improvement_steps += 1

        rolling_avg = self._rolling_average()
        if rolling_avg < self._target and not self._converged:
            self._converged = True
            self._converged_at_step = step_number
            return "converged"

        if self._no_improvement_steps >= self._patience:
            return "early_stop"

        return status

    def _rolling_average(self) -> float:
        window = self._losses[-self._window_size:]
        if not window:
            return float("inf")
        return sum(window) / len(window)
```

### Router State Machine with transitions

```python
# Source: transitions library docs (https://github.com/pytransitions/transitions)
# router/engine.py (NEW)

from transitions import Machine

class RouterStateMachine:
    """GQHSM-compatible router state machine backed by transitions."""

    states = [
        {"name": "pre_classify"},
        {"name": "keyword_match"},
        {"name": "regex_match"},
        {"name": "syntax_density"},
        {"name": "select_specialist"},
        {"name": "fallback_chain"},
        {"name": "classified", "final": True},
    ]

    def __init__(self, rules_config: dict):
        self.machine = Machine(
            model=self,
            states=RouterStateMachine.states,
            initial="pre_classify",
            auto_transitions=False,
        )

        # Build transitions from GQHSM-compatible JSON
        for transition_def in rules_config.get("transitions", []):
            self.machine.add_transition(
                trigger=transition_def["trigger"],
                source=transition_def["source"],
                dest=transition_def["dest"],
                conditions=transition_def.get("conditions", []),
                unless=transition_def.get("unless", []),
                after=transition_def.get("actions", []),
            )
```

### Adapter Validity Check

```python
# Source: Pattern from existing train_specialists_mlx.py extended with Phase 2 validation
# training/validation.py (NEW)

def validate_adapter(model_id: str, adapter_path: str, test_samples: list,
                     loss_threshold: float) -> dict:
    """Multi-prong adapter validity check (D-08).

    Returns:
        dict with keys: loadable, loss_valid, behavioral_diff, objective_errors,
                        subjective_diffs, overall_valid
    """
    import mlx_lm.utils as mlx_utils

    result = {"loadable": False, "loss_valid": False, "behavioral_diff": False,
              "objective_errors": 0, "subjective_diffs": 0, "overall_valid": False}

    # (a) Loadability check
    try:
        model, tokenizer = mlx_utils.load(model_id, adapter_path=adapter_path)
        result["loadable"] = True
    except Exception as e:
        result["load_error"] = str(e)
        return result

    # (b) Validation loss check on held-out test set
    val_loss = compute_validation_loss(model, tokenizer, test_samples)
    result["validation_loss"] = val_loss
    result["loss_valid"] = val_loss <= loss_threshold

    # (c) Behavioral difference check
    base_model, _ = mlx_utils.load(model_id)  # no adapter
    jaccard = compute_jaccard_similarity(base_model, model, tokenizer, test_samples[:5])
    result["behavioral_diff"] = jaccard < 0.95
    result["jaccard_similarity"] = jaccard

    result["overall_valid"] = all([
        result["loadable"], result["loss_valid"], result["behavioral_diff"]
    ])
    return result
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Distiller computes loss but doesn't track convergence | ConvergenceTracker with rolling window, two-tier stopping, patience | Phase 2 | Training can stop early when converged; operators get warning before hard-stop |
| Temperature sweep prints results to stdout | Structured JSON output at `artifacts/sweeps/{niche}_sweep.json` | Phase 2 | Data-driven temperature selection per specialist |
| Training metadata recorded but not validated | Post-training validation pass on held-out test set with multi-prong checks | Phase 2 | Adapter quality verified before downstream pipeline stages consume it |
| Evaluation metrics computed but not persisted per run | MetricStore extended for timestamped per-run persistence | Phase 2 | Trend analysis, auto-gating, and regression detection become possible |
| No router exists | GQHSM-compatible rules-based router with YAML-driven rules | Phase 2 | Query classification enables specialist selection; fallback chaining mirrors cascade pattern |
| Auto-gating for SGFP4 metrics only | Extended to training evaluation metrics with same consecutive-failure pattern | Phase 2 | Consistent gating across all pipeline stages |

**Deprecated/outdated:**
- `train_specialists.py` -- Already deprecated (Phase 1). Do not modify. Only `train_specialists_mlx.py` is the active trainer.
- Print-based sweep output -- Temperature sweep results currently printed to stdout. Phase 2 replaces with structured JSON persistence.

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | `transitions` 0.9.3 is already installed and working; no new install needed | Standard Stack | Low -- verified via pip show and import test. Phase 1 dependencies didn't require it, so it may need explicit addition to requirements. |
| A2 | Default thresholds (target=2.5, warning=3.0, hard_stop=5.0, patience=100, min_delta=0.01) are reasonable starting points | KD Convergence | MEDIUM -- these are educated estimates based on typical KD loss ranges. May need tuning per specialist. Operator can override in config. |
| A3 | GQHSM StateProto C# implementation uses states, transitions, triggers, guards, callbacks -- the Python JSON subset mirrors these concepts correctly | Router Rule Design | LOW -- GQHSM/StateProto is a C# project with .cs files; the conceptual model extraction is based on examining the file structure and the CONTEXT.md descriptions, not a deep read of the C# source. |
| A4 | Phase 1 pipeline (TeacherClient, cascade, checkpoint system, config loader) is complete and available for integration | Architecture | MEDIUM -- ROADMAP.md shows Phase 1 as not yet completed (unchecked). Phase 2 depends on Phase 1 outputs. If Phase 1 is incomplete, Phase 2 integration points may need adjustment. |
| A5 | `MetricStore` from Phase 4 can be extended for training evaluation metrics | Evaluation Persistence | LOW -- MetricStore was built for SGFP4 metrics and benchmark results (Phase 3/4). Extending it for training eval metrics is architecturally sound but wasn't part of its original design contract. |

## Open Questions

1. **Phase 1 completion status**
   - What we know: ROADMAP.md shows Phase 1 unchecked. Phase 3 and 4 are completed (marked [x]). Phase 2 depends on Phase 1 outputs (TeacherClient, cascade, checkpoint system, config loader).
   - What's unclear: Is Phase 1 complete but the checkbox wasn't updated? Or is work proceeding out of order (Phase 3, 4 done, now Phase 2)?
   - Recommendation: Verify Phase 1 is functional before Phase 2 planning starts. The planner should include a checkpoint to validate TeacherClient and cascade API are available.

2. **Test data availability for held-out validation**
   - What we know: `train_specialists_mlx.py` prepares `{train,valid}.jsonl` from HF datasets. The HF datasets (loaded via `load_from_disk`) may or may not have a test split.
   - What's unclear: Does each specialist's dataset at `data/specialists/{niche}/` contain a test split? If not, the validation pass needs to create a held-out set from the available data.
   - Recommendation: Planner should add a task to verify test split existence and create one if missing.

3. **LLM API threshold update mechanism (D-15)**
   - What we know: D-15 says "LLM API can recursively update gate thresholds based on observed performance trends." This is Claude's discretion.
   - What's unclear: Which LLM to use? What prompt? How often to update? What's the safety constraint (can it only loosen thresholds, or can it tighten them too)?
   - Recommendation: Implement as an optional feature gated behind a config flag (`adaptive_gating.enabled: false` by default). When enabled, the LLM receives the last N evaluation results and suggests threshold adjustments. Human operator reviews and approves changes.

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| Python 3 | All modules | Yes | 3.11.6 | -- |
| `mlx-lm` | Training, validation, evaluation | Yes | 0.28.4 | -- |
| `transitions` | Router state machine | Yes | 0.9.3 | `python-statemachine` 3.2.0 (not installed) |
| `pyyaml` | Config loading | Yes | 6.0.2 | -- |
| `nltk` | BLEU score computation | Yes | (installed) | -- |
| `datasets` (HF) | Data loading | Yes | (installed) | -- |
| `numpy` | Numerical ops | Yes | (installed) | -- |
| GQHSM submodule | JSON schema reference | Yes | Present at `GQHSM/` | -- |

**Missing dependencies with no fallback:** none
**Missing dependencies with fallback:** none

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest (detected via existing test infrastructure in gnus-poc/tests/) |
| Config file | none -- see Wave 0 |
| Quick run command | `pytest tests/test_convergence.py -x` |
| Full suite command | `pytest tests/ -x` |

### Phase Requirements -> Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| DIST-01 | KD loss converges below target within patience | unit | `pytest tests/test_convergence.py::test_converges_below_target -x` | No -- Wave 0 |
| DIST-01 | Two-tier stopping: warning logged, hard-stop aborts | unit | `pytest tests/test_convergence.py::test_two_tier_stopping -x` | No -- Wave 0 |
| DIST-02 | Temperature sweep produces structured JSON | integration | `pytest tests/test_distillation.py::test_temperature_sweep_output -x` | No -- Wave 0 |
| DIST-03 | Synthetic data quality checks (length, empty, dedup) | unit | `pytest tests/test_synthetic_quality.py::test_quality_checks -x` | No -- Wave 0 |
| TRAIN-01 | Adapter loads cleanly via MLX | integration | `pytest tests/test_training_validation.py::test_adapter_loadability -x` | No -- Wave 0 |
| TRAIN-01 | Adapter produces different output from base model | integration | `pytest tests/test_training_validation.py::test_behavioral_difference -x` | No -- Wave 0 |
| TRAIN-02 | Hyperparameters from config respected at runtime | unit | `pytest tests/test_training_config.py::test_hyperparameter_override -x` | No -- Wave 0 |
| TRAIN-03 | Evaluation metrics persisted per run | unit | `pytest tests/test_eval_persistence.py::test_metrics_persisted -x` | No -- Wave 0 |
| ROUTE-01 | Keyword rule matches code query | unit | `pytest tests/test_router_rules.py::test_keyword_code_detection -x` | No -- Wave 0 |
| ROUTE-01 | Syntax density rule routes math query | unit | `pytest tests/test_router_rules.py::test_syntax_density_math -x` | No -- Wave 0 |
| ROUTE-01 | No-match routes to encyclopedic | unit | `pytest tests/test_router_rules.py::test_default_fallback -x` | No -- Wave 0 |
| ROUTE-02 | Execution plan includes specialist and mode | unit | `pytest tests/test_router_engine.py::test_execution_plan_output -x` | No -- Wave 0 |

### Sampling Rate
- **Per task commit:** `pytest tests/test_convergence.py tests/test_router_rules.py -x`
- **Per wave merge:** `pytest tests/ -x`
- **Phase gate:** Full suite green before `/gsd:verify-work`

### Wave 0 Gaps
- [ ] `tests/test_convergence.py` -- covers DIST-01 convergence criteria
- [ ] `tests/test_distillation.py` -- covers DIST-02 temperature sweep output
- [ ] `tests/test_synthetic_quality.py` -- covers DIST-03 data quality checks
- [ ] `tests/test_training_validation.py` -- covers TRAIN-01 adapter validity
- [ ] `tests/test_training_config.py` -- covers TRAIN-02 hyperparameter respect
- [ ] `tests/test_eval_persistence.py` -- covers TRAIN-03 metric persistence
- [ ] `tests/test_router_rules.py` -- covers ROUTE-01 rule matching
- [ ] `tests/test_router_engine.py` -- covers ROUTE-02 execution plan output
- [ ] Framework install: `pip install pytest` -- if not already installed

## Security Domain

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|------------------|
| V2 Authentication | No | Not applicable -- local training pipeline, no user auth |
| V3 Session Management | No | Not applicable |
| V4 Access Control | No | Not applicable -- single-machine POC |
| V5 Input Validation | Yes | YAML schema validation for router rules and specialist configs; JSON Schema for GQHSM-compatible rule files; input sanitization for query strings passed to router |
| V6 Cryptography | No | Not applicable -- no cryptographic operations in training pipeline |

### Known Threat Patterns for Python ML Training Pipeline

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| YAML deserialization attacks (unsafe yaml.load) | Tampering | Always use `yaml.safe_load()`. Existing codebase already does this consistently. |
| Path traversal in config file paths (specialist configs reference arbitrary file paths) | Tampering | Validate all paths relative to project root. Reject paths containing `..` segments. |
| Large/slow regex in router rules (ReDoS) | Denial of Service | Compile regex patterns with timeout (Python 3.11+ `re.compile` doesn't have native timeout; use `regex` library or limit pattern complexity). Limit regex match attempts per query. |
| Prompt injection via query strings (malicious queries designed to trick router) | Spoofing | Router rules are pattern-based, not LLM-based -- prompt injection has no effect on classification. However, queries containing rule-triggering keywords (e.g., "def malicious_code") could route to wrong specialist -- this is expected behavior for rules-based routing. |
| Serialized object injection via JSON files (sweep output, evaluation results) | Tampering | Use `json.load()` (not `pickle`). All file formats are JSON -- no object deserialization risk. |
| Secrets in YAML config files | Information Disclosure | API keys stored in `.env` only -- never in committed YAML configs. This pattern is already enforced in Phase 1. Router rules contain no secrets. |

## Sources

### Primary (HIGH confidence)
- Existing codebase files:
  - `gnus-poc/distill/distillation.py` -- current Distiller implementation
  - `gnus-poc/distill/teacher.py` -- Phase 1 TeacherClient with multi-backend, circuit breaker, budget
  - `gnus-poc/distill/cascade.py` -- Phase 1 TeacherCascade pattern (mirrored by router fallback)
  - `gnus-poc/training/train_specialists_mlx.py` -- MLX LoRA trainer
  - `gnus-poc/eval/evaluator.py` -- SpecialistEvaluator (PPL, BLEU, ROUGE-L, latency)
  - `gnus-poc/eval/benchmarker.py` -- Benchmarker with gate checking and consecutive-failure tracking
  - `gnus-poc/eval/metric_store.py` -- MetricStore persistence pattern
  - `gnus-poc/config/pipeline.yaml` -- Two-layer config structure, eval_gates
  - `gnus-poc/config/specialists/code.yaml` -- Per-specialist config pattern
- `GQHSM/StateProto/` -- GQHSM conceptual model (states, transitions, triggers, guards)
- PyPI (verified via pip index): `transitions` 0.9.3, `python-statemachine` 3.2.0

### Secondary (MEDIUM confidence)
- `https://pypi.org/project/transitions/` -- transitions library features (YAML config, hierarchical states, conditions/guards) [WebFetch verified]
- `https://pypi.org/project/python-statemachine/` -- python-statemachine features (guards, YAML extra, async support) [WebFetch verified]
- `.planning/workstreams/poc/phases/01-pipeline-hardening/01-CONTEXT.md` -- Phase 1 architecture patterns (teacher cascade, checkpoint system, config loader)

### Tertiary (LOW confidence)
- Default threshold values (target=2.5, warning=3.0, hard_stop=5.0, patience=100, min_delta=0.01) -- based on training knowledge of typical KD loss ranges, not verified against this project's actual loss values. Marked for operator review.
- GQHSM conceptual model extraction -- based on directory structure and CONTEXT.md descriptions rather than deep inspection of C# source files. Tagged as [ASSUMED] in Assumptions Log.

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH -- all libraries verified installed (pip show) or available on PyPI (pip index). No new package installations needed except possibly adding `transitions` to requirements if not already declared.
- Architecture: HIGH -- all modules exist in the codebase and were inspected. Integration points with Phase 1 are documented in CONTEXT.md and verified against existing code (TeacherClient API, ConfigLoader, checkpoint system, cascade pattern).
- Pitfalls: MEDIUM -- identified from ML training experience and codebase analysis. KD oscillation and validation leakage are real risks but the specific oscillation amplitude for this project's models is unknown until training runs.

**Research date:** 2026-06-29
**Valid until:** 2026-07-29 (30-day stability window for ML training patterns)
