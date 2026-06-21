# Phase 2: Training & Distillation Quality - Research

**Researched:** 2026-06-21
**Domain:** ML training convergence, knowledge distillation, state machines, LLM-based evaluation
**Confidence:** MEDIUM (web search unavailable; reliance on training knowledge + codebase analysis)

## Summary

This research covers four areas specified by the Phase 2 context decisions: (1) KD convergence criteria and early stopping algorithms from ML literature, (2) GQHSM-compatible JSON state machine schema design from the GQHSM XML definition format, (3) lightweight Python state machine library selection for consuming JSON rule definitions, and (4) adaptive threshold strategies using LLM evaluation prompts.

The existing codebase provides a strong foundation: `Distiller` computes KD loss and temperature sweeps, `train_specialists_mlx.py` runs MLX LoRA training with skip-on-existing logic, `SpecialistEvaluator` computes PPL/BLEU/ROUGE/latency, and `Benchmarker` compares variants. Phase 2 adds convergence tracking, early stopping, structured metric persistence, post-training validation, and a greenfield rules-based router.

**Primary recommendation:** Extend existing modules rather than rewriting. The router is the only greenfield module. Use plateau-based early stopping with two-tier thresholds for KD convergence. Adopt `transitions` (0.9.3) for the Python state machine runtime, consuming a GQHSM-mirrored JSON schema. LLM-based adaptive thresholding should provide structured threshold recommendations with justification, logged for human review.

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| KD loss computation + convergence tracking | API / Backend (Python training) | -- | Training runs locally; loss tracking is in-process |
| Temperature sweep analysis | API / Backend (Python training) | CDN / Static (artifact output) | Sweep results are JSON files consumed by humans and later automation |
| Post-training validation pass | API / Backend (Python training) | -- | Validation runs against local held-out data |
| Adapter validity checks (loadability, loss, behavioral) | API / Backend (Python training) | -- | MLX loads adapters locally; inference comparison is in-process |
| Evaluation metric computation (PPL, BLEU, ROUGE, latency) | API / Backend (Python eval) | Database / Storage (JSON files) | Compute in-process, persist to structured artifacts |
| Metric persistence per run | Database / Storage (JSON files) | API / Backend (Python eval) | Structured JSONL artifact files with timestamps |
| Rules-based query classification | API / Backend (Python router) | -- | YAML-driven rule matching runs in-process |
| Specialist selection + execution plan | API / Backend (Python router) | -- | Router produces plan consumed by pipeline runner |
| LLM-based threshold evaluation | API / Backend (Python eval) | API / Backend (TeacherClient) | LLM prompt via existing TeacherClient; result logged |

## Standard Stack

### Core

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| `transitions` [ASSUMED] | 0.9.3 | Lightweight state machine runtime for rules-based router | Most mature Python FSM library (10+ years, actively maintained); supports hierarchical states, guards, callbacks, and graphviz export; mirrors GQHSM conceptual model directly |
| `numpy` | 1.26.4 (installed) | Numerical operations for loss computation, plateau detection, convergence tracking | Already in requirements.txt; used by Distiller and evaluator |
| `PyYAML` | 6.0.2 (installed) | YAML config parsing for router rules, training thresholds, gate configs | Already in requirements.txt; ConfigLoader pattern established |
| `mlx` / `mlx-lm` | 0.30.0 / 0.28.4 (installed) | LoRA adapter loading, model inference for behavioral validation | Already in requirements.txt; train_specialists_mlx.py depends on these |

### Supporting

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| `nltk` | 3.9.1 (installed) | BLEU/ROUGE computation for evaluation | Already used by SpecialistEvaluator; extends to behavioral diff scoring |
| `json` (stdlib) | -- | JSON serialization for sweep results, evaluation metrics, router execution plans | No extra dependency; Python stdlib |
| `dataclasses` (stdlib) | -- | Structured data containers for convergence state, router plans, validation results | Python stdlib; matches existing patterns (StageValidationResult) |
| `logging` (stdlib) | -- | Structured logging with levels for warning thresholds, convergence events | Python stdlib; already used in checkpoint.py |

### Alternatives Considered

| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| `transitions` [ASSUMED] | `automaton` (3.4.0, OpenStack) [ASSUMED] | `automaton` is a workflow/orchestration library (OpenStack project) with heavier dependency footprint (PrettyTable, etc.). Designed for state machine-based task orchestration, not rule-based routing classification. `transitions` is simpler, purpose-built for FSM, and maps more directly to GQHSM's states+transitions+guards model. |
| `transitions` [ASSUMED] | Custom FSM implementation | Custom code would require implementing state management, transition dispatch, guard evaluation, hierarchical nesting, and callback registration -- all features `transitions` provides out of the box. Custom code is acceptable if `transitions` proves insufficient, but the phase should start with the library. |

**Installation:**
```bash
pip install transitions
```

## Package Legitimacy Audit

> Required -- this phase installs `transitions`.

| Package | Registry | Age | Downloads | Source Repo | slopcheck | Disposition |
|---------|----------|-----|-----------|-------------|-----------|-------------|
| `transitions` | PyPI | 10+ yrs | ~2M/mo | github.com/pytransitions/transitions | [OK] | Approved |

**Packages removed due to slopcheck [SLOP] verdict:** none
**Packages flagged as suspicious [SUS]:** none

*Note: `transitions` is tagged [ASSUMED] for provenance because Context7/official docs verification was unavailable during research. slopcheck confirms legitimacy and PyPI registry confirms existence. The planner should gate installation behind `checkpoint:human-verify` for the [ASSUMED] tag.*

## Architecture Patterns

### System Architecture Diagram

