# Phase 2: Training & Distillation Quality - Context

**Gathered:** 2026-06-21
**Status:** Ready for planning

<domain>
## Phase Boundary

Delivers quality-gated knowledge distillation, LoRA specialist training, evaluation metrics persistence, and a GQHSM-compatible rules-based specialist router. Takes existing prototype modules (`Distiller`, `train_specialists_mlx.py`, `SpecialistEvaluator`) and adds convergence criteria, validation gates, structured metric persistence, and the first router implementation. All new code integrates with the Phase 1 hardened pipeline (checkpoint system, two-layer config, multi-backend TeacherClient).

**Requirements:** DIST-01 through DIST-03, TRAIN-01 through TRAIN-03, ROUTE-01 through ROUTE-02 (8 total)
</domain>

<decisions>
## Implementation Decisions

### KD Convergence & Temperature Sweeping
- **D-01:** `distill_loss_target` is per-specialist, configurable in `config/specialists/<niche>.yaml`. Different specialists have different convergence difficulty — medical needs tighter convergence than encyclopedic.
- **D-02:** Convergence definition and early stopping algorithm → researcher. Study ML literature best practices for KD convergence criteria (loss < target for N consecutive steps vs final loss only) and effective early stopping (plateau detection, patience-based).
- **D-03:** Patience (steps without improvement before stopping) configurable per specialist.
- **D-04:** Two-tier stopping: **warning threshold** (log + continue training) and **hard-stop threshold** (halt training entirely). Both thresholds → researcher to recommend effective defaults. Operator can adjust per specialist.
- **D-05:** Temperature sweep produces per-specialist JSON analysis file at `artifacts/sweeps/<niche>_sweep.json` containing: per-temperature loss curves, convergence rate per temperature, and identified best temperature. Enables data-driven temperature selection per specialist.

### Training Quality Validation
- **D-06:** Separate post-training validation pass on a held-out test set (not reused from training `val_batches`). Produces independent quality signal — also enables analysis of how to improve training.
- **D-07:** Validation loss threshold per specialist, configurable in `config/specialists/<niche>.yaml`.
- **D-08:** Multi-prong adapter validity check: (a) **loadability** — adapter weights load cleanly via MLX, (b) **validation loss** — below configured per-specialist threshold, (c) **behavioral** — inference output differs from base model. Subjective differences (style, tone, phrasing) are tracked separately from objective errors (facts, code correctness, math). Objective errors are more severe.

### Router Rule Design (GQHSM-Compatible)
- **D-09:** Python-native lightweight state machine runtime that consumes GQHSM-compatible JSON rule definitions. The JSON is the compatibility contract — when the C++ parent integrates GQHSM directly, the same JSON feeds into it. No C++ interop in the Python POC.
- **D-10:** Rule format mirrors GQHSM's conceptual model: **states** (classification states, specialist states), **transitions** (triggered by rule matches), **trigger conditions** (keyword, regex, token density), **guards** (confidence checks, domain constraints), **actions** (select specialist, log classification).
- **D-11:** Rule types support keyword matching, regex patterns, syntax density heuristics (e.g., >30% numeric tokens → math path), with configurable priority ordering. Rules defined in YAML, no code changes required to add/modify rules.
- **D-12:** Fallback chaining: if primary specialist classification has confidence below threshold, try next-best match. Mirrors the Phase 1 teacher cascade pattern (try Level 1, escalate to Level 2 if below threshold).
- **D-13:** GQHSM submodule at repo root (`GQHSM/`) — researcher and planner reference its StateProto and conceptual model for JSON schema design.

