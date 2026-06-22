# GNUS NEO SWARM — Run & Deploy Guide

> From a fresh build to a running node.
>
> **Current status:** The system runs in stub mode until MNN, SentencePiece,
> and secp256k1 are linked. See `AgentDocs/PRODUCTION_ROADMAP.md`
> for the task list to enable each dependency.
> Sections marked ⚠️ describe features that are not yet functional.

---

## SGProcessing Phases

**Phase 1 — Local (development/testing)**
`Neo Swarm → Input + .mnn → SGProcessingManager → Output → Neo Swarm → Human readable`
Use `SGProcessingManager/dev_proc_data_types`. Reference: `SuperGenius/test/src/processing_datatypes/`

**Phase 2 — Network (production)**
`Neo Swarm → Input + .mnn → SuperGenius → GNUS network → Output → Neo Swarm → Human readable`
Requires a running SuperGenius node. Phase 1 must work first.

---

## Prerequisites

- Full Xcode installed (`xcodebuild -version` shows output)
- thirdparty built at `thirdparty/build/OSX/Release/`
- GNUS-NEO-SWARM built (see Phase 1 below)

---

## Phase 1 — Build

### 1.1 Switch to Full Xcode

```bash
sudo xcode-select -s /Applications/Xcode.app/Contents/Developer
sudo xcodebuild -license accept
xcodebuild -version   # verify: shows Xcode 16.x or later
```

### 1.2 Build Thirdparty (one time only, ~2–3 hours)

```bash
# From workspace root (genius-llm-v1/)
cmake \
  -S thirdparty/build/OSX \
  -B thirdparty/build/OSX/Release \
  -DCMAKE_BUILD_TYPE=Release \
  -G Ninja

cmake --build thirdparty/build/OSX/Release --parallel
```

Verify key libraries exist:
```bash
ls thirdparty/build/OSX/Release/MNN/lib/libMNN.a
ls thirdparty/build/OSX/Release/GTest/lib/libgtest.a
ls thirdparty/build/OSX/Release/openssl/build/lib/libssl.a
```

### 1.3 Build GNUS-NEO-SWARM

```bash
# From workspace root (genius-llm-v1/)
cmake \
  -S GNUS-NEO-SWARM/build/OSX \
  -B GNUS-NEO-SWARM/build/OSX/Release \
  -DCMAKE_BUILD_TYPE=Release \
  -DGENIUS_BUILD_TESTS=ON \
  -G Ninja

cmake --build GNUS-NEO-SWARM/build/OSX/Release --parallel
```

The binary is at:
```
GNUS-NEO-SWARM/build/OSX/Release/neo-swarm
```

Add an alias for convenience:
```bash
alias neo-swarm="$(pwd)/GNUS-NEO-SWARM/build/OSX/Release/neo-swarm"
```

### 1.4 Run Tests

```bash
ctest \
  --test-dir GNUS-NEO-SWARM/build/OSX/Release \
  -C Release \
  --output-on-failure \
  --parallel
```

All 5 suites must pass:
```
test_fp4_codec              PASSED
test_router                 PASSED
test_reputation             PASSED
test_pipeline               PASSED
test_sgprocessing_pipeline  PASSED
```

---

## Phase 2 — Running (Stub Mode)

In stub mode the system runs the full pipeline but inference returns
placeholder text instead of real model output. This is useful for
verifying the pipeline, routing, and Flutter UI before a model is available.

### 2.1 Single Prompt

```bash
neo-swarm --prompt "What is 847 × 963?"
```

Output (stub mode):
```
[stub response — MNN not compiled in]
[mode=0 latency=2ms]
```

### 2.2 Interactive REPL

```bash
neo-swarm
```

```
NEO SWARM v1 — Interactive Mode
Type your prompt and press Enter. Type 'quit' to exit.

> What is the capital of France?
[stub response — MNN not compiled in]

[mode=0 latency=1ms]

> quit
```

