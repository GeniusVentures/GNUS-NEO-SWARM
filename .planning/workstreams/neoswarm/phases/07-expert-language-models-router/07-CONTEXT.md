# Phase 7: Expert Language Models + Router - Context

**Gathered:** 2026-07-15
**Status:** Ready for planning

<domain>
## Phase Boundary

Deploy 7 role-based ELMs (Planner, Primary Draft, Verifier, Arbiter, Refiner/Formatter, Grounding, Tool-Support) and 3 domain ELMs (Math, Code, Science) behind swappable interfaces, with a rule-based router extended to build and execute sequential specialist chains (e.g. Planner → Domain → Verifier → Refiner). Local-only, stateless. GAML memory is Phase 8, distributed swarm execution is Phase 9, safety profiles and Tool Intermediary are Phase 10.

</domain>

<decisions>
## Implementation Decisions

### ELM backing (what physically runs each role)
- **D-01:** Hybrid backing. By default every role ELM invokes the already-loaded core MNN model with a role-specific prompt template (shared backbone per doc 03 §5.2.1). No new model files required for Phase 7 to function.
- **D-02:** If config provides a model path for a role/domain, that ELM loads its own quantized `.mnn` (SGFP4 export from gnus-poc) instead of the shared backbone. Same `IELM` interface either way.
- **D-03:** Role prompt templates live as named constants/resources in the ELM implementations — not user-editable config in Phase 7.
- **D-04:** Missing model file for a configured path → `outcome::result` error at load, ELM falls back to shared-backbone mode with a logged warning (graceful degradation pattern from Phase 2).
- **D-19:** ELM `Process()` failures return `outcome::failure()` with specific error codes (`ModelLoadFailed`, `InferenceFailed`, `KnowledgeUnavailable`, `InternalError`). The chain executor `RunELMChain` handles these by stopping the chain gracefully and returning a partial response with whatever output accumulated from prior steps. This replaces the earlier unwritten fail-close convention where ELMs silently returned input unchanged on error.

### Interface design and legacy mapping
- **D-05:** New `IELM` interface (`I`-prefix convention): `GetName()`, `GetRole()`, `IsLoaded()`, `Load(path)`, `Process(input, ELMContext)`, `GetConfidence()`. `ISpecialist` remains untouched.
- **D-06:** Legacy mapping per doc 03 §5.2.6: `GrammarSpecialist` is wrapped by the Refiner/Formatter role ELM via adapter; `MathSpecialist` is wrapped as the Math domain ELM via adapter; `SymbolicFallback` stays internal to the Math path (not an ELM).
- **D-07:** Adapters use composition (has-a `ISpecialist`), not inheritance. Existing specialist tests unchanged.
- **D-08:** `ELMRole` enum and `ELMContext` struct added to `src/common/types.hpp`.

### Chain representation and routing rules
- **D-09:** `ExecutionChain` is a flat ordered list of steps; each step = `{ELMRole role, optional domain}`. No parallel edges in Phase 7 — struct designed so a DAG extension can be added later without breaking consumers.
- **D-10:** Multi-domain parallel dispatch (`Planner → [Math, Code] → Arbiter`) is explicitly deferred to Phase 9 (swarm dispatch concern).
- **D-11:** Router split: `RuleBasedRouter` keeps producing `RouteDecision` (unchanged responsibilities, existing tests intact); new `ELMChainBuilder` maps `RouteDecision` + `PromptFeatures` to an `ExecutionChain`.
- **D-12:** MVP chain selection implements doc 03 §6.2 heuristic triggers:
  - Numeric density → Math domain + Verifier
  - Code syntax → Code domain path
  - Grounding-sensitive → Grounding step before draft
  - Formatting-sensitive → Refiner/Formatter step after draft
  - Low complexity → Semantic Core only (Primary Draft)
  - High complexity/uncertainty → Planner → Domain → Verifier → Refiner
- **D-13:** `ApiServer` gains `RunELMChain(chain, task)` executing steps sequentially; output of each step feeds the next via `ELMContext`.

### Configuration surface
- **D-14:** ELM configuration is an `elms` section in the existing `--config` JSON file (consistent with Phase 2 D-09). Per-role/domain optional fields: `model` (path), `eager` (bool, default false).
- **D-15:** No new per-ELM CLI flags. Existing `--model`, `--grammar-model`, `--math-model` flags stay for backward compatibility.
- **D-16:** Lazy loading by default; `eager: true` per-ELM opt-in loads at `ApiServer::Initialize()`.

