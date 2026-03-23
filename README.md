# Genius Mixture of Specialist Small Language Model Project and Library


This is a Flutter UI and C++ library for the Decentralized Genius LLM Chat system
## General

- **Product Technical Design S** inside GENIUS_LLM_PTDS.md
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

## Usage

### Encoding Example
```cpp
#include <rlp_encoder.hpp>

int main() {
    rlp::RlpEncoder encoder;
    encoder.begin_list();
    encoder.add(42); // uint64_t
    encoder.add(true); // bool
    encoder.end_list();
    rlp::Bytes encoded = encoder.move_bytes();
    // encoded contains RLP-encoded list [42, true]
    return 0;
}
```

### Decoding Example
```cpp
#include <rlp_decoder.hpp>

int main() {
    rlp::Bytes data = /* some RLP data */;
    rlp::RlpDecoder decoder(data);
    auto list_payload_bytes = decoder.read_list_header_bytes(); // Returns byte count, not item count
    if (list_payload_bytes) {
        uint64_t num;
        bool flag;
        decoder.read(num);
        decoder.read(flag);
        // Use num and flag
    }
    return 0;
}
```

## Light-Client Monitoring Stack

The repository now contains the core building blocks required by the
[architecture design](Architecture.md) for running a SuperGenius light client that
monitors contract activity directly from EVM P2P networks. The
implementation spans three cooperating layers that map directly to the
design’s stages:

### 1. Peer Discovery (discv4)
- Located under `include/rlp/PeerDiscovery/` and `src/rlp/PeerDiscovery/`, the
  discovery module RLP-encodes/decodes v4 packets, manages bootstrap node
  metadata, and orchestrates UDP flows via Boost.Asio, mirroring the design’s
  discovery responsibilities.
- Unit coverage in `test/discv4/discovery_test.cpp` exercises PING/PONG
  construction, parsing, and timeout handling to validate the discovery flow
  end-to-end.

### 2. RLPx Transport and Session Management
- The `rlpx` subsystem (`include/rlpx/` and `src/rlpx/`) implements the secure
  TCP transport, including ECIES handshakes, AES/HMAC frame ciphers, message
  framing, and coroutine-based session orchestration—directly covering the
  RLPx and `eth` subprotocol requirements from the design.
- High-level session APIs expose message handlers for HELLO, STATUS, PING, and
  generic gossip, enabling the transaction/log filtering pipeline described in
  the design document.

### 3. Ethereum RLP Processing and Filtering Primitives
- Core encoding/decoding utilities in `include/rlp/` and `src/rlp/` provide the
  recursive RLP handling needed to parse block headers, transactions, and
  receipts once they are received over the wire, satisfying the design’s
  execution-layer processing goals.
- `include/rlp/rlp_ethereum.hpp` supplies Ethereum-specific helpers (e.g., for
  block header fields and bloom filters) that align with the consensus
  verification and log filtering steps laid out in the design.

These components can be composed inside SuperGenius to establish DevP2P
connections, validate chain consistency from checkpoints, and stream contract
events without centralized RPC endpoints.

## Testing

### Unit Tests

The project includes comprehensive unit tests covering RLP encoding/decoding, RLPx
crypto, ETH message handling, discv4 discovery, and more (499 tests total).

```bash
cd build/OSX/Debug
ctest --no-pager
```

---

### Live eth_watch Integration Testing

`eth_watch` connects directly to Ethereum P2P networks via discv4 + RLPx — no RPC
required. The test scripts below watch for GNUS.AI contract events across multiple
chains and can send test transactions to verify end-to-end detection.

#### Prerequisites

Install [Foundry](https://github.com/foundry-rs/foundry) for the `cast` tool (used to
sign and send transactions):

```bash
brew install foundry
```

#### 1. Generate a test wallet

Run once to create a dedicated test wallet and save it to a local `.env` file.
**`.env` is git-ignored — never commit it.**

```bash
cast wallet new --json | \
  node -e "const d=JSON.parse(require('fs').readFileSync(0,'utf8')); \
  console.log('# Test wallet — DO NOT COMMIT\nPRIVATE_KEY='+d[0].private_key+'\nTEST_ADDRESS='+d[0].address);" \
  > .env && cat .env
```

#### 2. Fund the test wallet

Send a small amount of GNUS to `TEST_ADDRESS` (shown in `.env`) on each chain you
want to test, from your own wallet. GNUS contract addresses:

| Chain | Address |
|-------|---------|
| Ethereum | `0x614577036F0a024DBC1C88BA616b394DD65d105a` |
| Polygon | `0x127E47abA094a9a87D084a3a93732909Ff031419` |
| BSC | `0x614577036F0a024DBC1C88BA616b394DD65d105a` |
| Base | `0x614577036F0a024DBC1C88BA616b394DD65d105a` |
| Ethereum Sepolia | `0x9af8050220D8C355CA3c6dC00a78B474cd3e3c70` |
| Polygon Amoy | `0xeC20bDf2f9f77dc37Ee8313f719A3cbCFA0CD1eB` |
| BSC Testnet | `0xeC20bDf2f9f77dc37Ee8313f719A3cbCFA0CD1eB` |
| Base Sepolia | `0xeC20bDf2f9f77dc37Ee8313f719A3cbCFA0CD1eB` |

> Source: [docs.gnus.ai/resources/contracts](https://docs.gnus.ai/resources/contracts/)

#### 3. Start watching all chains

In one terminal, start the watcher before sending transactions so events are caught
live:

#### What a successful run looks like

```
[Sepolia    ] HELLO from peer: Geth/v1.16.7-stable/linux-amd64/go1.25.1
[Sepolia    ] ETH STATUS: network_id=11155111
[Sepolia    ] NewBlockHashes: 1 hashes
[Sepolia    ] Transfer(0xYourAddress → 0xTestAddress, 1) at block 7654321
```

## Contributing

- Fork the repository.
- Create a feature branch.
- Submit a pull request with your changes and updated tests.

## License

This project is licensed under the MIT License. See [LICENSE.txt](LICENSE.txt) for details.

