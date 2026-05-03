# 20. Data-Driven Epistemic Arbitration and Cognitive OS Extensions

## 20.1 Purpose

This document extends the Genius Cognitive System and Genius LLM architecture with a formal Epistemic Arbitration Layer implemented as part of the emerging Cognitive OS.

The purpose of this section is to describe how the Requestor Node, already responsible for synthesis and final arbitration, can evolve into a configurable epistemic control plane capable of selecting and executing multiple reasoning frameworks over specialist outputs, grounded facts, structured memory, and trust signals.

The central idea is simple:

> Consensus alone determines which outputs are viable. Epistemic arbitration determines how viable outputs should be judged, challenged, and synthesized before final response emission.

This architecture does not replace the existing Semantic Core, specialist system, GAML memory layer, grounding layer, or reputation-based consensus engine. Instead, it introduces a higher-order control layer that governs how all of those components are interpreted at the final stage of cognition.

The initial motivation for this extension comes from two related observations:

1. The current Genius architecture already behaves like a Cognitive OS in everything except explicit epistemic formalization.
2. Existing reasoning-layer products in the broader market demonstrate that structured epistemology can serve as a major differentiator, but Genius can implement the same concept in a more modular, distributed, inspectable, and swarm-native form.

This document therefore formalizes a path for integrating:

- Sanskrit epistemology, especially Nyaya and pramana-based inquiry
- Kripke or modal reasoning
- hybrid arbitration frameworks
- data-driven hierarchical state machine execution
- JSON-defined reasoning machines
- dynamically loadable plugin modules
- future WASM-based epistemic extensions

The resulting system allows Genius to move from routed inference and weighted synthesis into a more explicit model of computational judgment.

---

## 20.2 Why this section exists

The existing PTDS already defines many of the ingredients required for a Cognitive OS.

These include:

- routed specialist execution
- structured memory via GAML
- Bridge Blocks and fact-based context construction
- grounding and validation
- reputation-weighted consensus
- swarm thinking traces
- secure tool mediation
- targeted retraining and critical-thinking specialists

However, the current documentation still leaves an important architectural gap.

The system explains:

- how tasks are routed
- how specialists execute
- how memory is assembled
- how trust is weighted
- how outputs are grounded
- how critics and verifiers challenge reasoning

But it does not yet fully define:

- how the final arbiter reasons over disagreement
- how alternative reasoning traditions can be selected at runtime
- how arbitration itself becomes inspectable and upgradeable
- how multiple epistemologies can coexist inside the same requestor-node flow
- how final synthesis can be governed by more than score aggregation alone

That is the purpose of this document.

The Genius system already contains the right primitives. This section makes those primitives explicit and turns them into an extensible architectural layer rather than an implicit orchestration behavior.

---

## 20.3 Architectural intent

Genius Cognitive System should evolve from a routed specialist architecture into a more complete Cognitive OS with six cooperating layers:

1. Context and memory layer
2. Routing and planning layer
3. Primary and secondary expert execution layer
4. Consensus and trust layer
5. Epistemic arbitration layer
6. Final synthesis and user-visible thinking context layer

The Epistemic Arbitration Layer sits between consensus and final synthesis.

A simplified high-level flow becomes:

Client/API  
-> Router and Planning Layer  
-> Memory and Context Assembly  
-> Semantic Core and Specialists  
-> Reputation-Weighted Consensus  
-> Epistemic Arbitration Layer  
-> Final Synthesis  
-> Grounding and Validation  
-> Final Response  
-> Memory Writeback and Learning Signals

This distinction is important.

The system should not assume that the highest weighted candidate answer is automatically the correct final answer.

Instead:

- consensus filters and ranks outputs
- epistemic arbitration reasons over them
- synthesis emits the final answer
- thinking trace records how the decision was made

This preserves the value of reputation and grounding while adding a missing layer of formal cognitive control.

---

## 20.4 Core design principles

### 20.4.1 Arbitration is a first-class cognitive function

