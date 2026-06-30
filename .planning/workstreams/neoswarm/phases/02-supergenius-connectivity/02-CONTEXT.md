# Phase 2: SuperGenius Connectivity — Context

**Gathered:** 2026-06-24 (updated from 2026-05-28)
**Status:** Ready for planning

<domain>
## Phase Boundary

The engine dispatches inference jobs to the SuperGenius blockchain compute network via **GeniusSDK** — a C shared library that internally handles gRPC transport through SuperGenius's `gRPCForSuperGenius`. GNUS-NEO-SWARM does NOT use raw gRPC — all transport goes through GeniusSDK.

The existing `SGClient` component in `src/network/sg_client/` bridges the local engine to GeniusSDK. Phase 1 (real secp256k1 identity and message signing) is complete. This phase covers wiring GeniusSDK dispatch — local inference via `SubmitDirect` already works.
</domain>

<decisions>
## Implementation Decisions

### Transport Architecture
- **D-14:** GeniusSDK is the transport. `SGClient` calls `GeniusSDKProcess(jsondata)` → the SDK internally handles gRPC to SuperGenius. Zero raw gRPC calls in GNUS-NEO-SWARM.
- **D-15:** `GeniusSDKProcess()` takes `JsonData_t` (char[2048], max 2KB). Payloads exceeding 2KB are a known constraint — decision needed on chunking or protocol change.
- **D-16:** GeniusSDK is already linked as `GeniusSDK_shared` in cmake (`CommonBuildParameters.cmake:294-310`). No new linking needed.

### SGClient API Surface (existing, partially implemented)
- **D-01:** Separate component in `src/network/sg_client/` with 5 files: `SGClient` (`super_genius_client.cpp/.hpp`), `SGChannelManager`, `SGJobSubmitter`, `SGResultCollector`, `SGMessageAuthenticator`
- **D-02:** Sync execution model — `SubmitJob(json) → outcome::result<vector<uint8_t>>`, blocking with condition_variable timeout
- **D-03:** `SGProcessingBridge` is a thin dispatch router: `m_networkMode ? SubmitNetwork(json) : SubmitDirect(json)`

### Current State of SGClient (post-refactor)
- `SGChannelManager` — IMPLEMENTED. gRPC channel, TLS, keepalive, health check, reconnect
- `SGMessageAuthenticator` — IMPLEMENTED. secp256k1 signing + nonce/timestamp replay
- `SGJobSubmitter` — STUB. Signs payload, `TODO(Phase 2): implement actual gRPC PubSub publish` → REPLACE with `GeniusSDKProcess()`
- `SGResultCollector` — STUB. `TODO(Phase 2): implement actual gRPC PubSub subscribe` → REPLACE with SDK callback or polling
- `SGClient` — PARTIAL. Orchestrates sub-components. `Connect()` creates channel, `SubmitJob()` signs + calls submitter, `Disconnect()` tears down.

### Error Handling & Fallback
- **D-08:** Auto-fallback to local MNN inference when SuperGenius unreachable
- **D-09:** GeniusSDK errors (returned as `GeniusNodeReturnValue_t`) → map to outcome Error codes. Transient errors retry; terminal errors fail immediately.
- **D-10:** `GeniusElmGetStatus()` reports `supergenius_connected` and `fallback_active`

### TLS & Endpoint Configuration (already implemented)
- **D-11:** `--sg-endpoint <host:port>` CLI flag — already parsed in `main.cpp`
- **D-12:** TLS config via `SGClient::Config` with CA/cert paths
- **D-13:** TLS fields in `ApiServer::Config` — `m_sgTlsCa`, `m_sgTlsCert`

### Open Discretion
- Exact `GeniusSDKProcess()` call pattern — how the JSON payload maps to `JsonData_t`
- Result collection through GeniusSDK — callback, polling, or condition_variable
- Timeout enforcement: SDK-level timeout vs engine-level timeout
- `GeniusSDKProcess()` error code mapping to `Error` enum
</decisions>

<canonical_refs>
## Canonical References

