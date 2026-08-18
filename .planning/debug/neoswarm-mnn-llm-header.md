---
status: investigating
trigger: "GNUS-NEO-SWARM fails to compile when built via the GeniusCognitiveSystem outer CMake project: mnn_inference_engine.cpp(22,10): error C1083: Cannot open include file: 'MNN/llm/llm.hpp': No such file or directory"
created: 2026-08-18
updated: 2026-08-18
---

## Symptoms

**Expected behavior:** `cmake --build build/Windows/Release --target neoswarm_core --config Release` (run from `W:\gnus\GeniusCognitiveSystem`) compiles `neoswarm_core` cleanly, now that CMake configure succeeds end-to-end (fixed earlier this session — see Context below).

**Actual behavior:** Compilation fails on the very first NEO-SWARM source file it touches:
```
W:\gnus\GeniusCognitiveSystem\GNUS-NEO-SWARM\src\core\engine\mnn_inference_engine.cpp(22,10): error C1083: Cannot open include file: 'MNN/llm/llm.hpp': No such file or directory
```

**Error messages:** Exact compiler output above. No other errors seen yet — build stops at this first compile unit.

**Timeline:** First real compile attempt against this outer build ever (GNUS-NEO-SWARM's own CMake configure had been broken by a separate, unrelated `get_third_party_dir()` thirdparty-path-resolution issue for the entire session until just now; that issue was fixed this session, which is what got us far enough to hit this new compile error for the first time).

**Reproduction:**
```
cd W:\gnus\GeniusCognitiveSystem
cmake --build build/Windows/Release --target neoswarm_core --config Release
```

## Context (carried over from originating session — treat as high-confidence prior findings, not fresh hypotheses to re-derive from scratch)

This session (a `/gsd-execute-phase 4 --ws neoswarm` run, now well past phase execution into ad-hoc CMake infra fixes) already:

1. Fixed GeniusCognitiveSystem's CMake configure by pointing `THIRDPARTY_DIR` at `W:\gnus\GeniusNetwork\thirdparty` and porting ~25 missing `find_package()` blocks (Vulkan, SuperGenius, GeniusSDK, MNN, Snappy, RocksDB, libp2p, ipfs-*, wallet-core, zkLLVM/crypto3, etc.) from `GeniusNetwork/GeniusSDK/cmake/CommonBuildParameters.cmake` into `GeniusCognitiveSystem/cmake/CommonBuildParameters.cmake`. Configure now succeeds.
2. During this same session's execution of neoswarm workstream **Phase 4, plan 04-03** (`.planning/workstreams/neoswarm/phases/04-sgprocessing-integration/04-03-SUMMARY.md`), the executor independently discovered and confirmed: the vendored MNN thirdparty build actually linked in this environment (`W:\gnus\GeniusNetwork\thirdparty\build\Windows\Release\MNN`) was built with `MNN_BUILD_LLM=OFF` — no `MNN/llm/` subdirectory exists under its installed `include/`, confirmed by direct `ls`. The *source* for MNN's LLM transformer engine does exist, at `W:\gnus\GeniusNetwork\thirdparty\MNN\transformers\llm\engine\include\llm\llm.hpp` — it's just never compiled into the actually-linked build output.
3. To work around this, plan 04-03 added a narrow, self-contained compile-time guard `SGPROC_HAS_MNN_LLM` in `W:\gnus\GeniusNetwork\SuperGenius\SGProcessingManager\src\processors\CMakeLists.txt` (auto-detects whether the linked MNN has LLM support) with exactly 2 `#ifdef SGPROC_HAS_MNN_LLM` sites (`ProcessingManager.hpp` include, `ProcessingManager.cpp` registration line) — when false, the `MNN_Llm` processor source file and its test target are simply excluded from the build rather than failing to compile.
4. **NEO-SWARM's own `mnn_inference_engine.hpp`/`.cpp` has no equivalent guard.** It unconditionally does `#include <MNN/llm/llm.hpp>` (line 22 of the .cpp, per this error) for `MNN::Transformer::Llm`, used by `MNNInferenceEngine::InferViaMnnLlm()`. This function was explicitly preserved *unchanged* by plan 04-04 (decision D-06 — `InferViaMnnLlm` and `InferViaSGProcessing` are the two supported inference paths, kept as-is) — plan 04-04 only deleted the *other*, hand-rolled `InferViaStandardInterpreter` path. Nobody had actually verified `InferViaMnnLlm`'s own `#include` resolves in this environment before now, because GNUS-NEO-SWARM's build was blocked by issue #1 for this entire session until moments ago.

**This is the same underlying environment fact (`MNN_BUILD_LLM=OFF` in the linked vendored MNN) surfacing a second time, in a second, unguarded call site.**

## Current Focus

hypothesis: NEO-SWARM's `mnn_inference_engine.hpp`/`.cpp` needs the same category of fix SGProcessingManager already applied (04-03) — either (a) a compile-time guard mirroring `SGPROC_HAS_MNN_LLM` around the `#include <MNN/llm/llm.hpp>` and everything that depends on `MNN::Transformer::Llm` (the `mnn_llm_` member, `InferViaMnnLlm()`, the LLM-directory-detection branch of `LoadModel()`), so `neoswarm_core` compiles cleanly against an MNN build without LLM support and the capability activates automatically once a build with `MNN_BUILD_LLM=ON` is available; or (b) obtaining/building a vendored MNN with `MNN_BUILD_LLM=ON` so the header genuinely exists (bigger, shared-infra change — the same MNN build is also linked by SGProcessingManager and by the concurrent `sgproc-render` workstream, so rebuilding it is not a purely-local decision).

test: Not yet started — this session is handing off before investigating further, per user request to continue in a fresh chat.

expecting: TBD by continuation session — first steps should probably be (1) read `mnn_inference_engine.hpp`/`.cpp` in full to scope exactly what's guarded-vs-unguarded and what a mirrored `SGPROC_HAS_MNN_LLM`-style guard would need to wrap (likely more surface area than SGProcessingManager's fix, since `mnn_llm_` looks like a class member used in multiple methods, not a single processor's isolated code path); (2) decide guard vs. MNN rebuild with the user, since option (b) has cross-workstream blast radius; (3) if guard chosen, mirror `SGProcessingManager/src/processors/CMakeLists.txt`'s exact detection idiom for consistency.

next_action: Read GNUS-NEO-SWARM/src/core/engine/mnn_inference_engine.hpp and .cpp in full to scope every reference to MNN::Transformer::Llm / mnn_llm_ / <MNN/llm/llm.hpp>, then decide fix approach (compile guard vs. MNN rebuild) — likely worth a quick check-in with the user on which direction, since (b) affects shared thirdparty infra used by SGProcessingManager and the sgproc-render workstream too.

## Evidence

- timestamp: 2026-08-18T22:58:00Z
  finding: "Reproduced independently: `cmake --build build/Windows/Release --target neoswarm_core --config Release` from `W:\\gnus\\GeniusCognitiveSystem` fails with `error C1083: Cannot open include file: 'MNN/llm/llm.hpp': No such file or directory` at `mnn_inference_engine.cpp(22,10)`. Prior to this, `neoswarm_common` target built successfully (so the failure is specific to this file/include, not a broader configure/link problem)."
- timestamp: 2026-08-18T22:58:00Z
  finding: "Confirmed via `ls`: `W:\\gnus\\GeniusNetwork\\thirdparty\\build\\Windows\\Release\\MNN\\include\\MNN\\` has no `llm/` subdirectory. `W:\\gnus\\GeniusNetwork\\thirdparty\\MNN\\transformers\\llm\\engine\\include\\llm\\llm.hpp` (source, not installed/built) does exist — same finding plan 04-03's executor already made independently for SGProcessingManager's own MNN_Llm processor."

## Eliminated

(none yet)

## Resolution

root_cause: (pending — strongly suspected to be `MNN_BUILD_LLM=OFF` in the linked vendored MNN, per Context above, but not yet formally confirmed as the *sole* cause for this specific call site by a continuation session)
fix:
verification:
files_changed:
