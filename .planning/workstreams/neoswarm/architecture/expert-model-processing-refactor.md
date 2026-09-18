# ADR: Expert Model and Model Processor Refactor

- **Status:** proposed
- **Date:** 2026-09-17
- **Scope:** GNUS-NEO-SWARM model/expert interfaces, GCS integration, local and distributed model execution
- **Decision type:** architecture, model taxonomy, runtime interface, migration plan
- **Parent architecture:**
  - `GeniusCognitiveSystem/docs/architecture/model-and-router.md`
  - `GeniusCognitiveSystem/docs/architecture/system-overview.md`
  - `GeniusCognitiveSystem/docs/architecture/speculative-decoding-and-vtg.md`
  - `GeniusCognitiveSystem/docs/architecture/eggroll-swarm-retraining.md`

## Context

GNUS-NEO-SWARM currently exposes the specialist model layer primarily through `IELM`, where ELM means **Expert Language Model**. The current interface is intentionally simple and language-oriented: an expert accepts text/context and returns text. That abstraction was sufficient while specialist execution was predominantly autoregressive language generation.

GCS now requires expert execution to describe several **orthogonal dimensions** rather than one inheritance taxonomy:

- **Cognitive role** — Planner, Verifier, Router, Formatter, Grounding, domain specialist, and similar jobs.
- **Public contract/capability** — language generation, bounded judgment, classification, ranking, refinement, infill, embedding, vision, and similar operations.
- **Processor architecture** — autoregressive, direct-logit/classifier, diffusion/denoising, encoder, reranker, multimodal, or another computation mechanism.
- **Execution backend** — MNN, SGProcessing, Vulkan/CPU, or a remote SuperGenius node.

**ELM — Expert Language Model** remains the precise label for an expert exposing a language-generation/transformation contract. **EJM — Expert Judgment Model** remains the precise label for an expert exposing bounded typed judgment. Diffusion is a processor architecture and may implement refinement **or judgment**; an Expert Diffusion Model (EDM) is therefore a useful implementation label, not a mutually exclusive peer contract that prevents the same expert from also acting as an EJM.

The architecture therefore must stop treating `language` as synonymous with `model execution`, and it must also stop treating `judgment` and `diffusion` as mutually exclusive model families.

This refactor also preserves a critical GCS authority boundary: expert outputs are advisory cognitive artifacts. Deterministic policy, capability, privacy, authorization, approval, and side-effect services remain authoritative.

## Decision

### 1. Introduce `IExpertModel` as the neutral expert abstraction

`IExpertModel` is the common lifecycle and metadata contract for model-backed cognitive experts.

Conceptually, the neutral expert object owns metadata and composes operation capabilities with one or more processors:

```text
IExpertModel
|-- role / domain / policy metadata
|-- advertised capabilities
|-- model artifact(s)
`-- processor adapter(s)
      |-- GENERATE
      |-- JUDGE / CLASSIFY / RANK / SCORE
      |-- REFINE / INFILL
      `-- future capabilities
```

Do **not** encode ELM, EJM, and diffusion as mutually exclusive subclasses. One loaded model artifact may expose multiple contracts through the same runtime state.

The common contract should own only concerns that are genuinely shared:

- model/expert identity;
- cognitive role and domain metadata;
- lifecycle (`Load`, `IsLoaded`, unload if supported);
- capability advertisement;
- artifact/version/runtime metadata;
- confidence/uncertainty metadata only where semantically meaningful;
- policy and privacy compatibility metadata.

It should **not** force every expert family through a `string -> string` function.

### 2. Keep ELM as a precise language-specific term

ELM continues to mean **Expert Language Model**.

An ELM exposes language-generation or language-transformation behavior, for example:

- open-ended generation;
- draft generation;
- explanation generation;
- summarization;
- formatting or rewriting where the output contract is language/text;
- streaming token generation.

The existing `IELM::Process(const std::string&, const ELMContext&) -> std::string` contract is therefore a legacy language-specific interface, not the correct root abstraction for every future expert model.

