---
created: 2026-08-26
status: seed — not yet a phase
---

# Seed: SGFP4 model support in MNNInferenceEngine / SGProcessingManager

## Why this doesn't fit an existing pending phase

`neoswarm`'s ROADMAP has Phase 4 (SGProcessing Integration) marked complete, with
pending phases 3 (GCS GlobalDB), 5 (Production Hardening), 6 (Testing & Validation),
8 (Agentic Memory) as the "pick among" set in STATE.md. **None of them cover this.**
Phase 4's scope was explicitly FP4_ULTRA + MNN LLM processors only (ROADMAP.md:74).
SGFP4 is a different format (see the evaluation doc below) and needs a new phase —
use `gsd-phase add`/`insert` in the new session, don't try to fold this into 3/5/6/8.

## Goal

Get a real SGFP4-quantized `.mnn` model running through
`MNNInferenceEngine → SGProcessingManager`, called **directly** (not via the
SuperGenius network/job-submission path — that's explicitly out of scope for now,
per earlier discussion in this thread).

## Required reading before planning this phase

1. `.planning/quick/260825-pgu-evaluate-mnn-sgfp4-pivot-fp4-implementat/260825-pgu-EVALUATION.md`
   (in the parent `GeniusCognitiveSystem` repo) — the full evaluation + its
   2026-08-26 addendum. Read the addendum, not just the original body.
2. This document, in full.

## What's now unblocked (as of 2026-08-26)

MNN's `sgfp4-pivot` workstream shipped `mnnconvert --sgfp4` — a real, self-contained
C++ encoder (`tools/fp4/sgfp4_encode.cpp`) that takes a normally-converted `.mnn` and
produces a real SGFP4-quantized `.mnn`, verified to load and run through the
**classic `Interpreter`/`createSession`/`runSession` API** (the one
`SGProcessingManager::MNN_Tensor::Process()` actually uses) on both CPU and Vulkan.
This closes the "nothing can produce a real SGFP4 `.mnn`" gap that blocked this work
before. You do not need to build any injection/conversion tooling — it exists now.

`mnnconvert` is not invoked by any automated pipeline in this project — it's a
manual step a human runs (same as `RUN_AND_DEPLOY.md`'s documented `llmexport.py`
usage). Producing a test `.mnn` means running it by hand.

## Blockers / gotchas to design around

1. **The VulkanInitMutex deadlock (see above) will hit any real local execution of
   `ProcessingManager::Create()`.** Options: (a) scope this phase to only prove the
   wiring/schema/dispatch logic reaches `ProcessingManager::Create()` and skip-gate
   the actual execution the same way Phase 4's `04-04` tests did
   (`HasUsableVulkanDevice()` → `GTEST_SKIP()`, citing the tracked bug by name — do
   NOT silently work around it or silently omit coverage); or (b) treat fixing that
   upstream bug as a prerequisite/blocking dependency of this phase, tracked
   separately as "sgproc-render Phase 18" (todo file above) — check whether that's
   been picked up before committing to real local E2E verification as a success
   criterion.
2. **Externalized-weight models likely don't load.** `mnnconvert --sgfp4` sets
   `external={offset,size}` for spilled weights but not `op->externalPath`, and
   `OpType_SGFP4Dequant` isn't covered by MNN's auto-injection for that field. Only
   verified working for small/inline models. **Use a small test model** (well under
   whatever size triggers `_largeModel` in MNN's `writeFb.cpp`) to sidestep this for
   now — don't discover it as a surprise mid-phase.
3. **A null-pointer-dereference risk exists in the exact code path this test
   exercises**: `SGProcessingManager/src/processors/processing_processor_mnn_tensor.cpp`
   — `Process()` can return `nullptr` (e.g. malformed/incompatible model file); the
   caller in `StartProcessing()` dereferences it unchecked
   (`procresults->host<float>()`). Worth a defensive fix alongside this phase, or at
   minimum being aware a bad test model will crash, not error cleanly.
4. **Two existing SGProcessingManager tests are stale/broken** against current
   source (`test/processors/mnn_tensor_fp4_test.cpp` — assert FP4_ULTRA decode is
   unavailable; it's actually live). Different format (E2M1, not SGFP4) but same
   file/area, worth fixing in the same pass if touching this code.
5. **Naming**: don't call this "Ultra FP4" anywhere in new docs/tests — that name is
   already used, and means something different (E2M1/`FP4_ULTRA`), in this exact
   codebase. Call it SGFP4 v2.

## Reference code (MNN side, read-only — do not modify MNN in this phase)

- `include/MNN/SGFP4DequantUtils.hpp` — normative decode logic + format constants.
- `source/backend/cpu/CPUSGFP4Dequant.cpp` (`onResize`) — how the op reads its
  external sidecar.
- `tools/fp4/sgfp4_encode.cpp` — the new C++ encoder inside `mnnconvert --sgfp4`.
- `demo/exec/pictureRecognition.cpp` — canonical classic Interpreter/Session pattern.
- `test/op/TestSGFP4Converter.cpp` (PHASE B) — existing example of loading a real
  SGFP4-containing `.mnn` via `createFromFile`/`createSession`/`runSession` and
  asserting decode correctness — closest available template for this phase's test.

## Not in scope for this phase (confirmed with the user earlier in this thread)

- Calling via the full SuperGenius network/job-submission path (direct call only).
- Building any SGFP4 conversion/injection tooling (already exists, see above).
- gnus-poc's `pipeline/runner.py` default flip (`--adaptive`) and its
  `"fp4_ultra_v0.2"` manifest naming collision — separate, lower-priority follow-ups,
  not blocking this phase since `mnnconvert --sgfp4` doesn't depend on gnus-poc at
  runtime.
