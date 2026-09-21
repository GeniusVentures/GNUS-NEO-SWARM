# Plan 02-06 Summary: CLI/Config Surface Cleanup

**Phase:** 02-supergenius-connectivity
**Status:** Complete
**Requirements:** SG-02, SG-03
**Wave:** 3 (depends_on: [05])

## Scope Reassessment (plan vs. reality)

Cross-referencing the plan against the current source revealed that **most of 02-06 was already landed by 02-05 (PR #83)** or was based on stale assumptions in `02-CONTEXT.md` (D-10/D-12). The executed scope is a narrow cleanup, not the full original plan.

| 02-06 item | Disposition |
|---|---|
| Task 1 — wire `SubmitNetwork()` → `SGClient::SubmitJob()` | ✅ Already done by 02-05 (`sg_processing_bridge.cpp:358-368`) |
| Task 2a — remove `--eth-key` / `m_ethKey` | ✅ Already done by 02-05 |
| Task 3a/3c — drop `m_ethKey`, identity-based init guard | ✅ Already done by 02-05 (SDK-owned identity) |
| Task 2c/3b — add `--sg-port` / `m_sgBasePort` | ❌ **Dropped as dead code** (see below) |
| Task 2b — rename `--sg-sdk-path` → `--sg-base-path` | ✅ Done — **but as JSON key, not CLI flag** (see below) |

## What Was Built

- **`src/main.cpp`**:
  - Removed the `--sg-sdk-path` CLI flag (Args field renamed, ParseArgs branch deleted, PrintHelp line removed).
  - Renamed `Args::m_sgSdkPath` → `Args::m_sgBasePath`.
  - Renamed JSON config key `sg_sdk_path` → `sg_base_path` (kept as the per-node override, D-09).
  - Updated main() wiring: `cfg.m_sgSdkBasePath = args.m_sgBasePath;`.
- **`src/api/api_server.hpp`**: updated the stale comment on `m_sgSdkBasePath` (removed "future cleanup will rename to --sg-base-path" — that cleanup is this plan; documented the JSON `sg_base_path` override).

## Decisions / Deviations from Plan

1. **`--sg-port` / `m_sgBasePort` dropped (dead code).** The port was a vestige of the pre-02-05 connection-management design where `SGClient` dialed the SDK as a remote peer. Post-02-05 the SDK runs fully in-process and binds its own P2P port internally — SuperGenius hardcodes the seed at `GeniusNode.cpp:317-318` (`InitNetwork(40001, ...)`), overridable only via the SDK's own `network_config.json`, never via an FFI argument. `SGClient::Config` has no port field and `GeniusSDKInit(base_path, dev_config)` accepts none. There is no field anywhere in the NEO-SWARM-controlled chain for a port to land in. The future OpenAI-compatible HTTP ingress port is a separate concern (API/proxy layer, different phase).

2. **Base path removed from CLI, kept in JSON.** SuperGenius nodes and all GeniusSDK examples hardcode the base path (`./` or `./sdk`) — none expose it as a command-line argument (`SDKIdleExample.cpp:17`, `SDKExampleCredentials.cpp:5`, `SDKExample.cpp:197`). The base path is a deployment detail, not a per-run operator flag. However, NEO-SWARM's `--config` JSON file is the idiomatic multi-node override mechanism (D-09), so `sg_base_path` remains available there — each node can run with its own JSON specifying a different base path.

3. **`ApiServer::Config::m_sgSdkBasePath` field name kept.** Already correct and referenced in `api_server.cpp:277`; renaming it would be churn beyond this plan.

## Artifacts

| File | Status |
|------|--------|
| `src/main.cpp` | Modified — CLI flag removed, JSON key + field renamed |
| `src/api/api_server.hpp` | Modified — stale comment updated |

## Verification

Grep checks (all pass):
- `--sg-sdk-path`: 0 · `m_sgSdkPath`: 0 · `sg_sdk_path`: 0
- `--eth-key`: 0 · `m_ethKey` (hpp): 0
- `sg_base_path` (JSON): 2 · `m_sgBasePath`: 4
- `m_client->SubmitJob` (bridge): 1

Build: `build/OSX/Debug` — cmake exit 0, ninja exit 0 (`neo-swarm` linked clean).

Runtime: `./neo-swarm --help` no longer lists `--sg-sdk-path`; `--config` retained.

## Code Review Fix (02-REVIEW.md)

- **WR-02:** `main()` was discarding the parsed `--port` value with `(void) args.port_;` and never assigning `cfg.m_grpcPort` — now wired (`cfg.m_grpcPort = args.port_;`). Pre-existing defect in a phase-touched file.
- **IN-01:** Fixed stale Doxygen `@file genius_chat.cpp` header → `main.cpp`.

## Follow-ups

- Phase 2 has two further unexecuted plans (02-07, 02-08) to assess for the same staleness before treating Phase 2 as complete.