### 3. Rename bounded Decision ELMs to Expert Judgment Models (EJMs)

The long-term architecture uses **EJM — Expert Judgment Model** for bounded semantic judgments.

An EJM consumes context plus a bounded criterion/choice contract and returns a typed judgment, not generated prose.

Representative outputs:

- boolean probability;
- fixed-choice probability distribution;
- classification result;
- bounded ordinal or continuous score;
- rank/order over candidates;
- calibrated confidence or uncertainty;
- parallel judgment bundle sharing one context prefix.

Representative uses:

- intent/domain classification;
- routing and expert selection;
- risk scoring;
- grounding/verification selection;
- claim/evidence classification;
- contradiction detection;
- verifier/arbiter judgments;
- policy-support scoring where deterministic policy remains authoritative.

A JEV-style selected-logit evaluator is an EJM backend even if it reuses a causal language-model backbone. The **backbone provenance does not define the expert contract**.

### 4. Treat diffusion as a processor architecture, not an exclusive contract

A diffusion-backed expert uses iterative denoising or masked/block refinement internally. **EDM — Expert Diffusion Model** may remain as shorthand for such an implementation, but it is not mutually exclusive with ELM/EJM contract labels.

A diffusion processor may expose, for example:

- **REFINE / INFILL** for missing JSON fields, code-patch skeleton completion, schema/template repair, or tool-call argument infill;
- **JUDGE / CLASSIFY / SCORE** by seeding a mostly fixed answer canvas, leaving bounded answer slots unresolved, and reading the exact candidate-token distributions at those slots;
- future multimodal judgment or refinement when the underlying model supports vision/audio inputs.

Initial GCS diffusion use remains deliberately small and bounded. Refinement output remains provisional until verified, and diffusion-based judgment remains advisory like any other EJM result.

This does not make image, audio, or video diffusion an MVP dependency.

### 5. Separate cognitive expert identity from processing mechanism

`IExpertModel` answers **what cognitive job this component performs**.

A model processor answers **how the underlying computation is executed**.

Target separation:

```text
Cognitive Expert
    |
    v
Expert Model Contract
    |
    v
Model Processor
    |
    v
Execution Backend
```

Examples:

```text
Verifier role
  -> required capability: JUDGE
  -> EJM contract
  -> direct-logit/autoregressive processor OR diffusion structured-read processor
  -> MNN / compatible runtime
  -> CPU/Vulkan/SGProcessing execution

Primary Draft role
  -> required capability: GENERATE
  -> ELM contract
  -> autoregressive processor
  -> MNN
  -> local or distributed execution

Formatter role
  -> required capability: REFINE
  -> diffusion processor
  -> MNN or compatible runtime
  -> local execution + schema verification
```

The runtime must not infer cognitive semantics merely from which backend executed the tensor graph.

### 6. Introduce neutral model processor interfaces

The processor layer should expose computation primitives without embedding GCS cognitive roles.

Conceptual target separates **operation interfaces** from **processor architecture**:

```cpp
class IModelProcessor {
public:
    virtual ~IModelProcessor() = default;
    virtual ProcessorCapabilities GetCapabilities() const = 0;
    virtual outcome::result<void> Load(const ModelArtifact& artifact) = 0;
    virtual bool IsLoaded() const = 0;
};

class IGenerationCapability {
public:
    virtual outcome::result<GenerationResult>
    Generate(const GenerationRequest& request) = 0;
};

class IJudgmentCapability {
public:
    virtual outcome::result<JudgmentResult>
    Judge(const JudgmentRequest& request) = 0;
};

class IRefinementCapability {
public:
    virtual outcome::result<RefinementResult>
    Refine(const RefinementRequest& request) = 0;
};
```

Concrete processor adapters may implement more than one operation interface:

```text
AutoregressiveProcessor
  -> IGenerationCapability
  -> IJudgmentCapability       (selected-logit / bounded read)

DiffusionProcessor
  -> IJudgmentCapability       (structured read)
  -> IRefinementCapability     (denoise / infill / repair)
```

