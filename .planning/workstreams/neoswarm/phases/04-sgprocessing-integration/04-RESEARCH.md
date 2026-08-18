# Phase 4: SGProcessing Integration - Research

**Researched:** 2026-08-18
**Domain:** Cross-repo C++ integration — SGProcessingManager (SuperGenius/GeniusNetwork submodule) + GNUS-NEO-SWARM build/inference-path consolidation
**Confidence:** HIGH (all claims below are `[VERIFIED: <file>:<line>]` via direct `Read`/`git`/`find` against the live `dev_childwallet` checkout and the live NEO-SWARM working tree, unless tagged `[ASSUMED]`)

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

- **D-01:** This phase is full cross-repo — plans include commits to both `SuperGenius/SGProcessingManager` (GeniusNetwork submodule) and `GNUS-NEO-SWARM`.
- **D-02:** NEO-SWARM does **not** build SGProcessingManager itself. SuperGenius already builds it (and everything it depends on, including protobuf-generated proto libs) as static libs at `GeniusNetwork\SuperGenius\build\<Platform>\<BuildType>\SuperGenius\lib\` (confirmed present for Windows Release: `SGProcessingManager/` subdir + `SGProcessingProto.lib`, `ConsensusProto.lib`, etc., all one consistent protobuf version). NEO-SWARM's CMake should link against this build output instead of whatever separate prebuilt "thirdparty" snapshot it references today.
- **D-03:** `W:\gnus\SuperGenius` (the stale `dev_persisprocresults` checkout) has been deleted by the user. `W:\gnus\GeniusNetwork\SuperGenius` (`dev_childwallet`) is the sole canonical SuperGenius checkout going forward — all research/planning/execution targets this one.
- **D-04:** The vendored MNN fork (`GeniusNetwork/thirdparty/MNN`, currently detached at a `master` snapshot with no FP4 Ultra code) has its FP4 Ultra work on `origin/MNN_Ultra` (unchecked-out), estimated by the user at "~80% done" but **unverified**. Research must determine its actual completeness before planning commits to finishing it in this phase. If it's far from done, defer full MNN-side completion to a separate phase and scope this phase to linking/wiring SGProcessingManager against whatever MNN currently exposes (see D-09).
- **D-05:** SGProcessingManager gains a processor (new file, e.g. `processing_processor_mnn_fp4.cpp`, or an adapted existing MNN processor — exact shape left to planning) that does what NEO-SWARM's `src/core/engine/mnn_inference_engine.cpp` currently does. Architectural principle: all actual MNN calls happen inside SGProcessingManager — it already owns Vulkan locking/coexistence (established by the `sgproc-render` workstream), and consolidating means SuperGenius network nodes automatically gain LLM-serving capability too.
- **D-06:** `MNNInferenceEngine` is **not deleted entirely**. `InferViaSGProcessing()` (network job submission to the SuperGenius swarm) stays as-is. For local/SingleNode calls, its internal implementation changes: instead of doing raw MNN inference itself, it calls `ProcessingManager::Init()` / `ProcessingManager::Process()` directly — an in-process call into SGProcessingManager, no network hop. Duplicate raw-MNN-invocation logic is removed from NEO-SWARM.
- **D-07:** PROC-01 (LLM generation) and PROC-02 (FP4_ULTRA) are not necessarily one merged processor — several existing MNN processors might already fit LLM generation with adaptation; a new processor is fine too if needed. Exact processor boundary is left to plan time.
- **D-08:** FP4_ULTRA — wire + stub, ship what's ready: re-enable FP4_ULTRA validation and wire the schema/dispatch plumbing end-to-end now. The actual decode/dequant call defers to MNN's own FP4 Ultra API once ready — plumbing ships even if MNN isn't fully there yet (contingent on D-04's research finding).
- **D-09:** Dequant math is **not** duplicated in SGProcessingManager. Pass-through to MNN: SGProcessingManager validates the format and hands the raw FP4_ULTRA-encoded buffer to MNN's own decode.
- **D-10:** Whether FP4_ULTRA re-enables the existing `TENSOR` DataType's commented-out validation branch versus needs its own DataType/processor is **not decided** — depends on what's actually required once the current (`dev_childwallet`) validation code and the FP4 Ultra spec are read in full. Left to plan-time investigation.
- **D-11:** PROC-03 is resolved by consolidation, not by a code fix: once NEO-SWARM links against GeniusNetwork's SuperGenius build output (D-02), there is one consistent protobuf version flowing through everything. Verify this holds and correct the stale CONCERNS.md/PROJECT.md references describing an active SentencePiece/protobuf conflict (SentencePiece does not currently exist in the codebase — no implementation file, no `GENIUS_HAS_SENTENCEPIECE` flag anywhere).
- **D-12:** FIX-04: re-verify, don't assume. After relinking against the GeniusNetwork build output, rebuild and confirm whether `-ld_classic` (currently the only confirmed fix, macOS-only, applied to `neoswarm_core` per `src/core/CMakeLists.txt:130-132`) is still needed. Get test binaries linking cleanly across whichever platforms are actually available to test (Windows confirmed available on this machine; macOS/Linux as available).

### Claude's Discretion

- Exact processor file/class boundary for the MNN LLM + FP4_ULTRA work in SGProcessingManager (D-05, D-07, D-10)
- Whether to reuse an existing MNN processor (e.g. adapt `MNN_ML`'s stub, or `MNN_String`) versus write a new one — investigate at plan time
- CMake mechanics for pointing NEO-SWARM at `GeniusNetwork\SuperGenius\build\<Platform>\<BuildType>\SuperGenius\lib\` instead of the current prebuilt-snapshot path

### Deferred Ideas (OUT OF SCOPE)

- Finishing `MNN_Ultra`'s FP4 Ultra decode work, if research shows it's far from done — candidate for its own phase (D-04)
- Re-adding SentencePiece tokenization — no active conflict exists today; only relevant if a future phase specifically needs SentencePiece over MNN's built-in `tokenizer.mtok`
- Implementing FP4 Ultra's dequant math inside SGProcessingManager — explicitly delegated to MNN (D-09), not this project's concern
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-------------------|
| PROC-01 | Add MNN LLM text generation processor to SGProcessingManager (SuperGenius repo) | See "Architecture Patterns" (`ProcessingProcessor` interface, current MNN_String/MNN_ML shape) and "Common Pitfalls" (MNN_String is single-forward-pass, not autoregressive — a real gap, not an adaptation) |
| PROC-02 | Add FP4_ULTRA input format processor to SGProcessingManager (SuperGenius repo) | See "Answers to CONTEXT.md Open Questions" Q-02 (MNN_Ultra completeness), "Common Pitfalls" (three incompatible FP4 formats exist across the codebase — must be resolved with the user before implementation) |
| PROC-03 | Resolve SentencePiece/SGProcessing protobuf version conflict (unified protobuf version) | See Q-03 (CMake link mechanics) — D-11's consolidation-not-code-fix approach is confirmed viable; SentencePiece confirmed absent from the codebase |
| FIX-04 | Fix test binary linker errors with SGProcessingManager enabled (duplicate protobuf symbols) | See Q-03 and "Common Pitfalls" — `-ld_classic` propagation mechanics confirmed structurally sound; must be re-verified empirically once relinked |
</phase_requirements>

## Project Constraints (from CLAUDE.md)

- **Minimal, surgical changes only.** No refactors, no architectural changes beyond what CONTEXT.md's decisions already scope. Every fix below (CMake path, `InputFormatToTypeString` bug, `ProcessOutput` conversion) should be the smallest possible diff.
- **No `#ifdef` feature gates** in source files. CMake already handles SGProcessingManager as an unconditional link-or-fail-at-configure-time dependency (`if(TARGET ...)` pattern) — preserve this, do not add compile-time stubs.
- **SuperGenius naming conventions apply inside SGProcessingManager work**: `m_` prefix members, PascalCase classes, `Get`/`Set`/`Is` accessors — already the established style there (confirmed throughout `ProcessingManager.hpp/cpp`).
- **`outcome::result<T>` error handling, no silent `(void)` discards** for any new/touched code. Note: `mnn_inference_engine.cpp:82` already has a pre-existing `(void) m_fp4Codec;` discard — this is pre-existing scope, only touch it if this phase's work actually deletes/uses `m_fp4Codec`.
- **C++17 only** — MNN's LLM API (`MNN::Transformer::Llm`) and SGProcessingManager's `ExecutionContext`/manifest machinery are already C++17-compatible; no new language-version risk introduced by this phase.
- **PR size limit 300 lines** — this phase's cross-repo scope (new processor + CMake relink + bridge fixes + engine cleanup) will almost certainly need to be split into multiple plans/PRs across the two repos, not one.
- **`checkpoint:human-verify` required before installing/using anything flagged suspicious** — not applicable; this phase introduces no new external packages (see Package Legitimacy Audit).

## Summary