### Requirements
- `.planning/workstreams/neoswarm/REQUIREMENTS.md` § SuperGenius Connectivity — SG-01 through SG-05
- SG-01 (SGClient component): ✅ done
- SG-02 (SubmitNetwork): ❌ stubbed — needs GeniusSDK wiring
- SG-03 (--sg-endpoint): ✅ done
- SG-04 (TLS): ✅ done
- SG-05 (deadline): ❌ not started

### GeniusSDK Interface
- `../GeniusSDK/src/GeniusSDK.h` — C API (345 lines). Key functions:
  - `GeniusSDKProcess(JsonData_t jsondata)` → `GeniusNodeReturnValue_t` — submits JSON for processing
  - `GeniusSDKGetProcessingStatus()` → `GeniusProcessingStatusInfo` — polling-based status
  - `GeniusSDKInit(base_path, ...)` — node initialization (called by SuperGenius, not us)
  - `GeniusSDKGetNodeState()` → `GeniusNodeState_t` — node health

### Existing Code
- `src/network/sg_client/SGClient` (`super_genius_client.cpp/.hpp`) — orchestrator, already wired into ApiServer
- `src/network/sg_client/SGJobSubmitter` — signs + builds task JSON, needs `GeniusSDKProcess()` call
- `src/network/sg_client/SGResultCollector` — condition_variable wait, needs SDK result polling
- `src/core/sgprocessing/SGProcessingBridge::SubmitNetwork()` — stub at line 355, returns NetworkError
- `src/api/ApiServer::Initialize()` — creates SGClient, calls Connect(). Already wired.
- `src/main.cpp` — parses `--sg-endpoint`, `--sg-tls-ca`, `--sg-tls-cert`
- `src/genius_elm_chat_completions.cpp` `GeniusElmGetStatus()` — reports connectivity status

### Architecture Decisions
- ROADMAP.md: "Connectivity uses GeniusSDK + libp2p GossipSub pubsub, NOT raw gRPC"
- ROADMAP.md: "Transport-layer gRPC lives in SuperGenius's `gRPCForSuperGenius/`"
- STATE.md: "GeniusSDK integration pattern needs research during planning"

### Pitfalls
- `JsonData_t` is fixed 2KB — payload compression or chunking may be needed
- `GeniusSDKProcess()` return values need cross-referencing with error handling
- GeniusSDK initialization (`GeniusSDKInit`) already called by SuperGenius process — we may NOT need to call it
- Result collection pattern unclear — GeniusSDK has no async callback API visible in header
</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `SGClient` already wraps channel + authenticator + job submitter + result collector
- `SGProcessingBridge::BuildSchemaJson()` already produces GNUS-compliant JSON
- `ApiServer::Initialize()` already initializes SGClient (lines 188-213)
- `ApiServer::RunSingleNode()` already falls back to local mode when network unavailable
- `ResultAggregation` — condition_variable + timeout pattern for collection

### Integration Points (what to change)
- `SGJobSubmitter::PublishJob()` — replace `TODO(Phase 2)` with `GeniusSDKProcess(jsondata)`
- `SGResultCollector::WaitForResult()` — replace `TODO(Phase 2)` with SDK polling
- `SGProcessingBridge::SubmitNetwork()` — replace `return NetworkError` with real dispatch through SGClient
- Decision: does `SGChannelManager` become unnecessary? The SDK handles gRPC internally.

### What NOT to change
- `SGMessageAuthenticator` — signing logic is separate from transport, stays
- `ApiServer` orchestration — already wired correctly
- `BuildSchemaJson()` — JSON schema generation stays
- `SubmitDirect()` — local path untouched
</code_context>

<deferred>
## Deferred Ideas
- Full libp2p P2P swarm (GossipSub, mDNS, DHT) — already partially implemented in `P2PNode`, deferred to Phase 9
- Escrow/staking integration with GNUS token — future milestone
- Multi-SuperGenius-node load balancing — single node for this milestone
</deferred>

---
*Phase: 02-supergenius-connectivity*
*Context updated: 2026-06-24*
