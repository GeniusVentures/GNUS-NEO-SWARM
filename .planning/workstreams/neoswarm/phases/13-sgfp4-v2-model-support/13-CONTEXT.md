# Phase 13: SGFP4 v2 Model Support - Context

**Gathered:** 2026-09-02
**Status:** Ready for planning

<domain>
## Phase Boundary

Run a real SGFP4-quantized `.mnn` model through `MNNInferenceEngine` → `SGProcessingBridge::SubmitDirect()` → `ProcessingManager::Create/Process` on the **direct-call path only** (no SuperGenius network/job submission), on both CPU and Vulkan backends — plus, in the same pass:

- Defensive null-check fix in `SGProcessingManager/src/processors/processing_processor_mnn_tensor.cpp` (`Process()` can return `nullptr`; `StartProcessing()` dereferences it unchecked via `procresults->host<float>()`)
- Deletion of orphaned NF4 `fp4_codec.{hpp,cpp}` + `test/core/test_fp4_codec.cpp` (dead code; consumer removed in commit `8ee7fa4`)
- Fixes for stale FP4-area tests: SuperGenius `test/processors/mnn_tensor_fp4_test.cpp` (asserts FP4_ULTRA decode unavailable; it is live) and NEO-SWARM `test_sg_connectivity.cpp` fp4_ultra lowercase-literal assertion

This is a **cross-repo phase** (same shape as Phase 4): work lands in SuperGenius/SGProcessingManager (`W:\gnus\GeniusNetwork\SuperGenius`, branch `dev_childwallet`) and GNUS-NEO-SWARM.

SGFP4 is a **model-weight compression format** decoded inside MNN's graph via `OpType_SGFP4Dequant` — not an input-tensor format like E2M1 `FP4_ULTRA`. Never conflate the two; never call this "Ultra FP4."

Out of scope (locked in seed):
- SuperGenius network/job-submission path (direct call only)
- Building SGFP4 conversion/injection tooling (`mnnconvert --sgfp4` + `sgfp4_inject` already exist)
- arxiv §8 verifiable-execution/attestation
- `InputFormat::SGFP4_V2` wire format — SGFP4 is not an input-tensor format
- gnus-poc `--adaptive` default flip and `"fp4_ultra_v0.2"` manifest naming collision (separate follow-ups)

</domain>

<decisions>
## Implementation Decisions

### E2E Verification Gate (VulkanInitMutex deadlock)
- **D-01:** Research step FIRST checks the current status of the `VulkanInitMutex` re-entrancy deadlock (sgproc-render Phase 18, tracked in the GeniusNetwork repo) before locking the verification approach. If fixed → real local E2E. If still open → see D-03 reconciliation. Decision is data-driven and documented in RESEARCH.md; never silently assumed.
- **D-02:** SGF-01's success criterion is **wiring proven + conditional execution**: the E2E test always runs the full path through `ProcessingManager::Create()`; output assertions execute when the environment allows; `GTEST_SKIP()` (citing the tracked bug by name) when it doesn't. Passes either way — no silent omission.
- **D-03:** Skip-gate mechanics reuse the 04-04 pattern exactly: `HasUsableVulkanDevice()` → `GTEST_SKIP()` with the tracked bug name in the skip message.

### Backend Coverage
- **D-04:** **CPU + Vulkan execution are both hard success criteria.** Reconciliation with D-01/D-02: if research finds the deadlock still open, the phase plan includes **fixing (or pulling the fix for) the sgproc-render Phase 18 deadlock as prerequisite work within this phase**. The CPU test ships first; Vulkan is skip-gated ONLY until the fix lands — it cannot be permanently skip-gated. The phase does not close with Vulkan unexecuted.
- **D-05:** Two explicit session tests: one with explicit CPU session type, one with explicit Vulkan session type — proving SGFP4 runs through both direct paths. Do not rely on processor defaults.

### Test Model Logistics
- **D-06:** A **tiny deliberately-built conv model** is committed to test assets. Constraints: conv-family weights >4096 elements each (so `OpType_SGFP4Dequant` ops actually exist — light tensors stay FP32); total size well below MNN's `_largeModel` externalization threshold (inline weights only — the `op->externalPath` injection gap for externalized SGFP4 weights is open). The plan documents the manual `mnnconvert --sgfp4` recipe that produced it (manual step — no automated pipeline invokes mnnconvert; same as RUN_AND_DEPLOY.md's llmexport.py usage).
- **D-07:** The E2E test **asserts ≥1 `OpType_SGFP4Dequant` op exists** in the loaded `.mnn` (walks the op list) — so a regression that silently produces an all-FP32 model fails loudly instead of passing vacuously.
- **D-08:** Naming discipline: all new tests/files/docs say "SGFP4" or "SGFP4 v2" — never "Ultra FP4"/"FP4 Ultra" (that name means E2M1/`FP4_ULTRA` in this codebase).

