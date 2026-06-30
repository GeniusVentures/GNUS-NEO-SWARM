# Feature Landscape

**Domain:** Production decentralized AI inference engine connecting to blockchain compute network
**Project:** GNUS NEO SWARM (SuperGenius ecosystem)
**Researched:** 2026-05-28
**Overall confidence:** HIGH

## Executive Summary

GNUS NEO SWARM transitions from a prototype that happens to produce real Mistral-7B text to a production-grade decentralized AI inference engine that securely connects to the SuperGenius blockchain compute network. The feature landscape divides cleanly into three tiers: table stakes without which the system is unsafe or inoperable in production, differentiators that give the GNUS ecosystem its competitive advantage over centralized AI APIs, and anti-features that would divert resources from what matters for this milestone.

This analysis is grounded in three sources: the actual codebase state (46 passing tests, all stub-mode subsystems), the validated project board issues, and the production patterns observed in Bittensor (decentralized AI), vLLM (production inference serving), and LiteLLM (AI gateway operations). The recommendation emphasizes security-first ordering — cryptographic identity and message signing before network dispatch — because connecting to a blockchain network without real authentication would be worse than not connecting at all.

## Table Stakes

Features users (node operators) and the network itself expect. Missing any one = system is unsafe, crashes in production, or fails at its core purpose.

| Feature | Why Expected | Complexity | Subsystem | Notes |
|---------|--------------|------------|-----------|-------|
| **Real LLM inference with MNN + SentencePiece** | Without real inference, there is no product. Both libraries are linked, code paths exist behind `#ifdef` guards. | Low | Engine | MNN and SentencePiece are already linked but the LLM text generation processor in SGProcessingManager is missing. The direct MNN path works; the SGProcessing path needs Issue #1 resolved. |
| **Cryptographic node identity (secp256k1)** | Every production decentralized system (Bittensor, libp2p, Ethereum) requires cryptographic identity. Nodes without real keys cannot be trusted by peers or the network. | Low | Security | Library is linked, headers included, `GENIUS_HAS_SECP256K1` definition missing. Single-line cmake fix. Already has PIMPL'd `NodeIdentity` class with Generate/Sign/Verify/PeerID. |
| **Message signing and verification** | Currently `MessageSigning::Verify()` always returns `true`. Any node can impersonate any other. This is the highest-risk security gap in the codebase — worse than no auth because it creates a false sense of security. | Medium | Security | Depends on secp256k1 enablement. Requires real `Verify` implementation calling `NodeIdentity::FromPublicKeyHex()` then `Verify()`. Must include tests for tampered signatures, wrong keys, empty signatures. |
| **gRPC network dispatch to SuperGenius** | The system's raison d'être is connecting to the SuperGenius blockchain compute network. `SubmitNetwork()` currently returns `Error::NotImplemented`. | High | SGProcessing | Requires implementing gRPC client to `gRPCForSuperGenius` (already in SuperGenius repo), adding endpoint config (`--sg-endpoint`), and handling connection lifecycle (connect, retry, timeout, disconnect). |
| **Crash-safe persistent reputation** | Reputation scores must survive restarts or the swarm has no memory of which nodes are trustworthy. `ReputationStorage::Deserialize` crashes on corrupt rows (unwrapped `std::stod`/`std::stoull` calls). | Medium | Reputation | RocksDB is linked. Need: try/catch wrappers for deserialization, corrupt-row skipping, and a test that a deliberately corrupt DB doesn't crash the process. |
| **Error handling in all production code paths** | Stub-mode systems (security, gRPC) swallow errors or return dummy values. Production code must propagate real errors to callers. | Medium | Cross-cutting | Covers: real gRPC error codes, timeout handling, connection refused, auth failure. Error codes already defined in `Error.hpp` (17 codes covering all domains). |
| **Remove hardcoded vocab size (32000)** | `SentencePieceTokenizer::VocabSize()` returns 32000 regardless of the loaded model. Logit vectors are allocated with this hardcoded size. A non-Mistral model crashes or produces garbage. | Low | Engine | Replace literal `32000` with `tokenizer_->VocabSize()` once SentencePiece is linked. |
| **Fix FFI re-init bug** | `GeniusSlmInit` resets `g_server` but `std::call_once` flag (`g_init_flag`) is never reset. Third init after a chat call leaves `g_server == nullptr`, causing crash on next chat. | Low | FFI | Remove `std::call_once`/`g_init_flag`, use simple null-check lazy init. Add test for multi-init sequence. |
| **Health/readiness endpoint** | Operators need to know if the engine is alive and capable of inference before routing traffic. Pattern seen in every production system (vLLM `/health`, Bittensor axon status, LiteLLM gateway). | Low | API | Add `/health` endpoint (or CLI equivalent) reporting model load status, key validity, gRPC connection state. |

