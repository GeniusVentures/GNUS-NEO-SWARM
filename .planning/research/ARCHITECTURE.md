# Production Architecture: GNUS NEO SWARM → SuperGenius Dispatch

**Domain:** Decentralized AI inference engine with blockchain compute network dispatch
**Researched:** 2026-05-28
**Confidence:** HIGH (primary sources: actual codebase + SuperGenius proto definitions + gRPC official docs)

## Executive Summary

The production architecture bridges two existing systems: **GNUS NEO SWARM** (local AI inference engine) and **SuperGenius** (blockchain compute network with distributed processing). The SuperGenius processing subsystem uses a PubSub room-based model (not simple client-server gRPC), defined in `SGProcessing.proto` and `SGProcessing-OpenAPI.yaml`. Neo Swarm must adopt this model: open a persistent gRPC channel, join processing grid channels, publish signed `Task` messages, and subscribe to result channels for `TaskResult` messages.

The security layer (secp256k1 `NodeIdentity` + `MessageSigning`) must authenticate every inference submission so SuperGenius can reward the submitting node on-chain. The existing stub-based paths (`MessageSigning::Verify` always `true`, `SubmitNetwork` returns `NotImplemented`) must be converted to production implementations.

## Recommended Architecture

### Production System Overview

```
┌──────────────────────────────────────────────────────────────────────────────────┐
│                              Entry Points                                          │
│  CLI (neo-swarm)                          Flutter FFI (Genius-MOS-SLM-FFI)        │
├──────────────────────────────────────────────────────────────────────────────────┤
│                          GeniusAPIServer (Façade — unchanged)                      │
├──────────┬────────────┬──────────────┬────────────┬────────────┬─────────────────┤
│  Router  │ Core Engine│ Specialists  │ Reputation │  Network   │  Knowledge      │
│ (same)   │ MNNInfer-  │ (post-proc)  │ RocksDB    │ P2PNode    │ TF-IDF stub     │
│          │ enceEngine │              │ persist.   │ libp2p     │                 │
│          │ SGProcess- │              │ CRDT sync  │ (Future)   │                 │
│          │ ingBridge  │              │            │            │                 │
│          │   ↓        │              │            │            │                 │
│          │ ┌──────────┴──────────────┴────────────┴────────────┴─────────────────┤
│          │ │                    NEW: SuperGeniusClient                            │
│          │ │  Channel Manager │ Job Submitter │ Result Collector │ Identity Auth  │
│          │ └───────────────────┬─────────────────────────────────────────────────┤
├──────────┴─────────────────────┼─────────────────────────────────────────────────┤
│                    Security Layer (HARDENED — real secp256k1)                      │
│  NodeIdentity (key gen/save/load/sign/verify)  MessageSigning (attach/verify)     │
├────────────────────────────────┼─────────────────────────────────────────────────┤
│                          Common / Types                                            │
└────────────────────────────────┼─────────────────────────────────────────────────┘
                                 │  gRPC channel + GossipPubSub
                                 ▼
┌──────────────────────────────────────────────────────────────────────────────────┐
│                          SuperGenius (external process)                            │
│  ┌────────────────────┐    ┌─────────────────────┐    ┌───────────────────────┐   │
│  │ gRPCForSuperGenius │    │ ProcessingServiceImpl│    │ ProcessingNode(s)     │   │
│  │ (account ops, etc) │    │ Grid channel coord   │    │ SubTask queue+engine  │   │
│  └────────────────────┘    └─────────────────────┘    └───────────────────────┘   │
│  ┌────────────────────────────────────────────────────────────────────────────┐  │
│  │                        GNUS Blockchain Network                              │  │
│  │  On-chain identity → reputation → escrow → reward distribution             │  │
│  └────────────────────────────────────────────────────────────────────────────┘  │
└──────────────────────────────────────────────────────────────────────────────────┘
```

### Component Boundaries (Production)