Phase 4 is pure C++ cross-repo integration work with no new third-party dependencies. Research re-verified every one of CONTEXT.md's four open questions directly against the live `dev_childwallet` checkout (confirmed via `git log`: HEAD `3682e99`, branch `dev_childwallet`, ahead of `origin/dev_childwallet` by 6 commits) and the live NEO-SWARM working tree, and found that the `sgproc-render` workstream's rework (Phases 06–16, all merged into this exact checkout) has changed `ProcessingManager`'s public API in ways that **break NEO-SWARM's existing bridge code at compile time**, independent of the CMake relink D-02 asks for. This is the single most important finding: **relinking alone is not sufficient — `SGProcessingBridge::SubmitDirect()` will not compile against the current `ProcessingManager::Process()` signature without a source change**, because `Process()` now returns a `ProcessOutput` struct (artifacts + manifest + combined hash) instead of a bare `std::vector<uint8_t>`, and there is no implicit conversion between them.

A second concrete, currently-live bug was found in NEO-SWARM's own bridge code: `SGProcessingBridge::InputFormatToTypeString(FP4_ULTRA)` returns the string `"fp4_ultra"` for the JSON `"type"` field, but SGProcessingManager's `DataType` enum's `from_json` only recognizes `"tensor"` (among 15 other DataType names) for the type field — `"fp4_ultra"` is not a valid `DataType` string anywhere. Since `MNNInferenceEngine::Config::m_useFp4` defaults to `true`, **every "sgprocessing"-mode inference call today would fail at `ProcessingManager::Create()`'s JSON-parse step** (`Error::INVALID_JSON`) the moment SGProcessingManager is actually linked and exercised, regardless of this phase's other work. This is a pre-existing type/format field confusion, not something introduced by the relink.

Third, a genuinely unresolved format ambiguity was found: the term "FP4" appears in at least **three functionally-incompatible encodings** across the ecosystem this phase touches — NEO-SWARM's own dead `fp4_codec.hpp` (NF4-style non-uniform 16-value LUT, 64×64 macroblocks, currently unused — `(void) m_fp4Codec;`), MNN_Ultra's native Vulkan/CPU dequant kernel (standard **E2M1** micro-float, `VulkanFP4Dequant`/`fp4_dequant.comp`, registered under `OpType_Dequantize`), and a third, separate "SGFP4 v2" adaptive-macroblock Python exporter tracked in this repo's own `poc` workstream (`FP4_AFFINE`/`T158_AFFINE` dual-mode, quadtree layout, referencing "PTDS v4 §6"). D-09's "pass raw FP4_ULTRA buffer through to MNN's decode" only makes sense if SGProcessingManager's `FP4_ULTRA` maps to MNN_Ultra's E2M1 format specifically — this needs explicit user confirmation before PROC-02 implementation, because none of CONTEXT.md's canonical_refs (`SGProcessingManager/FP4 Ultra.txt`) actually exists on disk in either repo.

Fourth, the `sgproc-render` workstream has an **open, unrelated, already-tracked build-stability bug** (queued as its own Phase 18, not yet started) where `ProcessingManager::Create()` deadlocks on any machine with a real Vulkan device present (`VulkanInitMutex` re-entrancy in the capability-probe path run unconditionally at `Init()`). This will block **any local end-to-end verification** of Phase 4's new processor via `ProcessingManager::Create()` on a real-GPU machine (this Windows machine included) until sgproc-render's Phase 18 ships — it is out of this phase's scope to fix, but must be documented as an execution/verification risk.