In most LLM systems, arbitration is either hidden inside the model or treated as a loose orchestration heuristic.

Genius should instead treat arbitration as an explicit reasoning layer with:

- defined phases
- defined guards
- structured transitions
- inspectable intermediate artifacts
- deterministic or bounded execution semantics

This allows the system to reason not only about answers, but about answer quality, evidence validity, contradiction pressure, and failure modes.

### 20.4.2 Epistemic frameworks are modular and swappable

The system must not hardcode a single reasoning tradition into the core architecture.

Instead, the Cognitive OS should support multiple epistemic frameworks that can be:

- selected per request
- selected by policy
- selected by task class
- combined in hybrid flows
- upgraded independently of the core LLM stack

This makes the arbitration layer future-compatible.

### 20.4.3 Framework logic should be data-driven

A major design goal is to keep epistemic behavior out of deeply embedded handwritten orchestration logic wherever possible.

The reasoning machine itself should be definable through:

- JSON machine definitions
- callback names
- guards
- configuration schemas
- plugin-provided implementations

This gives the system the ability to evolve arbitration behavior without modifying inference kernels, router code, or specialist weights.

### 20.4.4 The Requestor Node is the correct control point

The Requestor Node already receives:

- specialist drafts
- verifier outputs
- critic outputs
- memory packets
- grounding artifacts
- reputation scores
- policy flags
- synthesis responsibilities

It is therefore the natural location for a formal epistemic arbiter.

This architecture does not require introducing a new external subsystem. It deepens the role of a node that already exists.

### 20.4.5 Inspectable reasoning should not depend on raw chain-of-thought exposure

The arbitration layer should output a structured, high-level trace of:

- what was considered
- what was rejected
- what framework was used
- what contradictions were found
- why a final synthesis survived

This supports trust and debugging without relying on unrestricted chain-of-thought disclosure.

### 20.4.6 Plugins should remain extremely small

The long-term operational model assumes that new epistemic frameworks will be delivered as tiny shared objects or equivalent modules.

These plugins should be:

- small
- fast to write
- easy to update
- easy to ship to phones and desktops
- independent of the core MNN inference runtime

This is aligned with the deployment model of GNUS nodes and edge devices.

---

## 20.5 Relationship to the existing Genius architecture

### 20.5.1 Relation to the Semantic Core

The Semantic Core remains the primary broad reasoning and generation substrate.
It is not replaced by epistemic arbitration.

The Semantic Core still provides:

- general reasoning
- first-pass answer generation
- draft production
- fallback behavior for low-complexity tasks

Epistemic arbitration operates after candidate outputs exist.

### 20.5.2 Relation to specialists

The arbitration layer depends on specialists, including but not limited to:

- Planner and Memory Governor
- Primary Draft Specialist
- Verifier Specialist
- Synthesizer or Arbiter Specialist
- Refiner and Formatter Specialist
- Numeric Specialist
- Symbolic Math Specialist
- Tool and Execution Specialist
- Code Specialist
- Grounding Specialist
- Hierarchical Critical Thinking Specialists

It does not replace them.
It governs how their outputs are evaluated, challenged, and merged.

### 20.5.3 Relation to consensus

Consensus answers the question:

> Which outputs are viable and how much should each be trusted?

Epistemic arbitration answers the question:

> Given these viable outputs, how should they be examined, challenged, and synthesized into final knowledge?

This distinction is essential.

Consensus is a trust-weighting and coordination mechanism.
Epistemic arbitration is a reasoning and judgment mechanism.

### 20.5.4 Relation to grounding

Grounding remains part of the factual validation pipeline.

Epistemic arbitration consumes grounded facts as evidence.
It may use grounded artifacts to:

- validate a candidate output
- reject a candidate path
- enrich knowledge-source tagging
- refine the synthesis rationale

### 20.5.5 Relation to GAML

GAML memory is a critical upstream input.

The arbitration layer may consume:

- facts
- events
- policies
- state
- Bridge Blocks
- user or project preferences
- confidence-scored memory objects
- trusted vs untrusted memory partitions

This gives the arbitration layer structured evidence rather than only prompt text.

### 20.5.6 Relation to HCTS

HCTS is a natural critique source for epistemic arbitration.

The arbitration machine can invoke:

- generic critics
- domain critics
- cultural critics
- adversarial critics
- individual cognitive critics

These can be mapped into Sanskrit Tarka, contradiction passes, or hybrid challenge steps.

This makes HCTS more than a generic critique mechanism. It becomes a formal source of epistemic opposition.

---

## 20.6 Requestor Node as Epistemic Arbiter

### 20.6.1 Current role of the Requestor Node

Within the Genius architecture, the Requestor Node already behaves like:

- temporary orchestrator
- draft collector
- consensus coordinator
- synthesizer
- response finalizer

It effectively acts as the final cognitive assembly point for many tasks.

### 20.6.2 Extended role

This document extends the Requestor Node into the system's Epistemic Arbiter.

Its responsibilities now include:

- selecting an epistemic framework
- loading an arbitration machine
- preparing the arbitration context
- invoking framework-specific reasoning phases
- coordinating verifier and critic calls
- evaluating contradiction pressure
- determining whether synthesis is ready
- deciding whether escalation or recovery is required
- emitting a structured arbitration trace
- returning the final synthesis decision

### 20.6.3 Why this is the right place

This is the right place for epistemic arbitration because the Requestor Node already has access to the richest possible context:

- consensus-ranked outputs
- memory packets
- grounding signals
- specialist roles
- reputation scores
- latency metadata
- policy flags
- secure tool execution flags
- structured critique outputs

No other node in the architecture naturally has the same complete view.

### 20.6.4 Cognitive OS implication

With this extension, the Requestor Node becomes more than a coordinator.
It becomes the local execution engine for a configurable reasoning framework.

This is one of the major steps that moves Genius from:

- modular swarm inference

to:

- distributed cognitive operating system behavior

---

## 20.7 Why GQHSM is the correct runtime

### 20.7.1 Problem shape

The arbitration problem is not a single function call.
It is a staged, hierarchical, guard-driven reasoning process.

It must support:

- multiple frameworks
- nested phases
- conditional branching
- guard conditions
- retry and recovery
- contradiction-triggered detours
- finalization hooks
- trace output

This naturally maps to a hierarchical state machine.

### 20.7.2 GQHSM as the execution substrate

Genius already has a more advanced, data-driven hierarchical state machine system:

GQHSM

Repository reference:

https://github.com/Super-Genius/GQHSM

GQHSM is the intended executable runtime for this layer.

It provides the key property classical QHSM usage would lack in a pure hardcoded design:

> The machine definition can be loaded and modified from data, while the runtime remains native C++.

This makes it an ideal fit for Cognitive OS arbitration.

### 20.7.3 Why not hardcode the frameworks directly

A hardcoded Sanskrit or Kripke arbiter would work for a prototype, but it would create the wrong long-term shape.

Hardcoding would make:

- framework changes expensive
- experimentation slower
- plugin delivery harder
- inspection less clean
- third-party or future extensions more difficult

GQHSM avoids that by separating:

- machine structure
- callback registry
- runtime execution
- framework-specific behavior

### 20.7.4 Determinism and inspectability

Because GQHSM is an explicit runtime with states, guards, entry actions, exit actions, and internal actions, it naturally supports:

- deterministic or bounded execution
- explicit trace generation
- structured debugging
- machine-version tagging
- replay and audit support

These are all desirable properties for the arbitration layer.

---

## 20.8 Native implementation model: C++, MNN, and separation of concerns

### 20.8.1 Execution stack

The Genius stack already relies on:

- native C++
- Alibaba MNN
- heterogeneous node execution
- low-overhead runtime behavior

The epistemic arbitration layer should preserve this philosophy.

### 20.8.2 Separation of concerns

The proposed separation is:

- MNN and model runtime handle inference
- router and planning handle task decomposition
- GAML handles structured memory
- secure agent layer handles tool safety and side effects
- GQHSM handles epistemic arbitration and final staged judgment

This keeps each layer focused.

### 20.8.3 Why this is efficient

The arbitration layer is not a heavy inference subsystem.
It is mostly:

- control logic
- callback dispatch
- structured evaluation
- context mutation
- trace writing

This means it is lightweight enough to run comfortably even on constrained devices compared to the actual model compute path.

### 20.8.4 Why this fits mobile and desktop deployment

The arbitration runtime should be small, predictable, and updateable.
This matches the GNUS deployment model well:

- a phone or desktop can receive a new plugin
- a node can load a new framework without full model replacement
- a small shared object can add a major new reasoning capability

This is especially important because new epistemologies are not expected to appear often, but when they do, they can be delivered through a very lightweight update path.

---

## 20.9 Supported epistemic framework families

The Cognitive OS should support multiple families of reasoning frameworks.

### 20.9.1 Sanskrit epistemology

The first major family is Sanskrit epistemology, especially Nyaya and pramana-based reasoning.

This is attractive because it contributes a structured, multi-phase model of knowledge formation and validation rather than a generic prompt heuristic.

A useful practical phase sequence is:

1. Samshaya - doubt or problem framing
2. Pramana - identification of valid means of knowledge
3. Pancha Avayava - structured inferential construction
4. Tarka - challenge, debate, or counterfactual pressure
5. Hetvabhasa - fallacy detection
6. Nirnaya - ascertainment and final judgment

This fits the Genius architecture extremely well because it naturally maps onto:

- routing and doubt classification
- memory and grounding as knowledge-source inputs
- HCTS and verifier specialists as Tarka or Hetvabhasa stages
- synthesis as Nirnaya
- thinking trace as the inspectable record of the process

### 20.9.2 Kripke and modal reasoning

The second framework family is Kripke-style modal reasoning.

This is useful for:

- multiple plausible drafts
- uncertain world-state assumptions
- conflicting specialist outputs
- belief-state divergence across nodes
- state-based contradiction handling

In this framing, candidate outputs may be treated as possible worlds or belief states, and the arbiter may reason over:

- accessibility relations
- modal validity
- consistency under world transitions
- fixed-point convergence
- contradiction persistence

This is especially useful when the task is not simply "which answer is right," but "which interpretation survives structured possibility analysis."

### 20.9.3 Hybrid frameworks

Hybrid frameworks should be supported as first-class configurations.

Examples:

- Sanskrit inquiry followed by Kripke consistency filtering
- grounding-first arbitration followed by Tarka critique
- consensus ranking followed by Hetvabhasa fallacy rejection
- parallel Sanskrit and modal branches merged by weighted synthesis

This preserves flexibility and avoids false architectural rigidity.

### 20.9.4 Future frameworks

The system should remain compatible with future additions such as:

- Bayesian reasoning
- deontic logic
- Mimamsa-style interpretive reasoning
- policy-aware legal reasoning
- probabilistic contradiction handling
- domain-specific scientific arbitration

The plugin and callback system should be designed around this expectation.

---

## 20.10 Sanskrit epistemology as a practical arbitration model

### 20.10.1 Why Sanskrit reasoning is useful here

A Sanskrit-inspired epistemic framework is not being introduced as a purely philosophical embellishment.

It is useful because it provides a staged reasoning discipline for exactly the kind of tasks the Requestor Node must already perform:

- uncertainty framing
- evidence classification
- inferential construction
- challenge and refutation
- fallacy detection
- final ascertainment

### 20.10.2 Mapping the phases into Genius

#### Samshaya

Maps to:

- ambiguity detection
- uncertainty classification
- conflict identification
- deciding whether more evidence is needed

#### Pramana

Maps to:

- knowledge source tagging
- grounding source identification
- reputation-aware evidence weighting
- distinguishing inference from memory, testimony, retrieval, or direct tool result