### Cross-Repo Fix Mechanics (SGF-02/03/04)
- **D-09:** One phase, cross-repo plans (same as Phase 4): plans carry commits for both repos, committed **innermost-first** (SGProcessingManager → SuperGenius → GeniusNetwork root → NEO-SWARM); verify each level with `git status --short` before moving on.
- **D-10:** Build baseline: user rebuilt SuperGenius/GeniusSDK fresh on 2026-09-02, adding **Debug builds alongside Release** (`build/Windows/Release/SuperGenius/lib/` is the D-02 link path from Phase 4). Plans include an explicit SuperGenius rebuild step after SGF-02 (and any deadlock fix) land in source, so linked libs always match source. Debug builds are available for deadlock debugging specifically.
- **D-11:** SGF-02 ships with a **negative regression test**: feed a malformed/incompatible model through the MNN_Tensor processor and assert a clean error return (no crash), alongside the null-check fix itself.

### Claude's Discretion
- Exact shape of the SGF-02 error propagation (error code vs. exception vs. empty-result return) — based on what `StartProcessing()`'s existing error paths look like on `dev_childwallet`
- Which small conv model architecture to use for the committed test asset (e.g., a few stacked conv layers sized to exceed the 4096-element weight threshold while staying far under externalization size)
- CMake mechanics for wiring the committed `.mnn` test asset into the test suite
- Whether the CPU E2E test can run unconditionally (CPU path may not touch `VulkanInitMutex` at all — researcher verifies)

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Phase planning (this workstream)
- `.planning/workstreams/neoswarm/ROADMAP.md` § "Phase 13: SGFP4 v2 Model Support" — goal, scope, known risks, out-of-scope locks
- `.planning/workstreams/neoswarm/REQUIREMENTS.md` § "SGFP4 v2 Model Support (Phase 13)" — SGF-01..04 + verification constraint
- `.planning/workstreams/neoswarm/STATE.md` — Phase 4/13 blocker notes (Vulkan deadlock applies to SGF-01; externalized-weight gap)
- `.planning/workstreams/neoswarm/phases/04-sgprocessing-integration/04-CONTEXT.md` — Phase 4 decisions this phase builds on (D-02 link path, D-05/D-06 architecture, D-13 three-FP4-formats ruling)
- `.planning/workstreams/neoswarm/SGFP4-INTEGRATION-SEED.md` — the promoted seed (required reading per ROADMAP): goal, blockers/gotchas, reference code list, scope locks

### Evaluation (parent repo — read the addendum, not just the body)
- `W:/gnus/GeniusCognitiveSystem/.planning/quick/260825-pgu-evaluate-mnn-sgfp4-pivot-fp4-implementat/260825-pgu-EVALUATION.md` — full evaluation + 2026-08-26 addendum: `mnnconvert --sgfp4` verified through the classic Interpreter API (CPU + Vulkan); three-FP4-formats distinction; externalized-weight `op->externalPath` gap; E2E validation gate is liveness-only (no accuracy proof); conv-family-only coverage, >4096-element threshold

### Format spec
- `W:/gnus/GeniusCognitiveSystem/docs/architecture/sgfp4-format.md` (Doc 16) — SGFP4 format architecture reference

### MNN-side reference code (read-only — do NOT modify MNN in this phase)
- `include/MNN/SGFP4DequantUtils.hpp` (vendored MNN) — normative decode logic + format constants
- `source/backend/cpu/CPUSGFP4Dequant.cpp` (`onResize`) — how the op reads its external sidecar
- `tools/fp4/sgfp4_encode.cpp` — the C++ encoder inside `mnnconvert --sgfp4`
- `demo/exec/pictureRecognition.cpp` — canonical classic Interpreter/Session pattern
- `test/op/TestSGFP4Converter.cpp` (PHASE B) — closest existing template for loading a real SGFP4 `.mnn` via `createFromFile`/`createSession`/`runSession` and asserting decode correctness