**Primary recommendation:** Sequence this phase's NEO-SWARM-side work as: (1) fix the CMake link path to point at `GeniusNetwork\SuperGenius\build\<Platform>\<BuildType>\SuperGenius\lib\` including the newly-required sgproc-render libs; (2) fix `SGProcessingBridge::SubmitDirect()`'s return-type handling for the new `ProcessOutput` API; (3) fix `InputFormatToTypeString(FP4_ULTRA)` to return `"tensor"` not `"fp4_ultra"`; (4) get user confirmation on which FP4 format `FP4_ULTRA` actually targets before writing PROC-02's processor; (5) build the new LLM processor from scratch rather than adapting `MNN_String` (which is a single-forward-pass BERT-style processor, not an autoregressive generation loop) — the real autoregressive reference implementation to port is NEO-SWARM's own `InferViaMnnLlm`/`MNN::Transformer::Llm::response()` path; (6) treat the `VulkanInitMutex` deadlock as a known, out-of-scope, cross-workstream verification blocker, not something to silently work around.

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| MNN model loading, session creation, Vulkan locking | SGProcessingManager (SuperGenius repo) | — | D-05: "all actual MNN calls happen in SGProcessingManager" — it already owns the shared `VulkanInitMutex` coexistence contract with `RenderProcessor` |
| Autoregressive token generation loop (sampling, repetition penalty, EOS detection) | SGProcessingManager (new processor) | — | Currently duplicated in NEO-SWARM (`InferViaStandardInterpreter`) and via MNN's own API in NEO-SWARM (`InferViaMnnLlm`) — D-06 requires this move into SGProcessingManager so swarm nodes gain the capability automatically |
| FP4_ULTRA schema validation (dimensions, format compatibility) | SGProcessingManager (`ProcessingManager::CheckProcessValidity()`) | — | Same tier as every other `DataType`/`InputFormat` validation already there |
| FP4_ULTRA dequantization math | MNN (thirdparty, via `MNN_Ultra` branch's `VulkanFP4Dequant`) | — | D-09: explicitly not duplicated in SGProcessingManager |
| Job schema construction (`BuildSchemaJson`) | NEO-SWARM (`SGProcessingBridge`) | — | Unchanged — NEO-SWARM is the schema producer, SGProcessingManager is the consumer |
| Network dispatch to SuperGenius swarm | NEO-SWARM (`SGProcessingBridge::SubmitNetwork` / `SGClient`) | GeniusSDK | Unchanged by this phase (SG-02 is separately tracked, still stubbed) |
| Local/in-process inference invocation | NEO-SWARM (`MNNInferenceEngine::InferViaSGProcessing` → `SGProcessingBridge::SubmitDirect` → `ProcessingManager::Create`+`Process`) | SGProcessingManager | D-06: this path already exists and already does what D-06 asks — see Common Pitfalls for the compile break it currently has |
| Build/link of SGProcessingManager and its transitive deps | GeniusNetwork/SuperGenius (build output consumed as prebuilt static libs) | NEO-SWARM CMake (consumer only) | D-02: NEO-SWARM never builds SGProcessingManager itself |

## Standard Stack

This phase introduces **no new third-party libraries or packages**. All "stack" here is internal, already-vendored code across two repos:

| Component | Location | Role in this phase |
|-----------|----------|---------------------|
| SGProcessingManager | `GeniusNetwork/SuperGenius/SGProcessingManager` (submodule, `dev_childwallet`) | New MNN LLM + FP4_ULTRA processor lands here (PROC-01, PROC-02) |
| MNN (vendored fork) | `GeniusNetwork/thirdparty/MNN` (submodule, detached at `master` `2a36c8ab`) | Provides the actual inference/decode kernels the new processor calls into |
| MNN_Ultra branch | `origin/MNN_Ultra` on the same MNN submodule (unchecked-out) | Source of the E2M1 FP4 dequant kernel (`VulkanFP4Dequant`) — see Q-02 below for completeness |
| `neoswarm_core` (NEO-SWARM) | `src/core/` | Consumer: `mnn_inference_engine.cpp`, `sg_processing_bridge.cpp` — duplicate-logic removal target (D-06) |

**Version verification:** N/A — no package-manager-resolved dependency versions are introduced. All components are git submodules/checkouts pinned by commit, already present on this machine.

## Package Legitimacy Audit

**Not applicable.** This phase does not install any external package via npm/pip/cargo or any other registry. All work is against already-vendored git submodules (`SuperGenius`, `thirdparty/MNN`) and first-party source in both repos. No `checkpoint:human-verify` gate is required for package installation in this phase.

## Architecture Patterns

### System Architecture Diagram

```
                          ┌─────────────────────────────────────────┐
                          │            GNUS-NEO-SWARM                │
                          │                                           │
   ApiServer / router ───▶│  MNNInferenceEngine::Infer(task)          │
   (SingleNode mode)      │    ├─ "sgprocessing" mode (primary) ──┐   │
                          │    │    InferViaSGProcessing()        │   │
                          │    │      └─▶ SGProcessingBridge::    │   │
                          │    │           SubmitJob()            │   │
                          │    │             ├─ networkMode=false │   │
                          │    │             │    SubmitDirect()  │   │
                          │    │             └─ networkMode=true  │   │
                          │    │                  SubmitNetwork() │   │
                          │    │                  (SGClient, Phase 2, │
                          │    │                   stubbed today) │   │
                          │    │                                  │   │
                          │    └─ "interpreter" mode (fallback) ──┼─▶ DUPLICATE raw-MNN
                          │         InferViaMnnLlm()               │  invocation logic —
                          │         InferViaStandardInterpreter()   │  D-06 deletes this,
                          │         RunForward/SampleToken/         │  moves the capability
                          │         ApplyRepetitionPenalty          │  into SGProcessingManager
                          └───────────────────┬───────────────────────┘
                                              │ SubmitDirect() — in-process, no network
                                              ▼
                          ┌─────────────────────────────────────────┐
                          │      SGProcessingManager (SuperGenius)   │
                          │                                           │
                          │  ProcessingManager::Create(json)          │
                          │    ├─ Init(): parse JSON, register        │
                          │    │   16 DataType→processor factories    │
                          │    │   + RENDER PassType factory           │
                          │    │   + build CapabilityValidator         │
                          │    │     snapshot (Vulkan probe — SEE      │
                          │    │     Common Pitfalls: VulkanInitMutex  │
                          │    │     deadlock risk, unconditional)     │
                          │    └─ CheckProcessValidity(): per-DataType │
                          │        schema validation (TENSOR's FP4_ULTRA│
                          │        branch currently commented out)    │
                          │  ProcessingManager::Process(ioc, ...)      │
                          │    └─ ProcessInternal():                  │
                          │        SetProcessorByName(DataType) or    │
                          │        SetProcessorByPassType(RENDER)     │
                          │        └─▶ processor->StartProcessing()   │
                          │             (6-arg, ExecutionContext-aware)│
                          │             [NEW: MNN LLM processor here] │
                          │             [NEW: FP4_ULTRA path here]    │
                          │        └─ builds ExecutionManifest +      │
                          │           Artifacts (ProcessOutput)       │
                          └──────────────────┬────────────────────────┘
                                              │ links to (build-time only)
                                              ▼
                          ┌─────────────────────────────────────────┐
                          │  GeniusNetwork/thirdparty/MNN (vendored)  │
                          │  MNN::Transformer::Llm (autoregressive)   │
                          │  MNN::Interpreter (single-pass tensor)    │
                          │  [MNN_Ultra branch, unmerged]:            │
                          │    VulkanFP4Dequant (OpType_Dequantize)   │
                          │    fp4_dequant.comp (E2M1 GPU kernel)     │
                          └─────────────────────────────────────────┘
```

### Recommended Project Structure

No new directories are needed. Files touched:

```
GeniusNetwork/SuperGenius/SGProcessingManager/
├── include/processors/
│   └── processing_processor_mnn_fp4.hpp     # NEW (or adapted MNN_String/MNN_ML) — PROC-01
├── src/processors/
│   └── processing_processor_mnn_fp4.cpp     # NEW — autoregressive generation loop
├── src/processingbase/ProcessingManager.cpp # EDIT: re-enable FP4_ULTRA validation branch
                                              #        (line 894 today), register new processor

GNUS-NEO-SWARM/src/core/
├── CMakeLists.txt                            # EDIT: repoint _SGPROC_INCLUDE/_SGPROC_LIB_DIR
                                              #        at GeniusNetwork's build output; add the
                                              #        6 newly-required sgproc-render libs
├── sgprocessing/sg_processing_bridge.cpp     # EDIT: fix ProcessOutput→vector conversion;
                                              #        fix InputFormatToTypeString(FP4_ULTRA)
├── engine/mnn_inference_engine.cpp           # EDIT: delete InferViaStandardInterpreter/
                                              #        RunForward/SampleToken/ApplyRepetitionPenalty
                                              #        (raw MNN::Interpreter loop — D-06 removal
                                              #        target); InferViaMnnLlm's fate depends on
                                              #        whether it's kept as a fallback or also
                                              #        removed (plan-time call — it uses MNN's own
                                              #        native LLM API, not hand-rolled sampling, so
                                              #        it is less clearly "duplicate logic" than
                                              #        InferViaStandardInterpreter)

GNUS-NEO-SWARM/test/CMakeLists.txt            # EDIT: SUPERGENIUS_TEST_DATA_DIR default path
                                              #        (currently points at a nonexistent sibling
                                              #        "../SuperGenius", same root cause as CMake)
```

### Pattern: `ProcessingProcessor` interface (current, dev_childwallet)

**What:** Every processor in SGProcessingManager implements a single pure-virtual 6-argument `StartProcessing()` overload. This is a **materially different signature** from what an older/stale scout might have reported — it now takes an `ExecutionContext` (cancellation token, progress callback, deadline, GPU memory budget, output artifact byte budget) as its 6th argument, added by the `sgproc-render` workstream's cancellable-execution work (Phase 07).

`[VERIFIED: SGProcessingManager/include/processors/processing_processor.hpp:81-86]`

```cpp
virtual ProcessingResult StartProcessing( std::vector<std::vector<uint8_t>> &chunkhashes,
                       const sgns::IoDeclaration         &proc,
                       std::vector<char>                 &imageData,
                       std::vector<char>                 &modelFile,
                       const std::vector<sgns::Parameter> *parameters,
                       const ExecutionContext            &execCtx ) = 0;
```

A new MNN LLM/FP4_ULTRA processor MUST implement this exact 6-arg signature (not the older 4-arg / 5-arg forms implied by any pre-`sgproc-render` documentation). `ProcessingResult` itself also gained fields since any older scout would have seen: `output_locations`, and a `std::optional<ProcessingError> error` carrying a structured `ProcessingErrorStage` enum (`CANCELLED`, `TIMED_OUT`, `BUDGET_EXCEEDED`, etc.) instead of a bare empty-hash failure sentinel. `[VERIFIED: processing_processor.hpp:25-65]`

Every processor also inherits a `PushTeardown()`/`RunTeardown()` LIFO teardown-stack mechanism (D-14 of `sgproc-render`) for noexcept-safe cleanup during cancellation — MNN session/interpreter cleanup for the new processor should register via `PushTeardown()`, mirroring how existing MNN processors are expected to (protected method, `processing_processor.hpp:119-133`).

### Pattern: Processor registration (current, dev_childwallet)

**What:** `ProcessingManager::Init()` registers exactly 16 `DataType`-keyed processor factories (one per `DataType` enum value) plus one `PassType::RENDER`-keyed factory. There is **no dedicated `ML` DataType** — `MNN_ML` exists as a source file but is never registered anywhere; it is genuinely dead/orphaned code on `dev_childwallet`, same as it reportedly was on the stale branch. `[VERIFIED: SGProcessingManager/src/processingbase/ProcessingManager.cpp:378-416]` (registration list) cross-checked against `generated/DataType.hpp:19` (16-value enum, no `ML` member).

`MNN_String` (registered under `DataType::STRING`) is the closest existing "text" processor, but its implementation is a **single forward pass through an MNN session** (BERT-style: resize input tensors to a fixed `maxLength`, fill token IDs, run once, return the raw output tensor) — it has no generation loop, no sampling, no EOS detection, no KV-cache handling. `[VERIFIED: SGProcessingManager/src/processors/processing_processor_mnn_string.cpp:185-318]` This is **not** an adaptable autoregressive LLM processor; PROC-01 needs new looping/sampling logic, most naturally ported from NEO-SWARM's own `InferViaMnnLlm`/`InferViaStandardInterpreter` (see Don't Hand-Roll below for which of those two to actually port from).

### Pattern: `ProcessOutput` (new since `sgproc-render` Phase 08 — breaks NEO-SWARM's bridge)

**What:** `ProcessingManager::Process()` no longer returns `outcome::result<std::vector<uint8_t>>`. It returns `outcome::result<ProcessOutput>`, where `ProcessOutput` is a struct with `artifacts` (typed per-output records), `manifest` (`ExecutionManifest` — identity, timing, executor identity, terminal state), and `combinedHash` (`std::vector<uint8_t>`, the old return value). It offers `size()`/`empty()`/`begin()`/`end()` delegating to `combinedHash` for **partial** backward-compat, but **no implicit conversion operator to `std::vector<uint8_t>`**. `[VERIFIED: SGProcessingManager/include/processingbase/ProcessingManager.hpp:46-60]`

NEO-SWARM's `SGProcessingBridge::SubmitDirect()` currently does:
```cpp
// sg_processing_bridge.cpp:329-338 (current, dev_childwallet-incompatible)
auto process_result = pm->Process( ioc, chunkhashes, model_node, output_locations );
...
return outcome::success( process_result.value() );   // process_result.value() is ProcessOutput,
                                                       // function returns outcome::result<std::vector<uint8_t>>
```
This **will not compile** against the current `ProcessingManager.hpp` — there is no path from `ProcessOutput` to `std::vector<uint8_t>` via `outcome::success()`'s deduction. The minimal surgical fix is:
```cpp
return outcome::success( std::vector<uint8_t>( process_result.value().begin(), process_result.value().end() ) );
```
This is a **required fix for this phase**, independent of D-02's CMake relink — the current code was written against an older, pre-Phase-08 `ProcessingManager::Process()` signature and has apparently never been compiled against the real `dev_childwallet` headers (consistent with the CMake investigation below showing SGProcessingManager currently falls into stub/headers-only mode for this checkout, so this code path has likely never actually been exercised by a real build here).

### Anti-Patterns to Avoid