```
Input Query
    |
    v
[Router] --> rules.yaml --> [State Machine] --> specialist selection
    |                                   |
    v                                   v
[Pipeline Runner]                   [Execution Plan]
    |
    +--[Train Stage]---> train_specialists_mlx.py
    |       |
    |       +--[KD Distiller] --> convergence tracker
    |       |       |
    |       |       +-- early stopping (plateau detection)
    |       |       +-- two-tier thresholds (warning + hard-stop)
    |       |       +-- temperature sweep --> artifacts/sweeps/<niche>_sweep.json
    |       |
    |       +--[Validation Pass] --> held-out test set
    |               |
    |               +-- loadability check (MLX)
    |               +-- validation loss check
    |               +-- behavioral diff check (inference output delta)
    |
    +--[Eval Stage]---> SpecialistEvaluator
    |       |
    |       +-- perplexity, BLEU, ROUGE-L, latency
    |       +-- persist to artifacts/evaluations/<niche>_<timestamp>.json
    |       +-- auto-gating with per-specialist thresholds
    |
    +--[LLM Threshold Adapter] --> TeacherClient
            |
            +-- prompt: structured metrics + prior run context
            +-- response: recommended thresholds with justification
            +-- logged for human review (not auto-applied without confirmation)
```

### Recommended Project Structure

```
gnus-poc/
├── router/                        # Greenfield module
│   ├── __init__.py
│   ├── rules.py                   # RuleEngine: loads YAML rules, classifies queries
│   ├── state_machine.py           # GQHSM-compatible JSON state machine runtime (wraps transitions)
│   └── plan.py                    # ExecutionPlan dataclass (specialist, mode, confidence)
├── distill/
│   ├── distillation.py            # EXTEND: add convergence tracker, early stopping
│   ├── convergence.py             # NEW: ConvergenceTracker, PlateauDetector
│   └── sweep_analyzer.py          # NEW: temperature sweep analysis + structured output
├── training/
│   ├── train_specialists_mlx.py   # EXTEND: add post-training validation pass
│   └── adapter_validator.py       # NEW: loadability, validation loss, behavioral diff checks
├── eval/
│   ├── evaluator.py               # EXTEND: add structured metric persistence per run
│   ├── benchmarker.py             # EXTEND: add auto-gating with per-specialist thresholds
│   ├── metric_store.py            # NEW: structured JSONL persistence for evaluation runs
│   └── threshold_adapter.py       # NEW: LLM-based threshold recommendation
├── config/
│   ├── pipeline.yaml              # EXTEND: add training convergence, eval gates, router rules sections
│   ├── router_rules.yaml          # NEW: GQHSM-compatible rule definitions
│   └── specialists/<niche>.yaml   # EXTEND: add distill_loss_target, val_loss_threshold, eval_gates
└── tests/
    ├── test_convergence.py        # NEW
    ├── test_adapter_validator.py  # NEW
    ├── test_router.py             # NEW
    └── test_threshold_adapter.py  # NEW
```

### Pattern 1: Plateau Detection for Early Stopping

**What:** Track a rolling window of loss values. When loss has not improved by more than `min_delta` for `patience` consecutive steps AND loss is below the warning threshold, log a warning. When loss exceeds the hard-stop threshold at any point, halt training immediately. When patience is exhausted and loss is below the target threshold, training is considered converged.

**When to use:** Every KD training run. The Distiller's internal training loop calls `convergence_tracker.step(loss)` each iteration.

**Example:**
```python
# Source: Training knowledge -- standard plateau-based early stopping pattern
# Adapted for the two-tier stopping model specified in D-04

from dataclasses import dataclass, field
from typing import List, Optional

@dataclass
class ConvergenceConfig:
    distill_loss_target: float = 2.5
    distill_loss_warning: float = 3.0
    distill_loss_hard_stop: float = 5.0
    patience: int = 100
    min_delta: float = 0.01

@dataclass
class ConvergenceState:
    """Mutable tracking state for a single training run."""
    losses: List[float] = field(default_factory=list)
    best_loss: float = float("inf")
    steps_since_improvement: int = 0
    converged: bool = False
    hard_stopped: bool = False
    warning_issued: bool = False

class ConvergenceTracker:
    def __init__(self, config: ConvergenceConfig):
        self._config = config
        self._state = ConvergenceState()

    def step(self, loss: float) -> str:
        """Record a loss value and return status: 'continue', 'warning', 'hard_stop', 'converged'."""
        self._state.losses.append(loss)

        # Hard stop check (takes priority)
        if loss > self._config.distill_loss_hard_stop:
            self._state.hard_stopped = True
            return "hard_stop"

        # Improvement tracking
        if loss < self._state.best_loss - self._config.min_delta:
            self._state.best_loss = loss
            self._state.steps_since_improvement = 0
        else:
            self._state.steps_since_improvement += 1

        # Convergence check (loss below target AND patience exhausted)
        if (loss <= self._config.distill_loss_target and
                self._state.steps_since_improvement >= self._config.patience):
            self._state.converged = True
            return "converged"

        # Warning threshold check
        if (loss > self._config.distill_loss_warning and
                not self._state.warning_issued):
            self._state.warning_issued = True
            return "warning"

        return "continue"
```

### Pattern 2: GQHSM-Compatible JSON State Machine Schema

**What:** A JSON schema that mirrors GQHSM's XML state machine definition format. States have entry/exit actions. Transitions have event signals, guard conditions, and actions. Hierarchical states nest. The JSON format is a proper subset of GQHSM's conceptual model so it ports directly to C++ when the parent repo integrates the GQHSM C# runtime.

**When to use:** Router rule definitions. Single source of truth -- the same JSON feeds the Python POC router now and the C++ GQHSM engine later.

