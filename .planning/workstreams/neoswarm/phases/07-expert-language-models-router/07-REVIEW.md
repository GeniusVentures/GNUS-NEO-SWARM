---
phase: 07-expert-language-models-router
reviewed: 2026-07-16T00:00:00Z
depth: standard
files_reviewed: 5
files_reviewed_list:
  - src/elm/i_elm.hpp
  - src/elm/CMakeLists.txt
  - src/elm/elm_stub.cpp
  - src/common/types.hpp
  - src/CMakeLists.txt
findings:
  critical: 0
  warning: 1
  info: 7
  total: 8
status: issues_found
---

# Phase 07: Code Review Report — Wave 1 (ELM Core Types & Interface)

**Reviewed:** 2026-07-16
**Depth:** standard
**Files Reviewed:** 5
**Status:** issues_found (1 warning, 7 info — zero critical)

## Summary

Reviewed Phase 7 Wave 1 deliverables: the `IELM` abstract interface (`src/elm/i_elm.hpp`), new ELM core types in `src/common/types.hpp` (`ELMRole`, `ELMContext`, `ChainStep`, `ExecutionChain`, `ExecutionMode::ElmAssisted`, and two new `PromptFeatures` flags), the `neoswarm_elm` CMake library target, the compile-time verification stub, and the parent CMakeLists addition.

**Overall assessment:** Wave 1 is structurally sound. The `IELM` interface correctly delivers all 6 pure virtuals per decision D-05, mirrors the existing `ISpecialist` pattern, and has correct virtual destructor, const-correctness, and Doxygen. The new types in `types.hpp` honor decisions D-08 (types in common/types.hpp) and D-09 (flat chain with DAG-extensible struct shape). CMake is consistent with existing module conventions. No blockers for merge.

**Key concern (WR-01):** The `Process()` method has a redundant double-accounting of the previous step's output — it arrives as both the `input` parameter and `context.m_lastOutput`. This creates a synchronization burden on callers and ambiguity for ELM implementers. Should be resolved before Waves 2–6 add real implementations.

---

## Warnings

### WR-01: Redundant `m_lastOutput` in `ELMContext` vs `Process()` input parameter

**File:** `src/common/types.hpp:159` and `src/elm/i_elm.hpp:50`

**Issue:** The `Process()` method signature receives the previous step's output through two channels — the explicit `input` parameter (`const std::string& input`) and the context field `ELMContext::m_lastOutput`. The chain executor (per D-13: "output of each step feeds the next via ELMContext") must set `ctx.m_lastOutput` before each call so the two are always equal, creating a silent invariant that callers are responsible for maintaining.

If a future chain executor or test harness passes `context.m_lastOutput` that differs from the `input` argument, ELM implementations have no way to determine which is authoritative. Similarly, ELM implementers in Waves 2–6 have an ambiguous contract: should they use `input` or `context.m_lastOutput`?

**Recommended resolution — pick one of:**

1. **Remove `m_lastOutput` from ELMContext** — let the `input` parameter carry the previous output exclusively. Simplest fix, preserves the Process signature, removes the redundancy. The chain executor updates its own local variable for the next iteration, not the context struct.
   ```cpp
   // ELMContext without m_lastOutput:
   struct ELMContext
   {
       std::string m_originalTask;
       std::vector<std::pair<ELMRole, float>> m_stepConfidences;
       std::vector<KnowledgeFact> m_groundingFacts;
   };
   ```
2. **Remove the `input` parameter** — let Process read from `context.m_lastOutput`. Requires changing `context` from `const ELMContext&` to `ELMContext&` (the ELM should not mutate it, but the chain executor mutates it between calls anyway). Less clean — adds mutability to the context.
3. **Keep both but add a runtime assertion** — `assert(input == context.m_lastOutput)` in a debug build of Process. Least disruptive but hides a design smell.

**Recommendation:** Option 1 (remove `m_lastOutput`). It's the cleanest and incurs the smallest contract change. The chain executor maintains its own `std::string lastOutput` local variable; `ELMContext` carries only the aggregate state (original task, confidence history, grounding facts).

