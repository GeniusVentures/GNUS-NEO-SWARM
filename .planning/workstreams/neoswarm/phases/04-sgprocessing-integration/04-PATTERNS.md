# Phase 4: SGProcessing Integration - Pattern Map

**Mapped:** 2026-08-18
**Files analyzed:** 7 (new/edited, both repos)
**Analogs found:** 7 / 7

## File Classification

| New/Modified File | Repo | Role | Data Flow | Closest Analog | Match Quality |
|---|---|---|---|---|---|
| `SGProcessingManager/include/processors/processing_processor_mnn_fp4.hpp` (new) | SuperGenius | processor (class decl) | request-response (batch/one-shot job) | `SGProcessingManager/include/processors/processing_processor_mnn_string.hpp` | role-match (closest text-ish processor; NOT autoregressive) |
| `SGProcessingManager/src/processors/processing_processor_mnn_fp4.cpp` (new) | SuperGenius | processor (impl, autoregressive generation loop) | request-response w/ internal streaming loop | `mnn_string.cpp`'s `StartProcessing()`/`Process()` shape (structure) **+** `GNUS-NEO-SWARM/src/core/engine/mnn_inference_engine.cpp:323-345` `InferViaMnnLlm()` (actual generation logic to port) | exact for structure, exact for the ported logic |
| `SGProcessingManager/src/processingbase/ProcessingManager.cpp` (edit: `Init()` registration + `CheckProcessValidity()` FP4_ULTRA branch) | SuperGenius | service/registry (edit) | CRUD (register) + request-response (validate) | itself, `ProcessingManager.cpp:378-416` (registration block) and `:888-898` (TENSOR validation case) | exact (editing existing file, following its own established per-DataType pattern) |
| `GNUS-NEO-SWARM/src/core/CMakeLists.txt` (edit lines ~63-145) | NEO-SWARM | config (build) | N/A (build config) | itself — existing `_SGPROC_*` block | exact (surgical edit to existing block) |
| `GNUS-NEO-SWARM/src/core/sgprocessing/sg_processing_bridge.cpp` (edit: `SubmitDirect()`, `InputFormatToTypeString()`) | NEO-SWARM | service (bridge/adapter) | request-response | itself — existing `SubmitDirect()`/`InputFormatToTypeString()` | exact (editing existing file) |
| `GNUS-NEO-SWARM/src/core/engine/mnn_inference_engine.cpp` (edit: delete `InferViaStandardInterpreter`/`RunForward`/`SampleToken`/`ApplyRepetitionPenalty`; flag `fp4_codec.hpp` for removal) | NEO-SWARM | service/engine (edit) | request-response | itself | exact |
| `GNUS-NEO-SWARM/test/integration/test_sgprocessing_pipeline.cpp` (edit: add FP4_ULTRA/LLM cases) | NEO-SWARM | test | request-response | itself — existing FLOAT32 test cases in the same file | exact |
| `GNUS-NEO-SWARM/test/CMakeLists.txt` (edit: `SUPERGENIUS_TEST_DATA_DIR` default) | NEO-SWARM | config (test build) | N/A | itself, lines ~37-39 | exact |

## Pattern Assignments

### `SGProcessingManager/include/processors/processing_processor_mnn_fp4.hpp` + `.cpp` (new)

**Analogs:**
- Interface contract: `SGProcessingManager/include/processors/processing_processor.hpp` (base class — MUST implement this exact signature, not any older 4/5-arg form)
- Structural shape (imports, Vulkan lock, hashing/quantization plumbing, error result construction): `SGProcessingManager/src/processors/processing_processor_mnn_string.cpp`
- Actual generation-loop logic to port (NOT `InferViaStandardInterpreter`): `GNUS-NEO-SWARM/src/core/engine/mnn_inference_engine.cpp:323-345` (`InferViaMnnLlm`)