### NEO-SWARM code being touched/extended
- `src/core/sgprocessing/sg_processing_bridge.hpp` / `.cpp` — `SubmitDirect()` at :308 (the direct-call path SGF-01 exercises); `SubmitJob()` dispatch at :293-297
- `test/integration/test_sg_connectivity.cpp` — SGF-04b: stale fp4_ultra lowercase-literal assertion (:63-72)
- `test/integration/test_sgprocessing_pipeline.cpp` — correct reference assertions (:88-96) + Phase 4 FP4_ULTRA/LLM test cases (:233-255); pattern for new SGFP4 E2E tests
- `src/core/fp4/fp4_codec.hpp` / `.cpp`, `test/core/test_fp4_codec.cpp`, `src/core/CMakeLists.txt:2` — SGF-03 deletion targets (self-flagged dead code)

### SuperGenius side (GeniusNetwork checkout — `dev_childwallet`, the ONLY canonical checkout)
- `W:/gnus/GeniusNetwork/SuperGenius/SGProcessingManager/src/processors/processing_processor_mnn_tensor.cpp` — SGF-02: the unchecked `procresults->host<float>()` dereference
- `W:/gnus/GeniusNetwork/SuperGenius/test/processors/mnn_tensor_fp4_test.cpp` — SGF-04a: stale "decode unavailable" assertion
- `W:/gnus/GeniusNetwork/SuperGenius/build/Windows/Release/SuperGenius/lib/` — D-02 link path (user rebuilt fresh 2026-09-02; Debug builds also now exist)
- `W:/gnus/GeniusNetwork/.planning/workstreams/sgproc-render/` — where Phase 18 (VulkanInitMutex deadlock) status must be checked (D-01)

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `SGProcessingBridge::SubmitDirect()` (`sg_processing_bridge.cpp:308-380`) — the exact direct-call path SGF-01 exercises; already calls `ProcessingManager::Create()`/`Process()` locally, no changes needed to the bridge itself
- `test_sgprocessing_pipeline.cpp`'s Phase 4 test cases (:233-255) — established pattern for integration tests dispatching through `SubmitJob` with specific `InputFormat`s
- `HasUsableVulkanDevice()` → `GTEST_SKIP()` pattern from plan 04-04 — the exact skip-gate mechanics D-03 reuses
- `TestSGFP4Converter.cpp` (MNN, PHASE B) — loading a real SGFP4 `.mnn` via classic API + asserting decode; closest template for the new E2E test

### Established Patterns
- `outcome::result<T>` error propagation throughout both codebases
- PIMPL idiom, `m_`-prefixed members, C++17, Allman braces, `GENIUS_HAS_*` compile guards (NEO-SWARM conventions)
- Test binaries: `add_executable(test_{component})` with GTest; integration tests under `test/integration/`
- Cross-repo commit discipline: innermost-first for nested submodules, `git status --short` verification at each level

### Integration Points
- `SGProcessingBridge::SubmitJob()` → `SubmitDirect()` fallback (:293-297) — where an SGFP4 model enters the direct path today (schema JSON with model URI; the SGFP4-ness lives entirely in the `.mnn` file's op graph)
- NEO-SWARM links SuperGenius prebuilt static libs from `build/Windows/Release/SuperGenius/lib/` — rebuild-after-source-change rule (D-10) keeps these in sync
- MNN session type selection in the MNN_Tensor processor — where D-05's explicit CPU/Vulkan session pinning connects

</code_context>

<specifics>
## Specific Ideas

- "We can rebuild those if needed due to source changes. I also added debug builds." — user on SuperGenius/GeniusSDK rebuild posture (D-10): fresh rebuild is the baseline, rebuild-on-change is the rule, Debug builds exist for deadlock debugging
- The seed's framing carried through intact: "never call this 'Ultra FP4' — that name means E2M1/FP4_ULTRA in this codebase. Call it SGFP4 v2."
- User committed firmly to real GPU execution: "CPU + Vulkan both required" — accepted in-phase deadlock fixing as the cost rather than shipping permanently skip-gated Vulkan coverage

</specifics>

<deferred>
## Deferred Ideas

- Fixing the `op->externalPath` injection gap for externalized-weight SGFP4 models (MNN-side) — out of scope; handled by using small/inline test models only (D-06)
- gnus-poc `pipeline/runner.py` `--adaptive` default flip and `"fp4_ultra_v0.2"` manifest naming collision — separate, lower-priority follow-ups (seed-locked)
- arxiv §8 verifiable-execution/attestation — no anchor in the codebase family; net-new work if ever pursued
- `InputFormat::SGFP4_V2` wire format — only relevant if SGFP4-as-input ever becomes a real requirement (it isn't; SGFP4 is model-weight-side)
- Real-data accuracy/classification-correctness validation of SGFP4 decode (MNN's E2E gate is liveness-only) — MNN workstream concern, not this phase

</deferred>

---

*Phase: 13-sgfp4-v2-model-support*
*Context gathered: 2026-09-02*