### Grounding and Tool-Support boundaries
- **D-17:** `GroundingELM` wraps the existing `knowledge/` pipeline (`KnowledgeRetrieval`, `ContextInjection`, `FactValidation`) behind `IELM`. No new retrieval implementation, no new model.
- **D-18:** `ToolSupportELM` is an interface-conforming stub (pass-through with logged not-implemented status). Real tool-call formatting requires Phase 10's Tool Intermediary boundary.

### OpenCode's Discretion
- Exact `ELMContext` field set (must carry at minimum: original task, accumulated step outputs, per-step confidence)
- Role prompt template wording
- Chain-step timeout and confidence-threshold defaults
- File layout for ELM implementations (suggested: `src/elm/` or extend `src/specialists/`)
- Whether Science ELM ships as shared-backbone-only in Phase 7 (no trained model exists)

</decisions>

<specifics>
## Specific Ideas

- Role ELMs must be swappable per doc 03 §5.2.1 — "implementations are swappable" is the phase's core architectural requirement
- Execution flow: Task → RuleBasedRouter → RouteDecision → ELMChainBuilder → ExecutionChain → ApiServer::RunELMChain
- Wave-based execution with one PR per wave (established project workflow)

</specifics>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### ELM and Router architecture
- `../../docs/architecture/03-model-and-router.md` §5.2 — ELM definition, role-based ELMs, domain experts, invocation patterns, legacy specialist mapping
- `../../docs/architecture/03-model-and-router.md` §6 — Router responsibilities, MVP rule-based triggers (§6.2), evolution path (§6.3)
- `../../docs/architecture/11-distributed-swarm-thinking-context.md` §16.8 — Specialist taxonomy: role specialist responsibilities in detail

(Paths relative to repo root: `/Volumes/Work/Gnus_ai/GeniusNetwork/GeniusCognitiveSystem/docs/architecture/`)

### Existing contracts this phase builds on
- `src/router/i_router.hpp` — `IRouter` interface, `RouteDecision`
- `src/specialists/i_specialist.hpp` — `ISpecialist` interface being adapted
- `src/core/engine/inference_engine.hpp` — `InferenceEngine` abstraction (shared backbone access)
- `src/common/types.hpp` — Task, RouteTarget, ExecutionMode types being extended

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `RuleBasedRouter` + `PromptAnalyzer` (`src/router/`): feature extraction (numeric density, code syntax, complexity) already implements most §6.2 trigger inputs
- `GrammarSpecialist`, `MathSpecialist`, `SymbolicFallback` (`src/specialists/`): become Refiner and Math ELMs via adapters
- `KnowledgeRetrieval`/`ContextInjection`/`FactValidation` (`src/knowledge/`): backs GroundingELM
- `MNNInferenceEngine` (`src/core/engine/`): the shared backbone all default ELMs invoke
- `ApiServer` (`src/api/`): composition root where chain execution integrates

### Established Patterns
- `outcome::result<T>` error propagation, no exceptions, C++17 ceiling
- Config struct + constructor, `Initialize()` lifetime, Pimpl for heavy deps
- Stub/graceful degradation when optional backends missing
- `I`-prefix interfaces, `m_` members, snake_case files, `neoswarm_` CMake libs

### Integration Points
- `ApiServer::Process()` currently branches to `RunSingleNode/RunSpecialist/RunSwarm` — `RunELMChain` becomes the fourth path (or subsumes RunSpecialist)
- JSON config parsing in `main.cpp` gains `elms` section
- `test/` structure: `test/router/`, `test/specialists/`, `test/integration/` get ELM test targets

</code_context>

<deferred>
## Deferred Ideas

- PlannerELM → Planner **+ Memory Governor** extension (doc 11 §16.8.1.1 defines the full role as "Planner and Memory Governor Specialist"; the memory-governor half — retrieval prefiltering, Bridge Block selection, temporal resolution — requires GAML) — Phase 8. PlannerELM's Doxygen header must note this extension point so the missing half is not "fixed" prematurely.
- Multi-domain parallel dispatch + arbiter-mediated synthesis of parallel outputs — Phase 9 (swarm)
- Learned classifier router — Phase 7.5 / doc 03 §6.3 stage 2
- Cognitive planner producing full execution graphs — Phase 8+ (needs GAML memory)
- Real Tool-Support logic — Phase 10 (Tool Intermediary boundary)
- User-editable role prompt templates — future config enhancement
- Legal/Compliance, Operations, Customer Support, Finance domain ELMs (doc 03 §5.2.3) — future phases

</deferred>

---

*Phase: 07-expert-language-models-router*
*Context gathered: 2026-07-15*