### 2.3 Force a Specific Mode

```bash
# Force math specialist
neo-swarm --mode specialist --prompt "Solve x^2 + 5x + 6 = 0"

# Force grammar specialist
neo-swarm --mode specialist --prompt "Fix: She don't know nothing"

# Force single node
neo-swarm --mode single --prompt "Explain quantum entanglement"
```

### 2.4 Verbose Debug Output

```bash
neo-swarm --prompt "Calculate the integral of x^2" --verbose
```

Shows routing decisions, knowledge retrieval, and timing:
```
[INFO]  Route: target=CorePlusMath mode=Specialist confidence=0.91
[INFO]  Processing task task-1234: mode=1 route=1
[DEBUG] KnowledgeRetrieval: 0 facts retrieved (no facts file loaded)
[DEBUG] MNN not compiled in — running in stub mode
[DEBUG] Inference done: 0 tokens, 1ms
```

### 2.5 With Knowledge Base

Create a facts CSV:
```bash
cat > models/facts.csv << 'EOF'
Physics,The speed of light in vacuum is approximately 299792458 m/s.
Mathematics,Pi (π) is approximately 3.14159265358979.
Chemistry,Water (H2O) has a molecular weight of approximately 18.015 g/mol.
EOF
```

Run with knowledge grounding:
```bash
neo-swarm \
  --knowledge models/facts.csv \
  --prompt "What is the speed of light?" \
  --verbose
```

The `--verbose` flag shows which facts were retrieved and injected into the prompt.

---

## Phase 3 — Running with a Real Model ⚠️

> **Not yet available.** Requires MNN and SentencePiece to be linked.
> See `AgentDocs/PRODUCTION_ROADMAP.md` Tasks 1.1 and 1.2.

Once those tasks are complete, the steps are:

### 3.1 Get a Model File

```bash
pip3 install huggingface_hub

# Download Mistral 7B GGUF (~4.4 GB)
mkdir -p models
huggingface-cli download \
  TheBloke/Mistral-7B-Instruct-v0.2-GGUF \
  mistral-7b-instruct-v0.2.Q4_K_M.gguf \
  --local-dir ./models

# Download tokenizer
huggingface-cli download \
  mistralai/Mistral-7B-Instruct-v0.2 \
  tokenizer.model \
  --local-dir ./models

# Rename to match the convention GeniusAPIServer expects
cp models/tokenizer.model models/mistral-7b.tokenizer.model
```

### 3.2 Convert to MNN Format

```bash
python3 thirdparty/MNN/tools/transformers/llmexport.py \
  --path ./models \
  --export mnn \
  --quant_bit 4 \
  --quant_block 128
```

### 3.3 Run with Real Model

```bash
neo-swarm \
  --model models/mistral-7b.mnn \
  --prompt "What is 847 × 963?"
```

Expected output once MNN is linked:
```
815961
[mode=0 latency=342ms]
```

---

## Phase 4 — Swarm Mode (Multiple Nodes) ⚠️

> **Not yet available.** Requires Task 4.1 (connect `SubmitNetwork()` to SuperGenius gRPC).
> See `AgentDocs/PRODUCTION_ROADMAP.md`. Requires a running SuperGenius node.

Once Task 4.1 is complete:

```bash
neo-swarm \
  --model models/mistral-7b.mnn \
  --network \
  --sg-endpoint 192.168.1.10:50051 \
  --prompt "What is 1234 × 5678?"
```

---

## Phase 5 — Running as a Server ⚠️

> **Not yet available.** `--serve` currently runs a busy-loop placeholder.
> Requires gRPC to be wired. See `AgentDocs/PRODUCTION_ROADMAP.md` Task 4.2.

Once gRPC is implemented:

```bash
neo-swarm \
  --model models/mistral-7b.mnn \
  --knowledge models/facts.csv \
  --port 50051 \
  --key production.key \
  --db production-reputation.db \
  --serve
```

