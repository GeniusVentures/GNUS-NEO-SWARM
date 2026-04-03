# GNUS NEO SWARM - Globally Networked Ultra-Smart AI * Nano Expert Orchestrated * Specialist Wisdom Arising via Routed Micro-nodes
 - The fully decentralized swarm where a Micro LLM router orchestrates specialist Nano Language Models into emergent ultra-smart intelligence.


This is a Flutter UI and C++ library for the Decentralized Genius LLM Chat system
# GNUS NEO SWARM

**GNUS NEO SWARM** is the decentralized peer-to-peer swarm architecture powering **GNUS** — the Globally Networked Ultra-Smart Artificial Intelligence ecosystem.

### Acronym Breakdown
- **GNUS** — **G**lobally **N**etworked **U**ltra-**S**mart Artificial Intelligence  
- **NEO** — **N**ano **E**xpert **O**rchestrated  
- **SWARM** — **S**pecialist **W**isdom **A**rising via **R**outed **M**icro-nodes  

### What is GNUS NEO SWARM?

**GNUS NEO SWARM** is a fully decentralized peer-to-peer swarm where a **Micro LLM router** intelligently orchestrates a mixture of specialist **Nano Language Models (NLMs)**. 

Together, these tiny, efficient expert models produce emergent ultra-smart intelligence through local interactions and routed collaboration — with no central point of control, no single point of failure, and full scalability.

### Core Concepts

- **Nano Language Models (NLMs)**: Ultra-small, highly specialized micro/nano-scale language models optimized for narrow domains. They are lightweight, efficient, and ideal for edge or decentralized deployment.
- **Micro LLM Router**: The intelligent orchestration layer that dynamically routes tasks to the most appropriate specialist NLM in real time.
- **Specialist Mixture**: Instead of one giant model, many narrow experts work together. Their combined "wisdom" emerges from decentralized, peer-to-peer coordination.
- **Decentralized Swarm Architecture**: Built on resilient mesh networking principles. Nodes join and leave freely while the swarm maintains robustness and performance.

### Key Features

- Full decentralization with peer-to-peer communication
- Emergent collective intelligence from routed specialist NLMs
- Extremely efficient resource usage (runs on consumer hardware and decentralized compute networks)
- Fault-tolerant and highly scalable
- Designed to integrate with the broader **GNUS** decentralized compute ecosystem

### How It Works (High-Level)

1. A task arrives at the swarm.
2. The **Micro LLM router** analyzes the request and routes it to the best-suited specialist **Nano Language Models**.
3. The selected NLMs process their narrow expertise in parallel or sequence.
4. Results are combined through peer-to-peer interactions, producing a coherent, high-quality output that feels "ultra-smart".
5. The system self-organizes: wisdom **arises** from the routed micro-nodes rather than being dictated from above.

### Why GNUS NEO SWARM?

Traditional large language models are centralized, expensive, and brittle.  
**GNUS NEO SWARM** flips the paradigm — delivering powerful intelligence through a decentralized mixture of lightweight, specialist Nano Language Models orchestrated via a smart router.

This approach offers:
- Dramatically lower cost and energy usage
- Greater privacy and resilience
- True global scalability using the **GNUS** networked compute layer

## General

- **Product Technical Design Specification** inside GENIUS_LLM_PTDS.md
- **Type Safety**: Uses C++17 SFINAE and templates to ensure correct type handling.
- **Cross-Platform**: Build instructions provided for multiple platforms using Ninja and CMake.

## Dependencies

- **C++17**: Required for template features and type traits.
- **Boost.Outcome**: Used for error handling (`BOOST_OUTCOME_TRY`).
- **Google Test**: For unit tests (`gtest`).
- **intx**: Extended precision integer library for `uint256` support.

## Project Structure

- `src/`: Source files (`rlp_encoder.cpp`, `rlp_decoder.cpp`, etc.).
- `include/`: Header files (`rlp_encoder.hpp`, `rlp_decoder.hpp`, etc.).
- `test/`: Unit tests (`rlp_test.cpp`).
- `build/`: Platform-specific build directories (e.g., `build/OSX/`, `build/Linux/`).

## Building the Project

This project uses Ninja as the build system, with CMake for configuration. Builds are organized in platform-specific directories under `build/`, such as `build/OSX/` for macOS, `build/Linux/` for Linux, etc. Each platform directory contains subdirectories for build configurations (`Debug`, `Release`, `RelWithDebInfo`).

### Prerequisites

- Install CMake (`cmake`).
- Install Ninja (`ninja`).
- Ensure C++17-compatible compiler (e.g., `g++`, `clang++`).
- Install dependencies:
    - Boost (`boost-outcome` or full Boost suite).
    - Google Test (`libgtest-dev` on Ubuntu, or build from source).
    - intx (include as a submodule or install separately).

### Build Instructions

Builds are always run from inside the `build/<Platform>/<BuildType>/` directory.
`cmake ..` points to `build/<Platform>/` which contains the platform CMakeLists.
**Never run cmake from the repo root or `build/<Platform>/` directly.**

#### Debug Build
```bash
cd build/OSX
mkdir -p Debug && cd Debug
cmake .. -G "Ninja" -DCMAKE_BUILD_TYPE=Debug
ninja
```

#### Release Build
```bash
cd build/OSX
mkdir -p Release && cd Release
cmake .. -G "Ninja" -DCMAKE_BUILD_TYPE=Release
ninja
```

#### Release with Debug Info
```bash
cd build/OSX
mkdir -p RelWithDebInfo && cd RelWithDebInfo
cmake .. -G "Ninja" -DCMAKE_BUILD_TYPE=RelWithDebInfo
ninja
```

The optional `-DSANITIZE_ADDRESS=code` flag enables AddressSanitizer for memory leak detection.

> **If the build directory is ever deleted or CMakeCache.txt goes stale:**
> ```bash
> cd build/OSX
> rm -rf Debug          # or Release / RelWithDebInfo
> mkdir Debug && cd Debug
> cmake .. -G "Ninja" -DCMAKE_BUILD_TYPE=Debug
> ninja
> ```
> Do **not** delete the cache and re-run cmake in-place with a different source path —
> always recreate the directory and let `cmake ..` resolve everything from `build/<Platform>/`.

- **Output**: Built files are in `build/OSX/Debug/`, `build/OSX/Release/`, etc.
- **Platforms**: Replace `OSX` with `Linux`, `Windows`, `Android`, or `iOS` as needed.

### Running Tests
After building, run the test executable:
```bash
cd build/OSX/Debug
./rlp_test
```

## License

This project is licensed under the MIT License. See [LICENSE.txt](LICENSE.txt) for details.

---

**Status**: Early development / Prototype  
**Built on**: GNUS decentralized compute infrastructure  

For technical details, architecture diagrams, or how to contribute, see the [docs](./docs) folder or join the community.