**Schema design (derived from GQHSM XML analysis -- `Valve.xml`, `Air.xml`):**

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "title": "GQHSM State Machine Definition",
  "type": "object",
  "required": ["stateMachineInfo", "states", "transitions"],
  "properties": {
    "stateMachineInfo": {
      "type": "object",
      "required": ["name"],
      "properties": {
        "name": {"type": "string", "description": "Machine identifier (e.g., 'router_classifier')"},
        "version": {"type": "integer", "default": 1},
        "description": {"type": "string"},
        "namespace": {"type": "string", "default": "gnus.router"}
      }
    },
    "states": {
      "type": "array",
      "items": {
        "type": "object",
        "required": ["name"],
        "properties": {
          "name": {"type": "string"},
          "isStartState": {"type": "boolean", "default": false},
          "entryAction": {"type": "string", "description": "Callback name executed on state entry"},
          "exitAction": {"type": "string", "description": "Callback name executed on state exit"},
          "children": {
            "type": "array",
            "items": {"$ref": "#/properties/states/items"},
            "description": "Hierarchical child states (mirrors GQHSM nested StateGlyph)"
          },
          "metadata": {"type": "object", "description": "Arbitrary key-value annotations"}
        }
      }
    },
    "transitions": {
      "type": "array",
      "items": {
        "type": "object",
        "required": ["eventSignal", "source", "target"],
        "properties": {
          "name": {"type": "string", "description": "Optional label for debugging"},
          "eventSignal": {"type": "string", "description": "Trigger name (e.g., 'keyword_match', 'regex_match', 'no_match')"},
          "eventSource": {"type": "string", "description": "Port/source identifier (mirrors GQHSM EventSource)"},
          "guardCondition": {"type": "string", "description": "Guard callback name or inline expression"},
          "action": {"type": "string", "description": "Action callback name executed on transition"},
          "evaluationOrderPriority": {"type": "integer", "default": 0, "description": "Lower values evaluated first"},
          "transitionType": {"type": "string", "enum": ["Normal", "Internal"], "default": "Normal"},
          "source": {"type": "string", "description": "Source state name"},
          "target": {"type": "string", "description": "Target state name"}
        }
      }
    }
  }
}
```

**Example instance (router classification):**

```json
{
  "stateMachineInfo": {
    "name": "router_classifier",
    "version": 1,
    "description": "Rules-based query classification for specialist routing",
    "namespace": "gnus.router"
  },
  "states": [
    {
      "name": "pre_classify",
      "isStartState": true,
      "entryAction": "log_entry",
      "metadata": {"description": "Initial classification entry point"}
    },
    {
      "name": "keyword_match",
      "entryAction": "run_keyword_triggers",
      "metadata": {"description": "Evaluate keyword-based rules"}
    },
    {
      "name": "regex_match",
      "entryAction": "run_regex_triggers",
      "metadata": {"description": "Evaluate regex pattern rules"}
    },
    {
      "name": "syntax_density",
      "entryAction": "run_syntax_density_triggers",
      "metadata": {"description": "Evaluate syntax density heuristics"}
    },
    {
      "name": "select_specialist",
      "entryAction": "emit_specialist_selection",
      "metadata": {"description": "Terminal: specialist selected"}
    },
    {
      "name": "fallback_chain",
      "entryAction": "run_fallback_chain",
      "metadata": {"description": "Try next-best match when confidence below threshold"}
    },
    {
      "name": "no_match",
      "isStartState": false,
      "entryAction": "emit_default_specialist",
      "metadata": {"description": "Terminal: no match, route to default"}
    }
  ],
  "transitions": [
    {
      "name": "t_kw_hit",
      "eventSignal": "keyword_hit",
      "source": "keyword_match",
      "target": "select_specialist",
      "guardCondition": "confidence_above_threshold",
      "action": "set_selected_specialist",
      "evaluationOrderPriority": 10
    },
    {
      "name": "t_kw_miss",
      "eventSignal": "keyword_miss",
      "source": "keyword_match",
      "target": "regex_match",
      "evaluationOrderPriority": 20
    },
    {
      "name": "t_regex_hit",
      "eventSignal": "regex_hit",
      "source": "regex_match",
      "target": "select_specialist",
      "guardCondition": "confidence_above_threshold",
      "action": "set_selected_specialist",
      "evaluationOrderPriority": 10
    },
    {
      "name": "t_regex_miss",
      "eventSignal": "regex_miss",
      "source": "regex_match",
      "target": "syntax_density",
      "evaluationOrderPriority": 20
    },
    {
      "name": "t_syntax_hit",
      "eventSignal": "syntax_hit",
      "source": "syntax_density",
      "target": "select_specialist",
      "guardCondition": "confidence_above_threshold",
      "action": "set_selected_specialist",
      "evaluationOrderPriority": 10
    },
    {
      "name": "t_syntax_miss",
      "eventSignal": "syntax_miss",
      "source": "syntax_density",
      "target": "no_match",
      "evaluationOrderPriority": 20
    },
    {
      "name": "t_low_confidence",
      "eventSignal": "confidence_below_threshold",
      "source": "select_specialist",
      "target": "fallback_chain",
      "guardCondition": "has_fallback",
      "action": "try_next_best_match"
    },
    {
      "name": "t_fallback_resolved",
      "eventSignal": "fallback_hit",
      "source": "fallback_chain",
      "target": "select_specialist",
      "action": "set_selected_specialist"
    },
    {
      "name": "t_fallback_exhausted",
      "eventSignal": "fallback_miss",
      "source": "fallback_chain",
      "target": "no_match"
    }
  ]
}
```

**GQHSM mapping reference** (from `Valve.xml`, `Air.xml` analysis):

| GQHSM XML Element | JSON Equivalent | Purpose |
|-------------------|-----------------|---------|
| `StateMachineInfo` with `Name`, `Id`, `Version` | `stateMachineInfo.name`, `stateMachineInfo.version` | Machine identity |
| `StateGlyph` with `Name`, `IsStartState`, `EntryAction`, `ExitAction` | `states[].name`, `states[].isStartState`, `states[].entryAction`, `states[].exitAction` | State definition |
| Nested `StateGlyph` within parent (from `Air.xml` -- `Moving` contains `Gusting`, `Draft`) | `states[].children[]` | Hierarchical state nesting |
| `TransitionGlyph` with `EventSignal`, `EventSource`, `GuardCondition`, `Action`, `EvaluationOrderPriority`, `TransitionType` | `transitions[].eventSignal`, `transitions[].eventSource`, `transitions[].guardCondition`, `transitions[].action`, `transitions[].evaluationOrderPriority`, `transitions[].transitionType` | Transition definition |
| `StateTransitionPortGlyph` with `Name` | `transitions[].eventSource` | Named connection ports between machines |

### Pattern 3: Lightweight State Machine Runtime (wrapping `transitions`)

**What:** A thin adapter around `transitions` that consumes the GQHSM-compatible JSON schema and exposes trigger methods for the router classification pipeline.

**When to use:** Router rule execution. The `RuleEngine` loads JSON rules into the state machine and dispatches query analysis through it.

**Example:**
```python
# Integrating transitions library with GQHSM JSON format
# Source: Training knowledge of transitions library API [ASSUMED]

