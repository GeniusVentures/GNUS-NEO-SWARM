---
phase: 02-supergenius-connectivity
reviewed: 2026-08-09T00:00:00Z
depth: standard
files_reviewed: 6
files_reviewed_list:
  - src/main.cpp
  - src/api/api_server.hpp
  - src/network/sg_client/super_genius_client.cpp
  - test/network/test_sg_client.cpp
  - test/integration/test_sg_connectivity.cpp
  - test/CMakeLists.txt
findings:
  critical: 1
  warning: 3
  info: 3
  total: 7
status: issues_found
---

# Phase 02: Code Review Report

**Reviewed:** 2026-08-09
**Depth:** standard
**Files Reviewed:** 6
**Status:** issues_found

## Summary

Reviewed the six files changed by plans 02-06 (CLI flag removal / `sg_base_path` rename), 02-07 (Disconnect null-guard segfault fix + 5 lifecycle tests), and 02-08 (new SGProcessingBridge integration tests + CMake registration).

The 02-07 fix correctly guards `Disconnect()` against the moved-from null `m_impl`, but the same moved-from crash remains reachable through three other public methods — most notably `IsConnected()`, which the phase's own new tests call. This is the same root defect the plan set out to fix and it is only partially fixed. Additionally, `Disconnect()` calls `GeniusSDKShutdown()` unconditionally (even when the SDK was never initialized, and twice per object lifetime), and the `--port` CLI flag in main.cpp is parsed, documented, and then silently discarded.

The new integration tests are well-scoped (crash-safety and error propagation, no live SDK) and the CMake registration is correct. No C++20 features, no `sleep_for`, no `#ifdef` OS guards, no stubs introduced.

## Critical Issues

### CR-01: Moved-from SGClient still segfaults in IsConnected(), Initialize(), and SubmitJob()

**File:** `src/network/sg_client/super_genius_client.cpp:130-137` (also 47-80, 82-114)
**Issue:** Plan 02-07 fixed the moved-from null `m_impl` crash only in `Disconnect()` (line 119). The defaulted move constructor (`SGClient::SGClient( SGClient&& ) noexcept = default;`, line 44) leaves the source object's `std::unique_ptr<Impl>` null, and three other public methods dereference `m_impl` with no guard:

- `IsConnected()` (line 132): `if ( !m_impl->m_initialized )` — null deref, inside a `noexcept` function, so this is a hard segfault. This method is called by the phase's own new tests and by `ApiServer::IsSuperGeniusConnected()`.
- `Initialize()` (line 49): `m_impl->m_jobSubmitter = ...` — null deref.
- `SubmitJob()` (lines 84, 90): `m_impl->m_initialized` / `m_impl->m_jobSubmitter` — null deref.

The header (`super_genius_client.hpp:106`) documents `IsConnected()` as `noexcept`; a caller has no way to detect the moved-from state before calling it. Any code that moves an `SGClient` (e.g. into a container or `std::optional`) and then touches the source object — or any future caller that probes `IsConnected()` defensively — reintroduces the exact segfault 02-07 was written to eliminate. No test covers `IsConnected()` on a moved-from instance, so the gap is invisible to the suite.

**Fix:** Apply the same guard used in `Disconnect()` to the remaining entry points:

```cpp
bool SGClient::IsConnected() const noexcept
{
    if ( !m_impl || !m_impl->m_initialized )
    {
        return false;
    }
    return GeniusSDKGetNodeState() == GENIUS_NODE_READY;
}
```

```cpp
outcome::result<void> SGClient::Initialize()
{
    if ( !m_impl )
    {
        ClientLogger()->error( "Initialize: SGClient in moved-from state" );
        return outcome::failure( Error::InternalError );
    }
    // ... existing body
}
```

```cpp
outcome::result<std::vector<uint8_t>> SGClient::SubmitJob( const std::string& gnusSchemaJson )
{
    if ( !m_impl || !m_impl->m_initialized )
    {
        ClientLogger()->error( "SubmitJob: SGClient not initialized" );
        return outcome::failure( Error::InternalError );
    }
    // ... existing body
}
```

Also extend `TEST( SGClient, MoveConstructorTransfersOwnership )` in `test/network/test_sg_client.cpp:142` with `EXPECT_FALSE( client1.IsConnected() );` to pin the moved-from behavior.

## Warnings

### WR-01: Disconnect() calls GeniusSDKShutdown() unconditionally — uninitialized and double shutdown

**File:** `src/network/sg_client/super_genius_client.cpp:116-128`
**Issue:** `Disconnect()` resets the sub-components and sets `m_initialized = false`, but then calls `GeniusSDKShutdown()` on every invocation regardless of whether `Initialize()` ever succeeded. Two concrete consequences:

1. The phase's own new test `DisconnectBeforeInitDoesNotCrash` (`test_sg_client.cpp:152-159`) calls `Disconnect()` on a never-initialized client — so `GeniusSDKShutdown()` runs with no SDK node up. Whether that is safe depends entirely on undocumented SDK tolerance.
2. `~SGClient()` (line 41) calls `Disconnect()`, so any explicit `Disconnect()` followed by destruction calls `GeniusSDKShutdown()` twice per object. `m_initialized` is already false on the second pass, but the shutdown call is not conditioned on it.

**Fix:** Gate the SDK call on the initialized flag:

```cpp
void SGClient::Disconnect()
{
    // Guard: moved-from SGClient has null m_impl (defaulted move ctor).
    if ( !m_impl )
    {
        return;
    }
    m_impl->m_jobSubmitter.reset();
    m_impl->m_resultCollector.reset();
    if ( m_impl->m_initialized )
    {
        m_impl->m_initialized = false;
        GeniusSDKShutdown();
        ClientLogger()->info( "SGClient shut down — SDK node stopped" );
    }
}
```

### WR-02: --port CLI flag is parsed, documented, then silently discarded

**File:** `src/main.cpp:188-189, 308`
**Issue:** `--port <n>` is parsed into `args.port_` (line 189), shown in both the file-header usage block (line 15) and `PrintHelp()` (line 73), and overridable from JSON config (line 118-119) — but in `main()` the value is thrown away with `(void) args.port_;` (line 308) and never assigned to `cfg.m_grpcPort`. `ApiServer::Config::m_grpcPort` (`api_server.hpp:64`) therefore always stays at its default 50051 no matter what the user passes. Users specifying `--port 50052` get a server on 50051 with no warning. (Note: this likely predates the phase, but it sits in a phase-touched file and is a live behavioral defect.)

**Fix:**

```cpp
cfg.m_grpcPort = args.port_;
```

replacing the `(void) args.port_;` line. If the port is intentionally not yet wired to `Serve()`, remove the flag from help text until it is functional.

### WR-03: New lifecycle tests hardcode /tmp paths — not portable to Windows

**File:** `test/network/test_sg_client.cpp:137, 145`
**Issue:** The tests added by plan 02-07 set `cfg.m_geniusNodeConfig.BaseWritePath = "/tmp/test-sgclient-sdk"` and `"/tmp/test-sgclient-sdk-move"`. `/tmp` does not exist on Windows, which is a supported target per the project build matrix (`build/Windows/`). CLAUDE.md forbids OS `#ifdef` guards, so the test as written cannot be fixed with a platform branch — it needs a portable temp path. If any code path (now or later) creates that directory during construction, the test fails on Windows.

**Fix:** Use `std::filesystem::temp_directory_path()` (C++17, portable):

```cpp
cfg.m_geniusNodeConfig.BaseWritePath =
    ( std::filesystem::temp_directory_path() / "test-sgclient-sdk" ).string();
```

Requires `#include <filesystem>` at the top of the test file.

## Info

### IN-01: Stale @file header names a different source file

**File:** `src/main.cpp:2`
**Issue:** The Doxygen header reads `@file genius_chat.cpp` but the file is `main.cpp`. Mismatched `@file` tags break Doxygen's file-page association.
**Fix:** Change to `@file main.cpp`.

### IN-02: "./sdk" default duplicated in three places

**File:** `src/main.cpp:54, 130` (also `src/api/api_server.hpp:71`, `src/network/sg_client/super_genius_client.hpp:61`)
**Issue:** The SG base-path default `"./sdk"` is now a string literal in `Args::m_sgBasePath`, again in the config-load guard `args.m_sgBasePath == "./sdk"`, again as `ApiServer::Config::m_sgSdkBasePath`'s default, and again inside `SGClient::Config`'s default `GeniusNodeConfig`. Since the `--sg-sdk-path` CLI flag was removed in this phase, `m_sgBasePath` can only ever hold `"./sdk"` or the JSON value — the equality guard at line 130 is dead weight, and four copies of the literal invite drift (the project convention is named `constexpr` constants, no magic values).
**Fix:** Introduce one shared constant (e.g. `inline constexpr const char* kDefaultSgBasePath = "./sdk";` near the other SG defaults in `super_genius_client.hpp`) and reference it from all four sites; drop the redundant equality guard in `LoadConfigFile`.

### IN-03: Timing-based assertion with magic numbers in result-collector test

**File:** `test/network/test_sg_client.cpp:76-81, 90`
**Issue:** `EXPECT_LE( elapsed, std::chrono::seconds( 3 ) )` and `future.wait_for( std::chrono::seconds( 3 ) )` use bare literals `1`, `3`, `120` throughout the file. The values are timeout bounds rather than sleeps (so the no-`sleep_for` rule is not violated), but the project's no-magic-numbers rule applies to tests as well, and the 3-second upper bound is a flakiness surface on a heavily loaded CI machine.
**Fix:** Hoist to named constants at file scope, e.g. `constexpr auto kShortPollTimeout = std::chrono::seconds( 1 );` and `constexpr auto kPollCompletionSlack = std::chrono::seconds( 3 );`.

---

_Reviewed: 2026-08-09_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
