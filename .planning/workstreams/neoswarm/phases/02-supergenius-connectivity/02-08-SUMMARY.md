# Plan 02-08 Summary: SDK Dispatch Test Coverage

**Phase:** 02-supergenius-connectivity
**Status:** Complete
**Requirements:** SG-05 (test coverage for the SDK dispatch pipeline)
**Wave:** 5 (depends_on: [05, 06, 07])

## Scope Reassessment (plan vs. reality)

The plan's `interfaces` block was written against the pre-02-05 design and was stale in the same way as 02-06/02-07: it referenced `SGMessageAuthenticator`, `WaitForResult(taskId, timeout)`, `Initialize(identity)`, and `m_basePort` — none of which exist post-02-05 (SDK-owned identity, `PollForResult(timeout)`, no port field). Cross-referencing each task against the current test tree:

| 02-08 task | Disposition |
|---|---|
| Task 1 — SGJobSubmitter tests (oversized payload, max-size, empty) | ✅ Already covered by existing `test/network/test_sg_client.cpp` (SGJobSubmitter suite) |
| Task 2 — SGResultCollector tests (default timeout, poll, async, independent instances) | ✅ Already covered by existing `test/network/test_sg_client.cpp` (SGResultCollector suite) |
| Task 3 — SGClient lifecycle + SGProcessingBridge fallback tests | ⚠️ **Genuinely missing — executed here** |

Only Task 3 required new test code. The executed scope is therefore: 5 SGClient lifecycle tests added to the existing `test_sg_client.cpp`, plus a new `test/integration/test_sg_connectivity.cpp` for the bridge.

## What Was Built

### `test/network/test_sg_client.cpp` — 5 SGClient lifecycle tests appended
- `DefaultConfigMatchesNamedConstants` — pins `Config::m_resultTimeout` to `kDefaultResultTimeoutSeconds` and `BaseWritePath` to `"./sdk"`.
- `IsConnectedBeforeInitReturnsFalse` — pre-init state.
- `ConstructWithConfigDoesNotCrash` — custom `BaseWritePath` accepted.
- `MoveConstructorTransfersOwnership` — moved-from client destructs safely.
- `DisconnectBeforeInitDoesNotCrash` — `Disconnect()` on a never-initialized client is safe.

### `test/integration/test_sg_connectivity.cpp` — 8 SGProcessingBridge tests (new file)
- `BuildSchemaJsonValidParamsReturnsJson` — emits `gnus_spec_version` marker.
- `BuildSchemaJsonEmptyModelUriReturnsInvalidArgument` / `...EmptyInputUri...` — `Error::InvalidArgument`.
- `BuildSchemaJsonFP4UltraFormatEmitsFP4Type` — FP4_ULTRA → `"fp4_ultra"` type string.
- `SubmitJobNetworkModeNoClientFallsBackAndFails` — no client → `SubmitNetwork` NetworkError → auto-fallback to `SubmitDirect` → failure (no SGProcessingManager/model in test env), no crash.
- `SubmitJobDirectModeDoesNotRequireClient` — direct mode never touches the client.
- `SetClientNullptrDoesNotCrash`.
- `SubmitJobInvalidSchemaDoesNotAttemptDispatch` — schema failure short-circuits before any dispatch.

### `test/CMakeLists.txt`
- Registered `test_sg_connectivity` linking `neoswarm_core;neoswarm_network;neoswarm_common`.

## Production Bug Found & Fixed (root cause, not symptom)

The `MoveConstructorTransfersOwnership` test **segfaulted** — exposing a real bug in production code, which the test correctly surfaced (the test IS the specification):

- `SGClient::~SGClient()` calls `Disconnect()` unconditionally (`super_genius_client.cpp:39-42`).
- `Disconnect()` dereferenced `m_impl->m_jobSubmitter.reset()` with no null check.
- The move constructor is `= default`, so a moved-from `SGClient` has `m_impl == nullptr` — its destructor then dereferenced null → **segfault on any moved-from client's destruction** (would also hit production: e.g., a moved-from client in a container).

**Fix (minimal, 4 lines):** added a null-`m_impl` guard at the top of `Disconnect()` (`super_genius_client.cpp:117-121`). This also makes repeated `Disconnect()` calls safe. No test was modified to work around the bug — the bug was fixed at its source.

## Verification

- Build (`build/OSX/Debug`): cmake exit 0, ninja exit 0 — `test_sg_client` + `test_sg_connectivity` link clean.
- `test_sg_client`: **15/15 pass** (4 SGJobSubmitter + 6 SGResultCollector + 5 SGClient).
- `test_sg_connectivity`: **8/8 pass**.
- Full suite (`ctest`): **19/19 pass** — confirms the `Disconnect()` fix in the shared `neoswarm_network` library did not regress any dependent test (`test_network`, `test_pipeline`, `test_sgprocessing_pipeline`, etc.).

## Code Review Fixes (02-REVIEW.md — 1 Critical, 3 Warning resolved)

The pre-PR `/gsd-code-review` gate surfaced that the moved-from `SGClient` fix was **incomplete** — the null-`m_impl` guard was only in `Disconnect()`, leaving the same segfault reachable via three other public methods. All Critical/Warning findings were fixed at the source:

- **CR-01 (Critical):** Added the same `!m_impl` guard to `IsConnected()` (was a null deref inside `noexcept` — hard segfault), `Initialize()` (returns `InternalError`), and `SubmitJob()` (returns `InternalError`). Extended `MoveConstructorTransfersOwnership` with `EXPECT_FALSE( client1.IsConnected() )` to pin moved-from safety.
- **WR-01:** `Disconnect()` now gates `GeniusSDKShutdown()` on `m_initialized` — no shutdown call when never-initialized, and no double-shutdown via `~SGClient()`.
- **WR-02:** `src/main.cpp` was discarding `--port` with `(void) args.port_;` — now wired to `cfg.m_grpcPort`.
- **WR-03:** New lifecycle tests used hardcoded `/tmp/...` paths (breaks Windows) — switched to `std::filesystem::temp_directory_path()` (C++17, portable, no OS ifdef).
- **IN-01:** Fixed stale `@file genius_chat.cpp` header → `main.cpp`.
- **IN-03:** Hoisted magic-number timeout literals in the test file to named `constexpr` constants.

**IN-02 (`"./sdk"` default duplicated in 4 places) intentionally deferred** — introducing a shared constant and threading it through `ApiServer::Config`, `SGClient::Config`, and `Args` crosses file boundaries and exceeds this test-coverage plan's minimal-change scope; flagged as a follow-up refactor.

**Post-fix verification:** full build clean, `ctest` **19/19 pass**.

## Follow-ups

- Phase 2 plans 02-06, 02-07, 02-08 are now all executed. The original 02-06/02-08 `must_haves` no longer match the executed scope (large portions were already landed by 02-05); this is documented in each plan's SUMMARY Scope Reassessment table and the amended PLAN frontmatter/success_criteria.
- (Deferred, IN-02) Consolidate the `"./sdk"` base-path default into a single named constant shared by `super_genius_client.hpp`, `api_server.hpp`, and `main.cpp`.
