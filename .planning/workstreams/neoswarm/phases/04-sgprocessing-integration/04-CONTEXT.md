# Phase 4: SGProcessing Integration - Context

**Gathered:** 2026-08-18
**Status:** Ready for planning

<domain>
## Phase Boundary

The SuperGenius network can execute MNN LLM text generation and FP4_ULTRA-quantized model inputs via SGProcessingManager, with the current build/link setup consolidated so NEO-SWARM links a single consistent SGProcessingManager (and its protobuf) instead of a stale prebuilt snapshot.

This phase is **genuinely cross-repo**. Real work lands in two places:
1. **SuperGenius / SGProcessingManager** (`W:\gnus\GeniusNetwork\SuperGenius`, submodule of the `GeniusNetwork` monorepo, branch `dev_childwallet`) — new/adapted processor(s) for MNN LLM generation and FP4_ULTRA tensor input handling.
2. **GNUS-NEO-SWARM** — delete duplicate raw-MNN-invocation code, rewire call sites to route through SGProcessingManager (locally in-process or via network dispatch), fix the build to link against GeniusNetwork's SuperGenius build output.

**Critical environment correction (discovered this session, not previously documented):** The `W:\gnus\SuperGenius` standalone checkout (branch `dev_persisprocresults`, stale since 2026-07-01) **has been deleted**. `W:\gnus\GeniusNetwork\SuperGenius` (branch `dev_childwallet`) is now the sole SuperGenius checkout. It carries an entire mature GSD workstream, `sgproc-render` (16 phases, v1.0–v2.3), that reworked SGProcessingManager's execution model — capability/validation contracts, cancellable execution, structured artifacts/manifests, conformance test suites, and quantization/normalization handling for cross-hardware determinism. That workstream is "mostly a complete plan" per the user, with 3 small phases (17–19) still in progress in parallel with this work. **Any research/planning for this phase must read against the current `dev_childwallet` state, not any documentation or prior analysis based on the old `dev_persisprocresults` snapshot** (this includes the initial codebase scout performed during this discussion — see Open Questions).

In scope:
- New or adapted SGProcessingManager processor(s) doing MNN LLM autoregressive text generation (consolidating what `mnn_inference_engine.cpp` currently does locally in NEO-SWARM)
- Re-enabling/wiring FP4_ULTRA tensor input handling in SGProcessingManager (validation + dispatch plumbing), with actual dequant delegated to MNN
- Deleting duplicate raw-MNN-invocation logic from NEO-SWARM's `mnn_inference_engine`, rewiring its local-inference path to call `ProcessingManager::Init()`/`Process()` directly (in-process, no network) instead
- Fixing NEO-SWARM's CMake to link against `GeniusNetwork\SuperGenius\build\<Platform>\<BuildType>\SuperGenius\lib` (prebuilt-from-source static libs, one consistent protobuf) instead of its old separate/stale prebuilt SGProcessingManager snapshot
- Re-verifying (not assuming) whether the `-ld_classic` macOS linker workaround is still needed once that relink happens; extending whatever's actually needed to Linux/Windows test binaries
- Correcting stale docs (CONCERNS.md, PROJECT.md) that describe an active SentencePiece/protobuf conflict — SentencePiece does not currently exist in the codebase

Out of scope (this phase):
- Finishing the MNN_Ultra branch's FP4 Ultra decode work if research shows it's far from the "~80% done" estimate — that would move to a separate phase (see D-04)
- Re-adding SentencePiece tokenization (no active conflict to fix; only pursue if a future phase actually needs it)
- Implementing FP4 Ultra's dequant math inside SGProcessingManager itself (delegated to MNN — see D-09)
- Streaming token output to Flutter (already out of scope project-wide, per PROJECT.md)

</domain>

<decisions>
## Implementation Decisions

