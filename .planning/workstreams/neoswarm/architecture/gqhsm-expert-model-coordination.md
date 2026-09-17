# ADR Addendum: GQHSM Coordination of Expert Model Processors

- **Status:** proposed
- **Date:** 2026-09-17
- **Scope:** GNUS-NEO-SWARM runtime coordination, Expert Model processor dispatch, GCS integration
- **Companion decision:** `expert-model-processing-refactor.md`
- **Parent decision:** `runtime-coordinator.md`

## Context

The Expert Model refactor introduces multiple model-processing contracts beneath a common cognitive expert layer:

- **ELM — Expert Language Model** for language generation/transformation;
- **EJM — Expert Judgment Model** for bounded typed judgments, including JEV-style selected-logit evaluation;
- **EDM — Expert Diffusion Model** for iterative denoising, infill, or bounded refinement;
- future processor families such as embedding, reranking, vision, audio, or multimodal execution.

These processors differ in their internal inference loops, but most GCS orchestration around them is the same: resolve an expert, verify capability and policy, prepare context, execute, validate the result, emit artifacts, and either continue, escalate, retry, or fall back.

GNUS-NEO-SWARM already contains a GQHSM-compatible, data-driven hierarchical state-machine pattern. The current Python POC consumes JSON state-machine definitions and binds named entry, exit, guard, and transition actions to registered callbacks. The same JSON contract is intended to be consumable by the C++ GQHSM runtime.

This makes GQHSM a natural coordination mechanism for heterogeneous model processors without putting model-specific inference code into the RuntimeCoordinator.

## Decision

### 1. GQHSM coordinates processor lifecycle, not processor internals

The RuntimeCoordinator may use GQHSM-compatible hierarchical state machines to coordinate Expert Model stages.

GQHSM owns orchestration semantics such as:

- stage entry and exit;
- expert and processor resolution;
- capability guards;
- policy/privacy guards;
- local versus distributed placement decisions;
- retry/fallback/escalation transitions;
- verifier selection;
- artifact publication;
- cancellation, deadline, and terminal-state transitions.

GQHSM does **not** own:

- autoregressive decoding loops;
- sampling;
- tokenizer implementation;
- selected-logit/JEV scoring internals;
- KV-cache implementation;
- diffusion/denoising iteration loops;
- MNN graph execution;
- SGFP4 kernels;
- SGProcessingManager pass internals;
- SuperGenius worker scheduling internals.

Those remain processor/runtime responsibilities.

### 2. Use one generic processor-execution state machine

Do not create separate top-level state machines for ELM, EJM, and EDM.

Prefer one reusable execution lifecycle carrying a typed invocation in request state:

```text
resolve_expert
    ↓
resolve_processor
    ↓
prepare_input
    ↓
execute_processor
    ↓
validate_result
    ↓
┌──────────────┬───────────────┬───────────────┐
│ content path │ judgment path │ refinement path│
└──────────────┴───────────────┴───────────────┘
    ↓
verify / consume / commit
    ↓
complete | continue | fallback | escalate
```

The processor family changes the typed request/result and validation callback, not the overall orchestration model.

### 3. Processor selection is capability-driven

The state-machine context should carry the cognitive role and required capabilities rather than hard-code model class names.

Conceptual request:

```cpp
struct ExpertInvocation {
    ExpertRole role;
    ProcessorCapability requiredCapability;
    ExpertArtifactRef expert;
    ExecutionPolicy policy;
    ContextPacket context;
    InvocationPayload payload;
};
```

`InvocationPayload` may be a tagged/variant type containing, for example:

```text
GenerationRequest
JudgmentRequest
JudgmentBundleRequest
DiffusionRequest
```

The processor registry resolves the invocation to an adapter supporting the requested capability.

Conceptually:

```cpp
processor = registry.Resolve(
    invocation.expert,
    invocation.requiredCapability,
    executionRequirements);
```

This keeps GQHSM definitions stable when new processor implementations are added.

### 4. Results are typed stage artifacts

The generic execution callback should return a typed processor artifact rather than flattening every output to a string.

Conceptually:

```cpp
using ProcessorResult = std::variant<
    GenerationResult,
    JudgmentResult,
    JudgmentBundleResult,
    DiffusionResult
>;
```

The state-machine context records the result as a stage artifact together with provenance and execution metadata.

A result-type-aware callback determines how it affects cognitive state:

- `GenerationResult` may update or append content state;
- `JudgmentResult` normally updates control/judgment state and must not overwrite generated content by default;
- `DiffusionResult` remains provisional until its configured verifier accepts the refined block;
- all results may emit provenance, timing, model identity, quantization identity, and execution-integrity metadata.

### 5. Keep callback glue small

GQHSM should bind generic orchestration callbacks rather than one callback per concrete model.

Recommended callback surface:

```text
resolve_expert
resolve_processor
check_capability
check_policy
prepare_processor_input
execute_processor
validate_processor_result
select_verifier
commit_stage_artifact
emit_stage_event
select_fallback
```

Processor-specific behavior lives behind adapter interfaces such as:

```text
IAutoregressiveProcessor::Generate(...)
IJudgmentProcessor::Judge(...)
IDiffusionProcessor::Refine(...)
```

Adding a new implementation of an existing capability should normally require registry/configuration changes, not new GQHSM states.

### 6. Use hierarchical states for common behavior

GQHSM hierarchy can express shared lifecycle behavior once and specialize only where necessary.

Conceptual structure:

```text
expert_stage
├── resolve
├── prepare
├── execute
│   ├── local
│   └── delegated
├── validate
├── verify
├── commit
└── failure
    ├── retry
    ├── fallback
    └── escalate
```

The `execute` state's callback dispatches the typed invocation through the processor registry. It should not branch into a large hard-coded switch over every model artifact.

### 7. Processor family may influence guards and verification policy

The state graph remains shared, but guards may inspect capabilities and artifact type.

Examples:

```text
EJM
- require bounded choice/token validation when selected-logit mode is used
- evaluate calibration/uncertainty thresholds
- escalate when confidence or margin is insufficient

EDM
- require bounded iteration budget
- require schema/compiler/tool/target verification before commit

ELM
- enforce generation/token/deadline budgets
- optionally stream partial content events
```

These are policy/validation differences inside a common lifecycle, not separate orchestration systems.

### 8. Shared-prefix EJM fan-out is one processor operation

A JEV-style parallel judgment bundle should normally appear to GQHSM as one stage execution:

```text
prepare shared context
    ↓
execute JudgmentBundleRequest
    ↓
JudgmentBundleResult
    ↓
consume independent judgments
```

The EJM processor/runtime owns prefix/KV reuse and suffix fan-out. GQHSM should not model each tensor-level branch as a cognitive state unless the individual judgments themselves have different downstream cognitive dependencies.

This preserves the performance advantage of shared-prefix evaluation while keeping the state graph compact.

### 9. Distributed execution uses the same cognitive lifecycle

The state machine should not need a different cognitive graph merely because execution occurs on a remote SuperGenius node.

The `execute_processor` stage chooses an execution adapter:

```text
local processor adapter
        or
SGProcessing adapter
        or
SuperGenius distributed adapter
```

The adapter returns the same typed logical result contract plus execution provenance.

The RuntimeCoordinator/GQHSM remains responsible for what the stage means and what happens next; SuperGenius remains responsible for worker discovery, capability matching, assignment, transport, retries, execution attestation, accounting, and settlement.

### 10. GQHSM definitions remain data-driven

Processor orchestration should be representable in GQHSM-compatible JSON so execution policy can evolve without rewriting the runtime state engine.

Illustrative state fragment:

```json
{
  "states": [
    {"name": "resolve_processor", "entryAction": "resolve_processor"},
    {"name": "execute_processor", "entryAction": "execute_processor"},
    {"name": "validate_result", "entryAction": "validate_processor_result"},
    {"name": "verify", "entryAction": "select_verifier"},
    {"name": "commit", "entryAction": "commit_stage_artifact"},
    {"name": "fallback", "entryAction": "select_fallback"}
  ]
}
```

The exact schema should reuse the existing GQHSM compatibility contract rather than introduce a second state-machine format.

## Minimal implementation delta

The Expert Model refactor does not require a large new orchestration framework if GQHSM is used as the coordination layer.

The first useful implementation can be limited to:

1. neutral Expert Model metadata/capability types;
2. typed `GenerationRequest/Result`, `JudgmentRequest/Result`, and `DiffusionRequest/Result` contracts as needed;
3. a processor registry keyed by artifact + capability + execution requirements;
4. thin adapters over the existing MNN/ELM path and the new EJM/EDM primitives;
5. a typed stage-artifact container in request state;
6. generic GQHSM callbacks for resolve, execute, validate, verify, commit, fallback, and escalation;
7. one shared processor-execution state-machine definition.

The existing RuntimeCoordinator remains the owner of the overall GCS request lifecycle. GQHSM is an implementation mechanism for expressing and driving that lifecycle; it is not a second coordinator.

## Non-goals

This addendum does not:

- move model inference loops into GQHSM;
- require one state per model class;
- make state-machine definitions aware of MNN graph internals;
- replace SGProcessingManager or SuperGenius scheduling;
- make EJM judgments authoritative over deterministic policy;
- commit unverified EDM output;
- require all stages to use a state machine when a direct deterministic call is simpler.

## Consequence

The combination of **Expert Model contracts + capability-oriented processor adapters + GQHSM lifecycle coordination** should keep the implementation delta small. New model processors become pluggable execution capabilities under a stable cognitive state machine instead of requiring new top-level orchestration code for each model family.
