## Conflict Detection Report

Generated: 2026-06-18 | Mode: merge | Precedence: ADR > SPEC > PRD > DOC

---

### BLOCKERS (15)

All blockers are cross-ref graph cycles. These are navigational cycles (bidirectional "previous/next" links in a linear document series), not semantic dependency cycles. Each doc's content is self-contained and was extracted independently. The cycles prevent cross-document dependency resolution via the reference graph but do not affect per-document extraction.

[BLOCKER] Cross-ref cycle: 01-executive-summary <-> 02-system-overview
  Found: docs/architecture/01-executive-summary.md references 02-system-overview
  Found: docs/architecture/02-system-overview.md references 01-executive-summary
  Impact: Bidirectional navigation link. Does not block per-document extraction.
  -> Accept as navigational artifact of the document series format.

[BLOCKER] Cross-ref cycle: 02-system-overview <-> 03-model-and-router
  Found: docs/architecture/02-system-overview.md references 03-model-and-router
  Found: docs/architecture/03-model-and-router.md references 02-system-overview
  Impact: Bidirectional navigation link.
  -> Accept as navigational artifact.

[BLOCKER] Cross-ref cycle: 02-system-overview <-> 16-sgfp4-format
  Found: docs/architecture/02-system-overview.md references 16-sgfp4-format
  Found: docs/architecture/16-sgfp4-format.md references 02-system-overview
  Impact: Bidirectional navigation link.
  -> Accept as navigational artifact.

[BLOCKER] Cross-ref cycle: 03-model-and-router <-> 04-reputation-consensus
  Found: docs/architecture/03-model-and-router.md references 04-reputation-consensus
  Found: docs/architecture/04-reputation-consensus.md references 03-model-and-router
  Impact: Bidirectional navigation link.
  -> Accept as navigational artifact.

[BLOCKER] Cross-ref cycle: 03-model-and-router <-> 16-sgfp4-format
  Found: docs/architecture/03-model-and-router.md references 16-sgfp4-format
  Found: docs/architecture/16-sgfp4-format.md references 03-model-and-router
  Impact: Bidirectional navigation link.
  -> Accept as navigational artifact.

[BLOCKER] Cross-ref cycle: 04-reputation-consensus <-> 05-grounding
  Found: docs/architecture/04-reputation-consensus.md references 05-grounding
  Found: docs/architecture/05-grounding.md references 04-reputation-consensus
  Impact: Bidirectional navigation link.
  -> Accept as navigational artifact.

[BLOCKER] Cross-ref cycle: 05-grounding <-> 06-agentic-memory-layer
  Found: docs/architecture/05-grounding.md references 06-agentic-memory-layer
  Found: docs/architecture/06-agentic-memory-layer.md references 05-grounding
  Impact: Bidirectional navigation link.
  -> Accept as navigational artifact.

[BLOCKER] Cross-ref cycle: 06-agentic-memory-layer <-> 07-execution-and-performance
  Found: docs/architecture/06-agentic-memory-layer.md references 07-execution-and-performance
  Found: docs/architecture/07-execution-and-performance.md references 06-agentic-memory-layer
  Impact: Bidirectional navigation link.
  -> Accept as navigational artifact.

[BLOCKER] Cross-ref cycle: 07-execution-and-performance <-> 08-roadmap-and-risks
  Found: docs/architecture/07-execution-and-performance.md references 08-roadmap-and-risks
  Found: docs/architecture/08-roadmap-and-risks.md references 07-execution-and-performance
  Impact: Bidirectional navigation link.
  -> Accept as navigational artifact.

[BLOCKER] Cross-ref cycle: 08-roadmap-and-risks <-> 09-future-and-positioning
  Found: docs/architecture/08-roadmap-and-risks.md references 09-future-and-positioning
  Found: docs/architecture/09-future-and-positioning.md references 08-roadmap-and-risks
  Impact: Bidirectional navigation link.
  -> Accept as navigational artifact.

[BLOCKER] Cross-ref cycle: 09-future-and-positioning <-> 10-ai-safety
  Found: docs/architecture/09-future-and-positioning.md references 10-ai-safety
  Found: docs/architecture/10-ai-safety.md references 09-future-and-positioning
  Impact: Bidirectional navigation link.
  -> Accept as navigational artifact.

