<!-- GSD: generated 2026-06-17 -->
# Getting Started

## Prerequisites

- **C++17 compiler** — clang++ (macOS/Linux) or MSVC (Windows)
- **CMake 3.16+**
- **Ninja** build system
- **Thirdparty dependencies** — pre-built in `thirdparty/` (do not build separately)

## Quick Build

```bash
# Clone and enter the repo
cd GNUS-NEO-SWARM

# Build for your platform
cd build/OSX/Debug          # or Linux/Debug, Windows/Debug
cmake .. -G "Ninja" -DCMAKE_BUILD_TYPE=Debug
ninja
```

## First Run

```bash
# Run with a model
./neo-swarm --model /path/to/model.mnn --prompt "Hello, world!"

# Interactive mode (no --prompt)
./neo-swarm --model /path/to/model.mnn
```

## Using a Config File

Create a `config.json`:

```json
{
  "model": "/models/core.mnn",
  "mode": "specialist",
  "max-tokens": 1024,
  "temperature": 0.7
}
```

Then run:

```bash
./neo-swarm --config config.json --prompt "Explain quantum computing"
```

## Specialist Mode

To use domain-specific specialist models:

```bash
./neo-swarm \
  --model /models/core.mnn \
  --grammar-model /models/grammar.mnn \
  --math-model /models/math.mnn \
  --mode specialist \
  --prompt "Fix the grammar: he go to store yesterday"
```

## SuperGenius Network

Connect to the SuperGenius blockchain compute network:

```bash
./neo-swarm \
  --model /models/core.mnn \
  --sg-endpoint supergenius.example.com:50051 \
  --sg-tls-ca /certs/ca.pem \
  --sg-tls-cert /certs/client.pem
```

The engine will dispatch inference jobs to the SuperGenius network when available, and fall back to local inference on connection failure.

## Running Tests

```bash
cd build/OSX/Debug
ninja test
```

Tests cover security, routing, knowledge, network, reputation, FFI, integration, and benchmarks.

## Stale Build Recovery

If the build breaks after pulling updates:

```bash
cd build/OSX
rm -rf Debug
mkdir Debug && cd Debug
cmake .. -G "Ninja" -DCMAKE_BUILD_TYPE=Debug
ninja
```

## Next Steps

- [Architecture](docs/ARCHITECTURE.md) — system design and component overview
- [Configuration](docs/CONFIGURATION.md) — all CLI flags and config file options
- [Testing](docs/TESTING.md) — test structure and how to add tests
