# Phase 2: SuperGenius Connectivity — Plan

**Planned:** 2026-07-09
**Context:** 02-CONTEXT.md (12 decisions D-01 through D-12)
**Goal:** Every NEO-SWARM node links GeniusSDK in-process — no gRPC, P2P always.

---

## Architecture

GeniusSDK linked directly. `SGClient::Initialize()` calls `GeniusSDKInit()` — SDK generates own keypair. `SGJobSubmitter::PublishJob()` passes raw GNUS schema JSON to `GeniusSDKProcess()`. `SGResultCollector::PollForResult()` polls `GeniusSDKGetProcessingStatus()` with exponential backoff. `SubmitNetwork()` wired through `SGClient::SubmitJob()`. No signing layer on dispatch — SDK handles auth internally.

---

## Wave 1 — SGClient refactored to GeniusSDK *(merged — PR #79)*

**What:** Refactored SGClient Config to SDK paths. `Initialize()` calls `GeniusSDKInitWithKey()`. Stripped raw gRPC.

---

## Wave 2 — Core SDK wiring *(merged — PR #83)*

**What:**
- Deleted `sg_channel_manager.hpp/.cpp`, removed from CMakeLists
- Added `GetPrivateKey()` to NodeIdentity (later unused by SDK, serves P2P)
- `PublishJob()` passes raw JSON to `GeniusSDKProcess()` — no wrapper, no signing
- `PollForResult()` with exponential backoff 100ms→1s, 120s timeout
- `PollForResultAsync()` via `std::async` for non-blocking callers
- `SubmitNetwork()` wired to `m_client->SubmitJob()`
- SDK generates own identity via `GeniusSDKInit()` (no eth key derivation)
- Removed `m_ethKey` from Config/CLI/JSON
- Removed SGJobSubmitter dependency on SGMessageAuthenticator
- Auto-fallback to local MNN handled by `SubmitJob()` caller

**Files:** ~13 files merged across PR #79 + #83

---

## Wave 3 — Cleanup + finish *(this branch)*

**What:**
- Fix `fallback_active` in `GeniusElmGetStatus()` — currently hardcoded `false`
- Delete `sg_message_authenticator.*` (dead code — no callers after Wave 2)
- Align CLI flag naming (`--sg-sdk-path` vs plan)
- Update 02-PLAN.md and 02-05-SUMMARY.md to match post-review reality

**Files:** `genius_elm_chat_completions.cpp`, `sg_message_authenticator.*`, `src/network/CMakeLists.txt`, `main.cpp`

---

## Wave 4 — Tests

**What:**
- Unit tests for SGJobSubmitter with mock GeniusSDK
- Unit tests for SGResultCollector polling
- Integration test: SubmitJob flow
- Fallback + timeout tests

**Files:** New test files

---

## Summary

| Wave | What | Status |
|------|------|--------|
| 1 | SGClient refactor | ✅ Merged (#79) |
| 2 | SDK wiring + dispatch + polling | ✅ Merged (#83) |
| 3 | Cleanup + finish | 🔧 In progress |
| 4 | Tests | ⬚ Not started |
