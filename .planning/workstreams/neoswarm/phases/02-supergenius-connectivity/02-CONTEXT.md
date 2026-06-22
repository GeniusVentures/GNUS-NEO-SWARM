# Phase 2: SuperGenius Connectivity - Context

**Gathered:** 2026-05-28
**Status:** Ready for planning

<domain>
## Phase Boundary

The engine dispatches inference jobs to the SuperGenius blockchain compute network via TLS-protected, authenticated PubSub-based gRPC. A new `SuperGeniusClient` component in `src/network/sg_client/` bridges the local engine to the external SuperGenius process. Requires Phase 1 (real secp256k1 identity and message signing) to be complete.

This phase covers the network dispatch path only — local inference via `SubmitDirect` already works. The Flutter UI, streaming output, and swarm P2P are separate phases.
</domain>

<decisions>
## Implementation Decisions

### SuperGeniusClient API Surface
- **D-01:** Separate component in `src/network/sg_client/` with 6 files: `SuperGeniusClient.hpp/.cpp`, `SGChannelManager.hpp/.cpp`, `SGJobSubmitter.hpp/.cpp`, `SGResultCollector.hpp/.cpp`, `SGMessageAuthenticator.hpp/.cpp`
- **D-02:** Sync execution model — `SubmitJob(json) → outcome::result<vector<uint8_t>>`, blocking with condition_variable timeout (matches existing `ResultAggregation` pattern)
- **D-03:** `SGProcessingBridge` becomes a thin dispatch router: `network_mode_ ? client_->SubmitJob(json) : SubmitDirect(json)`

### gRPC Channel & Connection Management
- **D-04:** Single persistent gRPC channel per node with HTTP/2 multiplexing, reused across all jobs (not per-job connections)
- **D-05:** Exponential backoff reconnect: 1s → 2s → 4s → 8s → max 30s between attempts
- **D-06:** Eager connect at `GeniusAPIServer::Initialize()` — fail-fast if SuperGenius is unreachable at startup (fail-close philosophy from Phase 1)
- **D-07:** Health exposed via `GeniusSlmGetStatus()` with `supergenius_connected: bool` and `fallback_active: bool` fields; detailed logs for diagnostics

### Error Handling & Fallback Behavior
- **D-08:** Auto-fallback to local MNN inference (`SubmitDirect`) when SuperGenius is unreachable
- **D-09:** 3 retries with exponential backoff for gRPC transient errors (UNAVAILABLE, DEADLINE_EXCEEDED). Auth failures (PERMISSION_DENIED, UNAUTHENTICATED) fail immediately — no retry
- **D-10:** Operator visibility via `GeniusSlmGetStatus()` — Flutter UI can show "Connected to GNUS Network" badge or "Local Mode" fallback indicator

### TLS & Endpoint Configuration
- **D-11:** `--sg-endpoint <host:port>` CLI flag, default `localhost:50051`
- **D-12:** TLS required for non-localhost endpoints. Localhost allowed insecure with `warn`-level log message. Production: `--sg-tls-ca /etc/gnus/ca.pem`
- **D-13:** `--sg-tls-ca <path>` and `--sg-tls-cert <path>` CLI flags for TLS configuration. gRPC uses `grpc::SslCredentials()` from CA bundle

### OpenCode's Discretion
- Exact PubSub message format (derived from SuperGenius proto definitions)
- gRPC keepalive interval and timeout values
- Channel reconnect state machine implementation details
- `TaskResult` struct fields beyond raw bytes
- Integration test approach against local SuperGenius node
</decisions>

<canonical_refs>
## Canonical References

Downstream agents MUST read these before planning or implementing.

### Requirements
- `.planning/REQUIREMENTS.md` § SuperGenius Connectivity — SG-01 through SG-05

### Architecture
- `.planning/research/ARCHITECTURE.md` — Full production architecture, SuperGeniusClient design, 25-step data flow diagram, component boundaries
- `.planning/research/SUMMARY.md` § Architecture Approach — Design decisions: PubSub, persistent channel, timeout-bounded collection

