# Phase 4: SGProcessing Integration - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-08-18
**Phase:** 04-sgprocessing-integration
**Areas discussed:** Repo boundary, MNN LLM processor design, FP4_ULTRA scope, Protobuf conflict scope

---

## Repo Boundary

| Option | Description | Selected |
|--------|-------------|----------|
| Full cross-repo | Plans include commits to both SuperGenius and GNUS-NEO-SWARM | ✓ |
| NEO-SWARM only | Treat PROC-01/02 as external SuperGenius-team work | |
| Split into two phases | Do safe NEO-SWARM-side work now, defer cross-repo work | |

**User's choice:** Full cross-repo (recommended)
**Notes:** None additional.

| Option | Description | Selected |
|--------|-------------|----------|
| Local source build override | Build SGProcessingManager from local SuperGenius checkout | |
| Rebuild + republish prebuilt artifact | Follow existing thirdparty artifact pipeline | |
| Defer to planning | Investigate build-link mechanics at plan time | |

**User's choice:** Free text (Other) — "SuperGenius, thirdparty, and all related libraries are available in W:\gnus\GeniusNetwork. For the most part I believe we are just updating the MNN branch in thirdparty and maybe SGProcessingManager for fp4 handling. SGProcessingManager should not come from thirdparty, it should come from SuperGenius."
**Notes:** Revealed the existence of the GeniusNetwork monorepo, prompting investigation of its structure (led to discovering `sgproc-render` workstream and branch divergence — see below).

| Option | Description | Selected |
|--------|-------------|----------|
| dev_childwallet (GeniusNetwork) | Actively-developed branch with sgproc-render's work landed | ✓ |
| dev_persisprocresults (standalone) | The July 1 branch the scout examined | |
| Not sure — need to check | Flag as open question | |

**User's choice:** dev_childwallet (GeniusNetwork, recommended)
**Notes:** "I have removed W:\gnus\SuperGenius entirely to avoid confusion. W:\gnus\GeniusNetwork\SuperGenius is proper. sgproc-render is mostly a complete plan, I have a couple of small phases i'm working on in parallel but it's mostly good. Our vendored mnn in thirdparty has a MNN_Ultra with fp4 ultra in it. I believe it may be in a 80% completed state though. SGProcessingManager has fp4_ultra in the schema, but I don't think it's really ready to handle it until MNN accepts it."

| Option | Description | Selected |
|--------|-------------|----------|
| Yes, finish it this phase | Check out/merge MNN_Ultra, complete FP4 Ultra in MNN | |
| Treat MNN completion as external blocker | Phase 4 stops at enabling SGProcessingManager plumbing | |
| Investigate at plan time | Have researcher check actual completeness first | ✓ |

**User's choice:** Investigate at plan time (paraphrased) — "We have to figure out exactly what state MNN's fp4 is in. If it's far off, we may divert that to another phase, and just link SGProcessingManager."
**Notes:** Conditional decision — full implementation vs. deferral depends on research finding.

---

## MNN LLM Processor Design

| Option | Description | Selected |
|--------|-------------|----------|
| Mirror the approach | Port mnn_inference_engine's logic into the new SGProcessingManager processor | ✓ (paraphrased) |
| Independent implementation | Design fresh, no attempt to match NEO-SWARM's local engine | |
| Let Claude decide at planning | Defer to planner | |

**User's choice:** Free text (Other) — "Just a quick look through this file, it looks like it's either doing the work locally with mnn, or submitting to SGProcessingManager (really, to supergenius, where other nodes will use SGProcessingManager). In my opinion, sgprocessingmanager should likely have a 'processing_processor_mnn_fp4.cpp' that does what mnn_inference_engine does, and we can call that directly and remove that duplicate code from GNUS-NEO-SWARM. But we'll keep InferViaSGProcessing to submit a job to the SuperGenius network where other nodes might do that work. This makes more sense for the project I think."
**Notes:** Established the core architectural direction for this phase.

| Option | Description | Selected |
|--------|-------------|----------|
| Yes, one combined processor | PROC-01 and PROC-02 are one deliverable | |
| No, two separate processors | Keep LLM generation and FP4_ULTRA distinct | |
| Let Claude decide at planning | Defer processor boundary | ✓ (paraphrased) |