from transitions import Machine, State

class RouterStateMachine:
    """Thin adapter: consumes GQHSM JSON, exposes via transitions."""
    
    def __init__(self, sm_definition: dict, rule_handlers: dict):
        self._definition = sm_definition
        self._handlers = rule_handlers
        self._machine = None
        self._build()
    
    def _build(self):
        states = []
        transitions = []
        
        for state_def in self._definition["states"]:
            callbacks = {}
            if state_def.get("entryAction"):
                callbacks["on_enter"] = self._handlers.get(state_def["entryAction"])
            if state_def.get("exitAction"):
                callbacks["on_exit"] = self._handlers.get(state_def["exitAction"])
            
            # Handle hierarchical states
            if state_def.get("children"):
                sub_states = [
                    State(name=child["name"], **self._child_callbacks(child))
                    for child in state_def["children"]
                ]
                states.append(State(name=state_def["name"], **callbacks, children=sub_states))
            else:
                states.append(State(name=state_def["name"], **callbacks))
        
        for trans in self._definition["transitions"]:
            conditions = []
            if trans.get("guardCondition"):
                conditions.append(self._handlers.get(trans["guardCondition"], lambda: True))
            
            transitions.append({
                "trigger": trans["eventSignal"],
                "source": trans["source"],
                "dest": trans["target"],
                "conditions": conditions,
                "after": self._handlers.get(trans.get("action")),
            })
        
        class Model:
            pass
        
        self._machine = Machine(
            model=Model(),
            states=states,
            transitions=transitions,
            initial=self._find_start_state(),
            auto_transitions=False,
        )
    
    def trigger(self, event_name: str, *args, **kwargs):
        """Dispatch an event to the state machine."""
        self._machine.trigger(event_name, *args, **kwargs)
    
    @property
    def state(self) -> str:
        return self._machine.state
```

### Pattern 4: LLM-Based Adaptive Threshold Evaluation

**What:** Structure evaluation metrics and prior run context into a prompt for an LLM (via the existing `TeacherClient`), asking it to recommend updated gate thresholds with justification. Recommendations are logged, not auto-applied.

**When to use:** After each evaluation run produces metrics. The `ThresholdAdapter` runs as an optional post-evaluation step.

**Example:**
```python
# Prompt design for LLM-based threshold adaptation
# Source: Training knowledge -- structured evaluation prompting [ASSUMED]