#### Pancha Avayava

Maps to:

- explicit reasoning model construction
- structured claim-to-evidence chain assembly
- making the synthesis rationale legible

#### Tarka

Maps to:

- HCTS critique passes
- adversarial challenge
- contradiction probing
- counterfactual testing

#### Hetvabhasa

Maps to:

- verifier specialist invocation
- fallacy detection
- invalid inference rejection
- checking whether the candidate reasoning path is structurally weak

#### Nirnaya

Maps to:

- final synthesis
- commitment to the response
- trace emission
- decision that the answer is good enough to return

### 20.10.3 Why this is better than simple weighted merge

A weighted merge assumes good answers emerge from ranking and blending.
A Sanskrit-inspired pipeline assumes:

- knowledge sources matter
- challenge phases matter
- fallacy rejection matters
- judgment should follow inquiry

This makes the final response more epistemically disciplined.

---

## 20.11 Kripke modal arbitration in practical system terms

### 20.11.1 Why modal reasoning belongs here

Some Genius tasks will produce multiple answers that are all locally plausible.
This is especially true when:

- the prompt is ambiguous
- the memory state is incomplete
- different nodes infer different assumptions
- grounded facts only partially constrain the answer

A modal framework gives the arbiter a structured way to reason across these alternatives.

### 20.11.2 World construction

The system may construct candidate worlds from:

- draft A assumptions
- draft B assumptions
- memory-constrained variants
- grounded-fact-constrained variants
- policy-constrained variants

Each candidate becomes a structured hypothesis state.

### 20.11.3 Accessibility and survivability

The arbiter can then reason over:

- which worlds are accessible from the current evidence state
- which worlds violate known constraints
- which worlds contradict grounded or trusted memory
- which worlds remain consistent after verifier passes

### 20.11.4 Fixed-point resolution

Some contradictions only collapse after repeated evaluation.
A modal machine can support:

- repeated pruning
- convergence toward stable surviving states
- final synthesis from the most stable candidate world

This is valuable for uncertain multi-step tasks and conflicting swarm outputs.

---

## 20.12 Hybrid arbitration strategies

### 20.12.1 Sequential hybrid

A sequential hybrid pipeline may:

1. classify uncertainty
2. tag pramana sources
3. construct candidate reasoning paths
4. convert them into possible worlds
5. run contradiction and accessibility checks
6. synthesize from surviving world states

### 20.12.2 Parallel hybrid

A parallel hybrid pipeline may run:

- Sanskrit branch
- Kripke branch

in separate regions and then merge through a weighted synthesis strategy.

### 20.12.3 Why hybridization matters

Different epistemologies are strong at different things.

For example:

- Sanskrit inquiry is strong at staged knowledge validation and critique
- modal reasoning is strong at uncertain interpretation management
- hybridization lets the system use each where it matters most

---

## 20.13 GQHSM machine structure

### 20.13.1 Structural requirements

The arbitration runtime must support:

- top-level framework selection
- nested or composite states
- parallel regions
- guard conditions
- entry and exit actions
- internal actions
- shared context mutation
- recovery transitions
- final trace emission

### 20.13.2 Representative machine outline

A top-level machine may include:

- `Idle`
- `FrameworkSelector`
- `SanskritPipeline`
- `KripkePipeline`
- `HybridPipeline`
- `Finalize`
- `Escalate`

### 20.13.3 Sanskrit branch outline

A Sanskrit branch may include:

- `Samshaya`
- `Pramana`
- `PanchaAvayava`
- `Tarka`
- `Hetvabhasa`
- `Nirnaya`

### 20.13.4 Kripke branch outline

A Kripke branch may include:

- `WorldModel`
- `AccessibilityCheck`
- `ModalEvaluation`
- `ContradictionPressure`
- `FixedPointResolution`
- `WorldSelection`

### 20.13.5 Hybrid branch outline

A hybrid branch may:

- run Sanskrit and Kripke in orthogonal regions
- wait until both are merge-ready
- merge according to a configured strategy
- pass the merged result to final synthesis

