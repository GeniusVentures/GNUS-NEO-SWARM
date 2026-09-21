# ADR: NeoSwarm Runtime Coordinator Architecture

- **Status:** accepted
- **Date:** 2026-07-28
- **Scope:** GNUS-NEO-SWARM runtime, GCS integration, local and distributed execution
- **Decision type:** architecture, runtime coordination, implementation boundary
- **Parent decisions:**
  - `GeniusCognitiveSystem/docs/architecture/decisions/adr-runtime-component-ownership.md`
  - `GeniusCognitiveSystem/docs/architecture/decisions/adr-embeddable-sdk-and-modular-build.md`

## Context

GNUS-NEO-SWARM currently contains API orchestration, routing, model inference, specialists, retrieval, reputation, networking, security, SGProcessing integration, and Flutter-facing entry points. The existing `ApiServer` performs much of the top-level request coordination, while `MNNInferenceEngine` also contains multiple execution paths.

As GCS grows, the top-level request lifecycle must become an explicit runtime component. It must remain separate from model-runtime behavior, SGProcessingManager workload execution, and SuperGenius distributed scheduling.

The parent GeniusCognitiveSystem repository defines a generic `RuntimeCoordinator` contract and stable SDK boundary. GNUS-NEO-SWARM supplies the primary concrete implementation.

## Decision

### 1. GNUS-NEO-SWARM implements `NeoSwarmRuntimeCoordinator`

GNUS-NEO-SWARM will provide a concrete coordinator implementing the parent GCS `RuntimeCoordinator` interface.

```text
gcs::RuntimeCoordinator
        ^
        |
neoswarm::NeoSwarmRuntimeCoordinator
```

The coordinator owns the full runtime lifecycle of a GCS request within NeoSwarm.

### 2. Coordinator responsibilities

`NeoSwarmRuntimeCoordinator` is responsible for:

- accepting versioned GCS runtime requests;
- creating request and session state;
- invoking or consuming router and planner output;
- constructing and advancing cognitive execution stages;
- selecting context, memory, and grounding inputs;
- invoking the Semantic Core, ELMs, specialists, verifiers, arbiters, and synthesizers;
- deciding whether each stage runs locally or is delegated;
- coordinating parallel and sequential stages;
- enforcing request-level cancellation, deadlines, latency budgets, token budgets, spend budgets, and privacy constraints;
- emitting structured runtime events and partial results;
- collecting artifacts, provenance, execution claims, verification results, and usage;
- applying fallback and degradation policy;
- producing the final GCS runtime result.

### 3. Coordinator non-responsibilities

The coordinator does not implement:

- tokenization or detokenization algorithms;
- chat-template rendering internal to a model runtime;
- autoregressive token-generation loops;
- sampling, KV-cache management, or speculative decoding internals;
- SGFP4 weight decoding kernels;
- Vulkan compute kernels;
- SGProcessing pass execution internals;
- SuperGenius worker scheduling internals;
- direct tool side effects outside the Tool Intermediary contract.

Those responsibilities remain with the relevant composed services.

### 4. MNN invocation boundary

MNN is the model runtime for individual model invocations. The coordinator supplies model identity, prompt or token input, generation parameters, execution requirements, cancellation/deadline context, and event sinks through an adapter.

MNN owns:

- model and tokenizer loading;
- model-specific prompt templates;
- LLM generation and streaming;
- sampling and KV cache;
- CPU/Vulkan execution;
- MoltenVK-backed Vulkan execution on Apple platforms;
- native SGFP4 model-weight loading and execution.

GNUS-NEO-SWARM must not add a second LLM loop in SGProcessingManager or in the coordinator.

### 5. SGProcessingManager delegation boundary

SGProcessingManager is a subordinate workload executor used only when a stage fits its processing contract.

The coordinator may delegate:

- model-inference processing passes;
- compute-shader workloads;
- render workloads;
- tensor, media, and data transformations;
- ordered multi-pass processing graphs.

The coordinator remains responsible for the cognitive meaning of the stage, its placement in the request lifecycle, and how its outputs are used.

SGProcessingManager is not the GCS runtime coordinator and does not own routing, conversation state, expert policy, grounding strategy, verification, arbitration, or final synthesis.

### 6. SuperGenius delegation boundary

The coordinator may request distributed execution through the SuperGenius client and related transport services.

SuperGenius owns:

- node discovery and capability matching;
- queues, assignment, attempts, retries, and worker lifecycle;
- network transport;
- distributed artifact transfer;
- execution attestations;
- accounting and settlement.

The coordinator owns the reason for delegation, the cognitive stage being executed, request-level policy, and interpretation of returned results.

### 7. Runtime service composition

The target composition is:

```text
NeoSwarmRuntimeCoordinator
|-- Router / Planner
|-- Context Compiler / Memory Governor
|-- Grounding services
|-- ModelRuntime adapter
|   `-- MNN
|-- Specialist / ELM registry
|-- Verification / Arbitration / Synthesis
|-- ProcessingExecutor adapter
|   `-- SGProcessingManager
|-- DistributedExecutor adapter
|   `-- SuperGenius client
|-- Tool Intermediary client
|-- Reputation / EIS services
`-- Runtime event and artifact collector
```

These services are composed dependencies, not subclasses of `RuntimeCoordinator`.

### 8. Request state model

Each active request has an isolated state object containing at minimum:

- request and session identifiers;
- current lifecycle state and active stages;
- execution plan and stage dependencies;
- cancellation source;
- deadline and budget state;
- selected models, experts, adapters, and runtimes;
- context and memory references;
- emitted events and partial artifacts;
- local and distributed attempt records;
- verification, arbitration, and synthesis state;
- final result or terminal error.

No single mutable global processing-manager pointer may be used to represent progress for multiple concurrent requests.

### 9. Event and result contract

The coordinator emits structured events rather than relying only on a scalar progress value. Event classes include:

- accepted and planned;
- stage started, progressed, completed, skipped, or failed;
- model token or text delta;
- artifact produced;
- tool approval required;
- verification or arbitration update;
- retry or fallback;
- cancelled, timed out, failed, or completed.

Final results contain typed artifacts and an execution manifest rather than loose byte buffers or newline-separated locations.

### 10. Target code and build structure

The coordinator should become an independently buildable module with its own `CMakeLists.txt`, following existing NeoSwarm conventions.

```text
src/
|-- runtime/
|   |-- CMakeLists.txt
|   |-- runtime_coordinator.hpp
|   |-- neo_swarm_runtime_coordinator.hpp
|   |-- neo_swarm_runtime_coordinator.cpp
|   |-- runtime_request_state.hpp
|   |-- runtime_event_dispatcher.hpp
|   `-- adapters/
|       |-- CMakeLists.txt
|       |-- model_runtime_adapter.*
|       |-- processing_executor_adapter.*
|       `-- distributed_executor_adapter.*
`-- api/
    `-- CMakeLists.txt
```

The expected target is:

```text
neoswarm_runtime
```

`neoswarm_api` should depend on `neoswarm_runtime`. The runtime target then links only the services it composes through their public interfaces.

Subdirectories that become independently buildable or testable modules own their own `CMakeLists.txt`.

### 11. Migration from `ApiServer`

Migration should be incremental:

1. Define the parent GCS runtime contracts.
2. Introduce `neoswarm_runtime` and request-state types.
3. Move request lifecycle, execution-mode switching, cancellation, and event emission from `ApiServer` into `NeoSwarmRuntimeCoordinator`.
4. Keep `ApiServer` as a transport and API facade.
5. Wrap MNN, SGProcessingManager, and SuperGenius behind explicit adapters.
6. Replace hash-as-output and loose result handling with typed artifacts and manifests.
7. Move Flutter/native entry points to the parent GCS C ABI once available.

## Rejected alternatives

### Continue using `ApiServer` as an implicit all-purpose coordinator

Rejected because transport/API concerns become mixed with cognitive execution state, concurrency, cancellation, and service orchestration.

### Make SGProcessingManager the coordinator

Rejected because SGProcessingManager executes selected processing workloads but does not own the cognitive request lifecycle.

### Put the LLM generation loop in the coordinator

Rejected because model-generation semantics belong to MNN. The coordinator invokes models and consumes their streams; it does not recreate their decoder.

### Treat direct MNN and SGProcessingManager as mutually exclusive global engine modes

Rejected because a single GCS request may use direct local MNN for one stage, SGProcessingManager for another stage, and SuperGenius for a distributed stage. Selection is per stage and per execution requirement, not necessarily one process-wide mode.

### Expose NeoSwarm classes directly to Flutter

Rejected because applications should depend on stable parent GCS SDK and C ABI contracts, allowing native, remote, and mock backends.

## Consequences

- `ApiServer` becomes thinner and focuses on API transport and lifecycle entry points.
- Concurrent requests receive isolated state, progress, cancellation, and results.
- MNN remains the single owner of LLM generation and native SGFP4 model execution.
- SGProcessingManager remains useful for processing graphs without becoming the system-wide coordinator.
- Local and distributed execution can be mixed within one cognitive execution plan.
- The parent GCS Flutter SDK can plug into NeoSwarm through a stable runtime interface rather than internal classes.
- Future planning and implementation work should treat this accepted ADR as higher precedence than older codebase snapshots describing `sgprocessing` and `interpreter` as process-wide alternative engine modes.