### Evaluation → Training Feedback
- **D-14:** Automatic gating with per-metric, per-specialist thresholds. Each specialist has pass/fail gates on its domain-relevant metrics (e.g., code specialist: PPL < X, BLEU > Y).
- **D-15:** LLM API can recursively update gate thresholds based on observed performance trends. Adaptive gating — thresholds evolve as the system improves.
- **D-16:** Variance from prior run (metric delta) is logged for trend analysis. Severe outliers trigger parallel human review — logged as a notification, does NOT block pipeline execution. Review happens alongside continued pipeline operation.
- **D-17:** Auto-gating only blocks the pipeline after N configurable consecutive failures for the same specialist. Single failures log and continue. Prevents flaky runs from causing false blocks while catching persistent quality degradation.

### Claude's Discretion
- Choice of lightweight Python state machine library (`transitions`, `automaton`, or custom implementation)
- Convergence definition specifics and early stopping algorithm implementation
- Default threshold values and patience defaults
- JSON rule file schema design (GQHSM-compatible subset)
- Adapter behavioral validation test design (how to measure "different output")
- Evaluation metric persistence format and schema
- LLM-based threshold update mechanism and prompt design
</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Project Planning
- `.planning/workstreams/poc/ROADMAP.md` — Phase 2 goal, success criteria, and phase dependencies
- `.planning/workstreams/poc/REQUIREMENTS.md` — DIST-01 through DIST-03, TRAIN-01 through TRAIN-03, ROUTE-01 through ROUTE-02
- `.planning/workstreams/poc/PROJECT.md` — Key decisions: adapter-based specialists, per-specialist quantization, single-machine scope

### Phase 1 Context (dependencies)
- `.planning/workstreams/poc/phases/01-pipeline-hardening/01-CONTEXT.md` — Teacher cascade pattern (D-01 through D-04), dual-backend API (D-05 through D-08), pipeline runner (D-09 through D-12), budget controls (D-13, D-14), checkpoint validation (D-15, D-16)

### GQHSM Reference
- `GQHSM/` — Git submodule at repo root. Researcher should examine StateProto/ and the GQHSM conceptual model (states, transitions, triggers, guards, callbacks) to design the JSON rule schema.
- `GQHSM/StateProto/` — State machine prototype definitions
- `.planning/workstreams/poc/intel/context.md` §Cognitive OS Extension — GQHSM runtime description, plugin ABI, guard callbacks
- `.planning/workstreams/poc/intel/classifications/15-epistemic-arbitration-and-cognitive-os-00000000.json` — Epistemic Arbitration architecture reference

### Architecture Docs (GeniusCognitiveSystem)
- `../../docs/architecture/03-model-and-router.md` — Model and router design, specialist roles, ELM architecture
- `../../docs/architecture/13-eggroll-swarm-retraining.md` — Teacher→student distillation architecture

### Existing Implementation
- `gnus-poc/distill/distillation.py` — Distiller class (KD loss, temperature sweep) — prototype to harden
- `gnus-poc/training/train_specialists_mlx.py` — MLX LoRA trainer — add validation gates
- `gnus-poc/eval/evaluator.py` — SpecialistEvaluator (PPL, BLEU, ROUGE, latency) — add metric persistence
- `gnus-poc/eval/benchmarker.py` — Benchmarker (variant comparison) — extend for per-specialist gating
- `gnus-poc/config/pipeline.yaml` — Existing two-layer config, teacher cascade, training defaults
- `gnus-poc/distill/teacher.py` — Multi-backend TeacherClient (Phase 1 output) — router consumes for confidence checks
- `gnus-poc/distill/cascade.py` — Teacher cascade (Phase 1 output) — pattern to mirror in router fallback chaining
</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- **`Distiller`** (`distill/distillation.py`): Already computes KD loss, sweeps temperatures. Needs convergence tracking, early stopping, and structured output. Do not rewrite — extend.
- **`train_specialists_mlx.py`**: Already runs LoRA training via MLX. Produces `adapter_config.json` + `adapter_model.safetensors`. Needs post-training validation pass and metadata completeness check.
- **`SpecialistEvaluator`** (`eval/evaluator.py`): Already computes perplexity, BLEU, ROUGE-L, latency. Needs metric persistence to structured files and per-specialist threshold comparison.
- **`Benchmarker`** (`eval/benchmarker.py`): Already compares variants on metrics. Extend for auto-gating with per-specialist thresholds and trend analysis.
- **`TeacherClient`** (`distill/teacher.py`): Phase 1 multi-backend client. Router uses it for confidence checks on teacher outputs.
- **`cascade.py`** (`distill/cascade.py`): Phase 1 teacher cascade orchestrator. Router fallback chaining follows the same pattern (try primary, escalate if below threshold).

