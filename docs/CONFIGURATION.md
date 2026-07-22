<!-- GSD: generated 2026-06-17 -->
# Configuration

## Overview

GNUS NEO SWARM is configured via CLI flags and an optional JSON config file. CLI flags always override config file values. There are no environment variables.

## CLI Flags

All flags are passed to the `neo-swarm` executable:

| Flag | Default | Description |
|------|---------|-------------|
| `--model <path>` | *(required)* | Path to core MNN model file |
| `--grammar-model <path>` | *(none)* | Path to grammar specialist model |
| `--math-model <path>` | *(none)* | Path to math specialist model |
| `--mode <mode>` | `auto` | Execution mode: `single`, `specialist`, `swarm` |
| `--prompt <text>` | *(interactive)* | Prompt to process |
| `--port <n>` | `50051` | gRPC port |
| `--db <path>` | `./reputation.db` | Reputation database path |
| `--key <path>` | `./node.key` | Node key file path |
| `--config <path>` | *(none)* | JSON config file |
| `--sg-endpoint <host:port>` | `localhost:50051` | SuperGenius node address |
| `--sg-tls-ca <path>` | *(none)* | TLS CA certificate bundle for SuperGenius |
| `--sg-tls-cert <path>` | *(none)* | TLS client certificate for SuperGenius |
| `--network` | `false` | Enable P2P networking |
| `--knowledge <path>` | *(none)* | Path to Grokipedia facts CSV |
| `--max-tokens <n>` | `512` | Max tokens to generate |
| `--temperature <f>` | `0.7` | Sampling temperature |
| `--serve` | `false` | Start gRPC server (blocking) |
| `--verbose` | `false` | Enable debug logging |
| `--help` | `false` | Show help |

## JSON Config File

Pass `--config <path>` to load settings from a JSON file. Only settings that match a CLI flag are recognized. CLI flags override file values.

### Example config.json

```json
{
  "model": "/models/core.mnn",
  "grammar-model": "/models/grammar.mnn",
  "math-model": "/models/math.mnn",
  "mode": "specialist",
  "port": 50051,
  "db": "/data/reputation.db",
  "key": "/data/node.key",
  "sg-endpoint": "supergenius.example.com:50051",
  "sg-tls-ca": "/certs/ca.pem",
  "sg-tls-cert": "/certs/client.pem",
  "network": true,
  "knowledge": "/data/facts.csv",
  "max-tokens": 1024,
  "temperature": 0.5
}
```

### Precedence

1. CLI flags (highest priority)
2. Config file values
3. Built-in defaults (lowest priority)

### Flags NOT Read from Config File

These flags are CLI-only and ignored in the config file:

- `--prompt` — interactive input
- `--sg-tls-ca` — security-sensitive, must be explicit
- `--sg-tls-cert` — security-sensitive, must be explicit
- `--serve` — runtime mode flag
- `--config` — self-referential
- `--help` — display flag

## Runtime Configuration

### Logging

Debug logging is enabled with `--verbose`. The engine uses spdlog for all diagnostic output. Log levels: `debug`, `info`, `warn`, `error`.

<!-- VERIFY: spdlog integration — verify against src/common/logging.hpp -->

### Node Identity

The node key file (`--key`) stores an AES-256-GCM encrypted secp256k1 private key. On first run, a new keypair is generated and saved encrypted with the default passphrase. The passphrase is currently hardcoded in `ApiServer::Config::m_nodeKeyPassphrase`.

<!-- VERIFY: default passphrase value — verify against src/api/api_server.hpp Config struct -->

### SuperGenius Connection

To connect to the SuperGenius blockchain compute network:

```bash
neo-swarm --model /path/to/model.mnn \
  --sg-endpoint supergenius.example.com:50051 \
  --sg-tls-ca /path/to/ca.pem \
  --sg-tls-cert /path/to/client.pem
```

When connected, inference jobs can be dispatched to the SuperGenius network. On connection failure, the engine automatically falls back to local MNN inference.

<!-- VERIFY: fallback behavior — verify against src/api/api_server.cpp SuperGeniusClient initialization -->

## Build Configuration

Build configuration is managed by CMake files in `build/`:

| File | Purpose |
|------|---------|
| `build/CommonCompilerOptions.cmake` | Compiler flags, C++ standard, platform detection |
| `build/CommonBuildParameters.cmake` | Thirdparty dependency paths, project include dirs |
| `build/CompilationFlags.cmake` | Sanitizer flags, warning levels |
| `build/<Platform>/CMakeLists.txt` | Platform-specific entry point |

### Build Types

| Type | Use Case |
|------|----------|
| `Debug` | Development, debugging, full assertions |
| `Release` | Production, optimized, no debug symbols |
| `RelWithDebInfo` | Production with debug symbols for profiling |

### CMake Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `CMAKE_BUILD_TYPE` | `Debug` | Build type |
| `BUILD_TESTING` | `ON` | Build test executables |
| `BUILD_EXAMPLES` | `OFF` | Build example programs |
| `SANITIZE_ADDRESS` | `OFF` | Enable AddressSanitizer |

<!-- VERIFY: BUILD_TESTING and BUILD_EXAMPLES defaults — verify against build/CommonCompilerOptions.cmake -->