## Differentiators

Features that set GNUS NEO SWARM apart from centralized AI APIs (OpenAI, Anthropic) and other decentralized platforms (Bittensor). These are partially implemented already; productionizing them makes the competitive advantage real.

| Feature | Value Proposition | Complexity | Subsystem | Notes |
|---------|-------------------|------------|-----------|-------|
| **Swarm routing with reputation-weighted consensus** | No single point of failure or censorship. The router (`SingleNode`/`Specialist`/`Swarm` modes) can distribute inference across multiple nodes, using reputation scores to weight their contributions. This is what makes it "decentralized" rather than "proxied." | Medium (existing) | Router | Already implemented but reputation scores are ephemeral (no RocksDB persistence). Productionizing means: persistence makes scores survive restarts, real message signing ensures score updates come from legitimate peers. |
| **CRDT-based reputation sync** | Conflict-free replicated data type for reputation scores means nodes can share trust information peer-to-peer without a central authority. Reputation converges even with network partitions. | Medium (existing) | Reputation | `ReputationCRDT` is implemented. Production-grade needs: RocksDB-backed snapshot saving/loading, merge-on-connect with peers, anti-entropy protocol for stale nodes. |
| **SGProcessing bridge for compute offload** | Separates the engine (lightweight router + tokenizer) from heavy inference (GPU-heavy MNN forward pass). Enables mobile/edge nodes to use the swarm while server nodes do the compute. | High | SGProcessing | `SGProcessingBridge` builds GNUS-schema JSON and dispatches to `SGProcessingManager`. Phase 1 (direct) works. Phase 2 (network) is the differentiator — submit work to the SuperGenius network, get results back, verify they match. |
| **FP4 v3 quantization** | 4-bit weight quantization cuts model size and memory by 4x vs FP16. This is what makes Mistral-7B runnable on consumer hardware (phones, laptops). Proprietary codec, not available in any other inference engine. | Medium | Engine | FP4 decode/encode exists. FP4_ULTRA processor in SGProcessingManager is missing (Issue #2). Without it, quantized models can't use the network dispatch path. |
| **Native Metal/Vulkan GPU acceleration** | MNN provides GPU acceleration via Metal (Apple) and Vulkan (cross-platform). Production systems need GPU for throughput; CPU inference is too slow for interactive use. | Low (existing) | Engine | Already working. MNN linked, MoltenVK linked. Production concern: GPU memory management, OOM recovery, graceful fallback to CPU. |
| **Knowledge retrieval + fact validation** | Goes beyond raw LLM generation by retrieving relevant facts and validating claims against them. This is a differentiator vs. pure LLM APIs that hallucinate with no factual ground truth. | Medium | Knowledge | TF-IDF retrieval stub exists. Fact validation with tolerance windows exists. Production: replace TF-IDF with something more accurate (not this milestone — deferred), harden validation against edge cases. |
| **Specialist post-processing (grammar, math)** | Specialist models handle grammar correction and math verification after the main LLM inference. This is a composable micro-service pattern unique to the swarm architecture. | Low (existing) | Post-processing | Already implemented. Works as a pipeline after inference. |
| **YAML/JSON config file support** | Eliminates the need to recompile for every configuration change. Operators can tune reputation coefficients, knowledge thresholds, network settings, and model paths from a config file. | Medium | Config | Covered by Issue #8. yaml-cpp is in thirdparty. CLI already supports flags; config file adds a layer. |

## Anti-Features

Features to explicitly NOT build in this milestone. These would consume resources without moving the needle on production readiness or would introduce complexity that risks delaying the real priorities.

| Anti-Feature | Why Avoid | What to Do Instead |
|--------------|-----------|-------------------|
| **Full libp2p P2P network (GossipSub, mDNS, DHT)** | Vast complexity for this milestone. The system already connects to SuperGenius via gRPC for network dispatch. P2P interconnect between swarm nodes is a Phase 3+ concern after gRPC dispatch to SuperGenius is proven. | Route all inter-node communication through SuperGenius gRPC first. libp2p skeleton code exists but should remain skeleton until gRPC path is battle-tested. |
| **OAuth / social login for swarm nodes** | Engine-level feature that belongs in the application layer (Flutter UI), not the C++ engine. The engine should authenticate nodes via secp256k1 keys, not web identities. | Node authentication via signed secp256k1 messages. UI login is a Flutter concern for a later milestone. |
| **Real-time streaming token output (SSE/WebSocket)** | UX polish. The system already returns complete responses synchronously. Streaming adds complexity (callback management, partial JSON framing, Flutter stream integration) without improving reliability or security. | Defer to UX milestone. Production system works fine with batch responses for the compute network use case. |
| **Semantic embeddings for knowledge retrieval** | TF-IDF stub works for the fact-matching use case. Replacing it with embeddings (sentence-transformers, FAISS) adds Python dependencies, model loading overhead, and an entirely new inference pipeline. | Keep TF-IDF for this milestone. Evaluate embeddings when knowledge retrieval accuracy becomes a measurable bottleneck. |
| **Multi-model hot-swapping (load/unload at runtime)** | Complexity far exceeds value for a system that primarily runs Mistral-7B. vLLM supports LoRA adapter loading but warns it's unsafe for untrusted clients. | Single-model focus. If multi-model is needed later, implement as separate SGProcessing passes, not runtime swapping. |
| **iOS/Android deployment** | macOS is the proven platform. Mobile deployment requires platform-specific build toolchains, code signing, and app store compliance that distracts from core production readiness. | macOS first. Mobile follows once the macOS production system is stable. |
| **Web dashboard / admin UI** | Another application-layer concern. The CLI (`neo-swarm`) already provides all operator functionality. | Extend CLI with more commands if needed. Dashboard is a Flutter UI project for a later milestone. |
| **Model training / fine-tuning** | GNUS NEO SWARM is an inference engine. Training is a completely different pipeline with different data requirements, compute patterns, and infrastructure. | Keep inference-only. Training belongs in a separate project or a much later milestone. |

## Feature Dependencies

```
Real LLM Inference (MNN + SentencePiece)
 └─> Secp256k1 Node Identity ──> Message Signing & Verification
      │                               │
      │                               └─> Authenticated gRPC to SuperGenius
      │                                        │
      └─> RocksDB Reputation Persistence ──> CRDT Reputation Sync
               │
               └─> Reputation-Weighted Swarm Routing

SGProcessing FP4_ULTRA Processor ──> FP4 Network Dispatch
Config File ──> All subsystems (unblocks operator testing)
Fix re-init Bug ──> FFI Tests ──> Flutter Integration
Remove Hardcoded 32000 ──> Multi-model Support
```

**Critical path (must be sequential):**
1. MNN + SentencePiece → real inference working
2. secp256k1 → node has real identity
3. MessageSigning → peers can authenticate each other
4. gRPC SubmitNetwork → authenticated dispatch to SuperGenius

**Parallelizable:**
- RocksDB persistence fixes (independent of security)
- Config file support (independent of everything)
- FFI re-init fix (independent of everything)
- Hardcoded value removal (independent, but easier after SentencePiece linked)

**Composable (can be added incrementally):**
- FP4_ULTRA processor (adds a new data type, doesn't break existing ones)
- CRDT sync (works with or without network dispatch)
- Knowledge retrieval improvements (separate pipeline)

## MVP Recommendation

### Must-complete for this milestone (P0 — blocks production):

1. **Enable secp256k1 node identity** (Issue #3) — trivial cmake fix, unlocks everything
2. **Fix MessageSigning::Verify** (Issue #4) — closes the highest-risk security gap
3. **Implement SubmitNetwork() via gRPC** (Issue #5) — the core network connectivity feature
4. **Add LLM text generation processor** (Issue #1) — enables the SGProcessing path for LLMs
5. **Fix ReputationStorage deserialize crash** (PROD-3.2) — prevents production crashes from corrupt data
6. **Fix GeniusSlmInit re-init bug** (Issue #7) — prevents crash on repeated initialization
7. **Add `--sg-endpoint` CLI flag** (PROD-4.2) — operator needs to configure where to connect
8. **Fix test linker errors** (Issue #6) — can't test what you can't build

### Should-complete for this milestone (P1 — necessary for production quality):

9. **Add FP4_ULTRA processor** (Issue #2) — unlocks quantized model dispatch
10. **Remove hardcoded vocab size 32000** (PROD-5.1) — required for any non-Mistral model
11. **Encrypt node key file at rest** (PROD-2.3) — security hardening for key storage
12. **Add config file support** (Issue #8) — operators can tune without recompiling
13. **Add security tests** (Issue: security tests) — prove Verify is fixed, key generation works

### Could-complete for this milestone (P2 — nice to have):

14. **Add FFI layer tests** — prove re-init fix works
15. **Add knowledge module tests** — prove fact validation is correct
16. **Add health/readiness endpoint** — operational observability
17. **Wire Flutter on macOS device** — end-to-end chat UI with real engine

### Deferred to subsequent milestones:

- Full P2P libp2p integration
- Streaming token output
- Semantic embeddings
- Mobile deployment
- Web dashboard
- Multi-model support beyond Mistral-7B
- Model training/fine-tuning

## Sources

### Codebase analysis (HIGH confidence)
- `PRODUCTION_ROADMAP.md` — 17 validated tasks, priority ordering, dependency chain
- `PROJECT_BOARD_ISSUES.md` — 8 validated issues with acceptance criteria
- `PROJECT.md` — architecture, current state, constraints, known issues
- `SGProcessingBridge.cpp` — Phase 2 stub confirmed (`Error::NotImplemented`)
- `MessageSigning.cpp` — always-true Verify confirmed (line 59)
- `NodeIdentity.hpp` — full secp256k1 interface ready behind PIMPL
- `Error.hpp` — 17 error codes covering all domains

### Bittensor architecture (HIGH confidence — Context7 + official docs)
- Neuron architecture: wallet-based authentication, coldkey/hotkey pattern
- Axon: FastAPI-backed HTTP server with blacklist, priority, verify per synapse
- Dendrite: client-side wallet signing for authenticated requests
- Stake-weighted sybil resistance: validators stake TAO, miners prove compute
- Source: Context7 `/latent-to/bittensor` (420 snippets), `/websites/bittensor` (7 snippets)

### vLLM production patterns (HIGH confidence — official docs)
- `/metrics` endpoint: Prometheus format with request counts, token histograms, success/abort rates
- API key authentication: Bearer token for `/v1` endpoints, unprotected endpoints warned against
- Security: reverse proxy deployment essential, inter-node communication insecure by default
- Request limits: `VLLM_MAX_N_SEQUENCES` prevents memory exhaustion attacks
- Health check: `/health` and `/ping` endpoints for orchestration
- Source: Context7 `/vllm-project/vllm` (58203 snippets), `docs.vllm.ai` security docs

### LiteLLM gateway patterns (HIGH confidence — Context7)
- Request flow: authentication → rate limiting → routing → cost tracking → logging
- Virtual keys: per-key spend tracking, budget limits, model RPM/TPM rate limiting
- Retry/fallback: model group retry policies, backup model routing
- Audit trail: `litellm-changed-by` header for accountability
- Source: Context7 `/berriai/litellm` (16015 snippets)

### Industry standards (MEDIUM confidence — synthesized from multiple sources)
- **TLS for inter-node communication** — vLLM notes internal channels are unencrypted; production systems use network isolation or mTLS sidecars
- **Circuit breakers** — all production gateways implement circuit breaking for upstream failures; prevents cascading failure
- **Graceful degradation** — stub-mode architecture already implements this pattern; production extends it to timeouts, partial results, capacity limits