---

## 20.14 JSON-defined machine configuration

The machine definition should live in JSON or equivalent structured configuration.

This allows:

- version control of frameworks
- runtime framework switching
- hot-swappable machine definitions
- auditability
- deterministic deployment across nodes

### 20.14.1 Example machine definition

```json
{
  "machine": "EpistemicArbiter",
  "version": "1.0.0",
  "initialState": "FrameworkSelector",
  "frameworks": {
    "SANSKRIT": { "enabled": true },
    "KRIPKE": { "enabled": true },
    "HYBRID": { "enabled": true, "mergeStrategy": "reputationWeighted" }
  },
  "states": {
    "FrameworkSelector": {
      "type": "choice",
      "transitions": [
        { "guard": "selectFramework == 'SANSKRIT'", "target": "SanskritPipeline" },
        { "guard": "selectFramework == 'KRIPKE'", "target": "KripkePipeline" },
        { "guard": "selectFramework == 'HYBRID'", "target": "HybridPipeline" }
      ]
    },
    "SanskritPipeline": {
      "type": "composite",
      "initial": "Samshaya",
      "states": {
        "Samshaya": {
          "onEntry": "initializeContext",
          "do": "classifyProblem",
          "transitions": [
            { "guard": "hasValidKnowledgeSources", "target": "Pramana" }
          ]
        },
        "Pramana": {
          "do": "gatherKnowledgeSources",
          "transitions": [
            { "target": "PanchaAvayava" }
          ]
        },
        "PanchaAvayava": {
          "do": "constructReasoningModel",
          "transitions": [
            { "target": "Tarka" }
          ]
        },
        "Tarka": {
          "do": "critiqueAndValidate",
          "transitions": [
            { "guard": "hasNoCriticalContradictions", "target": "Hetvabhasa" },
            { "target": "Escalate" }
          ]
        },
        "Hetvabhasa": {
          "do": "performInference",
          "transitions": [
            { "target": "Nirnaya" }
          ]
        },
        "Nirnaya": {
          "do": "resolveAndSynthesize",
          "onExit": "emitTrace"
        }
      }
    },
    "KripkePipeline": {
      "type": "composite",
      "initial": "WorldModel",
      "states": {
        "WorldModel": {
          "do": "constructReasoningModel",
          "transitions": [
            { "target": "AccessibilityCheck" }
          ]
        },
        "AccessibilityCheck": {
          "do": "computeEpistemicWeights",
          "transitions": [
            { "target": "ModalEvaluation" }
          ]
        },
        "ModalEvaluation": {
          "do": "performInference",
          "transitions": [
            { "target": "FixedPointResolution" }
          ]
        },
        "FixedPointResolution": {
          "do": "resolveAndSynthesize",
          "onExit": "emitTrace"
        }
      }
    }
  },
  "globalActions": {
    "onEntry": "initializeContext",
    "onExit": "finalizeOutput"
  }
}
```

### 20.14.2 Why this matters

A JSON machine like this is:

- inspectable
- versionable
- easy to ship
- easy to update
- easy to adapt for new frameworks

This is one of the strongest arguments for GQHSM as the runtime.

---

## 20.15 Generic callback model

The callback registry should remain generic and framework-neutral.

The goal is to define a small, stable callback vocabulary that Sanskrit, Kripke, and future frameworks can all implement differently.

### 20.15.1 Context and lifecycle callbacks

Recommended generic callbacks:

- `initializeContext`
- `emitTrace`
- `finalizeOutput`

Responsibilities:

- load drafts
- load memory packets
- attach reputation and policy metadata
- allocate trace objects
- finalize response output
- write memory or log artifacts

### 20.15.2 Core reasoning callbacks

Recommended generic callbacks:

- `classifyProblem`
- `gatherKnowledgeSources`
- `constructReasoningModel`
- `performInference`
- `critiqueAndValidate`
- `resolveAndSynthesize`
- `computeEpistemicWeights`

