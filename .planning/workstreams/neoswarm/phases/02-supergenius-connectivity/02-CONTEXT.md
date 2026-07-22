# Phase 2: SuperGenius Connectivity - Context

**Gathered:** 2026-06-30
**Status:** Ready for planning

<domain>
## Phase Boundary

Wire GeniusSDK in-process so every NEO-SWARM node links the SDK directly. No remote endpoint, no gRPC channel management — everything is P2P always. `SGProcessingBridge::SubmitNetwork()` dispatches signed inference jobs via `GeniusSDKProcess()` and collects results via `GeniusSDKGetProcessingStatus()` polling.

PR #79 (Wave 1, merged) already refactored `SGClient` from gRPC to GeniusSDK headers. This context replans Waves 2+ to match the SDK API instead of the original gRPC-based architecture.
</domain>

<decisions>
## Implementation Decisions

### SGChannelManager — Dead Code Removal
- **D-01:** Delete `src/network/sg_client/sg_channel_manager.hpp` and `sg_channel_manager.cpp` entirely. The SDK handles all P2P internally — gRPC channel lifecycle is obsolete.
- **D-02:** Remove `sg_channel_manager` from `src/network/CMakeLists.txt`.

### Identity Mapping — NodeIdentity → GeniusSDK
- **D-03:** Derive the Ethereum private key from NodeIdentity. Add `GetPrivateKey()` getter returning `const PrivKey&` (32 bytes).
- **D-04:** `SGClient::Initialize()` hex-encodes the private key and passes it to `GeniusSDKInitWithKey()`. No separate `--sg-eth-key` flag — single source of truth.
- **D-05:** Same secp256k1 private key is used for both node P2P identity (PeerId via SHA-256) and blockchain identity (ETH address via keccak256).

### Result Collection — Polling Model
- **D-06:** Poll `GeniusSDKGetProcessingStatus()` with exponential backoff: 100ms → 200ms → 400ms → 800ms → max 1s. Wrapped in `condition_variable::wait_for` with 120s deadline.
- **D-07:** Completion signal: `status == GENIUS_PR_STATUS_IDLE` after having been `PROCESSING`. Status changes from PROCESSING → IDLE indicate job finished.
- **D-08:** **Open question for Wave 2 research:** The SDK header has no API for retrieving completed inference results. Investigate whether results arrive via the transaction layer (`GetInTransactions()`) or if a result-retrieval API is planned. Fallback: log results unavailable until SDK exposes them.

### Config Surface — JSON Config + CLI Overrides
- **D-09:** SDK configuration lives in the existing `--config <path>` JSON file. CLI flags override config values.
- **D-10:** CLI flags: `--sg-base-path <path>` (default `./sdk`) and `--sg-port <n>` (default `40001`).
- **D-11:** Remove obsolete gRPC flags: `--sg-endpoint`, `--sg-tls-ca`, `--sg-tls-cert`.
- **D-12:** `SGClient::Config` fields: `m_sdkBasePath`, `m_basePort`, `m_autoDht` (default true), `m_enableProcessing` (default true). Ethereum key derived from NodeIdentity, not a config field.

### OpenCode's Discretion
- Exact exponential backoff constants and deadline value
- Polling loop implementation details (max iterations, edge cases)
- Where to place `GetPrivateKey()` in NodeIdentity (public section, const-qualified)
- Hex-encoding helper placement (inline in SGClient or utility function)
</decisions>

<specifics>
## Specific Ideas

- "Every NEO-SWARM node links GeniusSDK in-process — no API-like calls, everything is P2P always"
- Node key file (`node.key`) is the single identity for both P2P and blockchain
- Graceful degradation: if SDK init fails or processing times out, fall back to local MNN inference (`SubmitDirect`)
- `GeniusElmGetStatus()` should expose `supergenius_connected: bool` and `fallback_active: bool`
</specifics>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### SDK API
- `../GeniusSDK/src/GeniusSDK.h` — Complete C FFI API: init, process, status, shutdown, balance, transactions
- `../GeniusSDK/example/SDKExample.cpp` — Reference usage: init pattern, config prompting, processing loop
- `../GeniusSDK/example/SDKIdleExample.cpp` — Minimal init + idle loop pattern

