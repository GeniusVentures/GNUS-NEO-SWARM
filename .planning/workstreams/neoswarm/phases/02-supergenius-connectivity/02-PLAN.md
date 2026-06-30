# Phase 2: SuperGenius Connectivity — Plan

**Planned:** 2026-06-30
**Context:** 02-CONTEXT.md (12 decisions D-01 through D-12)
**Goal:** Every NEO-SWARM node links GeniusSDK in-process — no gRPC API calls, everything is P2P always.

---

## Architecture

GeniusSDK is linked directly into the binary. `SGClient::Initialize()` calls `GeniusSDKInitWithKey()` using eth key derived from NodeIdentity. `SGJobSubmitter::PublishJob()` calls `GeniusSDKProcess()`. `SGResultCollector::WaitForResult()` polls `GeniusSDKGetProcessingStatus()` with exponential backoff. `SGMessageAuthenticator` signs payloads before dispatch. No gRPC channel management — `SGChannelManager` is deleted.

---

## Wave 1 — SGClient refactored to GeniusSDK *(merged)*

**PR:** #79 — merged 2026-06-30

**What:**
- Refactored `SGClient` Config from gRPC endpoint → SDK paths
- `Initialize()` calls `GeniusSDKInitWithKey()` in-process
- `SubmitJob()` routes through `GeniusSDKProcess()`
- Stripped raw gRPC from `super_genius_client.cpp`
- Added `--sg-endpoint`, `--sg-tls-ca`, `--sg-tls-cert` CLI flags (deprecated, removed in Wave 3)

**Plan:** 02-01-PLAN.md

---

## Wave 2 — Core SDK wiring *(02-05-PLAN.md)*

**Why:** Delete dead gRPC code, expose eth key, wire dispatch and result collection to SDK API.

**What:**
- Delete `sg_channel_manager.hpp/.cpp` and remove from CMakeLists.txt
- Add `GetPrivateKey()` to NodeIdentity
- Wire `SGJobSubmitter::PublishJob()` → `GeniusSDKProcess()` with signed payload
- Rewire `SGResultCollector::WaitForResult()` → `GeniusSDKGetProcessingStatus()` polling with exponential backoff (100ms→1s) + 120s deadline

**Files:** 9 files — sg_channel_manager.*, node_identity.*, super_genius_client.cpp, sg_job_submitter.*, sg_result_collector.*, network/CMakeLists.txt

---

## Wave 3 — End-to-end integration *(02-06-PLAN.md)*

**Why:** Connect the full dispatch pipeline and migrate CLI flags.

**What:**
- Wire `SGProcessingBridge::SubmitNetwork()` through SGClient
- Remove gRPC CLI flags: `--sg-endpoint`, `--sg-tls-ca`, `--sg-tls-cert`
- Add SDK CLI flags: `--sg-base-path`, `--sg-port`
- Update `ApiServer::Config` with SDK fields

**Files:** 4 files — sg_processing_bridge.cpp, main.cpp, api_server.*

---

## Wave 4 — Deadline, status, fallback *(02-07-PLAN.md)*

**Why:** Production hardening — timeouts, observability, graceful degradation.

**What:**
- Enforce 120s dispatch deadline
- Expose `supergenius_connected` and `fallback_active` via `GeniusElmGetStatus()`
- Auto-fallback to local MNN (`SubmitDirect`) on SDK failure
- Auth failures NOT swallowed

**Files:** 6 files — super_genius_client.*, sg_processing_bridge.cpp, genius_elm_chat_completions.cpp, api_server.*

---

## Wave 5 — Tests *(02-08-PLAN.md)*

**Why:** Prove the dispatch pipeline works end-to-end.

**What:**
- SGJobSubmitter unit tests with mock GeniusSDK
- SGResultCollector polling tests
- Integration test: SubmitJob → result
- Fallback test: SubmitNetwork failure → SubmitDirect
- Timeout test: 120s deadline triggers

**Files:** 4 test files + CMakeLists

---

## Summary

| Wave | Plan | What | PR |
|------|------|------|-----|
| 1 | 02-01 | SGClient refactored to GeniusSDK | #79 merged |
| 2 | 02-05 | Delete SGChannelManager, GetPrivateKey(), SDK wiring | #83 (update) |
| 3 | 02-06 | SubmitNetwork() E2E, CLI migration | New PR |
| 4 | 02-07 | Deadline, status, fallback | New PR |
| 5 | 02-08 | Tests | New PR |

---

## Open Questions

| Question | Resolution |
|----------|------------|
| Keep SGChannelManager? | Delete — handled by Wave 2 (D-01/D-02) |
| Identity mapping? | Derive eth key from NodeIdentity via GetPrivateKey() (D-03/D-04/D-05) |
| Result collection model? | Poll GeniusSDKGetProcessingStatus() + exponential backoff + 120s deadline (D-06/D-07) |
| SDK result retrieval API? | Open — no API in SDK header. Log warning if unavailable (D-08) |
| Config surface? | JSON config file + --sg-base-path + --sg-port CLI flags (D-09/D-10/D-11/D-12) |