- **Adapting `MNN_String` for autoregressive generation:** its `Process()` helper does exactly one `runSession()` call and returns. Wrapping a generation loop around it by calling `StartProcessing()` repeatedly from outside would re-load the MNN interpreter/session on every token (no KV-cache reuse) — likely correct in isolation but pathologically slow, and duplicates model-loading logic that should live once per job, not once per token.
- **Adding a new `#ifdef` feature gate for the new processor.** CLAUDE.md forbids this; use the same unconditional CMake `if(TARGET ...)` pattern already used for `MNN`/`Vulkan` in `src/core/CMakeLists.txt`.
- **Assuming CONTEXT.md's `SGProcessingManager/FP4 Ultra.txt` exists.** It does not (`find` across all of `GeniusNetwork`, excluding `build/`/`.git/`, returns zero matches). Do not cite it as a source in the plan; the actual FP4 Ultra format is defined by MNN_Ultra's `tools/fp4/quantize_fp4.py` docstring and `VulkanFP4Dequant`/`fp4_dequant.comp` — see Common Pitfalls.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Autoregressive token generation (sampling, repetition penalty, EOS) | A new custom sampling loop inside SGProcessingManager | Port the logic already proven in NEO-SWARM's `InferViaMnnLlm()`, which calls `MNN::Transformer::Llm::response()` — MNN's own native LLM API already implements the generation loop, KV-cache, and stopping criteria internally | `InferViaStandardInterpreter`'s hand-rolled loop (`RunForward`/`SampleToken`/`ApplyRepetitionPenalty`, ~150 lines) is the literal "duplicate raw-MNN-invocation logic" D-06 wants deleted — it exists only because `MNN::Transformer::Llm` wasn't being used for the "interpreter" fallback path. The new SGProcessingManager processor should call `MNN::Transformer::Llm::createLLM()`/`load()`/`response()` (as `InferViaMnnLlm` already correctly does), not reimplement sampling by hand. |
| FP4 dequantization math | A new dequant kernel in SGProcessingManager (CPU or Vulkan) | MNN_Ultra's `VulkanFP4Dequant` (registered under `OpType_Dequantize`) once that branch's format is confirmed to be the intended one (see Open Questions) | D-09 already forbids this explicitly; confirmed a working, unit-tested implementation already exists on `origin/MNN_Ultra` — reinventing it would violate both D-09 and the "don't duplicate MNN logic" principle. |
| Vulkan Manual init/mutex handling in the new processor | A separate Vulkan device/context setup path | `sgns::sgprocessing::VulkanInitMutex()` (already used by every existing MNN processor, e.g. `processing_processor_mnn_string.cpp:208`) | Every existing MNN processor takes this lock around `interpreter->createSession()`. A new processor skipping it would reintroduce exactly the kind of Vulkan coexistence bug `sgproc-render` Phase 01/18 exists to prevent/fix. |

**Key insight:** Almost everything PROC-01 needs already exists correctly implemented somewhere in the codebase (MNN's own `Transformer::Llm` API, already correctly wired in NEO-SWARM's `InferViaMnnLlm`) — the actual work is *moving* that call site into SGProcessingManager, not inventing new inference logic.

## Runtime State Inventory

This phase is a partial rename/consolidation (moving inference invocation code between repos, repointing build paths) — the following categories were checked explicitly per the verification protocol:

| Category | Items Found | Action Required |
|----------|-------------|------------------|
| Stored data | None — no databases, no persisted job records reference the old path structure. | None. |
| Live service config | None — no n8n/external service configs reference SGProcessingManager's location. | None. |
| OS-registered state | None — no Windows Task Scheduler/pm2/launchd registrations reference SuperGenius's path. | None. |
| Secrets/env vars | None — no env vars encode the `W:\gnus\SuperGenius` (deleted) path. `[VERIFIED]` no matches for that literal path across NEO-SWARM's `.env`-style config or CMake cache variables. | None. |
| Build artifacts / stale path references | **Found, concrete:** (1) `src/core/CMakeLists.txt:67-69` hardcodes `${PROJECT_ROOT}/../SuperGenius/SGProcessingManager/{include,generated}` — resolves to `W:\gnus\GeniusCognitiveSystem\SuperGenius\...`, which **does not exist** (confirmed via `find`). (2) `test/CMakeLists.txt:37-39` hardcodes `SUPERGENIUS_TEST_DATA_DIR` default to `${CMAKE_SOURCE_DIR}/../SuperGenius/test/src` — same nonexistent sibling path; the real fixture data lives at `GeniusNetwork/SuperGenius/test/src/processing_datatypes/` (confirmed present: `audio-processing-definition.json`, `bert-tiny.mnn`, etc.). (3) The generic `get_third_party_dir()` walk-up in `build/cmake/functions.cmake:202-249` looks for a sibling `thirdparty` directory (matching git remote `GeniusVentures/thirdparty`) by walking up from NEO-SWARM's own repo root — but `GeniusNetwork` (which contains the real `thirdparty` and `SuperGenius`) is a **sibling of `GeniusCognitiveSystem` under `W:\gnus`, not an ancestor of `GNUS-NEO-SWARM`** (`GNUS-NEO-SWARM` now lives at `GeniusCognitiveSystem/GNUS-NEO-SWARM/`, nested one level deeper after the recent `app-restructure` work). The walk-up will never find it and falls back to `THIRDPARTY_DIR = GeniusCognitiveSystem` (real_path of repo-root's parent), which has no `build/` output at all. | Code edit only, no data migration: repoint both CMake path variables at `GeniusNetwork/SuperGenius/...` (absolute or an explicit new cache variable — see Q-03), or introduce an explicit override cache variable so `-DGENIUSNETWORK_DIR=` (or similar) can be passed at configure time instead of relying on the ancestor-walk-up, which structurally cannot reach a sibling directory tree. |

## Common Pitfalls

### Pitfall 1: `ProcessOutput` return-type break (compile-time, not link-time)

**What goes wrong:** `SGProcessingBridge::SubmitDirect()` calls `outcome::success(process_result.value())` where `process_result.value()` is now a `ProcessOutput`, but the function signature promises `outcome::result<std::vector<uint8_t>>`. This will fail to compile against the current `dev_childwallet` `ProcessingManager.hpp`.
**Why it happens:** `sgproc-render`'s Phase 08 (Structured Artifacts & Manifests) changed `Process()`'s return type from a bare hash vector to a richer `ProcessOutput` struct, and NEO-SWARM's bridge code was written against an older API shape and never recompiled against the real header (see CMake findings below — SGProcessingManager currently resolves to stub/headers-only mode in this checkout, so this code path may never have actually built).
**How to avoid:** Explicitly construct `std::vector<uint8_t>(process_result.value().begin(), process_result.value().end())` before wrapping in `outcome::success()`. Small, one-line, surgical fix.
**Warning signs:** Any attempt to link NEO-SWARM against the real GeniusNetwork build output will surface this as a build error in `sg_processing_bridge.cpp` before any linker step is even reached.

### Pitfall 2: `InputFormatToTypeString(FP4_ULTRA)` returns an invalid `DataType` string

**What goes wrong:** `InputFormatToTypeString()` returns `"fp4_ultra"` for the JSON `"type"` field when format is `FP4_ULTRA`. `DataType`'s generated `from_json` only recognizes `"tensor"` (plus 15 other names, none of them `"fp4_ultra"`) `[VERIFIED: SGProcessingManager/generated/Generators.hpp:598-633]`. Since `MNNInferenceEngine::Config::m_useFp4` defaults to `true` `[VERIFIED: mnn_inference_engine.hpp:83]`, every default-config "sgprocessing"-mode job today would submit `"type": "fp4_ultra"`, fail `sgns::from_json()`'s enum parse (a `std::runtime_error`), get caught by `ProcessingManager::Init()`'s catch block, and return `Error::INVALID_JSON`.
**Why it happens:** `InputFormat` (the tensor *encoding*, e.g. FLOAT32/FP4_ULTRA) is being conflated with `DataType` (the *processor selector*, e.g. TENSOR/STRING). `FP4_ULTRA` should still select `DataType::TENSOR` (type="tensor"), with `FP4_ULTRA` communicated only via the separate `"format"` field (which `InputFormatToFormatString()` already gets right — it returns `"FP4_ULTRA"` correctly `[VERIFIED: sg_processing_bridge.cpp:86-87]`).
**How to avoid:** Fix `InputFormatToTypeString`'s `FP4_ULTRA` case to return `"tensor"`, matching every other numeric/tensor-ish format in that switch.
**Warning signs:** Any inference call through the default config today would already surface `Error::INVALID_JSON` the moment SGProcessingManager is actually linked and reachable — this is a pre-existing, currently-live bug, not something this phase introduces.

### Pitfall 3: Three incompatible "FP4" formats across the ecosystem