### SuperGenius Interface
- `../SuperGenius/gRPCForSuperGenius/openapi_yaml/SuperGenius-OpenAPI.yaml` — SuperGenius gRPC service definitions
- `../SuperGenius/gRPCForSuperGenius/` — Compiled gRPC stubs for C++ client

### Existing Code
- `src/core/sgprocessing/SGProcessingBridge.hpp` — Current bridge interface, `SubmitNetwork()` stub at line 340
- `src/core/sgprocessing/SGProcessingBridge.cpp` — `SubmitDirect` implementation, `BuildSchemaJson()`, `SubmitNetwork` stub
- `src/security/NodeIdentity.hpp` — Key generation, sign/verify (hardened in Phase 1)
- `src/security/MessageSigning.hpp` — Payload signing, nonce+timestamp replay protection (hardened in Phase 1)
- `src/api/GeniusAPIServer.hpp` — Orchestration façade, `Config` struct where channel config must integrate
- `src/genius_node.cpp` — CLI args parser where `--sg-endpoint`, `--sg-tls-ca`, `--sg-tls-cert` must be added

### Pitfalls
- `.planning/research/PITFALLS.md` § gRPC — Default-insecure channels, TLS enforcement, replay protection requirements
</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `SGProcessingBridge::BuildSchemaJson()` — Already produces GNUS-compliant JSON schema; SuperGeniusClient receives this directly
- `SGProcessingBridge::SubmitDirect()` — Local path implementation pattern for `SubmitNetwork()` to mirror
- `ResultAggregation` (`src/network/ResultAggregation.cpp`) — Sync timeout-bounded collection via condition_variable; same pattern for collecting PubSub results
- `NodeIdentity::Sign()` + `MessageSigning::Sign()` — Already hardened with RFC6979 nonces; SuperGeniusClient authenticates every Job via these

### Established Patterns
- All subsystem initialization flows through `GeniusAPIServer::Initialize()` — connect SuperGeniusClient there
- CLI args parsed in `src/genius_node.cpp` via manual `ParseArgs()` — add new flags there
- Config structs with sensible defaults (`Config{...}`) — match this for `SuperGeniusClient::Config`
- `outcome::result<T>` + `BOOST_OUTCOME_TRY` for all error propagation
- C++17, Allman bracing, 4-space indent, noexcept, unique_ptr ownership

### Integration Points
- `SGProcessingBridge::SubmitNetwork()` at `src/core/sgprocessing/SGProcessingBridge.cpp:340` — the stub to replace
- `SGProcessingBridge::Config::network_mode_` at `src/core/sgprocessing/SGProcessingBridge.hpp:38` — already exists, controls dispatch path
- `GeniusAPIServer::Config` — add `sg_endpoint_`, `sg_tls_ca_`, `sg_tls_cert_` fields
- `src/genius_node.cpp` `Args` struct — add `sg_endpoint_`, `sg_tls_ca_`, `sg_tls_cert_` fields
- `src/genius_slm_chat_c.cpp` `GeniusSlmGetStatus()` — add connectivity fields to status JSON
</code_context>

<specifics>
## Specific Ideas

- SuperGenius uses PubSub room-based dispatch (`GossipPubSub`), NOT simple unary gRPC — the first implementation must join the grid channel, publish signed Task messages, and subscribe to per-job result channels
- Every Task message must carry a secp256k1 signature so SuperGenius can map the public key to an on-chain identity
- Result collection pattern should match the existing `ResultAggregation::Collect()` — condition_variable + timeout, no async callbacks
- The engine should never crash or hang if SuperGenius is unreachable — graceful degradation to local mode is the expected behavior
</specifics>

<deferred>
## Deferred Ideas

- Full libp2p P2P swarm (GossipSub, mDNS, DHT) — Phase 2 routes through SuperGenius gRPC only
- Escrow/staking integration with GNUS token — future milestone
- Multi-SuperGenius-node load balancing — single node for this milestone
- gRPC reflection and service discovery — hardcoded endpoint for now
</deferred>

---
*Phase: 02-supergenius-connectivity*
*Context gathered: 2026-05-28*