### Established Patterns
- YAML config with two-layer structure (endpoints + models) — router rules follow same YAML-driven approach
- Per-specialist overrides via `config/specialists/<niche>.yaml` — training thresholds live here
- Checkpoint validation per stage, per niche — training/distillation stages plug into Phase 1 checkpoint system
- Budget enforcement before every API call — training runs respect budget cap from Phase 1
- Cost logging to JSONL — evaluation metrics follow similar structured persistence pattern

### Integration Points
- **Pipeline runner** (`pipeline/runner.py`): Train, evaluate, and distill stages consume the hardened modules from this phase
- **Config loader** (`config/loader.py`): Phase 1 ConfigLoader — router rules, training thresholds, and gate configs added here
- **Teacher cascade** (`distill/cascade.py`): Router fallback chaining mirrors the cascade pattern (confidence threshold → escalate)
- **Checkpoint system** (`pipeline/checkpoint.py`): Training and distillation validations are checkpoint checks
- **No router exists yet** — greenfield module. Place in `gnus-poc/router/` following existing package structure pattern
</code_context>

<specifics>
## Specific Ideas

- **Router rule format (GQHSM-compatible JSON):** States represent classification stages (pre_classify → keyword_match → regex_match → syntax_density → select_specialist → fallback_chain). Each state has trigger conditions and guard callbacks. Specialist selection is the terminal action. The JSON format should be a proper subset of GQHSM's state machine definition so it ports directly to C++.

- **Two-tier stopping example:**
  ```yaml
  training:
    distill_loss_target: 2.5
    distill_loss_warning: 3.0    # log warning, continue
    distill_loss_hard_stop: 5.0  # halt training
    patience: 100                 # steps without improvement
    min_delta: 0.01              # minimum improvement to reset patience
  ```

- **Auto-gate config example:**
  ```yaml
  evaluation:
    gates:
      perplexity: { max: 50.0, consecutive_failures_to_block: 3 }
      bleu_score: { min: 0.15, consecutive_failures_to_block: 3 }
    outlier_trigger:
      metric_drop_percent: 50    # >50% drop from prior → human review
  ```

- **Router rules example:**
  ```yaml
  router:
    rules:
      - name: "code_detection"
        priority: 10
        triggers:
          - type: keyword
            patterns: ["def ", "class ", "import ", "```"]
          - type: syntax_density
            threshold: 0.3
            chars: ["{", "}", "(", ")", ";", "="]
        action: select_specialist
        specialist: code
        fallback: encyclopedic
  ```
</specifics>

<deferred>
## Deferred Ideas

- **Learned router (ML-based classification):** User confirmed Phase 2 router is rules-based only. Learned routing (embedding-based, classifier) is a future phase enhancement.
- **Dynamic threshold evolution from evaluation data:** LLM API can update thresholds (D-15), but full autonomous threshold optimization without LLM involvement is deferred.
- **GQHSM C++ integration:** The Python POC uses a lightweight Python state machine. Direct GQHSM C++ runtime integration belongs to the parent GNUS-NEO-SWARM C++ repo.
- **Epistemic arbitration (full GQHSM pipeline):** The full epistemic arbitration layer (Sanskrit epistemology, Kripke modal reasoning, hybrid frameworks) is out of scope for gnus-poc — belongs to parent C++ repo.
</deferred>

---

*Phase: 02-training-distillation-quality*
*Context gathered: 2026-06-21*