**What goes wrong:** Three different, functionally-incompatible bit encodings all use the name "FP4" across repos this phase touches:
1. NEO-SWARM's own `fp4::FP4Codec` (`src/core/fp4/fp4_codec.hpp`) — an **NF4-style non-uniform 16-value lookup table** (`kFP4LUT`, values like `-0.6962f`, `-0.5251f`...), 64×64 macroblocks, per-macroblock scale, "PTDS §4.1". Currently **unused/dead code** — `MNNInferenceEngine`'s constructor does `(void) m_fp4Codec;` `[VERIFIED: mnn_inference_engine.cpp:82]`.
2. MNN_Ultra's native format — standard **E2M1 micro-float** (1 sign, 2 exponent bias=1, 1 mantissa bit; symmetricQuan nbits=4, per-channel scale), implemented in `VulkanFP4Dequant`/`fp4_dequant.comp`, registered under `OpType_Dequantize`, with a Python conversion tool (`tools/fp4/quantize_fp4.py`) whose docstring is the only real spec `[VERIFIED: origin/MNN_Ultra:tools/fp4/quantize_fp4.py:1-13]`.
3. A third, separate "**SGFP4 v2**" adaptive-macroblock format tracked in this repo's own `poc` workstream (`.planning/workstreams/poc/phases/03-fp4-quantization-artifact-integrity/`) — variable 4×4–64×64 blocks, `FP4_AFFINE`+`T158_AFFINE` dual-mode, quadtree layout, referencing a doc called "PTDS v4 §6" (a Python exporter at `quantize/fp4_exporter.py`, not present in this repo's source tree at time of research — referenced only from `poc` workstream planning docs).