THRESHOLD_EVALUATION_PROMPT = """You are an ML training quality analyst. Review the following specialist evaluation metrics and recommend updated gate thresholds.

## Specialist: {niche}
## Current Thresholds
- Perplexity max: {current_ppl_max}
- BLEU score min: {current_bleu_min}
- Consecutive failures to block: {current_consecutive_failures}

## Current Run Metrics
- Perplexity: {ppl:.3f}
- BLEU Score: {bleu:.4f}
- ROUGE-L: {rouge_l:.4f}
- Latency (ms/token): {latency:.2f}

## Prior Run Metrics (for trend analysis)
{prior_runs}

## Instructions
1. Compare current metrics against thresholds and prior runs.
2. If metrics are improving (PPL decreasing, BLEU increasing), recommend tightening thresholds.
3. If metrics are degrading, recommend keeping or loosening thresholds.
4. Identify any anomalous metric deltas that warrant human review.
5. Provide your recommendations in the following JSON format:

```json
{{
  "recommended_thresholds": {{
    "perplexity": {{"max": <float>, "reasoning": "<str>"}},
    "bleu_score": {{"min": <float>, "reasoning": "<str>"}},
    "consecutive_failures_to_block": {{"value": <int>, "reasoning": "<str>"}}
  }},
  "anomalies_detected": [{{"metric": "<str>", "delta_pct": <float>, "severity": "low|medium|high"}}],
  "confidence": <float 0.0-1.0>,
  "notes": "<str>"
}}
```

## Constraints
- Do not recommend thresholds that would immediately fail the current run.
- Threshold changes should be gradual (max 20% adjustment per evaluation).
- If confidence in recommendations is below 0.7, flag for human review.
"""
```

### Anti-Patterns to Avoid

- **Rewriting Distiller:** The existing `Distiller` class works. Add `ConvergenceTracker` as a separate composable component, not by rewriting the loss computation logic.
- **Hard-coding thresholds in source:** All thresholds, patience values, and gate configs belong in YAML (global `pipeline.yaml` with per-specialist overrides in `config/specialists/<niche>.yaml`). Follow the Phase 1 ConfigLoader pattern.
- **Silent auto-application of LLM-recommended thresholds:** D-15 says LLM "can" update thresholds, but the context defers full autonomous optimization. Recommendations should be logged for human review. If the planner decides to auto-apply, it must require `confidence > 0.9` and log the change.
- **Single monolithic router file:** The router has three separable concerns: rule loading (YAML/JSON), state machine execution (transitions), and execution plan generation. Keep them in separate files (`rules.py`, `state_machine.py`, `plan.py`).
- **Over-engineering the router state machine:** The router is rules-based (D-09, D-11). It does not need learned weights, embedding vectors, or ML classification. Keep it deterministic and inspectable.
- **Mixing behavioral validation with objective validation:** D-08 specifies subjective differences (style, tone, phrasing) are tracked separately from objective errors (facts, code correctness, math). The validation report must have distinct sections for these two categories.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| State machine runtime | Custom FSM implementation with state tracking, transition dispatch, guard evaluation, hierarchical nesting, callback registration | `transitions` [ASSUMED] | 10+ years of edge-case handling (reentrant transitions, queued events, state introspection, graphviz diagrams). Custom FSM would need: thread safety, callback lifecycle, graph export, hierarchical state management -- all solved by `transitions`. |
| Plateau detection in loss curves | Custom rolling-window averaging with magic numbers | `ConvergenceTracker` class with configurable `ConvergenceConfig` | Standard pattern (ReduceLROnPlateau from PyTorch, Keras EarlyStopping). Config-driven patience, min_delta, and two-tier thresholds. No external library needed -- simple dataclass-driven implementation. |
| Metric persistence format | Custom binary format or ad-hoc directory structure | Structured JSONL with timestamp-named files (`artifacts/evaluations/<niche>_<ISO8601>.json`) | Follows Phase 1 cost logging pattern (`artifacts/api_cost.jsonl`). JSON is GQHSM-compatible. Human-readable, git-diffable, simple to parse for trend analysis. |
| JSON schema validation | Custom validation function | `jsonschema` library (via pip) or inline validation in rule loader | `jsonschema` is the Python standard for JSON Schema validation (Draft 2020-12). The ConfigLoader pattern (class-based validation) is also acceptable if keeping dependencies minimal is preferred. |

**Key insight:** The state machine domain has well-known edge cases (event queue ordering during transitions, reentrant guard evaluation, hierarchical state entry/exit ordering). A mature library like `transitions` [ASSUMED] handles these correctly. Hand-rolling a state machine for this domain would introduce subtle bugs that only surface under specific transition sequences -- exactly the kind of bug that wastes debugging time in rule-based routing.

## Runtime State Inventory

> Omitted -- this is a greenfield-build phase, not a rename/refactor/migration phase. The router is a new module. All other changes extend existing modules without renaming identifiers, moving files, or changing storage keys.

## Common Pitfalls

### Pitfall 1: Convergence declared too early on noisy loss

**What goes wrong:** KD loss oscillates naturally (teacher logprobs vary per batch). A single lucky low-loss step triggers "converged" but the model hasn't truly converged. Subsequent distillation runs show degraded quality.

**Why it happens:** Single-point convergence check rather than sustained-below-threshold check.

**How to avoid:** Require loss below target for `patience` consecutive steps (configurable, default 100). The `steps_since_improvement` counter in `ConvergenceTracker` only resets when loss improves by `min_delta`. Do NOT declare convergence on step count alone -- loss must also be below target.

**Warning signs:** Loss curve oscillates by >20% between adjacent steps. If oscillation amplitude exceeds `min_delta`, patience will never be achieved with a reasonable `min_delta` -- increase `min_delta` or smooth with a rolling average.

### Pitfall 2: Behavioral validation produces false positives (base model = adapter output)

**What goes wrong:** The adapter loads but produces identical output to the base model. This means the adapter weights are all-zero or the training loop silently failed.

**Why it happens:** MLX LoRA training can silently produce zero-gradient updates if the model architecture doesn't match the adapter configuration. The adapter file exists and is loadable (passes check (a)) but is functionally inert.

**How to avoid:** The behavioral check must run inference on at least 3 diverse held-out prompts and compare outputs token-by-token with the base model. If ALL outputs are identical or differ only in whitespace, the adapter is invalid regardless of loadability. The check should also verify that adapter weights are not all-zero by loading the safetensors file and checking tensor norms.

**Warning signs:** `adapter_model.safetensors` file size is suspiciously small (<1KB). Training loss didn't decrease from initial value. training_metadata.json shows iters=0 or status != "complete".

### Pitfall 3: Router rule priority conflicts cause non-deterministic classification

**What goes wrong:** Two rules match the same query with the same priority but map to different specialists. The router picks one non-deterministically, producing different execution plans for identical queries.

**Why it happens:** The GQHSM model uses `EvaluationOrderPriority` for tiebreaking, but if two transitions from the same state have the same priority and both guard conditions pass, the state machine library may evaluate them in insertion order (which varies if rules are loaded from a dict/JSON where key order isn't preserved).

**How to avoid:** Rules in YAML must have unique priorities within the same source state. The router YAML schema enforces this at load time: if two rules share a source state AND priority, raise `ConfigValidationError`. Additionally, the state machine JSON schema uses an ordered array for transitions (not a dict), so insertion order is deterministic.

**Warning signs:** Logged execution plans show different specialists for nearly identical queries. Router test flakiness (passes sometimes, fails other times with different specialist selected).

### Pitfall 4: Metric persistence format incompatible with trend analysis

**What goes wrong:** Evaluation metrics are written as flat JSON per run but with inconsistent key names, missing timestamps, or non-comparable formats. Trend analysis (D-16) fails because it can't load prior runs.

**Why it happens:** The evaluator's `__main__` block currently writes flat results without timestamps or run identifiers. Extending it without a schema leads to format drift between runs.

**How to avoid:** Define a strict schema for evaluation result files and enforce it at write time. Use ISO 8601 timestamps in filenames. Include a version field so future code can handle format changes. The `MetricStore` class validates output against a schema before writing.

**Warning signs:** `artifacts/evaluations/` contains files with inconsistent keys. `json.load()` on a prior run file raises KeyError for expected fields.

## Code Examples

### Convergence Tracking Integration with Distiller

```python
# Source: Integration pattern from existing Distiller + ConvergenceTracker
# Extend Distiller.sweep_temperature() to track convergence per temperature

