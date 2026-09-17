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

GCS now requires multiple expert computation families whose public contracts are not all language generation:

- **Expert Language Models (ELMs)** generate or transform language.
- **Expert Judgment Models (EJMs)** perform bounded semantic judgment and return typed probabilities, scores, rankings, classifications, or choice distributions. A JEV-style direct-logit implementation is an EJM even when its backbone was pretrained as a language model.
- **Expert Diffusion Models (EDMs)** iteratively denoise, infill, or refine a bounded state or structured block. The existing Micro-Diffusion Block Drafter is the first planned EDM use case.
- future expert families may include embedding, reranking, vision, audio, multimodal, or other model types.

The architecture therefore must stop treating `language` as synonymous with `model execution` while preserving ELM as the correct name for experts whose contract really is language generation.

This refactor also preserves a critical GCS authority boundary: expert outputs are advisory cognitive artifacts. Deterministic policy, capability, privacy, authorization, approval, and side-effect services remain authoritative.

## Decision

### 1. Introduce `IExpertModel` as the neutral expert abstraction

`IExpertModel` is the common lifecycle and metadata contract for model-backed cognitive experts.

Conceptually:

```text
IExpertModel
|-- IExpertLanguageModel   (ELM)
|-- IExpertJudgmentModel   (EJM)
|-- IExpertDiffusionModel  (EDM)
`-- future expert model interfaces
```

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

### 4. Use EDM for diffusion-based experts

**EDM — Expert Diffusion Model** represents expert behavior based on iterative denoising, infill, or state refinement.

Initial GCS use is deliberately small and bounded:

```text
masked / partial structured block
        -> tiny role-specific denoiser
        -> few refinement steps
        -> deterministic or expert verification
        -> accepted block
```

Initial targets include:

- missing JSON fields;
- code patch skeleton completion;
- schema/template repair;
- tool-call argument infill;
- other low-entropy structured regions.

This does not require GCS to treat image diffusion as an MVP dependency. The abstraction merely avoids preventing future image/audio/video/latent diffusion experts.

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
  -> Expert Judgment Model
  -> selected-logit / judgment processor
  -> MNN
  -> CPU/Vulkan/SGProcessing execution

Primary Draft role
  -> Expert Language Model
  -> autoregressive processor
  -> MNN
  -> local or distributed execution

Formatter role
  -> Expert Diffusion Model
  -> micro-diffusion processor
  -> MNN or compatible runtime
  -> local execution + schema verification
```

The runtime must not infer cognitive semantics merely from which backend executed the tensor graph.

### 6. Introduce neutral model processor interfaces

The processor layer should expose computation primitives without embedding GCS cognitive roles.

Conceptual target:

```cpp
class IModelProcessor {
public:
    virtual ~IModelProcessor() = default;
    virtual ProcessorCapabilities GetCapabilities() const = 0;
    virtual outcome::result<void> Load(const ModelArtifact& artifact) = 0;
    virtual bool IsLoaded() const = 0;
};

class IAutoregressiveProcessor : public virtual IModelProcessor {
public:
    virtual outcome::result<GenerationResult>
    Generate(const GenerationRequest& request) = 0;
};

class IJudgmentProcessor : public virtual IModelProcessor {
public:
    virtual outcome::result<JudgmentResult>
    Judge(const JudgmentRequest& request) = 0;
};

class IDiffusionProcessor : public virtual IModelProcessor {
public:
    virtual outcome::result<DiffusionResult>
    Refine(const DiffusionRequest& request) = 0;
};
```

These names are illustrative; implementation may use adapters if changing the existing engine hierarchy directly would cause unnecessary churn.

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
DENOISE
INFILL
REFINE
EMBED
```

A node or processor may advertise multiple capabilities. The Router/RuntimeCoordinator selects an expert contract appropriate for the stage rather than assuming every loaded model supports generation.

Distributed capability advertisement should eventually expose stable identifiers such as:

```text
expert.language.generate
expert.language.stream
expert.judgment
expert.judgment.bundle
expert.diffusion.block
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

### 11. Generation-free EJM execution

For JEV-style EJMs, the preferred fast path is:

```text
context + criterion + bounded choices
        -> tokenize/validate choice labels
        -> prefill shared context
        -> one forward evaluation at answer boundary
        -> select allowed logits only
        -> normalize/calibrate
        -> JudgmentResult
```

No prose generation or parser loop is required.

The current MNN implementation already has a lower-level forward primitive internally. The refactor should expose an appropriate processor-level primitive without forcing the RuntimeCoordinator to depend on MNN internals.

Required correctness checks include:

- choice labels map to exactly one valid tokenizer token at the actual answer boundary;
- labels are distinct and round-trip correctly;
- cached and uncached execution agree within declared tolerance;
- option-order reversal/paraphrase tests do not reveal pathological instability;
- SGFP4 and other quantization modes are tested for judgment argmax, margin, and calibration drift rather than perplexity alone.

### 12. Shared-prefix judgment bundles

The EJM API should support a bundle of independent judgments against the same context packet.

This enables native shared-prefix/KV reuse and avoids repeating expensive context prefill for router, verifier, risk, grounding, or arbitration judgments.

A bundle remains a collection of independent typed judgments; sharing compute must not silently couple their semantics.

### 13. EDM execution remains verified and bounded

Micro-diffusion output is provisional until accepted by the configured verifier path.

Verification may be:

- schema validation;
- compiler/test/static analysis;
- tool dry-run;
- target-model verification;
- EJM/ELM verifier;
- another deterministic contract.

The initial EDM implementation should remain focused on low-entropy structured regions where verification is cheap.

## Naming and terminology

The preferred taxonomy is:

| Abbreviation | Name | Primary contract |
|---|---|---|
| **ELM** | Expert Language Model | generate/transform language |
| **EJM** | Expert Judgment Model | bounded semantic judgment |
| **EDM** | Expert Diffusion Model | iterative denoise/infill/refine |
| **EM** | Expert Model | neutral umbrella term |

`Decision ELM` is a transitional/deprecated architecture term. Existing code/comments may keep the old term temporarily during migration, but new interfaces and documentation should use **EJM**.

## Migration plan

### Phase 1 — Types and adapters, no behavioral break

- Add neutral `IExpertModel` metadata/lifecycle abstraction.
- Add capability flags.
- Introduce `IExpertLanguageModel`, initially adapting existing `IELM` behavior.
- Keep existing ELM registry and API paths operational.
- Add typed `JudgmentRequest`, `JudgmentResult`, and optional `JudgmentBundle` structures.

### Phase 2 — EJM runtime path

- Add `IExpertJudgmentModel` and judgment processor adapter.
- Expose selected-logit/forward functionality through the processor boundary.
- Implement tokenizer answer-boundary validation.
- Implement normalized probabilities plus calibration metadata.
- Add cached/shared-prefix judgment execution where supported.

### Phase 3 — Execution graph semantics

- Replace string-only expert-chain assumptions with typed stage artifacts.
- Prevent judgment artifacts from replacing content state by default.
- Allow router/planner stages to consume EJM outputs directly.
- Update expert registry to discover by role + capability + model family.

### Phase 4 — Distributed capability support

- Advertise ELM/EJM/EDM capabilities through node capability profiles.
- Add judgment and diffusion job/result contracts where SGProcessing or remote execution requires them.
- Preserve local cache affinity for shared-prefix judgment bundles.

### Phase 5 — EDM micro-diffusion prototype

- Introduce `IExpertDiffusionModel` / diffusion processor contract.
- Implement one Micro-Diffusion Block Drafter experiment for a schema/JSON or code-patch workload.
- Require deterministic validation before committing output.

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
- probability normalization;
- option order reversal;
- criterion paraphrase robustness;
- irrelevant-context robustness;
- missing-evidence/abstain behavior;
- cached vs fresh forward agreement;
- batch-one vs shared-prefix fanout agreement;
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

GCS/NeoSwarm should treat **Expert Model (EM)** as the umbrella abstraction and preserve **ELM** specifically for language experts. Bounded JEV-style models become **EJMs — Expert Judgment Models**. Diffusion-based experts become **EDMs — Expert Diffusion Models**. Expert identity remains a cognitive-layer concern, while model processors and execution backends remain separate implementation concerns.