None of these three is the same bit layout. CONTEXT.md's canonical_refs cites a spec file (`SGProcessingManager/FP4 Ultra.txt`, "macroblock quantization, symmetric/asymmetric dequant") that **does not exist anywhere on disk** — its description (macroblock, symmetric dequant) actually matches NEO-SWARM's own dead NF4 codec (#1), not MNN_Ultra's E2M1 format (#2), raising the possibility that the spec being referenced from memory in CONTEXT.md is actually describing the wrong (or a fourth, undiscovered) format.
**Why it happens:** Multiple independent FP4 quantization efforts happened across NEO-SWARM (direct engine work), the `poc` workstream (Python export pipeline), and the vendored MNN fork (native Vulkan kernel), all using the same informal name.
**How to avoid:** Before writing PROC-02's processor, get explicit user confirmation of which format `SGProcessingBridge`'s `InputFormat::FP4_ULTRA` is actually meant to represent end-to-end (almost certainly MNN_Ultra's E2M1, since D-09 requires pass-through to "MNN's own decode" and only MNN_Ultra has a working MNN-side decode kernel) — and treat NEO-SWARM's `fp4_codec.hpp`/`.cpp` as probably-orphaned code to flag for removal or explicit re-justification, not as the format this phase should target.
**Warning signs:** If PROC-02's validation logic or test fixtures are built against `fp4_codec.hpp`'s NF4 LUT while the actual dequant call ends up going through MNN_Ultra's E2M1 kernel, encoded buffers will silently decode to garbage (no format tag exists in the wire format to catch this at runtime).

### Pitfall 4: `VulkanInitMutex` re-entrancy deadlock blocks all local verification on real-GPU machines

**What goes wrong:** `ProcessingManager::Create()` unconditionally builds a `CapabilityValidator` snapshot during `Init()`, which probes for a Vulkan device via a lazily-constructed `RenderProcessor::InitializeContext()` call, taking `VulkanInitMutex()` `[VERIFIED: ProcessingManager.cpp:429-440]`. The `sgproc-render` workstream has an open, tracked, not-yet-started bug (queued as its own Phase 18, "Build Stability") where this exact path re-enters `VulkanInitMutex()` on the same thread and deadlocks/throws `"resource deadlock would occur"` — reproduced by the sgproc-render team on a real-Vulkan-device host, failing in 0–2ms, confirmed pre-existing (not caused by any recent phase) `[CITED: GeniusNetwork/.planning/todos/pending/2026-08-10-fix-vulkan-capability-probe-deadlock-in-processingmanager-cr.md]`.
**Why it happens:** Two separate call paths both lock `VulkanInitMutex()` — `CapabilityValidator::BuildSnapshot()`'s `ensureVulkanDevice` lambda and a separate `HasUsableVulkanDevice()` probe — and one of them is reachable from inside the other's already-locked scope.
**How to avoid:** Not fixable within this phase's scope (it's SGProcessingManager infrastructure owned by a different, in-progress workstream — `sgproc-render` Phase 18, "Depends on: Nothing... may execute in any order"). Document this explicitly as a known execution/verification blocker: **any local call to `ProcessingManager::Create()` on a machine with a real Vulkan device will currently deadlock**, which includes this exact Windows dev machine. Coordinate timing with the `sgproc-render` team/workstream, or accept that Phase 4's local end-to-end verification may need to wait for or run in parallel with sgproc-render Phase 18.
**Warning signs:** A test/manual run that hangs indefinitely (or throws `std::system_error: resource deadlock would occur`) the instant `ProcessingManager::Create()` is called — before any processor-specific code runs at all. Do not mistake this for a bug in the new MNN LLM/FP4_ULTRA processor itself.

### Pitfall 5: Missing new sgproc-render libraries when relinking

**What goes wrong:** The current `src/core/CMakeLists.txt:71-76` only searches for/links 6 SGProcessingManager libraries: `ProcessingBase`, `SGProcessors`, `DataSplitter`, `sgprocmanagerlogger`, `sgprocmanagertypes`, `sgprocmanagersha`. The actual Windows Release build output at `GeniusNetwork/SuperGenius/build/Windows/Release/SuperGenius/lib/SGProcessingManager/` now contains **12 libraries**: the original 6 plus `SGArtifacts.lib`, `SGCapability.lib`, `SGShaderCompiler.lib`, `sgproccapture.lib`, `sgprocmanagerdiff.lib`, `sgprocmanagerquant.lib` `[VERIFIED: directory listing]`. `ProcessingManager.cpp` now directly depends on `CapabilityValidator` (from `SGCapability`), `ExecutionManifest`/`artifact_serializer` (from `SGArtifacts`), and processors like `MNN_String` call `sgprocmanagerquant::QuantizeFloatBuffer`/`ResolveQuantScale` (from `sgprocmanagerquant`) `[VERIFIED: processing_processor_mnn_string.cpp:74,148]`.
**Why it happens:** These libraries didn't exist when NEO-SWARM's CMake link list was last written — they were added by `sgproc-render`'s Phases 06 (Capability), 08 (Artifacts), 10 (Capture/quant), all merged since.
**How to avoid:** When repointing the CMake link paths (D-02/Q-03), add all 6 newly-required libraries, not just the original 6. `SGShaderCompiler`/`sgproccapture` may not be needed if the new processor never touches render-pass or capture-harness code paths, but `SGCapability` and `SGArtifacts` are structurally required transitively by `ProcessingManager` itself, and `sgprocmanagerquant` is required by any MNN processor path (including whichever existing processor pattern the new one is based on).
**Warning signs:** Unresolved external symbol linker errors referencing `CapabilityValidator`, `ExecutionManifest`, or `sgprocmanagerquant::*` the moment the relink is attempted.

### Pitfall 6: MNN_Ultra branch is not a clean fast-forward onto the currently-checked-out MNN snapshot

**What goes wrong:** The MNN submodule's `HEAD` (`2a36c8ab`) is **not an ancestor of `origin/MNN_Ultra`** — they diverged from a common ancestor 3 commits back on `HEAD`'s side and 39 commits back on `MNN_Ultra`'s side `[VERIFIED via git merge-base/rev-list]`. HEAD's 3 extra commits include a rename of several x86/SSE backend source files (e.g. `GemmInt8.cpp` → `SSE_GemmInt8.cpp`) and a bugfix in `source/backend/vulkan/component/VulkanDevice.cpp` — and MNN_Ultra's own diff **also touches `VulkanDevice.cpp`** (241 lines changed) and the same SSE backend directory. A rebase or merge of `MNN_Ultra` onto the current checkout will very likely need manual conflict resolution in at least `VulkanDevice.cpp`.
**Why it happens:** Both branches evolved independently from the same May-2026 base commit; upstream MNN sync commits landed on `master` after `MNN_Ultra` was forked off.
**How to avoid:** If/when a future phase actually merges `MNN_Ultra`, budget real time for conflict resolution in the Vulkan backend files, not a trivial checkout-and-go.
**Warning signs:** N/A for this phase specifically (D-04 defers full MNN_Ultra completion) — but if this phase's plumbing work needs to reference MNN_Ultra's header/API shape (e.g. `VulkanFP4Dequant`'s public interface) without merging the whole branch, do so by reading the branch via `git show origin/MNN_Ultra:<path>` rather than checking it out, to avoid disturbing the currently-checked-out, currently-building `master` snapshot.

## Code Examples

### Existing correct in-process SGProcessingManager invocation pattern (the one D-06 wants extended, not replaced)

```cpp
// Source: GNUS-NEO-SWARM/src/core/sgprocessing/sg_processing_bridge.cpp:292-344 (current)
outcome::result<std::vector<uint8_t>> SGProcessingBridge::SubmitDirect(
    const std::string& jsondata,
    std::shared_ptr<boost::asio::io_context> ioc ) const
{
    auto pm_result = sgns::sgprocessing::ProcessingManager::Create( jsondata );
    if ( !pm_result ) { return outcome::failure( Error::InferenceFailed ); }
    auto pm = pm_result.value();
    auto processing = pm->GetProcessingData();
    const auto& passes = processing.get_passes();
    // ... extract ModelNode from passes[0].get_model()...
    std::vector<std::vector<uint8_t>> chunkhashes;
    std::vector<std::string> output_locations;
    auto process_result = pm->Process( ioc, chunkhashes, model_node, output_locations );
    // FIX NEEDED: process_result.value() is now ProcessOutput, not std::vector<uint8_t> —
    // must construct the vector explicitly:
    // return outcome::success( std::vector<uint8_t>( process_result.value().begin(),
    //                                                 process_result.value().end() ) );
}
```

### MNN's native autoregressive API (the correct reference implementation to port into the new SGProcessingManager processor)

```cpp
// Source: GNUS-NEO-SWARM/src/core/engine/mnn_inference_engine.cpp:323-345 (already correct — target for D-06's move)
outcome::result<InferenceResponse> MNNInferenceEngine::InferViaMnnLlm( const Task& task )
{
    std::ostringstream oss;
    mnn_llm_->response( task.m_prompt, &oss, nullptr, static_cast<int>( task.m_maxTokens ) );
    const auto* ctx = mnn_llm_->getContext();
    int gen_tokens = ctx ? static_cast<int>( ctx->output_tokens.size() ) : 0;
    // ... populate InferenceResponse ...
}
```
`MNN::Transformer::Llm::createLLM(dir)`/`load()`/`response()` already handles tokenization, KV-cache, and the sampling loop internally — this is the pattern the new SGProcessingManager processor should call into (with model loading happening inside `StartProcessing()`, under `VulkanInitMutex()`), not the hand-rolled `InferViaStandardInterpreter` loop.

### Current (broken-by-omission) TENSOR validation branch — FP4_ULTRA line

```cpp
// Source: SGProcessingManager/src/processingbase/ProcessingManager.cpp:888-898 (current, dev_childwallet)
case DataType::TENSOR:
{
    if ( input.get_format() )
    {
        const auto format = input.get_format().value();
        if ( format != sgns::InputFormat::FLOAT32 && format != sgns::InputFormat::FLOAT16 &&
             format != sgns::InputFormat::INT32 && format != sgns::InputFormat::INT16 &&
             format != sgns::InputFormat::INT8
             /*&& format != sgns::InputFormat::FP4_ULTRA*/ )   // <-- D-10's commented-out branch
        {
            m_logger->error( "Tensor type supports FLOAT32/FLOAT16/INT32/INT16/INT8 only" );
            return outcome::failure( Error::PROCESS_INFO_MISSING );
        }
    }
    ...
}
```
This is the exact re-confirmed current line (line 894 on `dev_childwallet` — differs from the stale scout's reported ~line 393, confirming Q-01's branch-currency concern was warranted). Uncommenting this one line is the minimal D-10 fix *if* FP4_ULTRA stays a `TENSOR`-typed input (recommended — see Answers to Open Questions, Q-01).

## State of the Art

| Old Approach (stale scout / pre-`sgproc-render`) | Current Approach (`dev_childwallet`, this session) | When Changed | Impact |
|---|---|---|---|
| `ProcessingProcessor::StartProcessing()` — reported 4-arg signature | 6-arg signature including `const ExecutionContext&` | `sgproc-render` Phase 07 (Cancellable Execution Context) | Any new processor must implement the 6-arg overload; a 4-arg override would simply not compile against the base class today. |
| `ProcessingManager::Process()` returns `outcome::result<std::vector<uint8_t>>` | Returns `outcome::result<ProcessOutput>` (artifacts + manifest + hash) | `sgproc-render` Phase 08 (Structured Artifacts & Manifests) | NEO-SWARM's bridge code must be updated — see Pitfall 1. |
| "16 of 18 processors registered" (stale scout claim) | All 16 `DataType`-keyed processors registered; `MNN_ML` remains genuinely unregistered/orphaned (no `ML` `DataType` exists); `RenderProcessor` registered separately under `PassType::RENDER` (not a `DataType`) | Unchanged in substance — re-confirmed directly against current `Init()` | The "18" figure (16 MNN `.cpp`/`.hpp` file pairs + `RenderProcessor` = 17, or counting `MNN_ML` as an 18th unregistered file) refers to *files on disk*, not registered factories — don't conflate the two when the planner counts "existing processors to adapt." |
| `-ld_classic` applied only to `neoswarm_core`, test binaries "don't use the same workaround" (per stale `CONCERNS.md`) | `target_link_options(neoswarm_core PUBLIC "LINKER:-ld_classic")` is a PUBLIC/INTERFACE property; `test/CMakeLists.txt`'s `neoswarm_test()` macro links `neoswarm_core` (even as PRIVATE) into each test executable, which still receives `neoswarm_core`'s INTERFACE link options transitively per normal CMake target-property propagation | Structural fact, not dated — CONCERNS.md (2026-05-27) appears to have been written before this was checked empirically | D-12's "re-verify, don't assume" is still the right call — this is a structural CMake argument for why it likely already propagates, not an empirical build confirmation (no build has been run in this session). |
| Stale `CONCERNS.md`/PROJECT.md describing an active SentencePiece/protobuf conflict | Confirmed: zero references to SentencePiece anywhere in NEO-SWARM's current source tree; no `GENIUS_HAS_SENTENCEPIECE` flag found | Consolidation already happened informally; docs never updated | D-11 is correct — this is a docs-correction task, not a code fix. |

**Deprecated/outdated:**
- Any documentation or prior research referencing `W:\gnus\SuperGenius` (`dev_persisprocresults` branch) is entirely superseded — that checkout has been deleted by the user.
- `CONCERNS.md`'s "SentencePiece/SGProcessing Protobuf Conflict" and "Test Binaries Fail to Link" entries (dated 2026-05-27) should be corrected/removed as part of this phase per D-11.

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | The intended FP4_ULTRA format is MNN_Ultra's E2M1 encoding (not NEO-SWARM's dead NF4 codec, not the `poc` workstream's SGFP4 v2) | Common Pitfalls (Pitfall 3), Summary | If wrong, PROC-02's validation/dispatch plumbing would be built around the wrong assumptions about buffer layout, and would need rework once the correct format is confirmed. **This is flagged as an open question requiring explicit user confirmation before implementation — see Open Questions.** |
| A2 | `-ld_classic`'s PUBLIC/INTERFACE propagation to test binaries via `neoswarm_test()`'s macro is structurally sufficient and CONCERNS.md's claim that tests lack the workaround is itself stale | State of the Art table | If wrong (e.g. some CMake generator or platform doesn't propagate INTERFACE link options the same way), FIX-04 may still need an explicit per-test-target `target_link_options()` call — low risk, cheap to verify empirically per D-12 once a real build is attempted. |
| A3 | `InferViaMnnLlm` (not `InferViaStandardInterpreter`) is the correct reference implementation to port into the new SGProcessingManager processor | Don't Hand-Roll, Code Examples | If the planner instead ports the hand-rolled sampling loop, this reintroduces exactly the kind of duplicate logic D-06 is meant to eliminate, and forfeits MNN's own KV-cache/stopping-criteria correctness for a hand-rolled equivalent. |

**If this table is empty:** N/A — see A1–A3 above; all three should be confirmed/resolved before or during plan-time.

## Open Questions

### Answers to CONTEXT.md's Q-01 through Q-04 (resolved by this research)

**Q-01 (branch currency) — RESOLVED.** Re-verified directly against `dev_childwallet` (`3682e99`, ahead of `origin/dev_childwallet` by 6 commits):
- `ProcessingProcessor::StartProcessing()` is a **6-argument** signature (chunkhashes, `IoDeclaration`, imageData, modelFile, parameters, `const ExecutionContext&`) — materially changed from any older 4-arg reporting, confirmed at `processing_processor.hpp:81-86`.
- All 16 `DataType`-keyed processors are registered (`Init()`, `ProcessingManager.cpp:378-416`); `RenderProcessor` is registered separately under `PassType::RENDER`, not a `DataType`.
- `MNN_ML` remains genuinely **unregistered** — there is no `DataType::ML` in the 16-value enum (`generated/DataType.hpp:19`), and no `RegisterProcessorFactory` call references `MNN_ML` anywhere in `Init()`. It is dead/orphaned source, unchanged in status from what the stale scout reported.
- The commented-out `TENSOR` FP4_ULTRA validation branch is now at **line 894** of `ProcessingManager.cpp` (not ~393 as the stale scout reported) — confirmed via direct `Read`.
- `MNN_String` is registered and functional (a single-forward-pass BERT-style processor, not autoregressive) — see Architecture Patterns for what it actually does.

**Q-02 (MNN_Ultra completeness) — RESOLVED, more precise than "~80%".** `origin/MNN_Ultra`'s own internal GSD-style planning artifacts (`.planning/STATE.md`, present on that branch) report **7/8 plans complete across a 5-phase roadmap (87%)**, last touched 2026-05-28 (branch has been dormant ~11 weeks as of this research date). Specifically:
- Phase 1 (Vulkan Attention Correctness & LLM E2E) — **complete, verified**: "E2E LLM validation — Vulkan produces coherent output."
- Phase 2 (Ultra FP4 Quantization: `VulkanFP4Dequant` execution class + `fp4_dequant.comp` shader) — **complete, verified**: correctness tests pass on both Vulkan and MoltenVK.
- Phase 3 (TurboQuant documentation) — complete, but this documents a **different feature** (KV-cache compression for attention, "TurboQuant-K/V" — not FP4 Ultra weight/tensor quantization at all; do not confuse the two when reading `TURBOQUANT.md`).
- Phase 4 (FP4 Model Conversion Pipeline) — **1 of 2 plans done**: the Python quantization tool (`tools/fp4/quantize_fp4.py`, standard E2M1 encoding) and a CPU reference dequant exist; plan 04-02 (an actual end-to-end "convert a real test model to FP4 Ultra and run inference on it" test, `FP4ModelTest.cpp`) is **explicitly stubbed, never executed** per the branch's own STATE.md.
- Phase 5 (model-level regression tests) — **not started at all** (0/0 plans), explicitly blocked on Phase 4's completion.
- **Additionally:** this branch is **not a clean merge/rebase** onto the currently-checked-out MNN `master` snapshot — they diverged 3 commits (HEAD side) / 39 commits (MNN_Ultra side) from a common ancestor, with an overlapping edit in `VulkanDevice.cpp` on both sides (see Pitfall 6).
- **Bottom line for D-04/D-08:** the GPU dequant *kernel* itself (`VulkanFP4Dequant`) is real, implemented, and unit-tested — the user's "~80%" estimate is roughly right for a narrow "is the kernel written" reading. But there is **no verified evidence of a full model successfully quantized-and-run end-to-end** through MNN's FP4 Ultra path yet, and merging the branch onto the current checkout is nontrivial (conflict risk in Vulkan backend files). This supports D-08's "wire + stub" scope decision: SGProcessingManager's plumbing can validate the format and call into MNN's real (tested-in-isolation) dequant kernel once that kernel is reachable, but a claim of "full FP4 Ultra text generation working end-to-end this phase" would be premature.

**Q-03 (CMake link mechanics) — RESOLVED, with a structural complication beyond what CONTEXT.md anticipated.** The exact confirmed Windows Release library set to link is at `GeniusNetwork/SuperGenius/build/Windows/Release/SuperGenius/lib/SGProcessingManager/` (12 `.lib` files — see Pitfall 5 for the full list and the 6 newly-required ones beyond NEO-SWARM's current 6). However, **the automatic build-root discovery mechanism NEO-SWARM's CMake relies on cannot reach GeniusNetwork at all**: `build/cmake/functions.cmake`'s `get_third_party_dir()` walks up from `GNUS-NEO-SWARM`'s own repo root looking for a sibling `thirdparty/` directory whose git remote matches `GeniusVentures/thirdparty` — but `GeniusNetwork` (which contains the real `thirdparty/` and `SuperGenius/`) is a **sibling of `GeniusCognitiveSystem`**, not an ancestor of `GNUS-NEO-SWARM` (which now lives nested one level deeper at `GeniusCognitiveSystem/GNUS-NEO-SWARM/` after the recent `app-restructure` work). The walk-up will never find it and silently falls back to a nonexistent build directory. **Recommendation:** rather than trying to make the generic ancestor-walk-up reach across sibling trees (which would be an architectural change to shared CMake infrastructure, against CLAUDE.md's minimal-change principle), make the fix local and surgical to `src/core/CMakeLists.txt`'s already-self-contained SGProcessingManager block (lines 63-145): replace the two hardcoded `${PROJECT_ROOT}/../SuperGenius/...` variables with an explicit, overridable cache variable (e.g. `set(GENIUSNETWORK_SUPERGENIUS_DIR "W:/gnus/GeniusNetwork/SuperGenius" CACHE PATH "...")` with an `EXISTS` guard and a sensible relative-path default guess), and do the same for `test/CMakeLists.txt`'s `SUPERGENIUS_TEST_DATA_DIR`. macOS/Linux build output locations under `GeniusNetwork/SuperGenius/build/{OSX,Linux}/<BuildType>/SuperGenius/lib/` were **not directly inspected** in this research session (no macOS/Linux machine available) — assume the same subdirectory structure applies (`SuperGenius/lib/` top level, `SuperGenius/lib/SGProcessingManager/` for the SGProcessingManager-specific libs) based on the platform-parameterized CMake pattern already used elsewhere in both repos, but confirm on those platforms before finalizing paths. `[ASSUMED]`

**Q-04 (sgproc-render overlap) — RESOLVED, real and currently-blocking.** `sgproc-render`'s Phase 18 ("Build Stability") targets exactly the `VulkanInitMutex` re-entrancy deadlock described in Pitfall 4, and is **not yet started** (0/TBD plans as of `sgproc-render`'s own STATE.md, `current_phase: 16`). It is explicitly documented as independent of Phases 16/17/19 ("may execute in any order") and as a **pre-existing bug that reproduces on every `ProcessingManager::Create()` call on a machine with a real Vulkan device present** — not scoped to concurrent/multi-threaded use only. Since this exact Windows machine has a real Vulkan device (per the confirmed Windows Release SuperGenius build output), **any local verification of Phase 4's new processor via `SubmitDirect()`/`ProcessingManager::Create()` will currently deadlock/throw here**, independent of anything Phase 4 itself does. Phases 16/17/19 of `sgproc-render` do not touch any of the files or interfaces Phase 4 needs (Phase 16 touches `ExecutionManifest` serialization only, Phase 17 touches render-path tolerance only, Phase 19 re-runs existing validation fixtures) — no interface conflict there, only the Phase 18 deadlock risk matters for this phase.

### Genuinely new open question raised by this research (not in CONTEXT.md, needs user input before PROC-02 implementation)

1. **Which FP4 format does `SGProcessingBridge`'s `InputFormat::FP4_ULTRA` actually need to target?**
   - What we know: Three incompatible "FP4" implementations exist across the ecosystem (NEO-SWARM's dead NF4 codec, MNN_Ultra's E2M1 kernel, the `poc` workstream's SGFP4 v2 Python exporter). D-09 assumes a single "MNN's own decode" target exists.
   - What's unclear: Whether `FP4_ULTRA` was always meant to mean "whatever MNN_Ultra ships" specifically, or whether it was meant to interoperate with NEO-SWARM's own `fp4_codec.hpp` (which predates this phase and is currently unused) or the separate `poc` workstream's export pipeline.
   - Recommendation: Surface this explicitly to the user before PROC-02 implementation begins (likely during `/gsd-plan-phase`'s own discuss/confirm step, or as an explicit checkpoint in the plan) — the answer determines whether NEO-SWARM's `fp4_codec.hpp`/`.cpp` should be deleted as orphaned code (if the answer is "MNN_Ultra's E2M1, always") or kept/reconciled (if there's a reason both need to coexist).

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| GeniusNetwork/SuperGenius checkout (`dev_childwallet`) | D-02, D-03, all of PROC-01/02/03 | Y | `3682e99`, ahead of origin by 6 commits | — |
| GeniusNetwork/SuperGenius Windows Release build output | D-02 CMake relink | Y | Confirmed present, 12 SGProcessingManager libs + all transitive proto/dep libs | — |
| GeniusNetwork/SuperGenius macOS/Linux build output | D-12 cross-platform re-verification | Not checked this session (Windows-only machine) | — | `[ASSUMED]` same directory structure as Windows; verify before finalizing plan on those platforms |
| GeniusNetwork/thirdparty/MNN (`master`, detached, `2a36c8ab`) | Baseline MNN for all processors | Y | Present, no FP4 Ultra code | — |
| `origin/MNN_Ultra` (unchecked-out remote branch) | PROC-02's actual decode kernel source | Y (fetchable, inspected via `git show`/`git diff` without checkout) | 39 commits ahead of a now-diverged common ancestor with `master` | Read via `git show origin/MNN_Ultra:<path>` rather than checking out, to avoid disturbing the building `master` snapshot, until a merge decision is made |
| Real Vulkan device on this machine | Any local `ProcessingManager::Create()` call | Y (this is exactly what triggers the Pitfall 4 deadlock) | — | None currently — this is the actual blocker, not a missing-tool gap |
| GNUS-NEO-SWARM configured build directory | Any actual compile/link verification | N — no `CMakeCache.txt` found under `build/Windows/` | — | Must run `cmake ..` fresh from a `build/<Platform>/<BuildType>` directory per README.md's documented pattern before any of this phase's fixes can be empirically verified |

**Missing dependencies with no fallback:**
- None that block *planning* — the Vulkan deadlock (Pitfall 4) blocks *local verification*, not planning or implementation of the source-code changes themselves.

**Missing dependencies with fallback:**
- macOS/Linux build output paths — assumed structurally identical to Windows pending direct verification when those platforms are available.

## Validation Architecture

### Test Framework

| Property | Value |
|----------|-------|
| Framework | GoogleTest (GTest), discovered via `find_package(GTest QUIET)` with a manual fallback search in `test/CMakeLists.txt:1-31` |
| Config file | `GNUS-NEO-SWARM/test/CMakeLists.txt` (NEO-SWARM side); `GeniusNetwork/SuperGenius/SGProcessingManager/test/CMakeLists.txt` (SuperGenius side, wired into CTest per `sgproc-render` Phase 10-06's `enable_testing()` ordering fix) |
| Quick run command | `ctest -R test_sgprocessing_pipeline` (NEO-SWARM); `ctest -R ProcessingDatatypesTest` (SuperGenius, but currently deadlocks per Pitfall 4 on real-Vulkan-device machines) |
| Full suite command | `ctest` from the respective configured `build/<Platform>/<BuildType>` directory |

### Phase Requirements → Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|---------------------|--------------|
| PROC-01 | New LLM processor generates coherent multi-token text via `ProcessingManager::Process()` | integration | New test needed, e.g. `SGProcessingManager/test/src/mnn_llm_processor_test.cpp` | ❌ Wave 0 |
| PROC-02 | FP4_ULTRA input passes `CheckProcessValidity()` and dispatches to a registered processor | unit | New test needed alongside existing `processing_datatypes_test.cpp` fixtures | ❌ Wave 0 |
| PROC-03 | Single protobuf version confirmed across the whole link (no duplicate-symbol errors) | build-verification (not a runtime test) | Full rebuild + link of `neoswarm_core` and its test binaries | N/A — verified by successful build, not a test file |
| FIX-04 | Test binaries link and run without duplicate-symbol errors on available platforms | build-verification | `ctest` (any suite) succeeding to link at all | N/A |

### Sampling Rate
- **Per task commit:** Attempt a fresh `cmake ..` + `ninja` build in `build/Windows/Release` (or `Debug`) after each CMake/source fix, since **no configured build currently exists** on this machine.
- **Per wave merge:** Full `ctest` run on whichever platform is available — expect the `VulkanInitMutex` deadlock (Pitfall 4) to block SGProcessingManager's own `ProcessingDatatypesTest`/`ProcessingDispatchTest` until `sgproc-render` Phase 18 lands; NEO-SWARM's own new tests should still be runnable if they avoid the deadlocking path (they can't — `SubmitDirect()` goes through the same `Create()` call). Document this as an expected, known-blocked test rather than treating it as a regression this phase caused.
- **Phase gate:** Given the confirmed `VulkanInitMutex` deadlock, a literal "full suite green" gate is not currently achievable end-to-end on a real-GPU machine — the plan should define a documented, narrower gate (e.g. "builds and links cleanly; schema/validation-level unit tests pass; full `ProcessingManager::Create()`-dependent integration tests are known-blocked pending sgproc-render Phase 18, tracked not silently skipped").

### Wave 0 Gaps
- [ ] New processor test (SuperGenius side) — no test currently exercises an MNN LLM generation processor or FP4_ULTRA end-to-end.
- [ ] NEO-SWARM integration test update — `test/integration/test_sgprocessing_pipeline.cpp` "only exercises FLOAT32 today; no FP4_ULTRA or LLM integration test exists yet" (confirmed: file only contains `SGProcessingBridge` schema-generation tests in the region read; needs a corresponding FP4_ULTRA/LLM case).
- [ ] `SUPERGENIUS_TEST_DATA_DIR` CMake variable fix (see Runtime State Inventory) — required before any SuperGenius-fixture-dependent NEO-SWARM test can even locate its data.

## Security Domain

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|-------------------|
| V2 Authentication | No | This phase does not touch auth; network dispatch (SG-02) is separately tracked and out of scope here. |
| V3 Session Management | No | N/A — no session concept in this phase's scope. |
| V4 Access Control | No | N/A. |
| V5 Input Validation | **Yes** | Existing `ProcessingManager::CheckProcessValidity()` pattern (per-`DataType` dimension/format checks) — the new FP4_ULTRA branch and the new LLM processor's `maxLength`/parameter handling must follow the same fail-closed, explicit-error pattern already used for every other `DataType` case (e.g. `Error::PROCESS_INFO_MISSING` on missing/invalid fields), not a silent default. |
| V6 Cryptography | No | No new cryptographic primitives introduced; FP4 quantization is a numeric encoding, not a cryptographic concern. |

### Known Threat Patterns for this stack

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|-----------------------|
| Malformed/oversized FP4_ULTRA buffer causing an out-of-bounds read in MNN's native dequant kernel | Tampering / Denial of Service | Validate declared dimensions (`block_len`, `chunk_stride`) against the actual buffer size *before* calling into MNN's decode, mirroring the existing `TEXTURE2_D` case's `block_len % block_line_stride` divisibility check (`ProcessingManager.cpp:956-964`) — do not trust the schema's declared size without a matching byte-length check against the actual input buffer. |
| Unbounded `maxLength`/`maxNewTokens` parameter causing unbounded memory/compute in the new autoregressive processor | Denial of Service | Apply the same pattern MNN_String already uses for `maxLength` (bounded, schema-parameter-driven, with a sane default) — cap generation length via `ExecutionContext`'s existing `deadlineMs`/budget fields rather than an unbounded loop. |
| Model file (`modelFile` buffer) from an untrusted/network-submitted job loaded directly by `MNN::Interpreter`/`MNN::Transformer::Llm` | Tampering / Elevation of Privilege (via a malicious model triggering a memory-safety bug in MNN's own parser) | Out of this phase's scope to fully mitigate (MNN's model-parsing hardening is a thirdparty concern) — but the new processor should not add *additional* untrusted-input trust beyond what existing MNN processors already accept the same way. |

## Sources

### Primary (HIGH confidence — direct file reads / git commands against live `dev_childwallet` and NEO-SWARM checkouts this session)
- `SGProcessingManager/include/processors/processing_processor.hpp` — current `ProcessingProcessor` interface
- `SGProcessingManager/include/processingbase/ProcessingManager.hpp` + `.cpp` — registration, `ProcessOutput`, validation logic, current FP4_ULTRA line number
- `SGProcessingManager/generated/DataType.hpp`, `generated/InputFormat.hpp`, `generated/Generators.hpp` — enum/JSON mapping ground truth
- `SGProcessingManager/src/processors/processing_processor_mnn_string.cpp`, `include/processors/processing_processor_mnn_ml.hpp` — current processor shapes
- `GNUS-NEO-SWARM/src/core/engine/mnn_inference_engine.hpp`+`.cpp`, `sgprocessing/sg_processing_bridge.hpp`+`.cpp` — current bridge/engine code, compile-break evidence
- `GNUS-NEO-SWARM/src/core/CMakeLists.txt`, `test/CMakeLists.txt`, `cmake/CommonBuildParameters.cmake`, `build/CommonCompilerOptions.cmake`, `build/cmake/functions.cmake` — CMake path resolution mechanics
- `GeniusNetwork/thirdparty/MNN` git log/diff/merge-base commands (`git log`, `git diff --stat`, `git merge-base`, `git rev-list --count`, `git show origin/MNN_Ultra:...`) — MNN_Ultra completeness and mergeability evidence
- `GeniusNetwork/.planning/workstreams/sgproc-render/{ROADMAP,STATE}.md`, `.planning/todos/pending/2026-08-10-fix-vulkan-capability-probe-deadlock-in-processingmanager-cr.md` — VulkanInitMutex deadlock evidence
- `GNUS-NEO-SWARM/.planning/workstreams/neoswarm/codebase/CONCERNS.md`, `.planning/workstreams/poc/phases/03-fp4-quantization-artifact-integrity/03-CONTEXT.md` — stale-docs and third-FP4-format evidence
- `find`/directory listings of `GeniusNetwork/SuperGenius/build/Windows/Release/SuperGenius/lib/` — confirmed library set

### Secondary (MEDIUM confidence)
- `GNUS-NEO-SWARM/CLAUDE.md` — project constraints (authoritative for this repo, but not independently re-verified against external standards docs)

### Tertiary (LOW confidence / assumed)
- macOS/Linux build output directory structure for `GeniusNetwork/SuperGenius` — assumed identical to Windows, not directly inspected this session (see Environment Availability)
- Which FP4 format `FP4_ULTRA` is meant to target — reasoned inference (A1), not confirmed by the user

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — no external packages, all internal code directly read this session
- Architecture: HIGH — `ProcessingProcessor`/`ProcessingManager` interfaces read directly from current `dev_childwallet` source, cross-checked against registration call sites
- Pitfalls: HIGH for Pitfalls 1, 2, 4, 5, 6 (all directly verified via source/git); MEDIUM for Pitfall 3 (format ambiguity is confirmed as a real discrepancy, but which format is "correct" is genuinely unresolved pending user input)

**Research date:** 2026-08-18
**Valid until:** ~14 days for the CMake/build-path findings (fast-moving, actively-developed cross-repo build surface, `sgproc-render` workstream still landing phases weekly) — re-verify branch state (`dev_childwallet` HEAD, `sgproc-render` STATE.md, `MNN_Ultra` branch tip) before planning if more than ~2 weeks have elapsed since this research.
