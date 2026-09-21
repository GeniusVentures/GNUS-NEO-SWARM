# ADR Addendum: GQHSM Coordination of Expert Model Processors

- **Status:** proposed
- **Date:** 2026-09-17
- **Scope:** GNUS-NEO-SWARM runtime coordination, Expert Model processor dispatch, GCS integration
- **Companion decision:** `expert-model-processing-refactor.md`
- **Parent decision:** `runtime-coordinator.md`

## Context

The Expert Model refactor separates **cognitive role**, **required capability**, **processor architecture**, and **execution backend**.

Examples of contracts/capabilities include:

- **ELM — Expert Language Model** for language generation/transformation;
- **EJM — Expert Judgment Model** for bounded typed judgments;
- **REFINE / INFILL** for bounded repair or completion;
- future embedding, reranking, vision, audio, or multimodal capabilities.

Processor architectures are orthogonal: autoregressive, direct-logit/classifier, diffusion, encoder, reranker, or multimodal processors may implement one or more of those capabilities. In particular, a diffusion processor may implement **JUDGE** through a bounded structured read as well as **REFINE** through denoising.

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

Do not create separate top-level state machines for ELM, EJM, or processor architectures such as diffusion.

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

The **required capability and result contract** determine the typed request/result and validation callback. Processor architecture changes implementation details behind the adapter, not the overall orchestration model.

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
RefinementRequest
```

The processor registry resolves the invocation to an adapter supporting the requested capability, then selects an allowed processor architecture and execution backend. A `JudgmentRequest` may therefore resolve to a causal selected-logit adapter or a diffusion structured-read adapter without changing GQHSM state.

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
    RefinementResult
>;
```

The state-machine context records the result as a stage artifact together with provenance and execution metadata.

A result-type-aware callback determines how it affects cognitive state:

- `GenerationResult` may update or append content state;
- `JudgmentResult` normally updates control/judgment state and must not overwrite generated content by default;
- `RefinementResult` remains provisional until its configured verifier accepts the refined block, regardless of whether the processor was diffusion-based or another implementation;
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

Processor-specific behavior lives behind small capability interfaces/adapters such as:

```text
IGenerationCapability::Generate(...)
IJudgmentCapability::Judge(...)
IRefinementCapability::Refine(...)
```

A concrete `AutoregressiveProcessor` or `DiffusionProcessor` may implement more than one of these interfaces.

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

### 7. Capability and processor architecture may influence guards

The state graph remains shared, but guards may inspect the **required capability**, processor architecture, and artifact type independently.

Examples:

```text
JUDGE capability
- require bounded-choice validation
- require exact candidate-token evaluation when the adapter uses token labels
- evaluate calibration/uncertainty thresholds
- optionally trigger bounded rereads/noise draws
- escalate when confidence or margin is insufficient

REFINE capability
- require bounded iteration/work budget
- require schema/compiler/tool/target verification before commit

GENERATE capability
- enforce generation/token/deadline budgets
- optionally stream partial content events

DIFFUSION processor architecture
- enforce canvas/step bounds where applicable
- keep stochastic rereads and denoising loops inside the processor adapter
```

These are policy/validation differences inside a common lifecycle, not separate orchestration systems.

### 8. Judgment bundles remain one processor operation unless semantically dependent

A parallel judgment bundle should normally appear to GQHSM as one stage execution:

```text
prepare shared context
    ↓
execute JudgmentBundleRequest
    ↓
JudgmentBundleResult
    ↓
consume independent judgments
```

The selected processor/runtime owns prefix/KV reuse, shared diffusion canvas reads, candidate-logit extraction, and bounded uncertainty rereads. GQHSM should not model tensor-level branches or repeated noise draws as cognitive states.

If judgments are declared **sequential/dependent**, GQHSM may stage them as separate cognitive steps so later judgments can consume earlier semantic results. Independence/dependency is therefore a request-level semantic property, not an inference-architecture property.

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
2. typed `GenerationRequest/Result`, `JudgmentRequest/Result`, and `RefinementRequest/Result` contracts as needed;
3. a processor registry keyed by artifact + capability + processor/runtime requirements;
4. thin adapters over the existing MNN generation path, causal/direct-logit judgment path, and diffusion judgment/refinement primitives;
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
- commit unverified refinement output;
- require all stages to use a state machine when a direct deterministic call is simpler.

## Consequence

The combination of **Expert Model contracts + capability-oriented processor adapters + GQHSM lifecycle coordination** should keep the implementation delta small. GQHSM selects what operation is required; the registry selects how that operation is computed. New autoregressive, diffusion, encoder, or multimodal processors therefore remain pluggable beneath a stable cognitive state machine instead of requiring new orchestration code for each processor architecture.