### Requirements
- `.planning/workstreams/neoswarm/REQUIREMENTS.md` — SG-01 through SG-05

### Architecture
- `.planning/workstreams/neoswarm/ROADMAP.md` § Phase 2 — Success criteria, phase dependencies
- `.planning/workstreams/neoswarm/codebase/ARCHITECTURE.md` — System overview, component responsibilities
- `.planning/workstreams/neoswarm/codebase/INTEGRATIONS.md` — External APIs, GeniusSDK integration patterns

### Existing Code
- `src/network/sg_client/super_genius_client.hpp` — SGClient public interface (already refactored to GeniusSDK)
- `src/network/sg_client/super_genius_client.cpp` — SGClient implementation (Initialize calls GeniusSDKInitWithKey)
- `src/network/sg_client/sg_job_submitter.hpp` — Job submission interface (to be wired to GeniusSDKProcess)
- `src/network/sg_client/sg_job_submitter.cpp` — Current implementation (stub, needs real SDK call)
- `src/network/sg_client/sg_result_collector.hpp` — Result collection interface (to be wired to polling)
- `src/network/sg_client/sg_result_collector.cpp` — Current implementation (condition_variable, needs SDK polling)
- `src/network/sg_client/sg_message_authenticator.hpp` — Message signing wrapper for Phase 1 security
- `src/security/node_identity.hpp` — NodeIdentity (needs GetPrivateKey() added)
- `src/core/sgprocessing/sg_processing_bridge.hpp` — Bridge dispatcher (SubmitNetwork stub)
- `src/core/sgprocessing/sg_processing_bridge.cpp` — Bridge implementation (network_mode_ flag)
- `src/api/api_server.hpp` — Orchestration facade, Config struct, SGClient ownership
- `src/api/api_server.cpp` — Server init, client lifecycle wiring
- `src/main.cpp` — CLI arg parsing (needs --sg-base-path, --sg-port; remove --sg-endpoint/--sg-tls-*)
</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `ResultAggregation` (`src/network/result_aggregation.hpp/.cpp`) — Sync timeout-bounded collection via condition_variable. Same pattern for SDK polling loop.
- `NodeIdentity::Generate()` / `LoadFromFile()` — Already produces 32-byte secp256k1 private key. Add getter, hex-encode, pass to SDK.
- `SGMessageAuthenticator` — Already wraps Phase 1 hardened signatures. Reused for signing job payloads before SDK dispatch.

### Established Patterns
- All subsystem init flows through `ApiServer::Initialize()` — SGClient::Initialize called there
- CLI args parsed in `main.cpp` via manual `ParseArgs()` — add `--sg-base-path`, `--sg-port` there
- Config structs with sensible defaults (`Config{...}`) — match for SGClient::Config
- `outcome::result<T>` + `BOOST_OUTCOME_TRY` for all error propagation
- PIMPL idiom hides heavy dependencies from headers
- C++17, Allman braces, 4-space indent, `m_` member prefix, `noexcept` by default

### Integration Points
- `SGProcessingBridge::SubmitNetwork()` — the stub to replace with real SDK dispatch
- `ApiServer::Config` — add `sg_base_path_`, `sg_port_` fields
- `main.cpp` `Args` struct — add `sg_base_path_`, `sg_port_` fields; remove `sg_endpoint_`, `sg_tls_ca_`, `sg_tls_cert_`
- `src/main.cpp` `PrintHelp()` — update help text
- Remove `sg_channel_manager` from `src/network/CMakeLists.txt`
</code_context>

<deferred>
## Deferred Ideas

- Separate `--sg-eth-key` flag for different on-chain identity — future if needed
- Multi-SuperGenius-node load balancing — single SDK node for v1
- Result retrieval API from SDK — blocked on SDK team roadmap
- gRPC-based dispatch for non-SDK environments — removed; P2P-only architecture
</deferred>

---

*Phase: 02-supergenius-connectivity*
*Context gathered: 2026-06-30*