def sweep_temperature_with_convergence(
    self,
    student_logits: np.ndarray,
    teacher_logprobs: list,
    target_ids: list,
    temperatures: Optional[list] = None,
    convergence_config: Optional[ConvergenceConfig] = None,
) -> dict:
    if temperatures is None:
        temperatures = [1.0, 2.0, 4.0, 8.0]
    if convergence_config is None:
        convergence_config = ConvergenceConfig()

    results = {"temperatures": {}, "convergence": {}}
    best_temp = temperatures[0]
    best_loss = float("inf")

    for temp in temperatures:
        self._temperature = temp
        tracker = ConvergenceTracker(convergence_config)

        # Per-temperature loss curve (simulated here; real impl uses batches)
        losses = []
        statuses = []
        for _step in range(convergence_config.patience + 50):
            loss = self.compute_distillation_loss(
                student_logits, teacher_logprobs, target_ids
            )
            losses.append(loss)
            status = tracker.step(loss)
            statuses.append(status)
            if status in ("converged", "hard_stop"):
                break

        results["temperatures"][str(temp)] = {
            "final_loss": round(losses[-1], 6),
            "best_loss": round(tracker._state.best_loss, 6),
            "steps_run": len(losses),
            "converged": tracker._state.converged,
            "hard_stopped": tracker._state.hard_stopped,
        }
        results["convergence"][str(temp)] = {
            "loss_curve": [round(l, 6) for l in losses],
            "status_log": statuses,
        }

        if losses[-1] < best_loss:
            best_loss = losses[-1]
            best_temp = temp

    results["best_temperature"] = best_temp
    results["best_loss"] = round(best_loss, 6)
    return results
```

### Metric Persistence with Schema Validation

```python
# Source: Pattern from existing CheckpointValidator + SpecialistEvaluator
# Structured metric persistence following Phase 1 patterns

import json
from datetime import datetime, timezone
from dataclasses import dataclass, asdict
from pathlib import Path

@dataclass
class EvalMetrics:
    niche: str
    timestamp_utc: str
    num_samples: int
    perplexity: float
    bleu_score: float
    rouge_l: float
    latency_ms_mean: float
    latency_ms_p95: float
    gates_passed: dict  # {gate_name: {"passed": bool, "threshold": float, "value": float}}
    version: str = "1.0"

class MetricStore:
    REQUIRED_FIELDS = [
        "niche", "timestamp_utc", "num_samples", "perplexity",
        "bleu_score", "rouge_l", "latency_ms_mean", "latency_ms_p95",
        "gates_passed", "version",
    ]

    def __init__(self, project_root: Path):
        self._eval_dir = project_root / "artifacts" / "evaluations"
        self._eval_dir.mkdir(parents=True, exist_ok=True)

    def persist(self, metrics: EvalMetrics) -> Path:
        data = asdict(metrics)
        self._validate(data)
        ts = metrics.timestamp_utc.replace(":", "").replace("-", "")
        out_path = self._eval_dir / f"{metrics.niche}_{ts}.json"
        out_path.write_text(json.dumps(data, indent=2), encoding="utf-8")
        return out_path

    def load_prior(self, niche: str) -> list:
        """Load all prior eval runs for trend analysis."""
        prior = []
        for f in sorted(self._eval_dir.glob(f"{niche}_*.json")):
            prior.append(json.loads(f.read_text(encoding="utf-8")))
        return prior

    def _validate(self, data: dict):
        missing = [k for k in self.REQUIRED_FIELDS if k not in data]
        if missing:
            raise ValueError(f"Missing required eval fields: {missing}")
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Single-point convergence check (loss < target once) | Plateau-based sustained convergence (loss < target for N consecutive steps) | ML best practice since ~2018 (ReduceLROnPlateau, EarlyStopping in PyTorch/Keras) | Eliminates false convergence from noisy loss |
| Binary stop/continue | Two-tier (warning + hard-stop) with configurable thresholds | Specified in Phase 2 D-04 | Operators get early signal without halting pipeline; hard-stop prevents runaway bad training |
| Flat metric output files | Structured JSONL with versioned schema, timestamps, and gate results | Phase 2 D-14, D-16 | Enables trend analysis across runs; gates become queryable |
| No convergence analytics | Per-temperature loss curves + convergence rate analysis in `artifacts/sweeps/` | Phase 2 D-05 | Data-driven temperature selection replaces guesswork |
| Adapter existence = valid | Multi-prong validation (loadability + loss + behavioral diff) | Phase 2 D-08 | Catches silently-failed training that produces inert adapters |