These names are illustrative; adapters are preferred when changing the existing engine hierarchy directly would cause unnecessary churn.

### 7. Prefer composition over a deep inheritance tree

An expert should normally compose one or more processors rather than encode every runtime combination through inheritance.

Conceptually:

```cpp
class ExpertModelBase {
    ExpertRole role;
    ExpertModelCapabilities capabilities;
    std::shared_ptr<IModelProcessor> processor;
};
```

A hybrid expert can expose multiple expert contracts while sharing a model artifact/backbone and runtime state.

Example:

```text
Verifier expert
|-- Judge(): correctness / contradiction probabilities
`-- Generate(): explanation only when the execution plan requests one
```

This preserves the useful GCS behavior previously described as a model exposing both generative and Decision ELM output without incorrectly naming the bounded path a language output.

### 8. Capability advertisement becomes first-class

Expert/model capability flags should describe behavior rather than family names alone.

Initial candidate capabilities:

```text
GENERATE
STREAM
JUDGE
CLASSIFY
RANK
SCORE
INFILL
REFINE
EMBED
VISION
```

Processor architecture is advertised separately, for example `AUTOREGRESSIVE`, `DIFFUSION`, `ENCODER`, or `MULTIMODAL`.

A node or processor may advertise multiple capabilities. The Router/RuntimeCoordinator selects the required contract first, then a compatible processor architecture and execution backend.

Distributed capability advertisement should eventually expose stable identifiers such as:

```text
expert.language.generate
expert.language.stream
expert.judgment
expert.judgment.bundle
expert.refine
processor.autoregressive
processor.diffusion
```

### 9. Judgment output must be typed and must not replace content state

The current sequential ELM chain assumes each expert returns text and that the returned text becomes the next `currentOutput`. That behavior is wrong for judgment-only experts.

The execution graph must distinguish at least:

- **content artifacts** — drafts, explanations, patches, formatted text;
- **control/judgment artifacts** — probabilities, scores, classifications, ranks, escalation recommendations;
- **refinement artifacts** — denoised/repaired bounded state;
- **evidence/provenance artifacts** — references and validation metadata.

An EJM result normally informs routing, verification, arbitration, or escalation. It must not overwrite the current generated content unless an explicit stage contract says to transform content.

### 10. Initial EJM contract

A minimal typed contract should support JEV-style bounded judgments without baking JEV-specific prompt syntax into the public API.

Candidate structures:

```cpp
struct JudgmentChoice {
    std::string id;
    std::string description;
};

struct JudgmentRequest {
    std::string context;
    std::string criterion;
    std::vector<JudgmentChoice> choices;
};

struct JudgmentResult {
    std::vector<float> probabilities;
    std::size_t selected = 0;
    float calibratedConfidence = 0.0f;
    float entropy = 0.0f;
    float top2Margin = 0.0f;
};
```

The real implementation should also carry model/artifact version, prompt/template version, tokenizer version, quantization/runtime identity, timing, and enough provenance for calibration and replay.

### 11. Bounded EJM execution is processor-independent

The public `JudgmentRequest` remains semantic. The processor adapter compiles it into the representation required by the selected architecture.

For a causal/direct-logit processor:

```text
context + criterion + bounded choices
        -> tokenize/validate choice labels
        -> prefill shared context
        -> one forward evaluation at answer boundary
        -> fetch logits for every allowed token id
        -> normalize/calibrate
        -> JudgmentResult
```

For a diffusion structured-read processor:

```text
context + criterion + bounded choices
        -> tokenize/validate single-token slot labels
        -> seed fixed answer canvas
        -> leave bounded answer slots unresolved
        -> run one bounded/read-only denoise step
        -> fetch logits for every allowed token id at each answer slot
        -> normalize/calibrate
        -> optional additional noise draws only when uncertainty is high
        -> JudgmentResult / JudgmentBundleResult
