---
status: testing
phase: 04-sgprocessing-integration
source: [04-VERIFICATION.md]
started: 2026-08-18T22:35:00Z
updated: 2026-08-18T22:35:00Z
---

## Current Test

number: 1
name: NEO-SWARM full build/link confirmation (PROC-03/FIX-04, plans 04-01/04-04)
expected: |
  Once the separate, pre-existing `get_third_party_dir()` thirdparty-resolution issue is fixed (out of this phase's scope), a fresh CMake configure + `cmake --build build/Windows/Release --target neoswarm_core test_sgprocessing_pipeline` in GNUS-NEO-SWARM succeeds: configure reports the new `GeniusNetwork/SuperGenius` link path, both targets build with zero unresolved-symbol errors, `SGProcessingBridge.BuildSchemaJson_Fp4Ultra` passes, and the two new Vulkan-skip-gated integration tests report SKIPPED (on this real-Vulkan-device machine) rather than hanging.
awaiting: user response

## Tests

### 1. NEO-SWARM full build/link confirmation (PROC-03/FIX-04, plans 04-01/04-04)
expected: Configure succeeds and reports the new `GeniusNetwork/SuperGenius` link path; `neoswarm_core` and `test_sgprocessing_pipeline` build with zero unresolved-symbol errors; `SGProcessingBridge.BuildSchemaJson_Fp4Ultra` passes; the two new integration tests report SKIPPED (not hanging) on this real-Vulkan-device machine.
result: [in progress] The original blocker (pre-existing `get_third_party_dir()` thirdparty-path resolution failure) is fixed — CMake configure now succeeds end-to-end. A second, distinct blocker surfaced immediately after: `neoswarm_core` fails to compile (`mnn_inference_engine.cpp` cannot find `MNN/llm/llm.hpp`), same root cause as plan 04-03's `SGPROC_HAS_MNN_LLM` finding (vendored MNN built with `MNN_BUILD_LLM=OFF`), but NEO-SWARM's own code has no equivalent guard. Tracked as debug session `.planning/debug/neoswarm-mnn-llm-header.md` — resume with `/gsd-debug continue neoswarm-mnn-llm-header`.

### 2. MNN LLM processor real execution (PROC-01, plan 04-03)
expected: After rebuilding the vendored MNN thirdparty library with `MNN_BUILD_LLM=ON` and reconfiguring SuperGenius, `SGPROC_HAS_MNN_LLM` evaluates TRUE at configure time, the `mnn_llm_test` target is generated and builds, and `ctest -C Release -R MNNLlmTest` passes both GTest cases (`EmptyModelFileFailsClosedWithResourceResolution`, `PreCancelledTokenFailsClosedWithCancelled`).
result: [pending]

## Summary

total: 2
passed: 0
issues: 0
pending: 2
skipped: 0
blocked: 0

## Gaps