**Base interface — every processor MUST implement this 6-arg signature** (`processing_processor.hpp:81-86`):
```cpp
virtual ProcessingResult StartProcessing( std::vector<std::vector<uint8_t>> &chunkhashes,
                       const sgns::IoDeclaration         &proc,
                       std::vector<char>                 &imageData,
                       std::vector<char>                 &modelFile,
                       const std::vector<sgns::Parameter> *parameters,
                       const ExecutionContext            &execCtx ) = 0;
```
`ProcessingResult` (`processing_processor.hpp:52-65`) carries `hash`, `output_buffers`, `output_locations`, and `std::optional<ProcessingError> error` (structured stage + message, `processing_processor.hpp:25-50`) — populate `.error` on failure paths instead of returning an empty/default result silently.

**Teardown pattern** (`processing_processor.hpp:98-133`) — protected `PushTeardown(std::function<void()>)` registers cleanup (e.g. MNN session/interpreter/LLM object destruction) onto a LIFO stack invoked via `RunTeardown()` on cancellation/exception. The new autoregressive processor MUST register its MNN session/LLM object teardown here (existing MNN processors don't yet do this consistently — `mnn_string.cpp` doesn't call `PushTeardown` at all since it has no long-lived session across calls; the new processor's LLM object DOES need this since generation is a longer-lived op that can be cancelled mid-loop per `ExecutionContext`).

**Class declaration pattern** (`processing_processor_mnn_string.hpp:20-55`):
```cpp
class MNN_String : public ProcessingProcessor
{
public:
    MNN_String() {}
    ~MNN_String() override {};
    ProcessingResult StartProcessing( std::vector<std::vector<uint8_t>> &chunkhashes,
                       const sgns::IoDeclaration         &proc,
                       std::vector<char>                 &textData,
                       std::vector<char>                 &modelFile,
                       const std::vector<sgns::Parameter> *parameters,
                       const ExecutionContext            &execCtx ) override;
private:
    std::unique_ptr<MNN::Tensor> Process( const std::vector<int32_t> &tokenIds,
                       std::vector<uint8_t> &modelFile, const int maxLength );
};
```
Follow this shape for the new class (e.g. `MNN_LlmFp4` or similar per D-07's discretion) — public ctor/dtor, single override, private helper(s) doing the actual MNN work.

**Imports pattern** (`processing_processor_mnn_string.cpp:1-11`):
```cpp
#include "processors/processing_processor_mnn_string.hpp"
#include "processingbase/vulkan_init_guard.hpp"
#include <functional>
#include <mutex>
#include <thread>
#include <sstream>
#include <algorithm>
#include <cstring>
#include <openssl/sha.h> // For SHA256_DIGEST_LENGTH
#include "util/sha256.hpp"
#include "util/quantization.hpp"
```
(The new file's header will instead need `<MNN/llm/llm.hpp>` or equivalent for `MNN::Transformer::Llm`, matching what `mnn_inference_engine.hpp` already includes for `InferViaMnnLlm`.)

**Vulkan lock pattern — MANDATORY, do not skip** (`processing_processor_mnn_string.cpp:206-210`):
```cpp
MNN::Session *session = nullptr;
{
    std::lock_guard<std::mutex> lock( sgns::sgprocessing::VulkanInitMutex() );
    session = interpreter->createSession(config);
}
```
Every existing MNN processor takes `VulkanInitMutex()` around session/interpreter creation. The new processor's `MNN::Transformer::Llm::createLLM()`/`load()` call (which internally creates a session) should be wrapped the same way to preserve the Vulkan coexistence contract with `RenderProcessor` (per Don't-Hand-Roll guidance in RESEARCH.md). NOTE: `ProcessingManager::Create()`'s own capability-probe path independently takes this same mutex and has a known re-entrancy deadlock bug (sgproc-render Phase 18, out of scope) — do not attempt to "fix" this from inside the new processor; just follow the same locking convention every other processor uses.

**Ported generation-loop logic — reference implementation, NOT the hand-rolled one** (`GNUS-NEO-SWARM/src/core/engine/mnn_inference_engine.cpp:323-345`):
```cpp
outcome::result<InferenceResponse> MNNInferenceEngine::InferViaMnnLlm( const Task& task )
{
    auto t0 = std::chrono::steady_clock::now();
    std::ostringstream oss;
    mnn_llm_->response( task.m_prompt, &oss, nullptr, static_cast<int>( task.m_maxTokens ) );
    auto t1 = std::chrono::steady_clock::now();
    double latency_ms = std::chrono::duration<double, std::milli>( t1 - t0 ).count();
    const auto* ctx = mnn_llm_->getContext();
    int gen_tokens = ctx ? static_cast<int>( ctx->output_tokens.size() ) : 0;
    InferenceResponse resp;
    resp.m_output = oss.str();
    resp.m_success = true;
    return outcome::success( std::move( resp ) );
}
```
Port this call pattern (`MNN::Transformer::Llm::createLLM()`/`load()`/`response()`) into the new processor's `StartProcessing()`/private helper — MNN's own API already handles tokenization, KV-cache, sampling, and stopping criteria. Do NOT port `InferViaStandardInterpreter`'s hand-rolled `RunForward`/`SampleToken`/`ApplyRepetitionPenalty` loop (that is exactly the duplicate logic D-06 wants deleted, not moved).

**Error-result pattern on failure** (`processing_processor_mnn_string.cpp:120-127`):
```cpp
if ( !procresults || procresults->elementSize() == 0 )
{
    m_logger->error( "MNN string processing produced no output (see prior errors)" );
    ProcessingResult errResult;
    errResult.error = ProcessingError{ ProcessingErrorStage::UNSPECIFIED,
                                        "MNN string processing produced no output" };
    return errResult;
}
```
Use `ProcessingErrorStage` values appropriately (e.g. `RESOURCE_RESOLUTION` for model-load failure, `CANCELLED`/`TIMED_OUT`/`BUDGET_EXCEEDED` when `execCtx` signals them) rather than always `UNSPECIFIED`.

**Success-result construction pattern** (`processing_processor_mnn_string.cpp:157-182`): compute SHA256 chunk hash via `sgprocmanagersha::sha256(...)`, push to `chunkhashes`, combine into `subTaskResultHash`, populate `ProcessingResult::hash` and `.output_buffers` (a `shared_ptr<pair<vector<string>, vector<vector<char>>>>` — first = labels, second = raw byte buffers). The new processor should populate `output_buffers` with the generated text bytes (or FP4_ULTRA-decoded tensor bytes for PROC-02), following this exact container shape so downstream artifact/manifest code (Phase 08 additions) can consume it uniformly.

**Quantization capture pattern** (`processing_processor_mnn_string.cpp:145-155`, only relevant if PROC-01/02's output also needs float quantization+capture):
```cpp
sgprocmanagerquant::QuantizeFloatBuffer( localCopy.data(), localCopy.size(), scale );
if ( execCtx.rawOutputCapture )
{
    ...
    execCtx.rawOutputCapture( std::vector<uint8_t>( quantizedBytes, quantizedBytes + dataSize ),
                               std::vector<uint8_t>( preQuantizeBytes, preQuantizeBytes + dataSize ) );
}
```
Only apply this if the new processor's output is a float tensor subject to the same quantize-then-capture-then-hash convention (Phase 10 CAPT-02) — for pure text-token output this may not apply; for FP4_ULTRA's dequantized tensor output it likely does.

---

### `SGProcessingManager/src/processingbase/ProcessingManager.cpp` (edit)

**Analog:** itself — follow the file's own established conventions exactly.

**Registration pattern to extend** (`ProcessingManager.cpp:378-416`, inside `Init()`):
```cpp
RegisterProcessorFactory( static_cast<int>( DataType::STRING ),
                          [] { return std::make_unique<sgprocessing::MNN_String>(); } );
...
RegisterProcessorFactory( static_cast<int>( DataType::TENSOR ),
                          [] { return std::make_unique<sgprocessing::MNN_Tensor>(); } );
```
If the new LLM/FP4 processor is dispatched via `DataType::STRING` or `DataType::TENSOR` (per D-07/D-10, left to plan time), add or replace the corresponding `RegisterProcessorFactory` lambda following this exact one-line-per-DataType style. If a new `DataType` value is genuinely required (D-10 undecided), note that `generated/DataType.hpp` is a **generated** file — check whether it's hand-edited or code-genned before touching it.

**TENSOR validation branch to (maybe) uncomment** (`ProcessingManager.cpp:888-898`, confirmed live at line 894 on `dev_childwallet`, NOT ~393 as a stale scout claimed):
```cpp
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
Recommended minimal fix (per RESEARCH.md's Code Examples section): uncomment the `FP4_ULTRA` clause in-place — this is the smallest surgical diff consistent with D-10 if FP4_ULTRA stays TENSOR-typed (aligns with the `InputFormatToTypeString` bugfix below, which should map FP4_ULTRA → `"tensor"` not `"fp4_ultra"`).

**Buffer-size validation pattern to mirror for FP4_ULTRA's dimension checks** (per RESEARCH.md Security Domain, `TEXTURE2_D` case at `ProcessingManager.cpp:956-964`): validate declared dimensions (block_len/chunk_stride equivalents) against the actual buffer byte length before dispatch — do not trust schema-declared size alone. Read the exact `TEXTURE2_D` case at plan/implementation time for the precise divisibility-check idiom to replicate for FP4_ULTRA's macroblock/scale fields.

---

### `GNUS-NEO-SWARM/src/core/sgprocessing/sg_processing_bridge.cpp` (edit)

**Analog:** itself.

**Fix 1 — `SubmitDirect()`'s `ProcessOutput`→`vector<uint8_t>` conversion** (current code, lines ~292-344):
```cpp
auto process_result = pm->Process( ioc, chunkhashes, model_node, output_locations );
if ( !process_result )
{
    BridgeLogger()->error( "ProcessingManager::Process failed (error={})", process_result.error().message() );
    return outcome::failure( Error::InferenceFailed );
}
BridgeLogger()->debug( "Process() succeeded: {} bytes, {} chunk hashes", process_result.value().size(),
                       chunkhashes.size() );
return outcome::success( process_result.value() );   // BROKEN: process_result.value() is now ProcessOutput
```
Minimal surgical fix (per RESEARCH.md Pitfall 1 / Code Examples):
```cpp
return outcome::success( std::vector<uint8_t>( process_result.value().begin(),
                                                process_result.value().end() ) );
```
`ProcessOutput` offers `size()`/`empty()`/`begin()`/`end()` delegating to its internal `combinedHash` member (`ProcessingManager.hpp:46-60`) but no implicit conversion operator — must construct the vector explicitly. Also note: there is dead/unreachable stub code after the `return` at the bottom of the current function (lines 340-344, `(void) jsondata; ... return outcome::success(...)` stub-mode fallback) — this is unreachable after the real `return` above it; flag for cleanup if touching this function anyway (not required by any decision, but worth a one-line note in the plan).

**Fix 2 — `InputFormatToTypeString(FP4_ULTRA)` bug** (current code, `sg_processing_bridge.cpp:39-62`):
```cpp
std::string InputFormatToTypeString( sgns::InputFormat fmt )
{
    switch ( fmt )
    {
        case sgns::InputFormat::FLOAT32: return "float";
        ...
        case sgns::InputFormat::FP4_ULTRA:
            return "fp4_ultra"; // BUG: not a valid DataType string — from_json only recognizes "tensor" etc.
        default:
            return "tensor";
    }
}
```
Fix: change the `FP4_ULTRA` case to `return "tensor";` (matching the `default` case's existing correct behavior for other numeric/tensor-ish formats), since `InputFormat` (wire encoding) must not be conflated with `DataType` (processor selector) — `InputFormatToFormatString()` right below it (lines 68-91) already correctly returns `"FP4_ULTRA"` for the separate `"format"` field and needs NO change.

---

### `GNUS-NEO-SWARM/src/core/engine/mnn_inference_engine.cpp` (edit)

**Analog:** itself — `InferViaMnnLlm` (KEEP, reference/port source — see processor pattern above) vs `InferViaStandardInterpreter` (DELETE, per D-06).

`InferViaStandardInterpreter` begins at line 350 (confirmed) and calls `RunForward`/`SampleToken`/`ApplyRepetitionPenalty` — this hand-rolled ~150-line sampling loop is the literal duplicate-invocation logic D-06 targets for removal, once local calls are rewired to `ProcessingManager::Init()`/`Process()` directly. `InferViaMnnLlm` (lines 323-345, shown above) is explicitly NOT duplicate logic — it already correctly delegates to `MNN::Transformer::Llm`'s native API — its fate (kept as a NEO-SWARM-side fallback vs. also removed once the new SGProcessingManager processor exists) is left to plan time per RESEARCH.md's Recommended Project Structure notes.

Also flag (do not necessarily delete in this same edit unless plan scopes it): `src/core/fp4/fp4_codec.hpp`/`.cpp` — confirmed orphaned/dead code (`(void) m_fp4Codec;` at `mnn_inference_engine.cpp:82`), predates and does not match MNN_Ultra's E2M1 target format (D-13). Flag for removal or explicit re-justification per D-13, don't build PROC-02 around it.

---

### `GNUS-NEO-SWARM/src/core/CMakeLists.txt` (edit lines ~63-145)

**Analog:** itself — existing self-contained SGProcessingManager block.

Current (broken path resolution, current code lines 63-145):
```cmake
set(_SGPROC_INCLUDE "${PROJECT_ROOT}/../SuperGenius/SGProcessingManager/include")
set(_SGPROC_GEN_INCLUDE "${PROJECT_ROOT}/../SuperGenius/SGProcessingManager/generated")
set(_SGPROC_LIB_DIR "${THIRDPARTY_BUILD_DIR}/SGProcessingManager/lib")

find_library(_SGPROC_PROCESSING_BASE ProcessingBase PATHS "${_SGPROC_LIB_DIR}" NO_DEFAULT_PATH)
find_library(_SGPROC_PROCESSORS SGProcessors PATHS "${_SGPROC_LIB_DIR}" NO_DEFAULT_PATH)
find_library(_SGPROC_DATASPLITTER DataSplitter PATHS "${_SGPROC_LIB_DIR}" NO_DEFAULT_PATH)
find_library(_SGPROC_LOGGER sgprocmanagerlogger PATHS "${_SGPROC_LIB_DIR}" NO_DEFAULT_PATH)
find_library(_SGPROC_TYPES sgprocmanagertypes PATHS "${_SGPROC_LIB_DIR}" NO_DEFAULT_PATH)
find_library(_SGPROC_SHA sgprocmanagersha PATHS "${_SGPROC_LIB_DIR}" NO_DEFAULT_PATH)

if(_SGPROC_PROCESSING_BASE AND EXISTS "${_SGPROC_INCLUDE}" AND EXISTS "${_SGPROC_GEN_INCLUDE}")
    target_include_directories(neoswarm_core PUBLIC "${_SGPROC_INCLUDE}" "${_SGPROC_GEN_INCLUDE}")
    target_link_libraries(neoswarm_core PUBLIC
        "${_SGPROC_PROCESSING_BASE}" "${_SGPROC_PROCESSORS}" "${_SGPROC_DATASPLITTER}"
        "${_SGPROC_LOGGER}" "${_SGPROC_TYPES}" "${_SGPROC_SHA}"
    )
    ...
    if(APPLE)
        target_link_options(neoswarm_core PUBLIC "LINKER:-ld_classic")
    endif()
else()
    # Headers only — stub mode
    ...
endif()
```
Required changes (per D-02/Q-03, RESEARCH.md Pitfall 5 + Q-03):
1. Replace `${PROJECT_ROOT}/../SuperGenius/...` (unreachable sibling-of-a-different-ancestor path) with an explicit overridable cache variable, e.g.:
   ```cmake
   set(GENIUSNETWORK_SUPERGENIUS_DIR "W:/gnus/GeniusNetwork/SuperGenius" CACHE PATH "Path to GeniusNetwork's SuperGenius checkout")
   set(_SGPROC_INCLUDE "${GENIUSNETWORK_SUPERGENIUS_DIR}/SGProcessingManager/include")
   set(_SGPROC_GEN_INCLUDE "${GENIUSNETWORK_SUPERGENIUS_DIR}/SGProcessingManager/generated")
   set(_SGPROC_LIB_DIR "${GENIUSNETWORK_SUPERGENIUS_DIR}/build/<Platform>/<BuildType>/SuperGenius/lib/SGProcessingManager")
   ```
   with an `EXISTS` guard, following the same `find_library(... PATHS ... NO_DEFAULT_PATH)` idiom already used for every existing lib.
2. Add `find_library()` calls (same idiom) for the 6 newly-required libraries confirmed present in the build output: `SGArtifacts`, `SGCapability`, `SGShaderCompiler`, `sgproccapture`, `sgprocmanagerdiff`, `sgprocmanagerquant` — `SGCapability`/`SGArtifacts`/`sgprocmanagerquant` are structurally required (transitively used by `ProcessingManager` and by MNN processors' `sgprocmanagerquant::QuantizeFloatBuffer` calls); `SGShaderCompiler`/`sgproccapture` may be skippable if the new processor never touches render/capture paths (verify at implementation time via unresolved-symbol errors).
3. Preserve the existing `if(APPLE) target_link_options(... "LINKER:-ld_classic") endif()` block as-is initially; re-verify empirically per D-12 rather than removing preemptively.
4. Preserve the existing `else()` stub-mode fallback structure and log messages — do not remove the graceful-degradation path, just repoint what it's checking for existence of.

**Do NOT** attempt to fix the generic `get_third_party_dir()` walk-up in `build/cmake/functions.cmake` — RESEARCH.md explicitly recommends against this as an architectural change violating CLAUDE.md's minimal-diff principle; keep the fix local to this file's self-contained block.

---

### `GNUS-NEO-SWARM/test/CMakeLists.txt` (edit, `SUPERGENIUS_TEST_DATA_DIR`)

**Analog:** itself, lines ~37-39 — same nonexistent-sibling-path bug as the CMakeLists above. Apply the same `GENIUSNETWORK_SUPERGENIUS_DIR`-relative fix: point `SUPERGENIUS_TEST_DATA_DIR`'s default at `${GENIUSNETWORK_SUPERGENIUS_DIR}/test/src` (confirmed real fixture path: `GeniusNetwork/SuperGenius/test/src/processing_datatypes/`, contains `audio-processing-definition.json`, `bert-tiny.mnn`, etc.).

---

### `GNUS-NEO-SWARM/test/integration/test_sgprocessing_pipeline.cpp` (edit)

**Analog:** itself — existing FLOAT32 schema-generation test cases in the same file (read the file directly at plan/implementation time to extract the exact GTest fixture/assertion idiom used for the FLOAT32 case, then mirror it for FP4_ULTRA and for the new LLM processor path). Not independently re-read in this pattern-mapping pass since RESEARCH.md already confirms its current scope (FLOAT32-only, `SGProcessingBridge` schema-generation focus) and no additional excerpt was needed beyond what's already documented there — read this file directly during PROC-02/PROC-01 test-writing to avoid drift.

## Shared Patterns

### `outcome::result<T>` error propagation
**Source:** Used throughout both `ProcessingManager.cpp`/`sg_processing_bridge.cpp`/`mnn_inference_engine.cpp`.
**Apply to:** All new/edited functions in both repos. Never silently discard an `outcome::result` — always check `.has_value()`/`!result` and propagate `outcome::failure(...)` or `outcome::success(...)` explicitly, per CLAUDE.md's "no silent `(void)` discards" constraint. Existing exception: `mnn_inference_engine.cpp:82`'s `(void) m_fp4Codec;` is pre-existing scope — only touch if this phase's work actually removes/uses `m_fp4Codec` (D-13 flags it for removal).

### `VulkanInitMutex()` locking convention
**Source:** `SGProcessingManager/src/processors/processing_processor_mnn_string.cpp:206-210`, and `ProcessingManager::Create()`'s own capability-probe path (`ProcessingManager.cpp:429-440`, per RESEARCH.md Pitfall 4).
**Apply to:** Any new MNN processor code that creates an MNN session/interpreter/LLM object — always take this lock around session creation. Known caveat: `ProcessingManager::Create()` has an open, out-of-scope re-entrancy deadlock bug in this exact mutex (sgproc-render Phase 18) that will block local end-to-end verification on this Windows machine (real Vulkan device present) — document as a known verification blocker in the plan, do not attempt to fix.

### `m_`-prefixed members, PascalCase classes, `Get`/`Set`/`Is` accessors
**Source:** Established throughout `ProcessingManager.hpp`/`.cpp` and all `MNN_*` processor classes.
**Apply to:** All new SuperGenius-side code (processor class, any new struct fields). NEO-SWARM side uses the same `m_` prefix convention already (`m_prompt`, `m_maxTokens`, etc. in `Task`/`InferenceResponse`).

### `ProcessingErrorStage`/`ProcessingError` structured failure reporting
**Source:** `SGProcessingManager/include/processors/processing_processor.hpp:25-65`, used in `processing_processor_mnn_string.cpp:123-126`.
**Apply to:** New processor's failure paths — set `ProcessingResult::error` with an appropriate `ProcessingErrorStage` (not always `UNSPECIFIED`) rather than returning a bare default-constructed `ProcessingResult`.

### `PushTeardown()` / `RunTeardown()` LIFO cleanup
**Source:** `processing_processor.hpp:98-133`.
**Apply to:** New processor's MNN session/LLM-object lifecycle — register cleanup via `PushTeardown()` so cancellation mid-generation-loop tears down cleanly (existing `MNN_String` doesn't need this since it's a single synchronous call with no cancellable long-running loop; the new autoregressive processor's multi-token loop is exactly the case this mechanism exists for).

### CMake `find_library(... PATHS ... NO_DEFAULT_PATH)` + `if(TARGET/EXISTS...) ... else() stub ... endif()` unconditional-dependency pattern
**Source:** `src/core/CMakeLists.txt:71-145` (existing SGProcessingManager block), and per CLAUDE.md forbidding new `#ifdef` feature gates.
**Apply to:** All CMake edits in this phase — preserve the existing configure-time link-or-stub pattern; do not introduce compile-time `#ifdef`s.

## No Analog Found

None — every file in this phase's scope is either an edit to an existing file (best possible analog: itself) or a new processor file with strong analogs (`processing_processor.hpp` for the interface, `processing_processor_mnn_string.cpp` for structure, `mnn_inference_engine.cpp`'s `InferViaMnnLlm` for the actual generation logic to port).

## Metadata

**Analog search scope:** `W:\gnus\GeniusNetwork\SuperGenius\SGProcessingManager\{include,src}\processors\`, `SGProcessingManager\include\processingbase\`, `SGProcessingManager\src\processingbase\ProcessingManager.cpp`; `W:\gnus\GeniusCognitiveSystem\GNUS-NEO-SWARM\src\core\{engine,sgprocessing}\`, `src\core\CMakeLists.txt`, `test\CMakeLists.txt`
**Files scanned:** 9 read directly (both repos) + RESEARCH.md's already-verified excerpts for `ProcessOutput`, `DataType.hpp`/`InputFormat.hpp`/`Generators.hpp`, `MNN_ML` status
**Pattern extraction date:** 2026-08-18