**Deprecated/outdated:**
- Single-file evaluation output: The current `SpecialistEvaluator.__main__` writes flat JSON without timestamps. Phase 2 replaces this with `MetricStore` producing timestamped, versioned files.
- Manual temperature selection: The current `Distiller.sweep_temperature` only returns best temperature. Phase 2 adds per-temperature loss curves and convergence data in structured sweep analysis files.
- No post-training validation: `train_specialists_mlx.py` writes metadata but doesn't validate the trained adapter produces different output. Phase 2 adds `AdapterValidator`.

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | `transitions` (0.9.3) is the best lightweight Python state machine library for this use case | Standard Stack | MEDIUM -- `automaton` or a custom implementation might be more suitable for GQHSM compatibility. The planner gates this behind `checkpoint:human-verify`. |
| A2 | `transitions` supports hierarchical state machines (HSM) with nested states, matching GQHSM's hierarchical model | Architecture Patterns | LOW -- transitions documentation mentions HSM support but exact capability match with GQHSM nesting model needs verification. If transitions HSM support is insufficient, a custom implementation may be needed. |
| A3 | Plateau-based early stopping with patience and min_delta is the standard convergence definition for KD | Standard Stack | LOW -- this is well-established in ML literature (PyTorch ReduceLROnPlateau, Keras EarlyStopping). The risk is in parameter defaults, not the approach itself. |
| A4 | GQHSM JSON schema should use callback name strings (not inline code) for entry/exit actions, guards, and transition actions | Architecture Patterns | LOW -- this matches the GQHSM plugin ABI model where callbacks are registered functions. Inline expressions would be incompatible with the C++ GQHSM runtime. |
| A5 | LLM threshold evaluation prompt should require structured JSON output with justification | Architecture Patterns | LOW -- structured output is a standard pattern for LLM evaluation tasks. The risk is in prompt effectiveness for specific threshold recommendations. |
| A6 | `pip index versions` confirms `transitions` exists on PyPI but authoritative docs verification via Context7 was unavailable | Package Legitimacy Audit | LOW -- slopcheck rates it [OK], the project has 10+ years of history and ~2M downloads/month. Legitimacy risk is minimal. |

## Open Questions (RESOLVED)

1. **RESOLVED: Router uses first-match with priority ordering.** Keyword, regex, and syntax_density rules short-circuit at the highest-priority match. Fallback chain handles "try next" when confidence below threshold. Matches GQHSM model (transitions evaluated in priority order, first guard-passing transition fires).

2. **RESOLVED: Behavioral diff uses token overlap ratio, configurable per specialist.** Default threshold: >5% token difference across 3 diverse prompts. Configurable in `config/specialists/<niche>.yaml` under `behavioral_diff_threshold`. AdapterValidator implements this in Plan 02-03.

