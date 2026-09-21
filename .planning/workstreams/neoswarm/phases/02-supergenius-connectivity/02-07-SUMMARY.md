# Plan 02-07 Summary: Timeout Enforcement + Connectivity Status

**Phase:** 02-supergenius-connectivity
**Status:** Complete (documentation-only — functionality already implemented)
**Requirements:** SG-05
**Wave:** 4 (depends_on: [05, 06])

## Scope Reassessment (plan vs. reality)

Cross-referencing the plan against the current source revealed that **all three tasks were already functionally implemented** — in one case (Task 2) with a *more correct* implementation than the plan specified. The plan's `interfaces` block was stale (referenced `result_m_timeout`, `WaitForResult(taskId, timeout)`, `Initialize(identity)`, `IsSuperGeniusConnected` at "line 101" — none of which match the post-02-05 code). No source changes were required.

| 02-07 task | Disposition |
|---|---|
| Task 1 — enforce 120s deadline + BroadcastTimeout log | ✅ Already enforced; specific log intentionally omitted (redundant) |
| Task 2 — `fallback_active` dynamic in `BuildStatusJson()` | ✅ Already implemented — **more correct than the plan** |
| Task 3 — verify graceful degradation + identity guard | ✅ Verified; identity-guard check was stale (SGClient no longer takes identity) |

## Task 1 — 120s Deadline (already enforced)

The deadline is enforced by `SGResultCollector::PollForResult(timeout)` polling loop. `SGResultCollectorConfig::m_resultTimeout` defaults to **120s** (`sg_result_collector.hpp:22`), and `SGClient::SubmitJob()` calls `PollForResult(m_impl->m_cfg.m_resultTimeout)` (`super_genius_client.cpp:106`).

The plan wanted two additions, both assessed as **redundant**:
- An explicit `"deadline=120s"` log line — the timeout is already logged by the polling loop's timeout path.
- A `BroadcastTimeout`-specific log branch in `SGProcessingBridge::SubmitJob()` — the bridge already handles *all* network failures (including BroadcastTimeout) through the existing fallback at `sg_processing_bridge.cpp:267-276`, logging `"Network dispatch failed ({})"` with `result.error().message()`. BroadcastTimeout is simply one such error; a dedicated branch would add log volume without changing behavior.

Per the minimal-change philosophy, neither cosmetic log was added. The deadline behavior the requirement (SG-05) actually demands — timeout enforced, fallback to local MNN on expiry — is present and correct.

## Task 2 — `fallback_active` (already implemented, better than planned)

`BuildStatusJson()` in `genius_elm_chat_completions.cpp:100-102`:
```cpp
j[ "supergenius_connected" ] = g_server->IsSuperGeniusConnected();
j[ "fallback_active" ]       = g_server->IsSuperGeniusNetworkEnabled() &&
                                !g_server->IsSuperGeniusConnected();
```

The plan specified `fallback_active = !sgConnected` — a cruder single condition that would **incorrectly report fallback-active in local-only mode** (where SuperGenius processing is disabled entirely, so there is nothing to "fall back" from). The landed two-condition version (`NetworkEnabled && !Connected`) is semantically correct: fallback is only "active" when SG processing was requested but the SDK is not connected. This was already implemented prior to this plan's execution. `kStatusJsonStub` (`:62-68`) correctly retains the hardcoded `fallback_active: true` for the no-server case.

## Task 3 — Graceful Degradation (verified)

- `ApiServer::IsSuperGeniusConnected()` is null-safe: `return m_sgClient != nullptr && m_sgClient->IsConnected();` (`api_server.cpp:715`). `IsConnected()` reads live SDK state via `GeniusSDKGetNodeState() == GENIUS_NODE_READY`.
- `Stop()` tears down the SDK: `if ( m_sgClient ) m_sgClient->Disconnect();` (`api_server.cpp:707`) → `GeniusSDKShutdown()`.
- `InitializeNetwork()` wires SGClient into the engine even when init fails, so the bridge receives a client whose `IsConnected()` returns false and the auto-fallback in `SGProcessingBridge::SubmitJob()` triggers `SubmitDirect()` on network failure — desired graceful degradation.
- **Stale check dropped:** the plan's Step A wanted to verify an `if ( m_identity && m_identity->IsLoaded() )` guard. Post-02-05, `SGClient::Initialize()` takes no identity argument (SDK-owned identity), so this guard no longer exists and the check is not applicable. Auth-failure non-swallowing is preserved at `sg_processing_bridge.cpp:269-273` (SignatureInvalid / IdentityError propagate, not swallowed).

## Verification (existing code, no changes)

- `sg_result_collector.hpp:22` — `m_resultTimeout{ 120 }`
- `super_genius_client.cpp:106` — `PollForResult( m_impl->m_cfg.m_resultTimeout )`
- `genius_elm_chat_completions.cpp:101-102` — dynamic `fallback_active`
- `api_server.cpp:707,715` — `Disconnect()` + null-safe `IsSuperGeniusConnected()`
- `sg_processing_bridge.cpp:267-276` — fallback to `SubmitDirect` on network failure; auth errors propagate

Build (`build/OSX/Debug`): cmake exit 0, ninja exit 0 — confirms no changes needed to compile clean.

## Follow-ups

- 02-08 (test coverage for the SDK dispatch pipeline) is the remaining Phase 2 plan. Tasks 1-2 are already covered by the existing `test/network/test_sg_client.cpp`; Task 3 (SGClient lifecycle + bridge fallback tests) is genuinely missing and handled in 02-08.