### Repo Boundary & Build Linkage
- **D-01:** This phase is full cross-repo — plans include commits to both `SuperGenius/SGProcessingManager` (GeniusNetwork submodule) and `GNUS-NEO-SWARM`.
- **D-02:** NEO-SWARM does **not** build SGProcessingManager itself. SuperGenius already builds it (and everything it depends on, including protobuf-generated proto libs) as static libs at `GeniusNetwork\SuperGenius\build\<Platform>\<BuildType>\SuperGenius\lib\` (confirmed present for Windows Release: `SGProcessingManager/` subdir + `SGProcessingProto.lib`, `ConsensusProto.lib`, etc., all one consistent protobuf version). NEO-SWARM's CMake should link against this build output instead of whatever separate prebuilt "thirdparty" snapshot it references today.
- **D-03:** `W:\gnus\SuperGenius` (the stale `dev_persisprocresults` checkout) has been deleted by the user. `W:\gnus\GeniusNetwork\SuperGenius` (`dev_childwallet`) is the sole canonical SuperGenius checkout going forward — all research/planning/execution targets this one.
- **D-04:** The vendored MNN fork (`GeniusNetwork/thirdparty/MNN`, currently detached at a `master` snapshot with no FP4 Ultra code) has its FP4 Ultra work on `origin/MNN_Ultra` (unchecked-out), estimated by the user at "~80% done" but **unverified**. Research must determine its actual completeness before planning commits to finishing it in this phase. If it's far from done, defer full MNN-side completion to a separate phase and scope this phase to linking/wiring SGProcessingManager against whatever MNN currently exposes (see D-09).

### MNN LLM Processor Consolidation (PROC-01)
- **D-05:** SGProcessingManager gains a processor (new file, e.g. `processing_processor_mnn_fp4.cpp`, or an adapted existing MNN processor — exact shape left to planning) that does what NEO-SWARM's `src/core/engine/mnn_inference_engine.cpp` currently does. **Architectural principle: all actual MNN calls happen inside SGProcessingManager** — it already owns Vulkan locking/coexistence (established by the `sgproc-render` workstream), and consolidating means SuperGenius network nodes automatically gain LLM-serving capability too.
- **D-06:** `MNNInferenceEngine` is **not deleted entirely**. `InferViaSGProcessing()` (network job submission to the SuperGenius swarm) stays as-is. For local/SingleNode calls, its internal implementation changes: instead of doing raw MNN inference itself, it calls `ProcessingManager::Init()` / `ProcessingManager::Process()` directly — an in-process call into SGProcessingManager, no network hop. Duplicate raw-MNN-invocation logic is removed from NEO-SWARM.
- **D-07:** PROC-01 (LLM generation) and PROC-02 (FP4_ULTRA) are not necessarily one merged processor — "FP4 is FP4," handled as its own concern within SGProcessingManager. Several existing MNN processors there might already fit LLM generation with adaptation; a new processor is fine too if needed. Exact processor boundary is left to plan time.

### FP4_ULTRA Scope (PROC-02)
- **D-08:** Wire + stub, ship what's ready: re-enable FP4_ULTRA validation and wire the schema/dispatch plumbing end-to-end now. The actual decode/dequant call defers to MNN's own FP4 Ultra API once ready — plumbing ships even if MNN isn't fully there yet (contingent on D-04's research finding).
- **D-09:** Dequant math is **not** duplicated in SGProcessingManager. Pass-through to MNN: SGProcessingManager validates the format and hands the raw FP4_ULTRA-encoded buffer to MNN's own decode, consistent with D-05's "all MNN calls happen in SGProcessingManager, no duplicate logic" principle.
- **D-10:** Whether FP4_ULTRA re-enables the existing `TENSOR` DataType's commented-out validation branch (`ProcessingManager.cpp:393`) versus needs its own DataType/processor is **not decided** — depends on what's actually required once the current (`dev_childwallet`) validation code and the FP4 Ultra spec doc are read in full. Left to plan-time investigation.

### Protobuf Conflict Scope (PROC-03 / FIX-04)
- **D-11:** PROC-03 is resolved by consolidation, not by a code fix: once NEO-SWARM links against GeniusNetwork's SuperGenius build output (D-02), there is one consistent protobuf version flowing through everything. Verify this holds and correct the stale CONCERNS.md/PROJECT.md references describing an active SentencePiece/protobuf conflict (SentencePiece does not currently exist in the codebase — no implementation file, no `GENIUS_HAS_SENTENCEPIECE` flag anywhere).
- **D-12:** FIX-04: re-verify, don't assume. After relinking against the GeniusNetwork build output, rebuild and confirm whether `-ld_classic` (currently the only confirmed fix, macOS-only, applied to `neoswarm_core` per `src/core/CMakeLists.txt:128-132`) is still needed. Get test binaries linking cleanly across whichever platforms are actually available to test (Windows confirmed available on this machine; macOS/Linux as available).

### Claude's Discretion
- Exact processor file/class boundary for the MNN LLM + FP4_ULTRA work in SGProcessingManager (D-05, D-07, D-10) — informed by reading `dev_childwallet`'s actual current `ProcessingManager.cpp`/`processing_processor.hpp`, not the stale scout from the `dev_persisprocresults` branch
- Whether to reuse an existing MNN processor (e.g. adapt `MNN_ML`'s stub, or `MNN_String`) versus write a new one — investigate at plan time
- CMake mechanics for pointing NEO-SWARM at `GeniusNetwork\SuperGenius\build\<Platform>\<BuildType>\SuperGenius\lib\` instead of the current prebuilt-snapshot path

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Planning documents (this workstream)
- `.planning/workstreams/neoswarm/ROADMAP.md` § Phase 4 — goal, success criteria, dependencies
- `.planning/workstreams/neoswarm/REQUIREMENTS.md` — PROC-01, PROC-02, PROC-03, FIX-04
- `.planning/workstreams/neoswarm/STATE.md` — Phase 4 blocker notes (some now superseded by this session's findings — see Open Questions)
- `.planning/workstreams/neoswarm/codebase/CONCERNS.md` — SentencePiece/protobuf conflict notes; **confirmed stale this session, needs correction** (D-11)

### SuperGenius / SGProcessingManager (GeniusNetwork checkout — `dev_childwallet` branch, the ONLY canonical checkout)
- `W:\gnus\GeniusNetwork\SuperGenius\SGProcessingManager\include\processingbase\ProcessingManager.hpp` — processor registration API (`RegisterProcessorFactory`, `SetProcessorByName`) — **re-read on `dev_childwallet`, not the stale scout's findings**
- `W:\gnus\GeniusNetwork\SuperGenius\SGProcessingManager\src\processingbase\ProcessingManager.cpp` — `Init()` registration calls, tensor-format validation logic (~line 393 on the stale branch — line number needs reconfirming on `dev_childwallet`)
- `W:\gnus\GeniusNetwork\SuperGenius\SGProcessingManager\include\processors\processing_processor.hpp` — `ProcessingProcessor` interface new processors implement — **likely changed by the sgproc-render workstream (cancellable execution, manifests) — verify current shape, do not assume the old 4-arg signature**
- `W:\gnus\GeniusNetwork\SuperGenius\SGProcessingManager\include\processors\processing_processor_mnn_string.hpp` / `processing_processor_mnn_ml.hpp` — closest existing patterns for a text/LLM processor (mnn_ml was an unregistered stub on the old branch — recheck status on `dev_childwallet`)
- `W:\gnus\GeniusNetwork\SuperGenius\SGProcessingManager\generated\DataType.hpp`, `generated\InputFormat.hpp` — dispatch-key enum and input-encoding enum (FP4_ULTRA lives in the latter)
- `W:\gnus\GeniusNetwork\SuperGenius\SGProcessingManager\FP4 Ultra.txt` — FP4 Ultra format spec (macroblock quantization, symmetric/asymmetric dequant) — reference for what MNN's decode should implement; SGProcessingManager itself does not implement this math (D-09)
- `W:\gnus\GeniusNetwork\SuperGenius\build\Windows\Release\SuperGenius\lib\` — confirmed build output NEO-SWARM should link against (D-02)

### sgproc-render workstream (GeniusNetwork — the execution-model rework Phase 4 must build on top of)
- `W:\gnus\GeniusNetwork\.planning\workstreams\sgproc-render\ROADMAP.md` — full phase history (v1.0–v2.3), what execution-contract/manifest/cancellation/quantization machinery already exists
- `W:\gnus\GeniusNetwork\.planning\workstreams\sgproc-render\STATE.md` — current status (mid-v2.3, Phases 17–19 in progress in parallel)

### Vendored MNN fork
- `W:\gnus\GeniusNetwork\thirdparty\MNN` — submodule, currently detached at a `master` snapshot (`2a36c8ab`, 2026-08-05) with no FP4 Ultra code; FP4 Ultra work lives on `origin/MNN_Ultra` (unchecked-out) — see D-04, Open Questions

### GNUS-NEO-SWARM code being replaced/rewired
- `src/core/engine/mnn_inference_engine.hpp` / `.cpp` — local MNN LLM engine; `InferViaSGProcessing()` stays, direct-inference internals get replaced per D-06
- `src/core/sgprocessing/sg_processing_bridge.hpp` / `.cpp` — `SubmitDirect()` (already calls `ProcessingManager::Create()`+`Process()` locally — the pattern D-06 extends), `SubmitNetwork()`, `InputFormatToTypeString()`/`InputFormatToFormatString()` (already maps `FP4_ULTRA` → `"fp4_ultra"` ahead of server support)
- `src/core/CMakeLists.txt` (lines ~63-145 link SGProcessingManager libs; lines ~128-132 the `-ld_classic` workaround) — needs repointing to the GeniusNetwork build output (D-02) and re-verification (D-12)
- `test/integration/test_sgprocessing_pipeline.cpp` — only exercises FLOAT32 today; no FP4_ULTRA or LLM integration test exists yet

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `SGProcessingBridge::SubmitDirect()` — already the "call SGProcessingManager locally, no network" pattern D-06 extends to replace `mnn_inference_engine`'s direct MNN calls
- `SGProcessingBridge::BuildSchemaJson()` / `InputFormatToTypeString()` — already emits `FP4_ULTRA` mapping ahead of server support; wiring work connects to this, doesn't replace it
- 18 existing `MNN_*` processor classes in SGProcessingManager (on the stale branch — recheck against `dev_childwallet`) — closest existing patterns to adapt rather than starting from zero

### Established Patterns
- `outcome::result<T>` error propagation throughout both codebases
- PIMPL idiom, `m_`-prefixed members, C++17, Allman braces (NEO-SWARM conventions)
- Compile-guard feature flags (`GENIUS_HAS_*`) gating optional dependencies in NEO-SWARM's CMake

### Integration Points
- `ApiServer` / router `SingleNode` mode — current caller of `mnn_inference_engine`'s direct-inference path, needs rewiring per D-06
- NEO-SWARM's `src/core/CMakeLists.txt` SGProcessingManager link block — needs repointing per D-02

</code_context>

<specifics>
## Specific Ideas

- "All actual mnn calls should happen in SGProcessingManager since it handles a lot of vulkan locking tasks and such. It also happens that jobs may be happening automatically on SuperGenius, so that's doubly useful." — the core architectural rationale behind D-05/D-06
- "SGProcessingManager should not come from thirdparty, it should come from SuperGenius" — the user's explicit correction that reshaped the entire repo-boundary discussion
- User has already removed the stale `W:\gnus\SuperGenius` checkout to eliminate ambiguity going forward

</specifics>

<deferred>
## Deferred Ideas

- Finishing `MNN_Ultra`'s FP4 Ultra decode work, if research shows it's far from done — candidate for its own phase (D-04)
- Re-adding SentencePiece tokenization — no active conflict exists today; only relevant if a future phase specifically needs SentencePiece over MNN's built-in `tokenizer.mtok`
- Implementing FP4 Ultra's dequant math inside SGProcessingManager — explicitly delegated to MNN (D-09), not this project's concern

### Reviewed Todos (not folded)
None — no pending todos matched this phase (`todo.match-phase` returned 0 matches).

</deferred>

<open_questions>
## Open Questions for Research (NOT decided here)

- **Q-01 (branch currency):** This discussion's initial codebase scout examined the stale `W:\gnus\SuperGenius` checkout (`dev_persisprocresults`, 2026-07-01) before the branch mixup was discovered. All specific claims from that scout (exact line numbers, the "16 of 18 processors registered" count, `ProcessingProcessor`'s exact interface signature, whether `MNN_ML` is still unregistered) **must be re-verified against `GeniusNetwork\SuperGenius` (`dev_childwallet`, 2026-08-17)** before planning — the interface may have changed materially under the `sgproc-render` workstream's capability/validation/cancellation/manifest work (Phases 06-09, 16).
- **Q-02 (MNN_Ultra completeness):** How complete is `origin/MNN_Ultra`'s FP4 Ultra decode support, actually? User estimated "~80%" but flagged it as unverified. This gates whether PROC-02's full decode path ships this phase or defers (D-04, D-08).
- **Q-03 (CMake link mechanics):** Exact CMake changes needed in NEO-SWARM's `src/core/CMakeLists.txt` to link against `GeniusNetwork\SuperGenius\build\<Platform>\<BuildType>\SuperGenius\lib\` instead of the current prebuilt snapshot path — including how this resolves per-platform (confirmed build output exists for Windows Release; macOS/Linux build output locations need checking).
- **Q-04 (sgproc-render overlap):** Does the `sgproc-render` workstream's Phase 18 (`ProcessingManager::Create()`'s `VulkanInitMutex` re-entrancy deadlock, still open/in-progress) affect or block the new MNN LLM / FP4_ULTRA processor's ability to run cleanly? Worth a research pass before planning locks in the processor's execution shape.

</open_questions>

---

*Phase: 04-sgprocessing-integration*
*Context gathered: 2026-08-18*