### Keep it Running (macOS LaunchAgent)

```bash
cat > ~/Library/LaunchAgents/ai.gnus.neo-swarm.plist << 'EOF'
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN"
  "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key>
  <string>ai.gnus.neo-swarm</string>
  <key>ProgramArguments</key>
  <array>
    <string>/path/to/GNUS-NEO-SWARM/build/OSX/Release/neo-swarm</string>
    <string>--model</string>
    <string>/path/to/models/mistral-7b.mnn</string>
    <string>--knowledge</string>
    <string>/path/to/models/facts.csv</string>
    <string>--port</string>
    <string>50051</string>
    <string>--key</string>
    <string>/path/to/production.key</string>
    <string>--db</string>
    <string>/path/to/production-reputation.db</string>
    <string>--serve</string>
    <string>--network</string>
  </array>
  <key>RunAtLoad</key>
  <true/>
  <key>KeepAlive</key>
  <true/>
  <key>StandardOutPath</key>
  <string>/tmp/neo-swarm.log</string>
  <key>StandardErrorPath</key>
  <string>/tmp/neo-swarm-error.log</string>
</dict>
</plist>
EOF

launchctl load ~/Library/LaunchAgents/ai.gnus.neo-swarm.plist
launchctl list | grep neo-swarm
tail -f /tmp/neo-swarm.log
```

Stop / restart:
```bash
launchctl unload ~/Library/LaunchAgents/ai.gnus.neo-swarm.plist
launchctl load   ~/Library/LaunchAgents/ai.gnus.neo-swarm.plist
```

---

## Phase 6 — Node Identity and Reputation ⚠️

> Node identity uses a real secp256k1 keypair once Task 2.1 is complete.
> Reputation persists to RocksDB once Task 3.1 is complete.
> Until then, identity is a random stub and reputation is in-memory only.

### Node Key

The first run with `--key` creates the keypair:
```bash
neo-swarm --key my-node.key --prompt "hello"
# Creates my-node.key on first run
```

**Back this file up.** It is the node's permanent identity on the network.
```bash
cp my-node.key my-node.key.backup
```

### Reputation Database

Keep the DB on persistent storage:
```bash
# Good
--db /Users/yourname/genius-data/reputation.db

# Bad — lost on restart
--db /tmp/reputation.db
```

---

## CLI Reference

```
BINARY
  GNUS-NEO-SWARM/build/OSX/Release/neo-swarm

OPTIONS
  --model <path>           Core MNN model file
  --grammar-model <path>   Grammar specialist model
  --math-model <path>      Math specialist model
  --mode single|specialist|swarm   Execution mode (default: auto)
  --prompt <text>          Single prompt (interactive REPL if omitted)
  --port <n>               gRPC port (default: 50051)
  --db <path>              Reputation DB path (default: ./reputation.db)
  --key <path>             Node key file (default: ./node.key)
  --network                Enable P2P networking
  --knowledge <path>       Grokipedia facts CSV
  --max-tokens <n>         Max tokens to generate (default: 512)
  --temperature <f>        Sampling temperature (default: 0.7)
  --serve                  Start gRPC server (blocking)
  --verbose                Enable debug logging
  --help                   Show help

MODES
  single      Fast, one node, core LLM only
  specialist  Core LLM + math or grammar expert (auto-detected by router)
  swarm       Multiple nodes, weighted consensus  ⚠️ requires SuperGenius gRPC (Task 4.1)
  auto        Router decides based on prompt content (default)

KEY FILES
  Binary:     GNUS-NEO-SWARM/build/OSX/Release/neo-swarm
  Node key:   ./node.key          (auto-created, back up)
  Reputation: ./reputation.db     (RocksDB, keep on persistent storage)
  Model:      ./models/mistral-7b.mnn
  Tokenizer:  ./models/mistral-7b.tokenizer.model
  Knowledge:  ./models/facts.csv
```

---

*GNUS NEO SWARM — May 2026*
