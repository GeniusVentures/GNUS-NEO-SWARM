# Phase 2: SuperGenius Connectivity — Plan

**Planned:** 2026-06-24
**Context:** 02-CONTEXT.md (updated 2026-06-24)
**Goal:** Wire GeniusSDK dispatch so the engine can send inference jobs to the SuperGenius network.

---

## Architecture Decision (pre-wave)

GeniusSDK handles gRPC transport internally. GNUS-NEO-SWARM does NOT need `SGChannelManager` (raw gRPC channel creation) — that was built under the incorrect assumption of using gRPC directly. `SGJobSubmitter` calls `GeniusSDKProcess()` instead. `SGResultCollector` polls `GeniusSDKGetProcessingStatus()`. `SGMessageAuthenticator` stays (signing is separate from transport).

---

## Wave 1 — Strip raw gRPC, wire GeniusSDK header

**Why this wave first:** Before any dispatch can work, the SGClient must link against GeniusSDK and stop using raw gRPC channel management.

**What:**
- Remove `SGChannelManager` from SGClient — GeniusSDK handles gRPC
- Add `#include "GeniusSDK.h"` to SGClient
- Update `SGClient::Initialize()` — remove channel manager initialization, add GeniusSDK initialization if needed
- Update `SGClient::Connect()` — call GeniusSDK health check instead of creating gRPC channel
- Update `SGClient::IsConnected()` — use `GeniusSDKGetNodeState()` instead of channel state
- Update `SGClient::Disconnect()` — remove channel teardown
- Remove `SGChannelManager` files from `src/network/CMakeLists.txt` if they're no longer needed

**Files:**
- `src/network/sg_client/super_genius_client.cpp/.hpp`
- `src/network/sg_client/sg_channel_manager.cpp/.hpp` (remove or keep as dead)
- `src/network/CMakeLists.txt` (update if removing)
- `src/api/api_server.cpp` (SGClient config passed from here)

**Deliverable:** SGClient compiles against GeniusSDK, no raw gRPC channel code in active path.

---

## Wave 2 — Wire SGJobSubmitter to GeniusSDKProcess

**Why this wave second:** The submitter is the actual dispatch — everything depends on it.

**What:**
- Replace `SGJobSubmitter::PublishJob()` TODO stub with `GeniusSDKProcess(jsondata)` call
- Map `GeniusNodeReturnValue_t` to `outcome::result<...>` error codes
- Handle `JsonData_t` (2KB char array) — truncate or reject oversized payloads
- Sign payload via `SGMessageAuthenticator::Sign()` before dispatch
- Log dispatch success/failure at debug level

**Files:**
- `src/network/sg_client/sg_job_submitter.cpp/.hpp`

**Deliverable:** `PublishJob()` calls GeniusSDK and returns success/error.

---

## Wave 3 — Wire SGResultCollector to GeniusSDK polling

**Why this wave third:** After submitting, results must come back.

**What:**
- Replace `SGResultCollector::WaitForResult()` TODO stub with polling loop
- Call `GeniusSDKGetProcessingStatus()` in a loop with sleep intervals
- Implement condition_variable + timeout pattern (matching `ResultAggregation`)
- Return result data when processing completes or timeout expires
- Handle error states (GENIUS_PR_STATUS_DISABLED = return error)

**Files:**
- `src/network/sg_client/sg_result_collector.cpp/.hpp`

**Deliverable:** `WaitForResult()` polls GeniusSDK until completion or timeout.

---

## Wave 4 — Wire SubmitNetwork() end-to-end

**Why this wave fourth:** Connects all components into the full dispatch path.

**What:**
- Replace `SGProcessingBridge::SubmitNetwork()` stub with `m_sgClient->SubmitJob(json)`
- Wire `network_mode_` flag to select SubmitNetwork vs SubmitDirect
- Handle the full lifecycle: build schema → sign → submit → wait for result → return
- Verify fallback behavior: if SubmitNetwork fails, auto-fallback to SubmitDirect

**Files:**
- `src/core/sgprocessing/sg_processing_bridge.cpp`
- `src/core/sgprocessing/sg_processing_bridge.hpp`

**Deliverable:** `SubmitNetwork()` dispatches through GeniusSDK and returns result or timeout.

---

## Wave 5 — Deadline enforcement + status reporting

**Why this wave last:** Non-functional requirements that complete the feature.

**What:**
- Add 120s deadline to SGClient::SubmitJob() — enforce via condition_variable timeout
- Wire `GeniusElmGetStatus()` to report `supergenius_connected` and `fallback_active`
- Expose `GeniusSDKGetNodeState()` through `IsSuperGeniusConnected()`
- Verify graceful degradation: unreachable SuperGenius → local mode, no crash
- Log connectivity changes at info level

**Files:**
- `src/network/sg_client/super_genius_client.cpp` (deadline in SubmitJob)
- `src/genius_elm_chat_completions.cpp` (GeniusElmGetStatus)
- `src/api/api_server.cpp` (IsSuperGeniusConnected)

**Deliverable:** Jobs timeout at 120s. Status reports connectivity. Unreachable is handled gracefully.

---

## Wave 6 — Tests

**What:**
- Unit tests for SGJobSubmitter with mock GeniusSDK
- Unit tests for SGResultCollector with mock polling
- Integration test: SubmitJob → mock SDK → result returned
- Fallback test: SubmitNetwork fails → auto-falls back to SubmitDirect
- Timeout test: SDK hangs → 120s deadline triggers

**Files:**
- `test/network/test_sg_client.cpp` (new)
- `test/integration/test_sg_connectivity.cpp` (new)

---

## Summary

| Wave | What | Files changed | Depends on |
|------|------|--------------|------------|
| 1 | Strip raw gRPC, wire GeniusSDK | SGClient, SGChannelManager, CMakeLists | Nothing |
| 2 | Wire JobSubmitter to SDK | SGJobSubmitter | Wave 1 |
| 3 | Wire ResultCollector to SDK | SGResultCollector | Wave 1 |
| 4 | Wire SubmitNetwork() end-to-end | SGProcessingBridge | Wave 1-3 |
| 5 | Deadline + status reporting | SGClient, FFI, ApiServer | Wave 4 |
| 6 | Tests | New test files | Wave 5 |

---

## Open Questions

| Question | Impact | Resolution |
|----------|--------|------------|
| Keep SGChannelManager? | Wave 1 | Remove — GeniusSDK handles gRPC |
| 2KB payload limit adequate? | Wave 2 | Reject oversized payloads for now |
| Result polling interval? | Wave 3 | 500ms polls, 120s timeout (240 polls max) |
| SDK init needed? | Wave 1 | Check `GeniusSDKInit` — likely already called by SuperGenius |
| `GeniusSDKProcess()` blocking? | Wave 2 | If blocking, wrap in thread + condition_variable |