---

## Info

### IN-01: Pre-existing naming inconsistency — `PromptFeatures` uses underscore suffix instead of `m_` prefix

**File:** `src/common/types.hpp:103-108`

**Issue:** `PromptFeatures` fields use trailing-underscore naming (`numeric_density_`, `has_code_syntax_`, `complexity_`, `token_count_`, `has_math_keywords_`, `has_grammar_request_`) rather than the project-standard `m_` prefix. The two new Phase 7 fields (`has_grounding_request_`, `has_formatting_request_` at lines 109–110) correctly follow the pre-existing local convention for consistency.

**Fix (pre-existing; not this PR's scope):** Rename all `PromptFeatures` fields to `m_` prefix in a separate cleanup pass.

### IN-02: Pre-existing naming inconsistency — `RouteDecision::confidence_` uses underscore suffix

**File:** `src/common/types.hpp:93`

**Issue:** `RouteDecision::confidence_` uses trailing underscore instead of `m_` prefix. `m_reasoning` and `m_mode` in the same struct correctly use `m_`.

**Fix (pre-existing; not this PR's scope):** Rename to `m_confidence` in a separate cleanup pass.

### IN-03: Pre-existing naming inconsistency — `NodeOutput::reputation_` uses underscore suffix

**File:** `src/common/types.hpp:122`

**Issue:** `NodeOutput::reputation_` uses trailing underscore instead of `m_` prefix. All other fields in the struct (`m_nodeId`, `m_output`, `m_perplexity`, `m_latencyMs`) correctly use `m_`.

**Fix (pre-existing; not this PR's scope):** Rename to `m_reputation` in a separate cleanup pass.

### IN-04: No `noexcept` on `IELM` pure virtual methods

**File:** `src/elm/i_elm.hpp:29,32,35,42,50,56`

**Issue:** Per CLAUDE.md — "All functions should be declared noexcept unless explicitly required to throw." None of the 6 `IELM` pure virtual methods are marked `noexcept`. However, this is consistent with the existing `ISpecialist` and `IRouter` interfaces, which also omit `noexcept`. The project-wide convention appears to rely on `outcome::result<T>` for error handling rather than `noexcept` annotations on virtual methods.

**Fix (project-wide, not this PR's scope):** If the team wants to enforce the `noexcept` guideline, add it across all interface hierarchies simultaneously so callers don't get inconsistent guarantees.

### IN-05: `ELMContext` does not retain outputs of prior chain steps beyond the last one

**File:** `src/common/types.hpp:158-162`

**Issue:** `m_stepConfidences` records per-step confidence scores but not per-step *outputs*. For chains longer than 2 steps, an ELM can see the immediately prior step's output (via the `input` parameter) but not earlier steps' outputs. For example, in a `Planner → Draft → Verifier → Refiner` chain, the Refiner sees the Verifier's output but not the Planner's plan or the Draft's raw text.

This is a deliberate Phase 7 constraint per decision D-09 (flat sequential chain) and is not a bug. However, if any Wave 2–6 ELM needs cross-step context (e.g., the Verifier comparing the Draft against the Planner's plan), this limitation will surface.

**Fix (future enhancement):** Add `std::vector<std::pair<ELMRole, std::string>> m_stepOutputs` to ELMContext when needed. Not required for Phase 7.

### IN-06: Comment confusion — `ExecutionMode::ElmAssisted` value is 3 but comment says "Mode 2"

**File:** `src/common/types.hpp:26`

**Issue:** 
```cpp
ElmAssisted = 3 ///< Mode 2 (doc 07 §9.2) — ELM-assisted sequential chain (Phase 7+)
```
The comment calls this "Mode 2" but the numeric value is 3. In the execution-mode numbering scheme, 0=SingleNode (Mode 1), 1=Specialist (Mode 2), 2=Swarm (Mode 3), 3=ElmAssisted. The "Mode 2" in the comment refers to this being a variant of the Specialist (Mode 2) sequential pattern, not the numeric enum value. The doc reference disambiguates, but a quick read is confusing.

**Fix:** Clarify comment: `///< ELM-assisted sequential chain — extends Mode 2 Specialist pattern (doc 07 §9.2, Phase 7+)`

### IN-07: Missing debug-only runtime invariant check between `input` and `context.m_lastOutput`

**File:** `src/elm/elm_stub.cpp:25-30`

**Issue:** The compile-time verification stub only checks that `sizeof(IELM)` compiles. If WR-01 is resolved by keeping both `input` and `m_lastOutput` (option 3), adding a runtime invariant assertion in a debug build of the stub (or a dedicated test) would catch caller mistakes early:
```cpp
#include <cassert>
// ...
static_assert(sizeof(sgns::neoswarm::elm::IELM) > 0, "IELM must be instantiable");
```
The current `sizeof` check does validate template instantiation but `static_assert` with a message string would be more self-documenting.

**Fix:** Replace `static_cast<void>(sizeof(...))` with `static_assert(sizeof(...) > 0, "...")` for better diagnostics. Alternatively, add a dedicated `static_assert` elsewhere — the stub's purpose is satisfied either way.

---

_Reviewed: 2026-07-16_
_Reviewer: OpenCode (gsd-code-reviewer)_
_Depth: standard_

---

## Follow-up Review — PR #105 (commit 4c02a1f)

**Reviewed:** 2026-07-24
**Depth:** standard
**Files Reviewed:** 15
**Files Reviewed List:**
- cmake/CommonBuildParameters.cmake
- src/api/api_server.cpp
- src/api/api_server.hpp
- src/common/error.cpp
- src/common/error.hpp
- src/core/CMakeLists.txt
- src/core/sgprocessing/sg_processing_bridge.cpp
- src/elm/domain_elm.cpp
- src/elm/role_elm.cpp
- src/main.cpp
- src/network/CMakeLists.txt
- src/network/sg_client/super_genius_client.cpp
- src/network/sg_client/super_genius_client.hpp
- test/elm/test_elm.cpp

**Findings:**
- critical: 2
- warning: 4
- info: 3
- total: 9

**Status:** issues_found

### Summary

PR #105 closes three gaps from the Phase 7 Wave 2 work: (1) ELM `Process()` now fails closed with a dedicated `Error::NotLoaded` instead of leaking through `ModelLoadFailed` / `InternalError`; (2) the SGClient → GeniusSDK boundary was re-plumbed for the new 2-arg `GeniusSDKInit(base_path, dev_config_json)` signature; (3) CMake switches three raw `*.a` globs to real imported targets via `find_package(libp2p / ipfs-bitswap-cpp / ipfs-lite-cpp CONFIG REQUIRED)`.

The structural changes are correct in isolation — verified against `SuperGenius/src/account/TokenID.hpp`, `GeniusSDK/include/GeniusSDK.h` (2-arg `GeniusSDKInit`), `GeniusSDK/src/GeniusSDK.cpp::ParseDevConfig` (expects `Address` / `Cut` / `TokenValue` / `TokenID` JSON keys), and `SGProcessingManager/include/processingbase/ProcessingManager.hpp` (4-arg `Process`). However, two defects in the integration must be fixed before merge: an unguarded `find_package(... REQUIRED)` block now hard-fails configure on machines without thirdparty builds, and the dev-config JSON is built with raw string concatenation without escaping, which produces malformed JSON whenever a config string contains a quote, backslash, or control character.

---

### Critical Issues

#### CR-01: Unguarded `find_package(... REQUIRED)` for libp2p / ipfs-bitswap-cpp / ipfs-lite-cpp breaks offline-configure fallback

**File:** `cmake/CommonBuildParameters.cmake:360-370`

**Issue:** Three new `find_package(... CONFIG REQUIRED PATHS ...)` calls are executed **unconditionally**, before the (now-removed) `if(SUPERGENIUS_BUILD_DIR AND NOT "${SUPERGENIUS_BUILD_DIR}" STREQUAL "")` guard that previously wrapped all SuperGenius / GeniusSDK resolution. Prior to this PR, a developer without the thirdparty build tree could still configure the project (SuperGenius lookup was skipped, the build continued with stubs, ELM-only paths compiled). After this PR, `find_package(... REQUIRED)` halts configure with a fatal error if `${THIRDPARTY_BUILD_DIR}/libp2p/lib/cmake/libp2p/libp2p-config.cmake` (etc.) is absent.

This violates the graceful-degradation contract implied by the rest of `CommonBuildParameters.cmake` (e.g., the `if(NOT SuperGenius_FOUND) message(STATUS ...)` fallback at line 412, and the `GeniusSDK cmake config not found` warning lower in the file). It also violates the project rule that "If a library is missing, fail at CMake configure time **with a clear error message**" — `find_package`'s default "Could not find a package configuration file" diagnostic does not tell the user *why* the package is required or that it can be made optional by disabling network mode.

Concrete reproduction: on a fresh clone, `cmake ..` in `build/OSX/Debug` with no `THIRDPARTY_BUILD_DIR` populated previously configured (with warnings). It now hard-fails.

**Fix:**
Either guard the three calls so they only run when the consumer targets will actually be linked, or demote to `QUIET` + a single explicit fatal check inside the block that needs them:

```cmake
# Only resolve if sgprocessing is enabled (i.e. the imported targets will be consumed).
set(_NEOSWARM_NEED_IPFS_TARGETS OFF)
if(EXISTS "${PROJECT_SUPER_ROOT}/SuperGenius/SGProcessingManager/include/processingbase/ProcessingManager.hpp")
    set(_NEOSWARM_NEED_IPFS_TARGETS ON)
endif()

if(_NEOSWARM_NEED_IPFS_TARGETS)
    find_package(libp2p CONFIG QUIET
        PATHS "${THIRDPARTY_BUILD_DIR}/libp2p/lib/cmake/libp2p" NO_DEFAULT_PATH)
    find_package(ipfs-bitswap-cpp CONFIG QUIET
        PATHS "${THIRDPARTY_BUILD_DIR}/ipfs-bitswap-cpp/lib/cmake/ipfs-bitswap-cpp" NO_DEFAULT_PATH)
    find_package(ipfs-lite-cpp CONFIG QUIET
        PATHS "${THIRDPARTY_BUILD_DIR}/ipfs-lite-cpp/lib/cmake/ipfs-lite-cpp" NO_DEFAULT_PATH)
    if(NOT libp2p_FOUND OR NOT ipfs-bitswap-cpp_FOUND OR NOT ipfs-lite-cpp_FOUND)
        message(FATAL_ERROR
            "NEO-SWARM: sgprocessing requires libp2p, ipfs-bitswap-cpp, and ipfs-lite-cpp "
            "from thirdparty. Build thirdparty first (see README.md → Building the Project), "
            "or disable sgprocessing.")
    endif()
endif()
```

If the project has already committed to "sgprocessing is always required," then the same `FATAL_ERROR` should be raised, but with an actionable message — the current `find_package` default diagnostic is not actionable.

---

#### CR-02: `devConfigJson` built with raw string concatenation — no JSON escaping of `Addr` / `Cut` / `TokenValueInGNUS`

**File:** `src/network/sg_client/super_genius_client.cpp:56-64`

**Issue:** The dev-config JSON is constructed by naive string concatenation:

```cpp
const std::string devConfigJson = std::string( "{" )
    + "\"Address\":\""   + nodeCfg.Addr             + "\","
    + "\"Cut\":\""        + nodeCfg.Cut              + "\","
    + "\"TokenValue\":\"" + nodeCfg.TokenValueInGNUS + "\","
    + "\"TokenID\":\""    + nodeCfg.TokenID.ToHex()  + "\"}";
```

`Addr`, `Cut`, and `TokenValueInGNUS` are user-configurable strings (`ApiServer::Config` → `SGClient::Config::m_geniusNodeConfig`). If any contains a double quote, backslash, newline, or other control character, the produced JSON is malformed and `GeniusSDK`'s `ParseDevConfig` (`GeniusSDK/src/GeniusSDK.cpp:91-99`) returns "Parse error" — causing `GeniusSDKInit` to return `nullptr`, which this code then maps to the generic `Error::NetworkError`. The actual cause (malformed JSON produced by us) is invisible to the operator.

Worse, an attacker who can influence these strings (e.g., via a config file read from disk or a CLI argument that later lands in this struct) could craft a value that produces valid-but-unintended JSON, e.g. `Addr = "0xabc\",\"Address\":\"0xevil` — the parser's `HasMember("Address")` check uses the last-seen member in many JSON parsers (RapidJSON keeps the first, but the intent is still subverted). This is a classic injection-style risk.

`GeniusNodeConfig::TokenID.ToHex()` is safe (always 64 lowercase hex chars from a fixed 32-byte buffer) — the vulnerability is confined to the three `std::string` fields.

**Fix:** Use a JSON library to serialize. The project already links RapidJSON (via GeniusSDK's transitive deps) and Boost.JSON is in the thirdparty tree:

```cpp
#include <boost/json.hpp>
// ...
const auto& nodeCfg = m_impl->m_cfg.m_geniusNodeConfig;
const boost::json::object devCfgObj{
    { "Address",    nodeCfg.Addr },
    { "Cut",        nodeCfg.Cut },
    { "TokenValue", nodeCfg.TokenValueInGNUS },
    { "TokenID",    nodeCfg.TokenID.ToHex() }
};
const std::string devConfigJson = boost::json::serialize( devCfgObj );
```

If pulling a JSON library into this translation unit is undesirable, at minimum escape the strings:

```cpp
auto escapeJson = []( const std::string& in )
{
    std::string out;
    out.reserve( in.size() + 8 );
    for ( char c : in )
    {
        switch ( c )
        {
            case '"':  out += "\\\""; break;
            case '\\': out += "\\\\"; break;
            case '\b': out += "\\b";  break;
            case '\f': out += "\\f";  break;
            case '\n': out += "\\n";  break;
            case '\r': out += "\\r";  break;
            case '\t': out += "\\t";  break;
            default:
                if ( static_cast<unsigned char>( c ) < 0x20 )
                {
                    char buf[8];
                    std::snprintf( buf, sizeof( buf ), "\\u%04x", c );
                    out += buf;
                }
                else
                {
                    out += c;
                }
        }
    }
    return out;
};
```

The library approach is preferred (fewer hand-rolled paths to get wrong).

---

### Warnings

#### WR-01: Hardcoded placeholder values `"0xcafe"`, `"0.65"`, `"1.0"` are not valid production defaults

**File:** `src/network/sg_client/super_genius_client.hpp:49`

**Issue:** The default-constructed `GeniusNodeConfig` uses:
- `Addr = "0xcafe"` — not a valid Ethereum address (a real one is `0x` + 40 hex chars). When `GeniusNode::SetPayoutAddress` or any code path that consumes `dev_config_.Addr` runs, it will receive garbage. The SDK does not reject this at `ParseDevConfig` time (only checks `IsString()`), so the bad value flows into payout / transaction code.
- `Cut = "0.65"` and `TokenValueInGNUS = "1.0"` — bare numeric strings without validation. If these flow into fixed-point parsers, malformed values will throw or produce undefined conversion results.
- Magic numbers per project rule: even though these are strings, the "no magic numbers" rule applies in spirit — these should be `constexpr` named constants or (better) required-from-caller with no defaults.

**Fix:** Remove the default initializer and force callers (ApiServer, tests) to provide real values:

```cpp
struct Config
{
    GeniusNodeConfig m_geniusNodeConfig;                // caller must populate
    std::chrono::seconds m_resultTimeout{ kDefaultResultTimeoutSec };
};
```

…with `inline constexpr std::chrono::seconds kDefaultResultTimeoutSec{ 300 };` at namespace scope. Then in `api_server.cpp`, surface the values from `ApiServer::Config` (or `main.cpp` CLI) instead of leaving them as SDK-library defaults. At minimum, define the placeholders as named constants and document that they are placeholder-only:

```cpp
inline constexpr const char* kPlaceholderPayoutAddr = "0xcafe"; // TODO Phase 7 Wave 3: real default
```

#### WR-02: `m_resultTimeout{ 300 }` — magic number

**File:** `src/network/sg_client/super_genius_client.hpp:50`

**Issue:** `std::chrono::seconds m_resultTimeout{ 300 };` — `300` is a magic number. Project rule: "NEVER use magic numbers. All numeric literals must be named constants using `constexpr` with `kCamelCase` naming (e.g., `kMaxRetryCount = 3`, `kDefaultPort = 3000`)."

**Fix:**
```cpp
inline constexpr unsigned int kDefaultResultTimeoutSeconds = 300; // 5 minutes

struct Config
{
    GeniusNodeConfig m_geniusNodeConfig{ /* ... */ };
    std::chrono::seconds m_resultTimeout{ kDefaultResultTimeoutSeconds };
};
```

#### WR-03: `_MISSING_DEPS` still stubs `ipfs-pubsub` while sibling IPFS targets are real

**File:** `cmake/CommonBuildParameters.cmake:381-405`

**Issue:** This PR removes `ipfs-lite-cpp::*` stubs (now satisfied by the real `find_package(ipfs-lite-cpp)`), but keeps the bare-name stub `ipfs-pubsub` (no namespace) alongside real namespaced imports. The strategy is now mixed: `ipfs-bitswap-cpp` and `ipfs-lite-cpp` are real, `ipfs-pubsub` is still a stub. If `sgns::genius_node`'s link interface ever consumes `ipfs-pubsub::*` symbols (not the bare `ipfs-pubsub`), the stub will silently swallow the dependency instead of failing the link. This masks real configuration drift.

Additionally, the surviving stub list contains targets that arguably *should* be real now that we have `find_package(libp2p)` and the rest — `Boost::json` and `Boost::unit_test_framework` in particular are available from any Boost installation, and stubbing them here could hide a missing Boost from configure output.

**Fix:** Add `find_package(ipfs-pubsub CONFIG ...)` (matching the pattern used for the other three), and remove `ipfs-pubsub` from `_MISSING_DEPS`. Audit the remaining stubs — any that can be promoted to real packages should be.

#### WR-04: Removed `if(SUPERGENIUS_BUILD_DIR)` guard causes `find_package(SuperGenius)` to run with garbage path

**File:** `cmake/CommonBuildParameters.cmake:407-419`

**Issue:** Prior code wrapped the SuperGenius lookup in `if(SUPERGENIUS_BUILD_DIR AND NOT "${SUPERGENIUS_BUILD_DIR}" STREQUAL "")`. After this PR, that guard is gone. When `SUPERGENIUS_BUILD_DIR` is unset (auto-detection at lines 377-390 also failed), the code still executes:

```cmake
set(SuperGenius_DIR "${SUPERGENIUS_BUILD_DIR}/SuperGenius/lib/cmake/SuperGenius/" CACHE PATH ...)
find_package(SuperGenius CONFIG QUIET)
```

`SUPERGENIUS_BUILD_DIR` expands to the empty string, producing `SuperGenius_DIR = "/SuperGenius/lib/cmake/SuperGenius/"` — a path at the filesystem root. `find_package` then silently searches a nonsense directory before falling through to the second `find_package` with the same empty base. This is harmless in practice (`QUIET` swallows the miss) but wasteful, confusing in trace output, and a regression from the previously explicit "skip if not configured" branch. The trailing `else()` arm that logged "SuperGenius not configured" is also gone — users now get no signal at all when SuperGenius was skipped.

**Fix:** Restore the guard around the SuperGenius block, or at least gate the `find_package` call:

```cmake
if(SUPERGENIUS_BUILD_DIR AND NOT "${SUPERGENIUS_BUILD_DIR}" STREQUAL "")
    # ... stubs + find_package(SuperGenius) ...
else()
    message(STATUS "SuperGenius not configured — GeniusSDK targets may have unresolved dependencies")
endif()
```

---

### Info

#### IN-01: `Error::NotLoaded = 21` conflates "not yet loaded" with "engine became null after load"

**File:** `src/elm/role_elm.cpp:133-137` and `src/elm/domain_elm.cpp:136-140`

**Issue:** The pre-existing code distinguished two failure states:
- `!m_loaded` → `ModelLoadFailed` (caller never called `Load()`, or `Load()` returned failure)
- `m_loaded && !engine` → `InternalError` (engine pointer became null after a successful load — a real invariant violation)

The new code maps both to `NotLoaded`. While `NotLoaded` is a better fit for the first case, it's a worse fit for the second: an engine that goes null *after* `Load()` succeeded is not "not loaded" — it's an internal inconsistency that should be loud. Operators triaging by error code will now see `NotLoaded` and reach for the "reload the model" playbook, when the actual fix is "find why the engine reset."

**Fix:** Keep `Error::NotLoaded` for the `!m_loaded` branch, but use `Error::InternalError` (or a new `Error::EngineLost`) for the post-load null-engine branch. The header comment for `NotLoaded` at `error.hpp:49` should also be tightened: `"ELM/ engine not loaded — cannot process"` is ambiguous; suggest `"Load() not called or returned failure — cannot process"`.

#### IN-02: Default `sgns::TokenID{}` is invalid (`valid_ = false`) but `ToHex()` still emits 64 zeros

**File:** `src/network/sg_client/super_genius_client.hpp:49` (via `SuperGenius/src/account/TokenID.hpp:44, 185-193`)

**Issue:** `sgns::TokenID{}` default-constructs with `valid_ = false`. `ToHex()` unconditionally serializes `data_` (32 zero bytes) → 64 zero hex chars. This accidentally satisfies the GeniusSDK parser's "exactly 64 hex digits" requirement and parses back as a *valid* all-zero `TokenID` (which `IsGNUS()` then reports as the GNUS token). The round-trip silently upgrades an invalid TokenID into a valid one — a subtle contract violation.

In practice this works ("GNUS token by default" is the intended semantic per `IsGNUS()`), but it relies on the implicit "invalid → zeros → parses as GNUS" chain. A future refactor that makes `ToHex()` validity-aware (e.g., returns empty string for invalid IDs) will silently break this call site.

**Fix:** Add a comment at the call site explaining the intent:

```cpp
// Default TokenID{} is invalid, but its ToHex() emits 64 zeros, which
// ParseDevConfig interprets as the GNUS token (IsGNUS()). Keep in sync
// with SuperGenius TokenID semantics.
sgns::TokenID TokenID;
```

…or construct explicitly: `sgns::TokenID::FromBytes( std::initializer_list<uint8_t>{ 0x00 } )`.

#### IN-03: Field-name mismatch — `m_sgSdkBasePath` no longer reflects its purpose

**File:** `src/api/api_server.hpp:69`, `src/api/api_server.cpp:277`, `src/main.cpp:77,203,313`

**Issue:** After this PR, `ApiServer::Config::m_sgSdkBasePath` is fed into `GeniusNodeConfig::BaseWritePath`. The CLI flag `--sg-sdk-path` is the only way to set it. The naming is now stale on both ends:
- The field is named `SdkBasePath` but is consumed as `BaseWritePath` (a write-path, not an SDK-install path).
- The CLI flag is `--sg-sdk-path` but the value lands in a write-path slot.

The Phase 2 plan (`.planning/workstreams/neoswarm/phases/02-supergenius-connectivity/02-06-PLAN.md:189`) already called for renaming `--sg-sdk-path` → `--sg-base-path` — that work was never executed. This PR makes the drift more visible by removing the parallel `--sg-base-port` flag (whose only purpose was to feed the now-deleted 4-arg `GeniusSDKInit`), without completing the rename.

**Fix:** Either execute the Phase 2 rename in a follow-up PR (rename `m_sgSdkBasePath` → `m_sgBasePath` and `--sg-sdk-path` → `--sg-base-path`), or update the field comment to acknowledge the dual naming:

```cpp
/// SDK data / write directory (CLI flag: --sg-sdk-path — retained for
/// backward compatibility; a future cleanup will rename to --sg-base-path).
std::string m_sgSdkBasePath = "./sdk";
```

---

_Reviewed: 2026-07-24_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