3. **RESOLVED: LLM recommendations logged by default, auto-applied only when confidence > 0.9 and change < 20%.** ThresholdAdapter implements this in Plan 02-04. Any change beyond these bounds is logged for human review only.

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| Python 3.10+ | All modules | Yes | 3.11.6 | -- |
| pytest | Testing | Yes | 8.3.5 | -- |
| mlx / mlx-lm | Adapter loading, training | Yes | 0.30.0 / 0.28.4 | -- |
| numpy | Loss computation, plateau detection | Yes | 1.26.4 | -- |
| PyYAML | Config/rule loading | Yes | 6.0.2 | -- |
| nltk | BLEU/ROUGE computation | Yes | 3.9.1 | -- |
| `transitions` [ASSUMED] | Router state machine | **No** | -- | Install via pip: `pip install transitions`. If unavailable, custom FSM in `router/state_machine.py`. |
| `openai` / `anthropic` SDKs | LLM threshold evaluation (via TeacherClient) | Yes | Installed (Phase 1) | -- |
| GQHSM submodule (C#) | JSON schema design reference | Yes | at repo root `GQHSM/` | -- |
| LiteLLM proxy | Teacher API for threshold evaluation | Yes | localhost:4000 (Phase 1) | -- |

**Missing dependencies with no fallback:**
- `transitions` [ASSUMED] -- must be installed before router module can run. The planner should add an install step.

**Missing dependencies with fallback:**
- None. All other dependencies are already installed or provided by Phase 1 infrastructure.

## Validation Architecture

### Test Framework

| Property | Value |
|----------|-------|
| Framework | pytest 8.3.5 |
| Config file | `pyproject.toml` (tool.pytest.ini_options) |
| Quick run command | `pytest tests/ -x -m "not slow"` |
| Full suite command | `pytest tests/ -x` |

### Phase Requirements to Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| DIST-01 | KD loss converges below configurable threshold with plateau-based early stopping | unit | `pytest tests/test_convergence.py::test_convergence_tracker_hard_stop -x` | New -- Wave 0 |
| DIST-01 | KD loss converges below target after patience steps with min_delta | unit | `pytest tests/test_convergence.py::test_convergence_tracker_converged -x` | New -- Wave 0 |
| DIST-02 | Temperature sweep produces per-temperature loss curves in structured JSON | unit | `pytest tests/test_distillation.py::test_sweep_with_convergence_output -x` | New -- Wave 0 |
| DIST-02 | Sweep analysis file contains convergence rate per temperature | unit | `pytest tests/test_distillation.py::test_sweep_analysis_structure -x` | New -- Wave 0 |
| TRAIN-01 | Adapter passes loadability, validation loss, and behavioral diff checks | integration | `pytest tests/test_adapter_validator.py::test_adapter_validity_checks -x` | New -- Wave 0 |
| TRAIN-01 | Behavioral check detects zero-gradient adapter (identical output to base) | integration | `pytest tests/test_adapter_validator.py::test_inert_adapter_detection -x` | New -- Wave 0 |
| TRAIN-02 | Training hyperparameters from YAML are respected at runtime | unit | `pytest tests/test_config.py::test_training_overrides_respected -x` | Extend -- Wave 0 |
| TRAIN-03 | Evaluation metrics persisted to structured JSON with timestamps | unit | `pytest tests/test_evaluator.py::test_metric_persistence_format -x` | New -- Wave 0 |
| TRAIN-03 | Prior metrics loadable for trend analysis | unit | `pytest tests/test_evaluator.py::test_load_prior_metrics -x` | New -- Wave 0 |
| ROUTE-01 | Keyword rules match queries and route to correct specialist | unit | `pytest tests/test_router.py::test_keyword_routing -x` | New -- Wave 0 |
| ROUTE-01 | No-match queries route to default encyclopedic specialist | unit | `pytest tests/test_router.py::test_no_match_default -x` | New -- Wave 0 |
| ROUTE-01 | Rules defined in YAML with no code changes required | unit | `pytest tests/test_router.py::test_yaml_driven_rules -x` | New -- Wave 0 |
| ROUTE-02 | Execution plan includes primary_specialist and execution_mode | unit | `pytest tests/test_router.py::test_execution_plan_structure -x` | New -- Wave 0 |

### Sampling Rate

- **Per task commit:** `pytest tests/ -x -m "not slow"`
- **Per wave merge:** `pytest tests/ -x`
- **Phase gate:** Full suite green before `/gsd:verify-work`

### Wave 0 Gaps

- [ ] `tests/test_convergence.py` -- covers DIST-01 convergence tracking and DIST-02 sweep analysis
- [ ] `tests/test_adapter_validator.py` -- covers TRAIN-01 adapter validity checks
- [ ] `tests/test_router.py` -- covers ROUTE-01 rule-based routing and ROUTE-02 execution plans
- [ ] `tests/test_evaluator.py` -- extends existing with TRAIN-03 metric persistence tests
- [ ] `tests/test_config.py` -- extends existing with TRAIN-02 hyperparameter override tests
- [ ] Framework install: `pip install transitions` -- new dependency for router module

## Security Domain

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | No | Phase 2 modules are internal pipeline components; authentication is handled at the API layer (Phase 1 TeacherClient handles API key auth). |
| V3 Session Management | No | No user sessions in training pipeline. |
| V4 Access Control | No | Single-machine training pipeline; no multi-user access control needed. |
| V5 Input Validation | Yes | YAML config validation (ConfigLoader pattern); JSON rule schema validation; evaluation metric schema validation. All external inputs (config files, rule definitions) are validated at load time. |
| V6 Cryptography | No | No cryptographic operations in this phase. |

### Known Threat Patterns for Python ML Training Pipeline

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| YAML deserialization attacks (unsafe yaml.load) | Tampering / Elevation | Use `yaml.safe_load()` exclusively (already done in ConfigLoader). Never use `yaml.load()`. |
| Path traversal in artifact file paths (e.g., `niche` parameter used in `artifacts/sweeps/<niche>_sweep.json`) | Tampering | Sanitize niche names: allow only `[a-z_]+`. The ConfigLoader already validates niche against the known specialists list. |
| Prompt injection in LLM threshold evaluation (user-controlled data in prior-run metrics fed to LLM prompt) | Tampering | The LLM prompt receives structured JSON data from prior runs, not user-submitted text. Format the data as a code block in the prompt. |
| Malicious rule definitions causing infinite loops or resource exhaustion (regex backtracking) | Denial of Service | Validate regex patterns at load time. Apply timeout to regex matching (Python's `re` doesn't support timeouts natively; use `regex` library with `timeout` parameter or limit input size). |
| Adapter file tampering (loading a malicious safetensors file) | Tampering | safetensors format is designed to be safer than pickle. Verify file integrity via size check before loading. The behavioral validation will catch adapters that produce nonsensical output. |

## Sources

### Primary (HIGH confidence)
- GQHSM XML state machine definitions (`Valve.xml`, `Air.xml`) -- analyzed to derive JSON schema, hierarchical state model, transition priority, and guard/action patterns
- Existing codebase: `distill/distillation.py`, `training/train_specialists_mlx.py`, `eval/evaluator.py`, `eval/benchmarker.py`, `config/loader.py`, `pipeline/checkpoint.py`, `distill/cascade.py`
- Phase 1 CONTEXT.md -- established patterns (two-layer config, per-specialist overrides, checkpoint validation, teacher cascade)
- Phase 2 CONTEXT.md -- all implementation decisions (D-01 through D-17)

### Secondary (MEDIUM confidence)
- GQHSM intel context (`intel/context.md` Cognitive OS Extension section) -- GQHSM runtime description, plugin ABI, guard callbacks, generic callbacks
- `pyproject.toml` and `requirements.txt` -- confirmed installed package versions
- `pip index versions` -- confirmed `transitions` 0.9.3 exists on PyPI

### Tertiary (LOW confidence)
- Training knowledge for plateau-based early stopping -- not verified against current ML literature publications
- Training knowledge for `transitions` library HSM capabilities -- not verified against official documentation
- Training knowledge for LLM prompt engineering patterns -- not verified against current research
- Training knowledge for JSON Schema Draft 2020-12 patterns -- not verified against official schema docs

## Metadata

**Confidence breakdown:**
- Standard stack: MEDIUM -- `transitions` [ASSUMED] needs human verification; all other packages are already installed and verified
- Architecture: HIGH -- patterns are directly derived from existing codebase (ConfigLoader, checkpoint pattern, cascade pattern) and GQHSM XML analysis
- Pitfalls: MEDIUM -- pitfalls are based on common ML training issues; actual Phase 2 implementation may surface project-specific pitfalls
- GQHSM JSON schema: HIGH -- directly derived from GQHSM XML format analysis (`Valve.xml`, `Air.xml`); states, transitions, guards, hierarchical nesting, and priority ordering all map cleanly

**Research date:** 2026-06-21
**Valid until:** 2026-07-21 (30 days -- domain is stable, no fast-moving dependencies)

**Web search unavailable:** This research was conducted without web search access. All web-dependent claims are tagged [ASSUMED]. The planner must add `checkpoint:human-verify` tasks before installing new packages or finalizing convergence algorithm defaults.