| Component | Responsibility | Communicates With | New/Existing |
|-----------|---------------|-------------------|--------------|
| `GeniusAPIServer` | Orchestration Façade — owns all subsystems, unchanged API | Router, Core, Specialists, Reputation, Network, Knowledge, Security | Existing (no changes) |
| `MNNInferenceEngine` | Local LLM inference via MNN + Metal/Vulkan | Tokenizer, FP4Codec, SGProcessingBridge | Existing (enhanced) |
| `SGProcessingBridge` | Dispatch router — routes to local SGProcessingManager OR `SuperGeniusClient` | SGProcessingManager (local), SuperGeniusClient (network) | **Refactored** |
| `SuperGeniusClient` | **NEW** — manages all SuperGenius network communication | SGProcessingBridge, Security layer, SuperGenius (external) | **NEW** |
| `TensorInterpreter` | Converts raw tensor bytes → human-readable text | SGProcessingBridge output | Existing (unchanged) |
| `NodeIdentity` | secp256k1 keypair generation, PeerId derivation, sign/verify | SuperGeniusClient, MessageSigning | Existing (**hardened**) |
| `MessageSigning` | Payload signing, signature attachment to JSON, verification+strip | SuperGeniusClient, NodeIdentity | Existing (**hardened**) |
| `ReputationStorage` | RocksDB-backed reputation persistence | ReputationScoring, Consensus | Existing (RocksDB enabled) |
| `P2PNode` | libp2p swarm communication (deferred) | Swarm mode nodes | Existing (stub, deferred) |

### Detailed Component: `SuperGeniusClient` (NEW)

This is the critical new component. It encapsulates all communication with the SuperGenius blockchain compute network.

```
src/network/sg_client/
├── SuperGeniusClient.hpp        # Public interface
├── SuperGeniusClient.cpp        # Implementation
├── SGChannelManager.hpp/.cpp    # gRPC channel lifecycle (create, keepalive, reconnect)
├── SGJobSubmitter.hpp/.cpp      # Publish Task messages to grid channel
├── SGResultCollector.hpp/.cpp   # Subscribe to result channel, timeout-bounded collection
└── SGMessageAuthenticator.hpp/.cpp # Sign payloads with NodeIdentity, verify results
```

**SuperGeniusClient Interface:**
```cpp
class SuperGeniusClient {
public:
    struct Config {
        std::string endpoint_ = "localhost:50051";  // SuperGenius node address
        std::chrono::seconds channel_timeout_{30};
        std::chrono::seconds result_timeout_{300};  // 5 min for inference
    };

    outcome::result<void> Initialize(const NodeIdentity &identity);
    outcome::result<void> Connect();                    // Create channel, join grid room
    outcome::result<std::string> SubmitJob(
        const std::string &gnusSchemaJson,              // From BuildSchemaJson()
        const std::string &resultsChannel                // Channel to receive results on
    );
    outcome::result<TaskResult> WaitForResult(
        const std::string &taskId,
        std::chrono::seconds timeout
    );
    void Disconnect();

private:
    // Channel management
    std::shared_ptr<grpc::Channel> channel_;
    std::shared_ptr<SGChannelManager> channel_manager_;

    // PubSub overlay
    std::shared_ptr<SGJobSubmitter> job_submitter_;
    std::shared_ptr<SGResultCollector> result_collector_;
    std::shared_ptr<SGMessageAuthenticator> authenticator_;
};
```

**Key Design Decisions:**

1. **PubSub, not Unary gRPC:** SuperGenius uses room-based GossipPubSub for processing. Neo Swarm must join the grid room, publish `Task` messages, and subscribe to `TaskResult` messages. A unary gRPC call would bypass SuperGenius's distributed processing infrastructure (queue management, ProcessingNode coordination, result aggregation).

2. **Channel Reuse:** Open one persistent gRPC channel to SuperGenius with HTTP/2 multiplexing and keepalive PING. Reuse across multiple inference jobs.

3. **Result Channels Per-Job:** Each inference job specifies a unique `results_channel` in the `Task` message (e.g., `results/<taskId>`). The result collector subscribes to that specific channel.

### Data Flow: Production Inference Network Path

```
Step  CLI/Flutter      GeniusAPIServer   SGProcessingBridge   SuperGeniusClient     SuperGenius          GNUS Network
───   ───────────────  ────────────────  ──────────────────   ─────────────────     ───────────          ────────────
 1    Process(prompt)──→                                                                                         
 2                     Route(prompt)                                                                             
 3                     network mode?                                                                             
 4                     AugmentPrompt()                                                                           
 5                     ──────────────→ SubmitJob(model_uri, input_uri, format, shape, ioc)                       
 6                                      BuildSchemaJson() → GNUS_Schema JSON                                    
 7                                      network_mode_? YES                                                      
 8                                      ─────────────────→ SubmitNetwork(gnus_schema_json)                       
 9                                                          auth = Sign(gnus_schema_json)                        
10                                                          Task{json_data=json, results_channel=results/<id>}   
11                                                          Publish(grid_channel, Task)                          
12                                                                               → ProcessingServiceImpl         
13                                                                                 OnMessage(Task)               
14                                                                                 Create ProcessingNode         
15                                                                                 Split into SubTasks            
16                                                                                 Distribute to nodes           
17                                                                             ←  ProcessingEngine.Process()     
18                                                                                 Aggregate SubTaskResults       
19                                                                                 Publish(results/<id>, TaskResult)
20                                                          OnResult(results/<id>) ←                              
21                                                          Verify(result.signature)                            
22                                      ←────────────────  TaskResult (raw bytes)                                
23                                      TensorInterpreter → text                                                 
24                   ←────────────────  GeniusResponse                                                          
25                   UpdateReputation()                                                                           
26  ← GeniusResponse                                                                                              
```