[BLOCKER] Cross-ref cycle: 10-ai-safety <-> 11-distributed-swarm-thinking-context
  Found: docs/architecture/10-ai-safety.md references 11-distributed-swarm-thinking-context
  Found: docs/architecture/11-distributed-swarm-thinking-context.md references 10-ai-safety
  Impact: Bidirectional navigation link.
  -> Accept as navigational artifact.

[BLOCKER] Cross-ref cycle: 11-distributed-swarm-thinking-context <-> 12-secure-agent-architecture
  Found: docs/architecture/11-distributed-swarm-thinking-context.md references 12-secure-agent-architecture
  Found: docs/architecture/12-secure-agent-architecture.md references 11-distributed-swarm-thinking-context
  Impact: Bidirectional navigation link.
  -> Accept as navigational artifact.

[BLOCKER] Cross-ref cycle: 12-secure-agent-architecture <-> 13-eggroll-swarm-retraining
  Found: docs/architecture/12-secure-agent-architecture.md references 13-eggroll-swarm-retraining
  Found: docs/architecture/13-eggroll-swarm-retraining.md references 12-secure-agent-architecture
  Impact: Bidirectional navigation link.
  -> Accept as navigational artifact.

[BLOCKER] Cross-ref cycle: 13-eggroll-swarm-retraining <-> 14-cognitive-retaining-system
  Found: docs/architecture/13-eggroll-swarm-retraining.md references 14-cognitive-retaining-system
  Found: docs/architecture/14-cognitive-retaining-system.md references 13-eggroll-swarm-retraining
  Impact: Bidirectional navigation link.
  -> Accept as navigational artifact.

Note: Larger cycles exist (e.g., 16->07->06->05->04->03->16) caused by doc 16 cross-referencing multiple earlier docs. These are recorded as distinct cycles but are all navigational in nature. 1 doc (15-epistemic-arbitration) is outside all cycles.

---

### WARNINGS (2)

[WARNING] Competing architectural paths: Adapter-based vs standalone specialists
  Found: docs/architecture/11-distributed-swarm-thinking-context.md (DOC) Section 16.15 describes two implementation paths:
    Path A: "separate small specialist models"
    Path B: "shared semantic backbone with multiple specialist adapters"
  Context: Both are compatible with the swarm-thinking design. The documentation does not lock in one choice.
  Open items noted in 11 Section 16.15.1:
    - Which specialists are full models vs adapters
    - How adapters are composed or switched
    - Whether synthesis, verifier, and planner roles use shared or independent backbones
    - What teacher data is used for each specialist
    - What evaluation sets measure each specialist role
  Impact: gnus-poc (ELM teacher->student training/distillation) must select a concrete path for its implementation. Synthesis cannot pick without losing intent.
  -> Choose one variant or document both as separate implementation phases before routing to roadmap.

[WARNING] Undefined quantization policy for specialist models
  Found: docs/architecture/11-distributed-swarm-thinking-context.md (DOC) Section 16.14.5:
    - "which specialists should share a backbone versus remain separate models"
    - "whether adapter composition should be preferred over multiple standalone specialists"
    - "whether role specialists and domain specialists should use the same quantization policy"
    - "how reputation should interact with quantization-induced quality drift"
  Also relevant: docs/architecture/16-sgfp4-format.md (SPEC) defines the quantization format in detail but does not specify per-specialist quantization policy.
  Impact: gnus-poc uses SGFP4 quantization format. The quantization strategy for different specialist types is undefined and will affect the distillation pipeline design.
  -> Define quantization policy per specialist role before implementing the training pipeline.

---

### INFO (0)

No auto-resolved conflicts. All 16 documents describe complementary architectural layers of the same system (GeniusCognitiveSystem). The 2 SPEC-classified documents (04-reputation-consensus, 12-secure-agent-architecture) carry higher precedence than the 14 DOC-classified documents under the default ordering but no content contradictions were found requiring resolution.

No ADR or PRD documents were present in the ingest set, so no ADR-vs-X or PRD-overlap conflicts were possible.

No UNKNOWN/low-confidence classifications were found -- all 16 docs carry high or medium confidence with unambiguous type assignments.

The existing Architecture.md in .planning/ is a negligible stub. No existing locked decisions, requirements, or constraints needed checking against (merge mode with empty existing context).
