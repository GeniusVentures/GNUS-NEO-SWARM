<!-- GSD: generated 2026-06-17 -->
# Architecture

## System Overview

GNUS NEO SWARM is a decentralized peer-to-peer inference engine that orchestrates specialist nano language models (NLMs) into emergent ultra-smart intelligence. The `ApiServer` class is the composition root — it owns all subsystems and wires them together during `Initialize()`.

Three execution modes are supported:

| Mode | Path | Use Case |
|------|------|----------|
| **single** | `ApiServer → Core LLM → Response` | Simple queries, one model handles everything |
| **specialist** | `ApiServer → Router → Core + Specialist → Response` | Domain-specific routing (grammar, math) |
| **swarm** | `ApiServer → Router → Broadcast → [Nodes] → Consensus → Response` | Full P2P distributed inference |

## Component Diagram

```
┌─────────────────────────────────────────────────────────┐
│                      ApiServer                          │
│                    (composition root)                    │
├──────────┬──────────┬──────────┬──────────┬─────────────┤
│  Router  │  Core    │ Security │ Network  │ Reputation  │
│          │  Engine  │          │          │             │
├──────────┼──────────┼──────────┼──────────┼─────────────┤
│ RuleBased│ MNN Inf  │ NodeId   │ P2PNode  │ WeightedCon │
│ Router   │ Engine   │ Message  │ SuperGen │ RepScoring  │
│          │ FP4Codec │ Signing  │ iusClient│ RepStorage  │
│          │ Tokenize │ KeyEnc   │ ResultAg │ RepCRDT     │
├──────────┴──────────┴──────────┴──────────┴─────────────┤
│  Specialists          │  Knowledge                      │
│  GrammarSpecialist    │  KnowledgeRetrieval              │
│  MathSpecialist       │  ContextInjection                │
│                       │  FactValidation                  │
└───────────────────────┴──────────────────────────────────┘
```

## Data Flow

1. **Entry** — `main.cpp` parses CLI args, creates `ApiServer::Config`, calls `Initialize()`
2. **Identity** — `NodeIdentity` loads or generates a secp256k1 keypair, derives `PeerId`
3. **Routing** — `RuleBasedRouter` analyzes the `Task` and produces a `RouteDecision`
4. **Knowledge** — `KnowledgeRetrieval` fetches relevant facts; `ContextInjection` augments the prompt
5. **Inference** — One of three runners executes:
   - `RunSingleNode()` — core MNN engine processes directly
   - `RunSpecialist()` — delegates to `GrammarSpecialist` or `MathSpecialist`
   - `RunSwarm()` — broadcasts via `P2PNode`, collects results, runs `WeightedConsensus`
6. **Validation** — `FactValidation` checks output against knowledge base
7. **Reputation** — `ReputationScoring` updates peer scores; `ReputationStorage` persists to RocksDB

## Key Abstractions

| Interface | File | Role |
|-----------|------|------|
| `InferenceEngine` | `src/core/engine/inference_engine.hpp` | Abstract inference backend (MNN, SGProcessing) |
| `IRouter` | `src/router/rule_based_router.hpp` | Task routing decisions |
| `ISpecialist` | `src/specialists/grammar_specialist.hpp` | Domain-specific model interface |
| `P2PNode` | `src/network/p2p_node.hpp` | Peer-to-peer networking |
| `SuperGeniusClient` | `src/network/` | gRPC client to SuperGenius blockchain compute |
| `WeightedConsensus` | `src/reputation/weighted_consensus.hpp` | Multi-node result consensus |
| `NodeIdentity` | `src/security/node_identity.hpp` | Cryptographic identity management |
| `KnowledgeRetrieval` | `src/knowledge/knowledge_retrieval.hpp` | Fact lookup and retrieval |

## Directory Structure

```
src/
├── api/              # ApiServer — composition root, gRPC service
├── common/           # Shared types, error codes, logging (spdlog)
├── core/             # MNN inference engine, FP4 codec, tokenizer, SGProcessing bridge
│   ├── engine/       # MNNInferenceEngine — cross-platform inference
│   ├── fp4/          # FP4 ultra-quantized codec
│   ├── tokenizer/    # SentencePiece / whitespace tokenizer
│   └── sgprocessing/ # SGProcessingManager bridge
├── knowledge/        # Knowledge base: retrieval, context injection, fact validation
├── network/          # P2P networking (libp2p), SuperGenius gRPC client
├── reputation/       # Peer reputation: CRDT, scoring, storage (RocksDB)
├── router/           # Rule-based task routing
├── security/         # secp256k1 identity, message signing, AES-256-GCM key encryption
└── specialists/      # Domain-specific nano language models
```

## Build System

Each module is a static CMake library (`neoswarm_<module>`). The dependency graph flows upward:

```
neoswarm_common (base types, logging)
    ↑
neoswarm_security (crypto identity)
    ↑
neoswarm_core (inference engine)
    ↑
neoswarm_router, neoswarm_reputation, neoswarm_knowledge, neoswarm_specialists
    ↑
neoswarm_network (P2P, SuperGenius client)
    ↑
neoswarm_api (composition root)
    ↑
neo-swarm (main executable)
```

## Platform Support

| Platform | Build Dir | Notes |
|----------|-----------|-------|
| macOS | `build/OSX/` | MoltenVK for GPU acceleration |
| Linux | `build/Linux/` | Native Vulkan |
| Windows | `build/Windows/` | MSVC + Ninja |
| Android | `build/Android/` | Cross-compiled |
| iOS | `build/iOS/` | Cross-compiled, MoltenVK |

## Thirdparty Dependencies

All dependencies are pre-built in `thirdparty/` for each platform. Key libraries:

- **MNN** — Inference engine (cross-platform, Vulkan GPU support)
- **libp2p** — P2P networking
- **protobuf** — Serialization (SGProcessing, SuperGenius gRPC)
- **OpenSSL** — TLS for SuperGenius connections
- **secp256k1** — Cryptographic identity
- **RocksDB** — Reputation persistence
- **spdlog + fmt** — Logging
- **nlohmann/json** — JSON config parsing
- **Boost** — ASIO, outcome, various utilities