### Security Integration: Identity + Signing in Dispatch Pipeline

The secp256k1 identity authenticates Neo Swarm nodes to the SuperGenius network, enabling on-chain reward distribution.

**Authentication Flow:**

```
Node Startup:
  NodeIdentity::LoadFromFile("node.key") → secp256k1 keypair
  PeerId = SHA-256(compressed_pub_key) → "a1b2...f3e4"
  
Job Submission:
  GNUS_Schema JSON = BuildSchemaJson(model, input, format, shape)
  signature = MessageSigning::Sign(GNUS_Schema JSON)
  signed_payload = AttachSignature(GNUS_Schema JSON) → JSON with "sig" field
  
  SGProcessing::Task task;
  task.json_data = signed_payload;    // Contains GNUS Schema + signature
  task.results_channel = "results/" + task_id;
  task.escrow_path = "/escrow/" + task_id;
  
  Publish to grid channel → SuperGenius receives signed task

SuperGenius Side (existing ProcessingServiceImpl):
  OnMessage(Task) → Extract pub_key_hex from signature metadata
  Verify signature against on-chain identity → Authenticate node
  Begin ProcessingNode distributed computation
  
  On processing complete:
  TaskResult contains SubtaskResult array with node_address fields
  Results published to results_channel
  
  On-chain reward distribution:
  Map pub_key_hex → account on GNUS blockchain
  Escrow settlement triggers reward transfer
```

**Implementation: SGMessageAuthenticator**

```cpp
class SGMessageAuthenticator {
public:
    explicit SGMessageAuthenticator(const NodeIdentity &identity);

    // Sign a GNUS Schema JSON payload and attach the signature
    outcome::result<std::string> SignPayload(const std::string &jsonPayload);

    // Verify a result payload from SuperGenius
    outcome::result<void> VerifyResult(
        const std::string &signedPayload,
        const std::string &expectedPubKeyHex
    );

private:
    const NodeIdentity &identity_;
    MessageSigning signer_;  // Wraps identity_
};
```

**Note on `MessageSigning::AttachSignature`:** The existing implementation already provides JSON signature attachment — it appends a `"sig"` field to the JSON payload containing the DER-encoded signature. The `VerifyAndStrip` method validates and removes the signature. This existing pattern is the correct production pattern — enable it by fixing the stub (Task 2.2).

## Patterns to Follow

### Pattern 1: gRPC Channel + MetadataCredentials for Identity

**What:** Use gRPC's `MetadataCredentialsPlugin` to attach the node's PeerId and signature to every gRPC call as metadata headers.

**When:** Every call to SuperGenius (room join, broadcast, subscribe).

**Example:**
```cpp
class NodeIdentityCredentialsPlugin : public grpc::MetadataCredentialsPlugin {
public:
    NodeIdentityCredentialsPlugin(const NodeIdentity &identity)
        : identity_(identity) {}

    grpc::Status GetMetadata(
        grpc::string_ref /*service_url*/,
        grpc::string_ref /*method_name*/,
        const grpc::AuthContext &/*channel_auth_context*/,
        std::multimap<grpc::string, grpc::string> *metadata) override
    {
        metadata->insert({"x-node-peer-id", identity_.PeerId()});
        metadata->insert({"x-node-pub-key", PubKeyToHex(identity_.PublicKey())});
        return grpc::Status::OK;
    }

private:
    const NodeIdentity &identity_;
};
```

### Pattern 2: Timeout-Bounded Result Collection

**What:** Subscribe to the result channel with a deadline. Collect `SubTaskResult` messages. When all subtasks complete or timeout fires, aggregate and return.

**When:** After publishing a `Task`, call `WaitForResult(taskId, timeout)`.

**Why not the existing `ResultAggregation`:** The existing `ResultAggregation` is designed for libp2p swarm mode (multiple peer responses). For SuperGenius, we collect a single aggregated `TaskResult` from the results channel. However, the timeout-bounded collection pattern is similar — use `std::condition_variable` + `wait_for`.