**User's choice:** Free text (Other) — "Well fp4 is fp4, sgprocessingmanager would handle that. There are already several mnn processors available in sgprocessingmanager which might for the llm generation. If we need a new processor, we can do that too. Either way, all actual mnn calls should happen in SGProcessingManager since it handles a lot of vulkan locking tasks and such. It also happens that jobs may be happening automatically on SuperGenius, so that's doubly useful."
**Notes:** Surfaced the firm architectural principle: all MNN calls happen in SGProcessingManager (Vulkan locking, automatic swarm-serving benefit).

| Option | Description | Selected |
|--------|-------------|----------|
| Delete the engine, route through the bridge | Delete mnn_inference_engine entirely | |
| Keep a thin wrapper | Keep same interface, forward to bridge internally | |
| Let Claude decide at planning | Defer to planner | |

**User's choice:** Free text (Other) — "The engine has some useful aspects i.e. MNNInferenceEngine::InferViaSGProcessing, so I don't think we delete it entirely. Existing SingleNode calls would just call ProcessingManager::Init / ProcessingManager::Process directly (as opposed to inferviasgprocessing which sends a job to the gnus network)"
**Notes:** Landed between the two proposed options — partial deletion, not full deletion or unchanged wrapper.

---

## FP4_ULTRA Scope

| Option | Description | Selected |
|--------|-------------|----------|
| Wire + stub, ship what's ready | Re-enable validation/plumbing now, defer decode to MNN readiness | ✓ |
| Full gate on MNN readiness | Don't touch SGProcessingManager until MNN_Ultra confirmed complete | |
| Let Claude decide once MNN's state is known | Defer entirely | |

**User's choice:** Wire + stub, ship what's ready (recommended)
**Notes:** None additional.

| Option | Description | Selected |
|--------|-------------|----------|
| Yes — it's a TENSOR input format | Re-enable existing commented-out validation branch | |
| No — give it its own DataType/processor | Add dedicated FP4_ULTRA DataType + processor | |
| Let Claude decide at planning | Confirm shape after reading current validation logic | ✓ (paraphrased) |

**User's choice:** Free text (Other) — "Just depends on what is required, if we need a new processor factory then we should make one. If it works as tensor, that's fine too."
**Notes:** No hard preference — pragmatic, plan-time call.

| Option | Description | Selected |
|--------|-------------|----------|
| Pass-through to MNN | SGProcessingManager validates, MNN does the actual dequant | ✓ |
| Implement the codec in SGProcessingManager | SGProcessingManager owns the dequant math | |
| Let Claude decide at planning | Defer until MNN's API surface is known | |

**User's choice:** Pass-through to MNN (recommended)
**Notes:** Consistent with the "no duplicate MNN logic" principle from the LLM processor discussion.

---

## Protobuf Conflict Scope

| Option | Description | Selected |
|--------|-------------|----------|
| Verify + correct docs | Confirm no active conflict, correct stale docs | (superseded, see below) |
| Re-add SentencePiece properly | Bring back real SentencePiece integration | |
| Leave PROC-03 deferred | No active conflict, no scheduled SentencePiece work | |

**User's choice:** Free text (Other) — "NEO-SWARM doesn't need to build SGProcessingManager at all, SuperGenius is build as static libs (W:\gnus\GeniusNetwork\SuperGenius\build\Windows\Release\SuperGenius\lib) including sgprocessingmanager, we just need to link them."
**Notes:** Reframed the entire question — confirmed via directory listing that this build output exists with a consistent protobuf across all libs.

| Option | Description | Selected |
|--------|-------------|----------|
| Re-verify, fix cross-platform | Confirm -ld_classic still needed after relinking, fix cross-platform | ✓ |
| Keep the existing workaround as-is | Don't re-litigate necessity, just extend to other platforms | |
| Let Claude decide at planning | Defer to researcher/planner findings | |

**User's choice:** Yes, re-verify and confirm (recommended) — asked after confirming the GeniusNetwork build output first.
**Notes:** None additional.

---

## Claude's Discretion

- Exact processor file/class boundary for MNN LLM + FP4_ULTRA work in SGProcessingManager
- Whether to reuse an existing MNN processor (adapt `MNN_ML` stub or `MNN_String`) vs. write a new one
- CMake mechanics for pointing NEO-SWARM at GeniusNetwork's SuperGenius build output

## Deferred Ideas

- Finishing MNN_Ultra's FP4 Ultra decode work, if research shows it's far from done — candidate for its own phase
- Re-adding SentencePiece tokenization — no active conflict exists; only relevant if a future phase specifically needs it
- Implementing FP4 Ultra's dequant math inside SGProcessingManager — explicitly delegated to MNN, not this project's concern