These names are deliberately generic so they can map to:

- Samshaya, Pramana, Tarka, Nirnaya
- world-model construction
- modal inference
- Bayesian belief revision
- future custom frameworks

### 20.15.3 Guard callbacks

Recommended generic guards:

- `hasSufficientReputation`
- `hasValidKnowledgeSources`
- `hasNoCriticalContradictions`
- `isHybridMergeReady`
- `requiresHumanReview`

These can control transitions without embedding framework-specific names into the runtime.

### 20.15.4 Why generic callbacks matter

This allows the machine format to remain stable while plugins change behavior.
That makes framework delivery much easier.

---

## 20.16 Plugin architecture

### 20.16.1 Why plugins are the right shape

Each new epistemic framework should be delivered as a small shared library.

Typical formats:

- `.so`
- `.dll`
- platform-native shared objects

This is preferred because plugins are expected to be:

- extremely small
- very fast to write
- rare to change
- cheap to ship in app updates

This is ideal for phones, desktops, and other GNUS nodes.

### 20.16.2 What a plugin does

A plugin registers callback implementations into the GQHSM registry.

It does not need to define the entire runtime.
It only supplies behavior for generic callback names.

### 20.16.3 Stable plugin ABI

A minimal shared header should define the ABI.

Example:

```cpp
#pragma once
#include "GQHSM.h"
#include "EpistemicContext.h"

extern "C" {
 bool GQHSM_RegisterEpistemicPlugin(GQHSM::Registry& registry, EpistemicContext& ctx);
 const char* GQHSM_GetPluginName();
 const char* GQHSM_GetPluginVersion();
 const char* GQHSM_GetSupportedFrameworks();
}
```

### 20.16.4 Example plugin shape

A Sanskrit plugin may register:

- `classifyProblem`
- `gatherKnowledgeSources`
- `constructReasoningModel`
- `critiqueAndValidate`
- `performInference`
- `resolveAndSynthesize`

with Sanskrit-specific function bodies.

A Kripke plugin may register the exact same names with modal logic implementations.

### 20.16.5 Operational advantages

This gives the system a deployment model in which:

- a new plugin can be shipped as part of an app update
- a node can gain a new reasoning framework with minimal code churn
- the core requestor-node runtime remains stable
- framework experimentation does not disturb the model runtime

---

## 20.17 Future WASM extension path

The initial implementation should favor native shared libraries for simplicity and speed.

However, the architecture should remain compatible with a later WASM path.

### 20.17.1 Why WASM is attractive later

WASM would enable:

- stronger isolation
- safer third-party extensions
- cross-platform plugin portability
- deterministic runtime behavior
- sandboxed experimental frameworks

### 20.17.2 Why not require it first

The current need is speed and simplicity.

Because the plugins are expected to be tiny and infrequently updated, native `.so` and `.dll` delivery is the easiest initial path.

### 20.17.3 Forward compatibility

The plugin contract should therefore be designed so that a future WASM module can export behavior equivalent to the native ABI.

---

## 20.18 Epistemic context model

The arbitration runtime needs a structured context object shared across states and callbacks.

### 20.18.1 Required inputs

A representative `EpistemicContext` should include:

- request ID
- selected framework
- specialist drafts
- verifier outputs
- HCTS outputs
- GAML memory packets
- grounding facts
- reputation scores
- latency metadata
- policy flags
- safety flags
- tool execution context if present
- recovery state
- arbitration trace object
- final synthesis buffer

### 20.18.2 Why this context matters

A generic context object keeps the runtime uniform.
It allows plugins and machines to focus on reasoning rather than plumbing.

---

## 20.19 Example plugin and loader behavior

### 20.19.1 Example registration flow

At startup or framework activation:

1. load plugin
2. obtain registration symbol
3. register callbacks
4. load JSON machine
5. bind callback names to machine states
6. execute machine against `EpistemicContext`

### 20.19.2 Example loader shape