### Pattern 3: Connection Resilience (Keepalive + Reconnect)

**What:** gRPC channels use HTTP/2 PING keepalive (detect dead connections in seconds, not minutes). On connection failure, reconnect with exponential backoff.

**When:** `SuperGeniusClient::Connect()` sets up keepalive parameters. `SGChannelManager` handles reconnection.

**gRPC Keepalive Configuration (C++):**
```cpp
grpc::ChannelArguments args;
args.SetInt(GRPC_ARG_KEEPALIVE_TIME_MS, 10000);          // PING every 10s
args.SetInt(GRPC_ARG_KEEPALIVE_TIMEOUT_MS, 3000);         // Wait 3s for PING ACK
args.SetInt(GRPC_ARG_KEEPALIVE_PERMIT_WITHOUT_CALLS, 1);  // Allow PING on idle
args.SetInt(GRPC_ARG_HTTP2_MAX_PINGS_WITHOUT_DATA, 0);    // Unlimited PINGs
```

### Pattern 4: Single Process, Multiple Submission Queues

**What:** `SGProcessingBridge::SubmitNetwork` is inherently asynchronous — the job is submitted to SuperGenius and results arrive later via PubSub. The bridge should not block the calling thread. Instead, it returns immediately with a `task_id` and the caller polls or waits.

**Implementation approach:**
- `SubmitNetwork` returns `outcome::result<std::string>` (the `task_id`)
- Caller calls `WaitForResult(task_id, timeout)` to block for the result
- Internally, `SuperGeniusClient` maintains a `map<task_id, promise<TaskResult>>`

**Why not async callbacks:** C++17 coroutines are permitted per the project's coding standards but Boost.Asio coroutines require C++20. Use the simpler promise/future pattern with `std::condition_variable`.

## Anti-Patterns to Avoid

### Anti-Pattern 1: Unary gRPC Call for Long-Running Inference

**What:** Using a simple `Infer(request) → InferResponse` unary RPC to submit inference jobs to SuperGenius.

**Why bad:** Inference jobs take seconds to minutes (Mistral-7B token generation). A unary gRPC call would block the HTTP/2 stream for the entire duration, waste resources, and break if the connection drops mid-inference. It also bypasses SuperGenius's distributed processing infrastructure (queue management, node coordination).

**Instead:** Use the PubSub pattern: publish a `Task` message, subscribe to the `results_channel`, collect `TaskResult`. This is exactly what SuperGenius's `ProcessingServiceImpl` expects.

### Anti-Pattern 2: New Connection Per Job

**What:** Creating a new gRPC channel for each inference job submission.

**Why bad:** TCP+TLS handshake overhead per job adds 100-500ms latency. HTTP/2 connection coalescing is wasted. Connection limits on the SuperGenius side become a bottleneck.

**Instead:** Create a single persistent channel at startup. Use it for all jobs. gRPC multiplexes concurrent RPCs over the same HTTP/2 connection.

### Anti-Pattern 3: Unsigned Messages to SuperGenius

**What:** Sending Task messages without secp256k1 signatures.

**Why bad:** SuperGenius cannot authenticate the submitting node. No on-chain identity mapping. No escrow, no reward distribution. A malicious node could inject fake jobs.

**Instead:** Every `Task` message must include a signature (via the existing `MessageSigning::AttachSignature` pattern). SuperGenius maps the public key to an on-chain identity before processing.

### Anti-Pattern 4: Blocking the Inference Pipeline on Network

**What:** `GeniusAPIServer::Process()` blocks waiting for `SubmitNetwork` to complete (which can take 30-300 seconds for inference).

**Why bad:** The existing architecture is single-threaded — one request at a time. Blocking on network inference makes the entire server unresponsive.

**Instead (short-term):** Document that `Process()` is blocking (acceptable for CLI single-shot mode). Add a configurable `timeout_` parameter.

**Instead (long-term/future):** Add a worker thread pool. `Process()` returns immediately with a `task_id`. Caller polls `GetResult(task_id)`. This requires architectural changes to GeniusAPIServer.

## Scalability Considerations

| Concern | At 1 Node (Local) | At 10 Nodes (SuperGenius) | At 100+ Nodes |
|---------|-------------------|---------------------------|---------------|
| Connection management | Single gRPC channel to SuperGenius | Keepalive PINGs catch dead nodes; exponential backoff reconnect | SuperGenius load balances ProcessingNodes internally |
| Job throughput | Sequential (single-threaded server) | Multiple concurrent jobs via PubSub | Bounded by SuperGenius grid capacity |
| Result collection | Direct `Process()` call | Single result channel subscription per job | Multiple concurrent subscriptions to different `results/<id>` channels |
| Security | Local identity, no network auth needed | Signed messages, key verification on SuperGenius side | On-chain identity mapping enables permissioned access |
| Reputation | Local RocksDB storage | Reputation scores synced via CRDT over PubSub | On-chain reputation tracks submission quality |