```

No prose generation or parser loop is required in either path.

The compiled processor request should carry the exact candidate token ids. It must **not** depend on global top-k logprobs, because a valid bounded choice may fall outside the returned top-k even though it must still participate in the normalized choice distribution.

The current MNN implementation already has a lower-level forward primitive internally. The refactor should expose an appropriate processor-level primitive without forcing the RuntimeCoordinator to depend on MNN internals.

Required correctness checks include:

- choice labels map to exactly one valid tokenizer token at the actual answer boundary when the selected processor requires single-token slots;
- labels are distinct and round-trip correctly;
- all allowed candidate token logits are requested/evaluated explicitly;
- read-only/bounded execution stops once the judgment state is available rather than completing an unnecessary generation/commit loop;
- cached and uncached execution agree within declared tolerance;
- option-order reversal/paraphrase tests do not reveal pathological instability;
- uncertainty/entropy thresholds trigger bounded rereads or escalation rather than silently converting uncertainty into confidence;
- SGFP4 and other quantization modes are tested for judgment argmax, margin, and calibration drift rather than perplexity alone.

### 12. Judgment bundles declare dependency semantics

The EJM API should support multiple judgments against the same context packet while distinguishing **independent** from **sequential/dependent** judgments.

Conceptually:

```cpp
enum class JudgmentDependency {
    Independent,
    Sequential
};
```

Independent judgments may share a prefix, forward pass, or diffusion canvas when supported. Sequential judgments are staged so later judgments may condition on earlier results.

This enables native shared-prefix/KV reuse or multi-slot diffusion reads without silently coupling semantics. Additional stochastic/noise draws used only to estimate uncertainty remain an internal processor operation, not separate cognitive stages.

### 13. Diffusion-backed refinement remains verified and bounded

Diffusion REFINE/INFILL output is provisional until accepted by the configured verifier path. Diffusion JUDGE output follows the same advisory/calibration rules as any other EJM result.

Verification may be:

- schema validation;
- compiler/test/static analysis;
- tool dry-run;
- target-model verification;
- EJM/ELM verifier;
- another deterministic contract.

The initial EDM implementation should remain focused on low-entropy structured regions where verification is cheap.

## Naming and terminology

The preferred terminology is deliberately multi-axis:

| Term | Meaning |
|---|---|
| **EM** | Expert Model; neutral umbrella for a model-backed cognitive expert |
| **ELM** | Expert Language Model; expert exposing a language-generation/transformation contract |
| **EJM** | Expert Judgment Model; expert exposing a bounded typed judgment contract |
| **EDM** | Expert Diffusion Model; shorthand for a diffusion-backed expert implementation; may also expose EJM and/or refinement capabilities |
| **Autoregressive / Diffusion / Encoder / Multimodal** | processor architecture labels, orthogonal to cognitive role and public contract |

`Decision ELM` is a transitional/deprecated architecture term. Existing code/comments may keep the old term temporarily during migration, but new interfaces and documentation should use **EJM** for the judgment contract.

Critically, **EDM is not a third exclusive contract alongside ELM and EJM**. A diffusion-backed Verifier can be an EJM; a diffusion-backed Formatter can expose REFINE; one artifact may expose both.

## Migration plan

### Phase 1 — Types and adapters, no behavioral break

- Add neutral `IExpertModel` metadata/lifecycle abstraction.
- Add capability flags independently from processor-architecture flags.
- Add small operation interfaces for generation, judgment, and refinement rather than a deep ELM/EJM/EDM inheritance tree.
- Keep existing `IELM` registry and API paths operational through a generation-capability adapter.
- Add typed `JudgmentRequest`, `JudgmentResult`, and `JudgmentBundle` structures with dependency semantics.

### Phase 2 — EJM runtime path

- Add a judgment-capability adapter over the existing causal/direct-logit path.
- Expose selected-logit/forward functionality through the processor boundary.
- Implement tokenizer answer-boundary validation and exact candidate-token-logit retrieval.
- Implement normalized probabilities plus calibration metadata.
- Add cached/shared-prefix judgment execution where supported.
- Keep the public EJM contract processor-independent so a diffusion structured-read adapter can implement the same `Judge(...)` operation later.

### Phase 3 — Execution graph semantics

- Replace string-only expert-chain assumptions with typed stage artifacts.
- Prevent judgment artifacts from replacing content state by default.
- Allow router/planner stages to consume EJM outputs directly.
- Update expert registry to discover by role + capability + model family.

### Phase 4 — Distributed capability support

- Advertise cognitive capabilities separately from processor architecture through node capability profiles.
- Add typed judgment/refinement job/result contracts where SGProcessing or remote execution requires them.
- Preserve local cache affinity for shared-prefix judgment bundles and architecture-specific shared state.

### Phase 5 — Diffusion processor prototype

- Introduce a diffusion processor adapter that can expose `IRefinementCapability` and, where supported, `IJudgmentCapability`.
- Implement one Micro-Diffusion Block Drafter experiment for a schema/JSON or code-patch workload.
- Prototype one bounded structured-read judgment using fixed single-token slots and exact candidate logits if a suitable diffusion model/runtime is available.
- Require deterministic validation before committing refinement output.

### Phase 6 — Calibration, retraining, and compatibility cleanup

- Add EJM calibration objectives to EGGROLL training/evaluation paths.
- Add SGFP4 judgment stability benchmarks.
- Deprecate `Decision ELM` terminology in code and docs.
- Remove legacy `IELM` aliases only after downstream GCS/Flutter/SDK integrations have migrated.

## Testing requirements

### ELM

- existing generation/streaming behavior remains unchanged during migration;
- legacy role ELM tests continue to pass.

### EJM

- fixed-choice correctness;
- probability normalization over the complete allowed choice set;
- exact candidate-token retrieval independent of top-k;
- option order reversal;
- criterion paraphrase robustness;
- irrelevant-context robustness;
- missing-evidence/abstain behavior;
- cached vs fresh forward agreement;
- batch-one vs shared-prefix or shared-canvas agreement;
- independent vs sequential bundle semantics;
- bounded/read-only termination;
- uncertainty-triggered reread behavior;
- quantization precision variants;
- Brier/log-loss/calibration and confident-error metrics;
- escalation threshold behavior.

### EDM

- bounded iteration count;
- deterministic verifier acceptance;
- rollback/rejection behavior;
- schema/compiler/tool validation as applicable;
- no unverified block commitment.

## Non-goals

This ADR does not:

- require immediate implementation of image/audio/video diffusion;
- require replacing MNN;
- require a new top-level GCS execution mode solely for EJM or EDM;
- grant model judgments authority over deterministic policy/capability services;
- require converting every existing specialist into a new model family;
- require removing ELM terminology where the component really is a language model.

## Consequences

### Positive

- terminology matches actual model contracts;
- JEV-style judgment becomes a first-class runtime path rather than a language-generation special case;
- diffusion fits naturally without abusing the ELM name;
- future non-language experts can be added without another root-interface rewrite;
- routing and distributed capability advertisement become more explicit;
- typed judgment artifacts improve correctness and orchestration semantics.

### Costs

- registry and execution graph contracts must become typed/capability-aware;
- compatibility adapters are required during migration;
- MNN/SGProcessing boundaries need a judgment primitive beyond generation;
- tests must cover calibration and processor-mode stability, not only generated text quality.

## Decision summary

GCS/NeoSwarm should treat **Expert Model (EM)** as the umbrella abstraction and keep **cognitive role**, **public capability contract**, **processor architecture**, and **execution backend** as separate dimensions. **ELM** identifies a language-generation contract; **EJM** identifies a bounded judgment contract. **Diffusion** identifies a processor architecture, and **EDM** may be used as shorthand for a diffusion-backed expert without implying that it cannot also be an EJM. Autoregressive and diffusion processors may both implement the same `JUDGE` contract, while diffusion may additionally implement `REFINE/INFILL`.
