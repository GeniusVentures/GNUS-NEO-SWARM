# Phase 13: SGFP4 v2 Model Support - Research

**Researched:** 2026-09-02
**Domain:** Cross-repo MNN SGFP4 model-weight decode wiring (NEO-SWARM ↔ SuperGenius/SGProcessingManager ↔ vendored MNN)
**Confidence:** HIGH (all claims below are `[VERIFIED]` against the actual checked-out source on this machine unless tagged `[ASSUMED]`)

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

- **D-01:** Research step FIRST checks the current status of the `VulkanInitMutex` re-entrancy deadlock (sgproc-render Phase 18) before locking the verification approach. If fixed → real local E2E. If still open → see D-03 reconciliation. Decision is data-driven, documented below — never silently assumed.
- **D-02:** SGF-01's success criterion is wiring proven + conditional execution: the E2E test always runs the full path through `ProcessingManager::Create()`; output assertions execute when the environment allows; `GTEST_SKIP()` (citing the tracked bug by name) when it doesn't.
- **D-03:** Skip-gate mechanics reuse the 04-04 pattern exactly: `HasUsableVulkanDevice()` → `GTEST_SKIP()` with the tracked bug name in the skip message.
- **D-04:** CPU + Vulkan execution are both hard success criteria. If the deadlock is still open, fixing it (or pulling the fix) becomes prerequisite work within this phase. CPU ships first; Vulkan is skip-gated ONLY until the fix lands.
- **D-05:** Two explicit session tests: one with explicit CPU session type, one with explicit Vulkan session type — proving SGFP4 runs through both direct paths.
- **D-06:** A tiny deliberately-built conv model is committed to test assets (conv-family weights >4096 elements each; total size well below `_largeModel`'s externalization threshold; inline weights only). Manual `mnnconvert --sgfp4` recipe documented.
- **D-07:** The E2E test asserts ≥1 `OpType_SGFP4Dequant` op exists in the loaded `.mnn`.
- **D-08:** Naming discipline: "SGFP4"/"SGFP4 v2" only, never "Ultra FP4"/"FP4 Ultra".
- **D-09:** One phase, cross-repo plans (SGProcessingManager → SuperGenius → GeniusNetwork root → NEO-SWARM), innermost-first commits, `git status --short` verification at each level.
- **D-10:** User rebuilt SuperGenius/GeniusSDK fresh 2026-09-02 with Debug builds alongside Release. Plans include an explicit SuperGenius rebuild step after SGF-02 (and any deadlock fix) land in source.
- **D-11:** SGF-02 ships with a negative regression test: feed a malformed/incompatible model through the MNN_Tensor processor and assert a clean error return (no crash).

### Claude's Discretion

- Exact shape of SGF-02's error propagation (error code vs. exception vs. empty-result return) — based on `StartProcessing()`'s existing error paths.
- Which small conv model architecture to use for the committed test asset.
- CMake mechanics for wiring the committed `.mnn` test asset into the test suite.
- Whether the CPU E2E test can run unconditionally (CPU path may not touch `VulkanInitMutex` at all) — **see Finding 3 below: this discretion point is resolved by a bigger finding — there currently IS no CPU codepath in `MNN_Tensor::Process()` at all.**

### Deferred Ideas (OUT OF SCOPE)

- Fixing the `op->externalPath` injection gap for externalized-weight SGFP4 models (MNN-side).
- gnus-poc `pipeline/runner.py` `--adaptive` default flip and `"fp4_ultra_v0.2"` manifest naming collision.
- arxiv §8 verifiable-execution/attestation.
- `InputFormat::SGFP4_V2` wire format.
- Real-data accuracy/classification-correctness validation of SGFP4 decode (MNN's E2E gate is liveness-only).
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| SGF-01 | Real SGFP4-quantized `.mnn` runs through `MNNInferenceEngine` → `SGProcessingBridge::SubmitDirect()` → `ProcessingManager::Create/Process` (direct call, no network) | Finding 1 (bridge wiring, unchanged), Finding 2 (deadlock CLOSED), Finding 3 (**no CPU backend exists — must be added**), Finding 4 (mnnconvert --sgfp4 recipe), Finding 5 (test model sizing) |
| SGF-02 | Null-check fix: `Process()` can return `nullptr`; `StartProcessing()` dereferences unchecked (`procresults->host<float>()`) | Finding 6 (exact site, line numbers, all 4 null-return paths inside `Process()`) |
| SGF-03 | Delete orphaned `fp4_codec.{hpp,cpp}` + `test/core/test_fp4_codec.cpp` | Finding 7 (all reference sites enumerated) |
| SGF-04 | Fix stale FP4 tests: SuperGenius `mnn_tensor_fp4_test.cpp` + NEO-SWARM `test_sg_connectivity.cpp` | Finding 8 (SGF-04a exact stale assertion), Finding 9 (SGF-04b exact stale assertion) |
</phase_requirements>

## Summary

Phase 4's `SGProcessingBridge::SubmitDirect()` already implements the exact direct-call path SGF-01 needs (`ProcessingManager::Create()` → `Process()` → read output file) and requires **no changes**. The `VulkanInitMutex` re-entrancy deadlock that gated Phase 4's E2E verification (D-01's open question) is **confirmed CLOSED**: `sgproc-render` Phase 18 fixed it via commit `528a92a` (already an ancestor of the currently-checked-out `SGProcessingManager` submodule HEAD, `e1f28d7`), verified 2026-08-20 with a passing regression `TEST_F` and a 3-test ctest gate on this exact real-Vulkan-device class of machine. This resolves D-01 outright: **real local E2E is achievable now**, not merely skip-gated wiring-proof.

However, research surfaced a bigger, more consequential finding than the deadlock: **every MNN processor in SGProcessingManager — including `MNN_Tensor::Process()`, the exact function SGF-01 exercises — hardcodes `config.type = MNN_FORWARD_VULKAN`. There is no CPU backend codepath anywhere in the processor layer.** D-05's "two explicit session tests: one CPU, one Vulkan" and D-04's "CPU ships first" cannot be satisfied by test-side changes alone — `MNN_Tensor::Process()` itself needs a new parameter (mirroring the existing `ResolveQuantScale(parameters)` convention) to make `config.type` configurable. This is now the phase's central implementation task, not a footnote.

SGF-02's null-deref site is precisely located: `MNN_Tensor::StartProcessing()` line 334-335 in `processing_processor_mnn_tensor.cpp`, calling `Process()` inside a per-window loop and immediately dereferencing the result via `procresults->host<float>()` with zero null-check, even though `Process()` itself has 4 distinct internal `return nullptr;` paths. SGF-03's dead code is confirmed self-contained (one CMake source-list line, one test-target line, zero other references). SGF-04a and SGF-04b are both confirmed stale against current source with exact contradicting line numbers.

`mnnconvert --sgfp4` is a real, present, boolean CLI flag (`tools/converter/source/common/cli.cpp:230`) that triggers an `InsertSGFP4Dequant` graph-rewrite pass over conv-family weights, mutually exclusive with `--weightQuantBits`/`--hqq`/`--fp16`. MNN's `_largeModel()` externalization threshold is a hard **2000 MB (2GB)** float-summed op-weight size — any deliberately tiny test model sits nowhere near it, so D-06's "inline weights only" constraint is easily satisfied by construction, not a close call.

**Primary recommendation:** Treat this phase as two work streams: (1) a small, source-touching backend-selection fix to `MNN_Tensor::Process()` (new discovery, not in original CONTEXT.md scope, but required to satisfy D-04/D-05 as literally stated) alongside the SGF-02 null-check fix in the same file/task; (2) the already-well-understood dead-code deletion (SGF-03) and stale-test fixes (SGF-04) which need no new investigation.

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Direct-call dispatch (`SubmitDirect`) | API/Backend (NEO-SWARM `SGProcessingBridge`) | — | In-process C++ call, no network boundary; already implemented, unchanged this phase |
| SGFP4 model-weight decode | API/Backend (vendored MNN, inside `ProcessingManager::Process()`'s MNN session) | — | Decode happens inside MNN's graph execution (`OpType_SGFP4Dequant`), not at the NEO-SWARM or SGProcessingManager layer — those layers only load bytes and read output tensors |
| Backend (CPU/Vulkan) selection | API/Backend (`SGProcessingManager::MNN_Tensor::Process()`) | — | `MNN::ScheduleConfig::type` is set once, inside `Process()`, currently hardcoded — this phase's new work item |
| Null-safety / error propagation | API/Backend (`StartProcessing()`) | — | Caller-side responsibility; `Process()` already signals failure via `nullptr`, caller must honor it |
| Test model production (`mnnconvert --sgfp4`) | Build/Tooling (MNN CLI, manual step) | — | Not invoked by any automated pipeline; a human runs it once to produce a committed fixture |

## Finding 1: `SGProcessingBridge::SubmitDirect()` — unchanged, exact path SGF-01 exercises

**File:** [src/core/sgprocessing/sg_processing_bridge.cpp](../../../../../src/core/sgprocessing/sg_processing_bridge.cpp) lines 308-380 (public API: [sg_processing_bridge.hpp](../../../../../src/core/sgprocessing/sg_processing_bridge.hpp))

```cpp
outcome::result<std::vector<uint8_t>> SGProcessingBridge::SubmitDirect(
    const std::string& jsondata,
    std::shared_ptr<boost::asio::io_context> ioc ) const
{
    auto pm_result = sgns::sgprocessing::ProcessingManager::Create( jsondata );
    if ( !pm_result ) { return outcome::failure( Error::InferenceFailed ); }
    auto pm = pm_result.value();
    auto processing = pm->GetProcessingData();
    const auto& passes = processing.get_passes();
    // ... extracts ModelNode from passes[0].get_model()->get_input_nodes()[0] ...
    sgns::ModelNode model_node = input_nodes[0];
    std::vector<std::vector<uint8_t>> chunkhashes;
    std::vector<std::string> output_locations;
    auto process_result = pm->Process( ioc, chunkhashes, model_node, output_locations );
    // ... reads output_locations[0] from disk, returns bytes ...
}
```

`[VERIFIED: read source]` This is byte-identical to the pattern Phase 4's `04-04` plan documented and is already the exact call chain SGF-01 requires: `MNNInferenceEngine` (or a test harness calling the bridge directly) → `SubmitJob()`/`SubmitDirect()` → `ProcessingManager::Create()` → `Process()`. **No changes needed to the bridge itself** — confirmed, matches CONTEXT.md's existing-code-insights claim.

`SubmitJob()` (lines ~264-297) dispatches to `SubmitDirect()` either directly (`m_networkMode=false`) or as an auto-fallback after `SubmitNetwork()` fails for non-auth reasons — both routes reach the same `SubmitDirect()` body.

## Finding 2: VulkanInitMutex deadlock is CLOSED (resolves D-01)

`[VERIFIED: git + planning artifacts]`

- Bug tracked at `GeniusNetwork/.planning/todos/pending/2026-08-10-fix-vulkan-capability-probe-deadlock-in-processingmanager-cr.md`, queued to `sgproc-render` workstream Phase 18 (BUILD-01).
- Phase 18 closed 2026-08-20. [18-VERIFICATION.md](file:///W:/gnus/GeniusNetwork/.planning/workstreams/sgproc-render/phases/18-build-stability/18-VERIFICATION.md) (status: `passed`, 4/4 must-haves) confirms the underlying fix was commit `528a92a` in the `SGProcessingManager` submodule, predating the phase itself — Phase 18 only added a persistent regression `TEST_F(VulkanConcurrentInitTest, CreateSucceedsWithRealVulkanDevicePresent)` + a fail-fast CMake `TIMEOUT=12` + an evidence trail. It explicitly did **not** modify `VulkanInitMutex()`/`CapabilityValidator::BuildSnapshot()`/`RenderProcessor::InitializeContext()`.
- **Independently re-confirmed this session**, in this exact checkout:
  ```
  cd W:\gnus\GeniusNetwork\SuperGenius\SGProcessingManager
  git log -1 --format="%H %ci %s"
  # e1f28d73dd10bb787e25ee07f46b8e3106d88ddc 2026-08-20 22:20:31 feat: wire real FP4_ULTRA decode via MNN's E2M1 dequant utility
  git merge-base --is-ancestor 528a92a HEAD
  # exit 0 → 528a92a IS an ancestor of current HEAD
  ```
- **Discrepancy vs. CONTEXT.md:** CONTEXT.md's canonical_refs states the SuperGenius branch is `dev_childwallet`. The actual current branch, confirmed via `git branch --show-current` in the `SuperGenius` outer repo this session, is **`dev_cognitive`**. This does not change the deadlock-fixed conclusion (the fix is present on this branch, verified directly above) but the plan should not assume `dev_childwallet` is the working branch — verify branch name again at plan/execute time in case it has moved further.

**Consequence for D-01/D-02/D-04:** Per D-01's own decision tree, "if fixed → real local E2E." The phase should target **real E2E execution assertions**, not a permanently-skip-gated wiring-only test. The `HasUsableVulkanDevice()` → `GTEST_SKIP()` pattern (D-03) should still exist in the new test as a **defensive gate for hosts with no Vulkan device at all** (the normal, expected use of that helper — see Finding 3's inverted-skip note from `04-04`), not as a deadlock workaround. D-04's "Vulkan skip-gated ONLY until the fix lands... cannot be permanently skip-gated" is satisfied: the fix has landed, so Vulkan execution should genuinely run and assert results on this machine.

## Finding 3: No CPU backend exists in any MNN processor — new blocker for D-04/D-05

`[VERIFIED: grep across all SGProcessingManager processors]`

Every processor's `Process()`/equivalent hardcodes the Vulkan backend, with zero conditional or parameter-driven selection:

```
processing_processor_mnn_bool.cpp:432        config.type = MNN_FORWARD_VULKAN;
processing_processor_mnn_buffer.cpp:363      config.type = MNN_FORWARD_VULKAN;
processing_processor_mnn_float.cpp:422       config.type = MNN_FORWARD_VULKAN;
processing_processor_mnn_image.cpp:186       netConfig.type      = MNN_FORWARD_VULKAN;
processing_processor_mnn_int.cpp:381         config.type = MNN_FORWARD_VULKAN;
processing_processor_mnn_mat2/3/4.cpp:444    config.type = MNN_FORWARD_VULKAN;
processing_processor_mnn_string.cpp:203      config.type = MNN_FORWARD_VULKAN;  // "Use Vulkan backend as requested"
processing_processor_mnn_tensor.cpp:478      config.type = MNN_FORWARD_VULKAN;   <-- SGF-01's exact target
processing_processor_mnn_texture1d/texturecube/vec2/3/4/volume.cpp   config.type = MNN_FORWARD_VULKAN;
```

The comment on `processing_processor_mnn_string.cpp:203` ("Use Vulkan backend as requested") suggests this was a deliberate historical choice, not an oversight — but it means **D-05's "explicit CPU session type test" cannot be satisfied by test code alone.** `MNN_Tensor::Process()` (in `processing_processor_mnn_tensor.cpp`, exact function SGF-01 exercises) needs a new backend-selection input.

**Recommended approach (Claude's discretion area, informed by existing convention):** Mirror `sgprocmanagerquant::ResolveQuantScale(parameters)`'s established pattern — resolve a schema-declared parameter (e.g. `"backend"` of type `STRING`/`INT`, values `"cpu"`/`"vulkan"`) from the generic `parameters` array passed into `StartProcessing()`, defaulting to the current behavior (`MNN_FORWARD_VULKAN`) when absent, so this is additive and non-breaking for every existing caller/test that doesn't pass the new parameter. `MNN_Tensor::Process()`'s signature (`Process(signalData, modelFile, length)`) would need to also receive the resolved backend type (or `StartProcessing()` resolves it and passes it through as a new `Process()` parameter) — a small, scoped, single-file change.

**Scope note:** This IS a change to `processing_processor_mnn_tensor.cpp` beyond the SGF-02 null-check fix — both land in the same file, ideally the same task/commit, since both touch `Process()`'s signature/behavior directly.

## Finding 4: `mnnconvert --sgfp4` — real, present, exact CLI contract

`[VERIFIED: read source]` Vendored MNN checkout: `W:\gnus\GeniusNetwork\thirdparty\MNN`

- Flag declared at `tools/converter/source/common/cli.cpp:230-232`: `"sgfp4"`, help text *"save conv-family weights as SGFP4 v2 (quadtree-adaptive FP4) via inserted SGFP4Dequant nodes"*.
- Parsed at `cli.cpp:493-494`: `if (result.count("sgfp4")) { modelPath.useSGFP4 = true; }`.
- **Hard mutex** at `cli.cpp:577-580`: `--sgfp4` cannot be combined with `--weightQuantBits`, `--hqq`, or `--fp16` — these transform the same conv weights and the combination errors out (`return false`).
- `MNNConverter.cpp:29-31`: a failed conversion exits non-zero **only** when `--sgfp4` was requested (existing flag-off exit-code behavior is preserved).
- Only **conv-family** weights are targeted (per help text and D-06's "conv-family weights >4096 elements each" framing) — the encoder (`tools/fp4/sgfp4_encode.cpp`) performs a quadtree-adaptive scale/mode search per macroblock (ported from the `gnus-poc` Python exporter), consistent with the `sgfp4-format.md` architecture doc's §22.7 "Adaptive Mode Selection."

**Recipe for D-06's test model (documented, not automated per CONTEXT.md/RUN_AND_DEPLOY.md's `llmexport.py` precedent):**
```
mnnconvert -f <SRC_FRAMEWORK> --modelFile <src_model> --MNNModel <out>.mnn --sgfp4
```
where `<src_model>` is a normally-exported small conv-only network (e.g. ONNX/TF) with at least one conv layer whose weight tensor has >4096 elements (so `OpType_SGFP4Dequant` insertion actually triggers — the quadtree encoder operates on 64x64 macroblocks per `sgfp4-format.md` §22.2, and MNN's own graph-rewrite pass presumably has its own minimum-size gate mirroring this; a >4096-element weight guarantees at least one full macroblock).

**Note:** `W:\gnus\GeniusNetwork\thirdparty\MNN` already contains leftover artifacts from a prior manual run (`sgfp4_mi_base_1788200226_9961.mnn` ~1.15MB, `sgfp4_mi_base2_1788200226_491.mnn` ~2MB, plus a broken 5-byte `sgfp4_mi_out_*.mnn`/`.weight` pair). These are **scratch/debug leftovers, not committed fixtures** — do not reuse them as the phase's test asset; they have no accompanying provenance/recipe documentation and the 5-byte output pair indicates an incomplete/failed run. Produce a fresh, deliberately-sized, documented model per D-06 instead.

## Finding 5: `_largeModel()` externalization threshold — 2000 MB (2GB), not a close call

`[VERIFIED: read source]` `tools/converter/source/common/writeFb.cpp:70-79`:
```cpp
static bool _largeModel(const MNN::NetT* netT) {
    float summer = 0.0f;
    for (auto& op : netT->oplists) {
        summer+= _computeOpExternalSizeInMB(op.get());
        if (summer > 2000.0f) {
            MNN_PRINT("Model larger than 2GB\n");
            return true;
        }
    }
    // ... repeats for subgraphs ...
}
```
Triggered only when `!config.saveExternalData && config.model != modelConfig::MNN` (`writeFb.cpp:108-112`) — i.e. only during format-conversion runs, not when writing a plain `.mnn` directly. A deliberately tiny conv model (single-digit KB to low single-digit MB) sits at least 3 orders of magnitude below this threshold — D-06's "well below `_largeModel`'s threshold" constraint is trivially satisfied, not a risk area requiring careful sizing.

## Finding 6: SGF-02's exact null-deref site

`[VERIFIED: read source]` `W:\gnus\GeniusNetwork\SuperGenius\SGProcessingManager\src\processors\processing_processor_mnn_tensor.cpp`

**The unchecked dereference** (lines 334-336, inside `MNN_Tensor::StartProcessing()`'s per-window loop):
```cpp
auto procresults = Process( patch, modelFileBytes, patchLength );
const float *data = procresults->host<float>();          // <-- crashes if procresults == nullptr
size_t dataSize = procresults->elementSize() * sizeof( float );
```
Used again at lines 340 (`GetOutputLayout( *procresults )`) and 360 (`OutputIndex1D( *procresults, ... )`) — all downstream of the same unchecked pointer.

**`Process()`'s 4 distinct `return nullptr;` paths** (lines ~464-518):
```cpp
std::unique_ptr<MNN::Tensor> MNN_Tensor::Process(...)
{
    auto interpreter = ...createFromBuffer(...);
    if ( !interpreter ) { m_logger->error(...); return nullptr; }   // (1) malformed model bytes

    MNN::ScheduleConfig config;
    config.type = MNN_FORWARD_VULKAN;   // see Finding 3
    MNN::Session *session = nullptr;
    { std::lock_guard<std::mutex> lock( sgns::sgprocessing::VulkanInitMutex() );
      session = interpreter->createSession( config ); }
    if ( !session ) { m_logger->error(...); return nullptr; }        // (2) session creation failure

    auto inputTensor = interpreter->getSessionInput( session, nullptr );
    if ( !inputTensor ) { m_logger->error(...); return nullptr; }     // (3) no input tensor
    // ... copies data in, runs session ...
    auto outputTensor = interpreter->getSessionOutput( session, nullptr );
    if ( !outputTensor ) { m_logger->error(...); return nullptr; }    // (4) no output tensor
    // ... returns real output tensor
}
```
Case (1) is the realistic trigger for SGF-02's "malformed/incompatible model" scenario (D-11's negative regression test) — a byte buffer that isn't a valid MNN flatbuffer, or a valid-but-incompatible model, will make `MNN::Interpreter::createFromBuffer` return null, and `Process()` propagates that as `nullptr` cleanly — it's the *caller* (`StartProcessing()`) that fails to check it.

**Fix shape (Claude's discretion, guided by existing convention):** `StartProcessing()` already returns `ProcessingResult{}` (a bare default-constructed struct — see the pre-existing early-return pattern at lines ~248-262 for invalid dimensions/format) for other validation failures earlier in the same function, and elsewhere in the file returns a populated `ProcessingResult{ {}, nullptr, {}, ProcessingError{ stage, message } }` (seen in the `CANCELLED` case, lines ~464-472). The most consistent fix: after `auto procresults = Process(...)`, add `if ( !procresults ) { return ProcessingResult{ {}, nullptr, {}, ProcessingError{ ProcessingErrorStage::..., "MNN_Tensor::Process returned null (malformed or incompatible model)" } }; }` before the `procresults->host<float>()` line — matching the structured-error convention `mnn_tensor_fp4_test.cpp` already exercises (`ProcessingErrorStage::FORMAT_UNSUPPORTED` for a different case). D-11's negative test feeds a byte buffer that fails `createFromBuffer` (e.g. truncated/garbage bytes) and asserts this new structured error, not a crash.

## Finding 7: SGF-03's dead-code scope — fully self-contained

`[VERIFIED: read source + CMake]` NEO-SWARM repo:

- `src/core/fp4/fp4_codec.hpp` — already carries a Phase-4-D-13 header comment flagging it as orphaned/candidate for removal (its `MNNInferenceEngine` consumer was already removed in `04-04`, per plan text referencing commit `8ee7fa4`).
- `src/core/fp4/fp4_codec.cpp` — implementation, no other file includes `fp4_codec.hpp` besides its own `.cpp` and the test.
- `src/core/CMakeLists.txt:2` — `add_library(neoswarm_core STATIC fp4/fp4_codec.cpp ...)` — single source-list entry to remove.
- `test/CMakeLists.txt:59` — `neoswarm_test(test_fp4_codec core/test_fp4_codec.cpp "neoswarm_core")` — single test-target entry to remove.
- `test/core/test_fp4_codec.cpp` — the test file itself, self-contained (only includes `fp4_codec.hpp` + gtest).

Deletion is mechanically simple: remove the 2 CMake lines + delete the 3 files. No other file in either repo references `FP4Codec`, `fp4_codec.hpp`, or `m_fp4Codec` — confirmed via the same grep pattern `04-04`'s own acceptance criteria used (`git grep -c "fp4_codec\|FP4Codec"`), and `MNNInferenceEngine` (the only prior consumer) already has zero references per `04-04-PLAN.md` Task 2's completed work.

## Finding 8 (SGF-04a): `mnn_tensor_fp4_test.cpp` — exact stale assertion

`[VERIFIED: read source]` `W:\gnus\GeniusNetwork\SuperGenius\SGProcessingManager\test\processors\mnn_tensor_fp4_test.cpp`

```cpp
TEST( MnnTensorFp4Test, Fp4UltraRecognizedButDecodeUnavailable )
{
    // ...
    ASSERT_TRUE( callResult.result.error.has_value() );
    EXPECT_EQ( callResult.result.error->stage, ProcessingErrorStage::FORMAT_UNSUPPORTED );
    EXPECT_NE( callResult.result.error->message.find( "MNN_Ultra" ), std::string::npos )
        << "message was: " << callResult.result.error->message;
    // asserts decode is UNAVAILABLE
}
```
This directly contradicts the current source in `processing_processor_mnn_tensor.cpp` (lines ~274-278):
```cpp
else if ( format == sgns::InputFormat::FP4_ULTRA )
{
    // Pass-through to MNN's own E2M1 decode (D-09) -- no dequant math duplicated here.
    const auto *src = reinterpret_cast<const uint8_t *>( tensorData.data() );
    MNN::dequant_fp4_packed_cpu( src, signalValues.data(), expectedElements );
}
```
FP4_ULTRA decode is now **live** (confirmed via `git log`: `SGProcessingManager` HEAD commit `e1f28d7` is literally titled *"feat: wire real FP4_ULTRA decode via MNN's E2M1 dequant utility"*, dated 2026-08-20 — after this test was written). The test needs rewriting to assert a **successful decode** (or at minimum no longer asserts `FORMAT_UNSUPPORTED`/"MNN_Ultra"-pending-message) for a validly-sized FP4_ULTRA buffer. Note this uses `#include "processors/processing_processor_mnn_tensor.hpp"` and calls `MNN_Tensor::StartProcessing()` directly (never via `ProcessingManager::Create()`) — it deliberately never touches `VulkanInitMutex`/needs a real Vulkan device, per its own file-header comment; that isolation property should be preserved by whatever replaces the stale assertion.

## Finding 9 (SGF-04b): `test_sg_connectivity.cpp` — exact stale assertion

`[VERIFIED: read source]` NEO-SWARM: `test/integration/test_sg_connectivity.cpp` lines 63-72:
```cpp
TEST( SGConnectivity, BuildSchemaJsonFP4UltraFormatEmitsFP4Type )
{
    SGProcessingBridge bridge;
    auto result = bridge.BuildSchemaJson( kModelUri, kInputUri, sgns::InputFormat::FP4_ULTRA, { 1, 256, 256, 3 } );
    ASSERT_TRUE( result.has_value() );
    // FP4_ULTRA maps to the dedicated "fp4_ultra" type string in the schema.
    EXPECT_NE( result.value().find( "fp4_ultra" ), std::string::npos );   // <-- WRONG, lowercase literal
}
```
This directly contradicts the correct, passing reference assertions in `test/integration/test_sgprocessing_pipeline.cpp` lines 88-96 (`BuildSchemaJson_Fp4Ultra`):
```cpp
EXPECT_NE( res.value().find( "\"type\":\"tensor\"" ), std::string::npos );
EXPECT_NE( res.value().find( "\"format\":\"FP4_ULTRA\"" ), std::string::npos );
EXPECT_EQ( res.value().find( "fp4_ultra" ), std::string::npos );   // must NEVER appear lowercase
```
`BuildSchemaJson()` emits `"type":"tensor"` + `"format":"FP4_ULTRA"` (uppercase, in a separate `format` field) — never the bare lowercase string `"fp4_ultra"`. `test_sg_connectivity.cpp`'s assertion is the exact inverse of what the correct reference test in the same repo already checks. Fix: replace the lowercase-literal search with the correct `"type":"tensor"` / `"format":"FP4_ULTRA"` pair, mirroring `test_sgprocessing_pipeline.cpp`'s pattern.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| SGFP4 model-weight quantization/injection | A new encoder | `mnnconvert --sgfp4` (already exists, `tools/fp4/sgfp4_encode.cpp`) | Explicitly out of scope per CONTEXT.md; tool is verified working through the classic API |
| SGFP4 decode-correctness verification | Custom decode-and-compare logic | MNN's own `MNN/SGFP4DequantUtils.hpp` normative decode + existing `test/op/SGFP4*Test.cpp` suite (MNN's own workstream) | This phase's E2E gate is liveness-only (D-07's "≥1 op exists" + successful run), not accuracy — accuracy validation is explicitly deferred (see Deferred Ideas) |
| Backend (CPU/Vulkan) parameter resolution | A bespoke ad hoc flag | Mirror `sgprocmanagerquant::ResolveQuantScale(parameters)`'s find-by-name-in-`parameters` convention | Established, already-tested pattern in the same file family (`include/util/quantization.hpp`) |

## Code Examples

### Classic Interpreter/Session API — closest existing template

`W:\gnus\GeniusNetwork\thirdparty\MNN\test\op\SGFP4ClassicAPITest.cpp` (NOT `TestSGFP4Converter.cpp` as CONTEXT.md's canonical_refs names it — see note below) demonstrates the exact classic-API flow `MNN_Tensor::Process()` uses, with an **explicit CPU config**:

```cpp
// Source: thirdparty/MNN/test/op/SGFP4ClassicAPITest.cpp (lines ~117-140)
std::shared_ptr<Interpreter> net(Interpreter::createFromFile(modelPath.c_str()), Interpreter::destroy);
ScheduleConfig cfg;
cfg.type = MNN_FORWARD_CPU;                     // <-- explicit CPU, proves the pattern MNN_Tensor::Process() lacks
auto session = net->createSession(cfg);
auto inputTensor = net->getSessionInput(session, nullptr);
net->resizeSession(session);
::memcpy(inputTensor->host<float>(), inputVals.data(), kMatrixDim * sizeof(float));
net->runSession(session);
auto outputTensor = net->getSessionOutput(session, nullptr);
std::shared_ptr<Tensor> outUser(new Tensor(outputTensor, Tensor::CAFFE));
outputTensor->copyToHostTensor(outUser.get());
const float* got = outUser->host<float>();
```
**Note:** This test is gated by `#ifdef MNN_SUPPORT_TRANSFORMER_FUSE` at its top — `[ASSUMED]` this build flag is enabled in the vendored MNN build NEO-SWARM/SuperGenius link against (not independently re-verified this session against the actual CMake cache) — worth a quick confirm at plan time (`ccmake`/cached-variables check on `build/Windows/Release`) since if it's off, this specific file wouldn't even compile in this checkout, though `OpType_SGFP4Dequant`/the CPU decode kernel itself is a separate, unconditional feature.

### Backend-selection fix shape (Finding 3), by analogy to the existing quant-scale pattern

```cpp
// Existing pattern (include/util/quantization.hpp), already used at
// processing_processor_mnn_tensor.cpp:194:
const float scale = sgprocmanagerquant::ResolveQuantScale( parameters );

// New, analogous resolver this phase should add (naming/shape at Claude's
// discretion, but following this exact find-by-name-in-parameters convention):
// MNNForward ResolveMnnBackend( const std::vector<sgns::Parameter> *parameters );
// -- falls back to MNN_FORWARD_VULKAN (today's exact behavior) when absent/invalid.
```

## Common Pitfalls

### Pitfall 1: Assuming CONTEXT.md's branch name is current
**What goes wrong:** Plans reference `dev_childwallet` for the SuperGenius checkout; the actual current branch is `dev_cognitive`.
**Why it happens:** CONTEXT.md was written from an earlier conversation snapshot; the branch was switched or renamed since.
**How to avoid:** Re-run `git branch --show-current` in `SuperGenius` at plan/execute time, don't hardcode the branch name from CONTEXT.md into commit instructions.

### Pitfall 2: Treating the Vulkan deadlock fix as still-open
**What goes wrong:** Building a permanently-skip-gated Vulkan test "just in case," per the seed's original (now-outdated) framing.
**Why it happens:** The seed and CONTEXT.md were written before Phase 18 closed (2026-08-20) — later than the seed's 2026-08-26 creation date, so this is genuinely new information the seed could not have had... actually the seed IS dated 2026-08-26, after the 2026-08-20 fix. **Re-verify:** the fix landed before the seed was written, meaning the seed's framing of this as an open risk was already slightly stale at seed-creation time; independently reconfirmed fresh this session regardless (see Finding 2).
**How to avoid:** Trust Finding 2's fresh, independently-run `git merge-base --is-ancestor` check over any narrative claim in older planning docs.

### Pitfall 3: Missing the hardcoded-Vulkan blocker until integration time
**What goes wrong:** Writing the CPU E2E test first (per D-04's "CPU ships first"), only to discover at execution time that `MNN_Tensor::Process()` has no way to request CPU at all — the "CPU" test would silently run on Vulkan anyway.
**Why it happens:** `config.type = MNN_FORWARD_VULKAN` is buried inside `Process()`, three call layers below the schema JSON the bridge builds; nothing in the schema currently has a "backend" field to plumb through.
**How to avoid:** Treat Finding 3 as a first-class implementation task, not a test-writing detail — plan it as its own task alongside SGF-02 (same file), before attempting SGF-01's two session tests.

### Pitfall 4: Conflating SGFP4 (weight format) with FP4_ULTRA (input format) in new test/doc text
**What goes wrong:** Calling anything in this phase "Ultra FP4"/"FP4 Ultra" (D-08's explicit naming lock).
**Why it happens:** Both formats live in the exact same processor file (`processing_processor_mnn_tensor.cpp`) and the same general "4-bit" conceptual space — easy to blend the names when writing quickly.
**How to avoid:** SGFP4 only ever appears as a graph op (`OpType_SGFP4Dequant`) discovered by walking the loaded `.mnn`'s op list (D-07) — it is never an `InputFormat` enum value, never appears in `BuildSchemaJson()`'s format field. FP4_ULTRA is the `InputFormat` enum value and schema `"format"` string. If new code ever sets `format=FP4_ULTRA` for an SGFP4 test, that's a naming-conflation bug, not a valid test.

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|---------------|--------|
| FP4_ULTRA (E2M1) decode "unavailable"/pending | Live via `MNN::dequant_fp4_packed_cpu` | SGProcessingManager commit `e1f28d7`, 2026-08-20 | `mnn_tensor_fp4_test.cpp`'s `Fp4UltraRecognizedButDecodeUnavailable` test is now factually wrong (SGF-04a) |
| `ProcessingManager::Create()` deadlocks with a real Vulkan device present | Fixed, regression-tested | `528a92a` (predates Phase 18, confirmed ancestor of current HEAD), formally verified 2026-08-20 | Real local E2E (not just wiring-proof) is now achievable for SGF-01 |

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | `MNN_SUPPORT_TRANSFORMER_FUSE` is enabled in the vendored MNN build NEO-SWARM/SuperGenius currently link against | Code Examples § Classic API | If disabled, `SGFP4ClassicAPITest.cpp`'s pattern is still valid *reference* reading but that specific file wouldn't compile as-is in this build; the underlying `OpType_SGFP4Dequant`/CPU decode kernel is a separate, unconditional MNN feature so SGF-01 itself is unaffected — only affects which existing test file can be used as a literal copy-paste template |
| A2 | A >4096-element conv weight is sufficient (not just necessary) to trigger at least one full 64x64 SGFP4 macroblock and therefore an actual `OpType_SGFP4Dequant` insertion via `mnnconvert --sgfp4`'s graph-rewrite pass | Finding 4 | If MNN's `InsertSGFP4Dequant` pass has additional undiscovered gating logic (e.g. a minimum op count, specific conv attributes), D-06's model might convert without producing the op, silently failing D-07's assertion at test time rather than at model-build time — mitigated by D-07 itself (asserts ≥1 op exists, so this would be caught, not silently passed) |

## Open Questions

1. **Exact backend-selection mechanism shape for `MNN_Tensor::Process()`**
   - What we know: the existing `ResolveQuantScale(parameters)` convention is the established pattern to mirror; `MNN::ScheduleConfig::type` accepts `MNN_FORWARD_CPU` or `MNN_FORWARD_VULKAN`.
   - What's unclear: whether the new parameter should live in the job schema's generic `parameters` array (schema-driven, consistent with quant scale) or as a new dedicated field on `IoDeclaration`/`Dimensions` (more visible, less generic).
   - Recommendation: use the `parameters` array (schema-driven) for consistency with the one existing precedent in this exact file, unless the planner finds a reason `IoDeclaration` is a better fit once looking at the full schema generator.

2. **`MNN_SUPPORT_TRANSFORMER_FUSE` status in the linked MNN build**
   - What we know: the flag gates `SGFP4ClassicAPITest.cpp`'s compilation in MNN's own test suite; unrelated to the CPU decode kernel itself.
   - What's unclear: whether it's ON in the specific prebuilt MNN static lib NEO-SWARM/SuperGenius currently link against.
   - Recommendation: quick `grep`/cached-CMake-variable check at plan/execute time; does not block phase scoping either way.

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| `mnnconvert` CLI (`--sgfp4` flag) | D-06 test model production | ✓ | Present in `thirdparty/MNN/tools/converter`, flag confirmed in source | — |
| Real Vulkan device on build/test machine | SGF-01 Vulkan session test | ✓ (confirmed by Phase 18's own verification, run on "this exact Windows machine") | — | `HasUsableVulkanDevice()` → `GTEST_SKIP()` for hosts without one (expected/valid per D-34 in sgproc-render's own docs) |
| SuperGenius/SGProcessingManager Debug + Release builds | D-10 rebuild step | ✓ | User rebuilt fresh 2026-09-02, both configs present at `build/Windows/{Release,Debug}` | — |
| `MNN_SUPPORT_TRANSFORMER_FUSE` build flag | Reusing `SGFP4ClassicAPITest.cpp` literally as a template | Unconfirmed this session (A1) | — | Read the pattern as a reference even if not directly reusable/compilable as-is |

**Missing dependencies with no fallback:** none identified.
**Missing dependencies with fallback:** Vulkan device absence (skip-gate, D-03) — but confirmed present on this machine per Phase 18's own verification evidence, so the Vulkan test should genuinely execute here, not merely be exercised via the skip path.

## Validation Architecture

### Test Framework

| Property | Value |
|----------|-------|
| Framework | GoogleTest (GTest), via `neoswarm_test(...)` CMake macro (NEO-SWARM) and `addtest(...)` (SGProcessingManager) |
| Config file | `test/CMakeLists.txt` (NEO-SWARM), `SGProcessingManager/test/**/CMakeLists.txt` (SuperGenius submodule) |
| Quick run command | `ctest --test-dir build/Windows/Release -R test_sg_connectivity --output-on-failure` (NEO-SWARM); `ctest --test-dir build/Windows/Debug -R mnn_tensor_fp4_test --output-on-failure` (SuperGenius, use Debug per D-10) |
| Full suite command | `ctest --test-dir build/Windows/Release --output-on-failure --parallel` (NEO-SWARM, per RUN_AND_DEPLOY.md's documented 5-suite gate) |

### Phase Requirements → Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| SGF-01 | SGFP4 `.mnn` runs through `SubmitDirect()` → `ProcessingManager::Create/Process`, CPU session | integration (real-model E2E) | `ctest --test-dir build/Windows/Release -R "SGProcessingPipeline.SgfP4.*Cpu"` | ❌ new test, Wave 0 |
| SGF-01 | Same, Vulkan session (skip-gated only if no device) | integration (real-model E2E) | `ctest --test-dir build/Windows/Release -R "SGProcessingPipeline.SgfP4.*Vulkan"` | ❌ new test, Wave 0 |
| SGF-01 | ≥1 `OpType_SGFP4Dequant` op present in loaded `.mnn` (D-07) | unit/assertion inside the E2E test | (same test binary as above, additional assertion) | ❌ new, same file |
| SGF-02 | Malformed model → clean error, no crash (D-11) | unit | `ctest --test-dir build/Windows/Debug -R mnn_tensor_fp4_test -x -k` (new `TEST` case in `mnn_tensor_fp4_test.cpp`) | ❌ new test case, Wave 0 |
| SGF-03 | Deletion — no crash/build regression | build-only | `cmake --build build/Windows/Release --target neoswarm_core` (must succeed with no `fp4_codec` reference) | n/a (deletion, not new test) |
| SGF-04a | `mnn_tensor_fp4_test.cpp` FP4_ULTRA decode assertion corrected | unit | `ctest --test-dir build/Windows/Debug -R MnnTensorFp4Test.Fp4UltraRecognized` | ✓ exists, needs rewrite |
| SGF-04b | `test_sg_connectivity.cpp` fp4_ultra literal corrected | unit | `ctest --test-dir build/Windows/Release -R SGConnectivity.BuildSchemaJsonFP4UltraFormatEmitsFP4Type` | ✓ exists, needs rewrite |

### Sampling Rate
- **Per task commit:** targeted `ctest -R <specific test>` in the repo the task touched.
- **Per wave merge:** full suite in both repos (`ctest --test-dir build/Windows/{Release,Debug}`), innermost submodule first per D-09.
- **Phase gate:** Full suite green (both configs) before `/gsd-verify-work`, plus manual confirmation the committed `.mnn` test asset is present and its production recipe is documented (D-06).

### Wave 0 Gaps
- [ ] New backend-selection resolver + `MNN_Tensor::Process()` signature change (Finding 3) — must land before either SGF-01 session test can meaningfully differ
- [ ] New E2E test file/cases for SGF-01 (CPU + Vulkan sessions, `OpType_SGFP4Dequant` presence assertion) — likely a new `test/integration/test_sgfp4_e2e.cpp` in NEO-SWARM, or new cases appended to `test_sgprocessing_pipeline.cpp` following its existing `Fp4UltraFormat_DispatchesToTensorProcessor` pattern
- [ ] Committed `.mnn` test asset + documented manual `mnnconvert --sgfp4` recipe (D-06) — does not exist yet anywhere in either repo
- [ ] New negative-regression `TEST` case for SGF-02 in `mnn_tensor_fp4_test.cpp` (malformed model bytes → structured error, D-11)

*(No pre-existing test infrastructure gap beyond the above — GTest/CTest wiring, fixture directory conventions, and the `neoswarm_test`/`addtest` macros are all already established and reusable.)*

## Security Domain

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V5 Input Validation | yes | `StartProcessing()`'s existing pre-flight checks (dimensions, format, buffer size) already reject malformed job schemas before reaching `Process()`; SGF-02 extends this discipline to `Process()`'s own return value |
| V6 Cryptography | no | Not touched by this phase |
| V2/V3/V4 (Auth/Session/Access) | no | Direct in-process call, no new trust boundary crossed |

### Known Threat Patterns for this stack

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| Null-pointer dereference from an untrusted/malformed model file (SGF-02's exact bug) | Denial of Service | Explicit null-check + structured `ProcessingError` return (this phase's fix) — never a raw crash on attacker-influenced or corrupted input |
| Accepting a model whose weight tensor is silently mis-decoded (no verification the SGFP4 op actually ran) | Tampering (data integrity, not security-critical here but correctness-critical) | D-07's "assert ≥1 `OpType_SGFP4Dequant` op exists" — a regression that silently drops back to all-FP32 fails loudly instead of passing vacuously |

## Sources

### Primary (HIGH confidence — read directly this session)
- `W:\gnus\GeniusNetwork\SuperGenius\SGProcessingManager\src\processors\processing_processor_mnn_tensor.cpp` — full null-deref site + hardcoded backend
- `W:\gnus\GeniusNetwork\SuperGenius\SGProcessingManager\test\processors\mnn_tensor_fp4_test.cpp` — SGF-04a stale assertion
- `w:\gnus\GeniusCognitiveSystem\GNUS-NEO-SWARM\test\integration\test_sg_connectivity.cpp` — SGF-04b stale assertion
- `w:\gnus\GeniusCognitiveSystem\GNUS-NEO-SWARM\test\integration\test_sgprocessing_pipeline.cpp` — correct reference assertions + existing FP4_ULTRA/LLM integration test pattern
- `w:\gnus\GeniusCognitiveSystem\GNUS-NEO-SWARM\src\core\sgprocessing\sg_processing_bridge.cpp` — `SubmitDirect()`/`SubmitJob()` full bodies
- `w:\gnus\GeniusCognitiveSystem\GNUS-NEO-SWARM\src\core\fp4\fp4_codec.hpp` — SGF-03 deletion target, self-flagged dead
- `W:\gnus\GeniusNetwork\.planning\workstreams\sgproc-render\phases\18-build-stability\{18-01-SUMMARY.md,18-VERIFICATION.md}` — deadlock closure evidence
- `W:\gnus\GeniusNetwork\thirdparty\MNN\tools\converter\source\common\{cli.cpp,writeFb.cpp}` — `--sgfp4` flag + `_largeModel` threshold
- `W:\gnus\GeniusNetwork\thirdparty\MNN\test\op\SGFP4ClassicAPITest.cpp` — closest existing classic-API + explicit-CPU-config template
- Fresh `git log`/`git merge-base --is-ancestor` runs in both `SuperGenius` and `SuperGenius/SGProcessingManager` this session

### Secondary (MEDIUM confidence)
- `w:\gnus\GeniusCognitiveSystem\docs\architecture\sgfp4-format.md` — format spec (macroblock/header/mode-selection design intent, cross-referenced against `sgfp4_encode.cpp`'s actual constants, consistent)

### Tertiary (LOW confidence / flagged for validation)
- A2 (macroblock-size-to-op-insertion guarantee) — inferred from spec + encoder constants, not independently traced through MNN's graph-rewrite pass source this session
- A1 (`MNN_SUPPORT_TRANSFORMER_FUSE` build flag state) — not checked against actual CMake cache this session

## Metadata

**Confidence breakdown:**
- Standard stack / existing wiring (Findings 1, 2, 4, 5): HIGH — all directly read from source/git this session
- Backend-selection gap (Finding 3): HIGH confidence the gap exists (exhaustive grep across all processors); MEDIUM confidence on the exact recommended fix shape (a reasonable, convention-following proposal, not the only possible design)
- Null-deref site (Finding 6) / dead-code scope (Finding 7) / stale tests (Findings 8, 9): HIGH — exact line numbers read directly
- Validation architecture: MEDIUM — test commands/paths inferred from existing CMake/CTest conventions in both repos, not independently executed this session

**Research date:** 2026-09-02
**Valid until:** 14 days (fast-moving cross-repo submodule state; re-check branch name and deadlock-fix ancestry if planning is delayed)