## Suggested Build Order (Dependency Graph)

```
Phase 1: SECURITY HARDENING ───────────────────── (prerequisite for all network ops)
  │  Task 2.1: Enable secp256k1 → real NodeIdentity
  │  Task 2.2: Fix MessageSigning::Verify → real signature verification
  │  Task 6.1: Add security tests → key gen, sign/verify roundtrip, tamper detection
  │
  ▼
Phase 2: SUPERGENIUS CLIENT ───────────────────── (core network component)
  │  Create src/network/sg_client/SuperGeniusClient.hpp/.cpp
  │  Create SGChannelManager (channel lifecycle, keepalive)
  │  Create SGJobSubmitter (publish Task to grid channel)
  │  Create SGResultCollector (subscribe to result channel)
  │  Create SGMessageAuthenticator (sign payloads with identity)
  │  Task 4.2: Add --sg-endpoint CLI flag
  │
  ▼
Phase 3: BRIDGE INTEGRATION ───────────────────── (wire existing Bridge to new Client)
  │  SGProcessingBridge::Config: add endpoint_, result_timeout_
  │  SGProcessingBridge::SubmitNetwork(): call SuperGeniusClient::SubmitJob + WaitForResult
  │  Replace Error::NotImplemented with real implementation
  │  Wire GENIUS_HAS_SGPROCESSING guard for compile-time optionality
  │
  ▼
Phase 4: PERSISTENCE ──────────────────────────── (survive restarts)
  │  Task 3.1: Link RocksDB → real ReputationStorage
  │  Task 3.2: Fix Deserialize crash → try/catch stod/stoull
  │
  ▼
Phase 5: FIXES & INTEGRATION ──────────────────── (production polish)
  │  Task 5.1: Remove hardcoded vocab size 32000
  │  Task 5.2: Fix GeniusSlmInit re-init bug
  │  Task 6.2: FFI layer tests
  │  Task 6.4: Network integration tests (with SuperGenius test node)
  │  Task 5.3: Config file support (YAML)
  │
  ▼
Phase 6: FLUTTER UI ───────────────────────────── (end-user experience)
  │  Task 7.1: Wire Flutter to real dylib on device
  │  Task 7.2: Streaming token output (future)
```

**Dependency rationale:**
- Security hardening MUST come first — every network message needs a valid signature
- SuperGeniusClient can be developed in parallel with Phase 4 (persistence) since they don't share code
- Bridge integration depends on both Security (Phase 1) and SuperGeniusClient (Phase 2)
- Fixes and integration tests should gate the production release

## Sources

| Source | Type | Confidence |
|--------|------|------------|
| `src/core/sgprocessing/SGProcessingBridge.cpp` — actual SubmitNetwork stub | Primary (code) | HIGH |
| `SuperGenius/src/processing/proto/SGProcessing.proto` — Task/SubTask/TaskResult definitions | Primary (code) | HIGH |
| `SuperGenius/src/processing/processing_service.hpp` — ProcessingServiceImpl architecture | Primary (code) | HIGH |
| `SuperGenius/gRPCForSuperGenius/openapi_yaml/SGProcessing-OpenAPI.yaml` — PubSub room API | Primary (code) | HIGH |
| `proto/genius_api.proto` — Neo Swarm client-facing gRPC definitions | Primary (code) | HIGH |
| `proto/genius_internal.proto` — Inter-node task/result messages with signature field | Primary (code) | HIGH |
| `src/security/MessageSigning.hpp/.cpp` — existing AttachSignature/VerifyAndStrip pattern | Primary (code) | HIGH |
| `src/security/NodeIdentity.cpp` — existing secp256k1 Sign/Verify implementation | Primary (code) | HIGH |
| `grpc.io/docs/guides/auth/` — MetadataCredentialsPlugin pattern for custom auth | Official doc | HIGH |
| `grpc.io/blog/grpc-on-http2/` — gRPC channel/keepalive/connection management | Official doc | HIGH |
| `grpc.io/docs/guides/interceptors/` — Interceptor patterns for auth logging | Official doc | HIGH |
| `AgentDocs/PRODUCTION_ROADMAP.md` — Phase 2, Phase 4 tasks confirming architecture intent | Project doc | HIGH |