The loader scans a plugin directory for shared objects, loads them, and registers any valid epistemic plugins into the runtime registry.

This architecture supports:

- optional frameworks
- partial deployment sets
- framework versioning
- selective enablement by node capability or policy

---

## 20.20 Output model and thinking trace

The arbitration layer should emit a structured JSON trace rather than opaque raw text.

### 20.20.1 Example trace artifact

```json
{
  "request_id": "uuid",
  "framework": "sanskrit_hybrid_v1",
  "arbiter_node": "node_id",
  "states_visited": [
    "FrameworkSelector",
    "Samshaya",
    "Pramana",
    "PanchaAvayava",
    "Tarka",
    "Hetvabhasa",
    "Nirnaya"
  ],
  "candidate_outputs": [
    "draft_a",
    "draft_b"
  ],
  "knowledge_sources": [
    "GAML:fact_store",
    "Grokipedia",
    "VerifierSpecialist",
    "HCTS:Adversarial"
  ],
  "rejected_paths": [
    {
      "candidate": "draft_b",
      "reason": "contradiction_with_grounded_fact"
    }
  ],
  "final_output": "draft_a_refined",
  "needs_followup": false
}
```

### 20.20.2 Why this is important

This trace can be used for:

- swarm thinking visibility
- debugging
- auditability
- replay
- memory writeback
- retraining targets
- framework benchmarking

This extends the existing thinking trace concept into a more explicit cognitive lineage artifact.

---

## 20.21 Integration with memory writeback and retraining

### 20.21.1 Memory writeback

The arbitration layer should influence what gets written back to GAML.

For example:

- surviving synthesis rationales
- rejected contradiction patterns
- validated source mappings
- framework success metadata
- user preference effects
- escalation outcomes

### 20.21.2 Retraining implications

The arbitration trace also creates new retraining opportunities.

Possible targets:

- framework selection policy
- contradiction detection quality
- synthesis quality after Tarka
- verifier usefulness
- HCTS invocation policy
- plugin quality scoring

This makes epistemic arbitration not only a control layer but a learning signal generator.

---

## 20.22 Strategic implications

### 20.22.1 Why this matters competitively

Many systems now recognize the need for a reasoning layer above base models.

What differentiates Genius is that it can combine:

- routed specialists
- structured memory
- distributed swarm execution
- reputation-aware trust
- secure agent mediation
- inspectable thinking traces
- and now formal, selectable epistemic arbitration

This is a much more complete Cognitive OS stack than a simple reasoning shell over one centralized LLM.

### 20.22.2 Why this matters architecturally

The system is no longer only:

- model
- router
- memory
- consensus
- synthesis

It now becomes:

- model
- router
- memory
- consensus
- epistemic arbiter
- synthesis
- structured trace
- adaptive evolution

That is a materially different system category.

---

## 20.23 Risks and open questions

Several questions remain open and should be treated as active design areas.

These include:

- how framework selection should be triggered
- how much runtime overhead hybrid arbitration adds
- how deterministic plugins must be
- how framework success should influence reputation
- whether some frameworks should be policy-gated by domain
- how to version trace schemas cleanly
- how to benchmark Sanskrit vs Kripke vs hybrid performance
- when arbitration should escalate to human review
- whether some tool-execution scenarios require dedicated epistemic profiles

These are real design questions, not blockers.

---

## 20.24 Summary

This document adds a missing control layer to the Genius Cognitive System:

formal epistemic arbitration

That layer is implemented through:

- the Requestor Node as Epistemic Arbiter
- GQHSM as the data-driven hierarchical state machine runtime
- JSON-defined arbitration machines
- generic callback registration
- tiny shared-library framework plugins
- future WASM-compatible extension paths
- structured JSON thinking traces

The result is a Cognitive OS architecture that does not merely generate and rank answers.

It can also reason explicitly about how answers should be judged.

---

[Previous: Personalized Cognitive Critical Thinking](./14-cognitive-retaining-system.md) | [Architecture Index](./INDEX.md)
