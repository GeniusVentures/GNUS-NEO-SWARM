<!-- GSD: generated 2026-06-17 -->
# GNUS NEO SWARM

**GNUS NEO SWARM** — **G**lobally **N**etworked **U**ltra-**S**mart AI · **N**ano **E**xpert **O**rchestrated · **S**pecialist **W**isdom **A**rising via **R**outed **M**icro-nodes

A fully decentralized peer-to-peer swarm where a micro LLM router orchestrates specialist nano language models into emergent ultra-smart intelligence. Runs real MNN inference on consumer hardware, connected to the SuperGenius blockchain compute network for distributed AI.

## Architecture

The engine is a C++17 application with these core modules:

| Module | Purpose |
|--------|---------|
| `api` | REST/gRPC API server — the composition root |
| `router` | Intelligent task routing to specialist models |
| `specialists` | Domain-specific nano language models (grammar, math, etc.) |
| `core` | MNN inference engine, FP4 codec, tokenizer, SGProcessing bridge |
| `network` | P2P networking via libp2p |
| `security` | secp256k1 node identity, message signing, key encryption |
| `reputation` | Peer reputation tracking and scoring |
| `knowledge` | Knowledge base integration (Grokipedia facts) |

Three execution modes:
- **single** — one model handles everything
- **specialist** — route to domain-specific models
- **swarm** — full P2P swarm with distributed inference

## Quick Start

```bash
# Build
cd build/OSX/Debug
cmake .. -G "Ninja" -DCMAKE_BUILD_TYPE=Debug
ninja

# Run
./neo-swarm --model /path/to/model.mnn --prompt "Hello, world!"
```

## CLI Usage

```
neo-swarm --model <path> [options]

Options:
  --model <path>           Core MNN model file (required)
  --grammar-model <path>   Grammar specialist model
  --math-model <path>      Math specialist model
  --mode single|specialist|swarm   Execution mode (default: auto)
  --prompt <text>          Prompt to process (interactive if omitted)
  --port <n>               gRPC port (default: 50051)
  --db <path>              Reputation DB (default: ./reputation.db)
  --key <path>             Node key file (default: ./node.key)
  --config <path>          JSON config file (CLI flags override file values)
  --sg-endpoint <host:port>  SuperGenius node address
  --sg-tls-ca <path>       TLS CA certificate for SuperGenius
  --sg-tls-cert <path>     TLS client certificate for SuperGenius
  --network                Enable P2P networking
  --knowledge <path>       Path to Grokipedia facts CSV
  --max-tokens <n>         Max tokens to generate (default: 512)
  --temperature <f>        Sampling temperature (default: 0.7)
  --serve                  Start gRPC server (blocking)
  --verbose                Enable debug logging
  --help                   Show help
```

## Building

Builds use Ninja + CMake from platform-specific directories under `build/`.

### Prerequisites

- CMake 3.16+
- Ninja
- C++17 compiler (clang++ or g++)
- Thirdparty dependencies (managed separately in `thirdparty/`)

### Build Pattern

```bash
cd build/<Platform>/<BuildType>   # e.g. build/OSX/Debug
cmake .. -G "Ninja" -DCMAKE_BUILD_TYPE=<BuildType>
ninja
```

Platforms: `OSX`, `Linux`, `Windows`, `Android`, `iOS`
Build types: `Debug`, `Release`, `RelWithDebInfo`

### Stale Build Directory

If `CMakeCache.txt` goes stale, delete and recreate:

```bash
cd build/OSX
rm -rf Debug
mkdir Debug && cd Debug
cmake .. -G "Ninja" -DCMAKE_BUILD_TYPE=Debug
ninja
```

## Testing

```bash
cd build/OSX/Debug
ninja test
```

Tests are in `test/` organized by module: `security/`, `router/`, `knowledge/`, `network/`, `reputation/`, `ffi/`, `integration/`, `benchmark/`.

## Project Structure

```
├── src/
│   ├── main.cpp              # CLI entry point
│   ├── api/                  # API server (composition root)
│   ├── router/               # Task routing logic
│   ├── specialists/          # Domain-specific NL models
│   ├── core/                 # MNN engine, FP4, tokenizer, SGProcessing
│   ├── network/              # P2P networking
│   ├── security/             # Crypto identity & signing
│   ├── reputation/           # Peer reputation
│   ├── knowledge/            # Knowledge base
│   └── common/               # Shared utilities, logging, error types
├── test/                     # Unit and integration tests
├── build/                    # Platform-specific build dirs
├── cmake/                    # CMake configuration
└── docs/                     # Documentation
```

## License

MIT License. See [build/LICENSE](build/LICENSE).

---

**Status**: Active development
**Built on**: GNUS decentralized compute infrastructure
