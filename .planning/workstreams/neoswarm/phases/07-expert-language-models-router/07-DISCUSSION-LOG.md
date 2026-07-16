# Phase 7: Expert Language Models + Router — Discussion Log

**Date:** 2026-07-15
**Mode:** User-delegated auto-selection ("clearly analyse and choose best all choices")
**Prior context:** A previous 07-CONTEXT.md (2026-07-13) was deleted by the user as potentially wrong; discussion restarted fresh from architecture docs 03 and 11.

---

## Areas Presented

1. What physically backs each role ELM
2. ELM interface design & legacy specialist mapping
3. Chain representation & MVP routing rules
4. ELM configuration surface
5. Grounding + Tool-Support boundaries

User selected: all (delegated final choice to OpenCode after options were presented with analysis).

---

## Area 1: ELM backing

**Options presented:**
- A. Shared backbone + role prompts (zero extra memory, works today)
- B. Separate model file per role (7 permanent stubs in practice)
- C. Hybrid — shared backbone default, optional per-role model path

**Selected: C (Hybrid).** Role-specific trained models do not exist yet (gnus-poc trained domain LoRA specialists only). Doc 03 §5.2.1 explicitly sanctions shared-backbone ELMs. C gives B's migration path at A's cost. Eliminates the 8GB memory risk.

## Area 2: Interface design

**Selected: new `IELM` + composition adapters; `ISpecialist` untouched.** Legacy mapping straight from doc 03 §5.2.6: Grammar → Refiner/Formatter, Math → Math domain ELM, SymbolicFallback stays internal. Minimal-change, existing tests intact.

## Area 3: Chain representation

**Selected: flat sequential step list, graph-ready struct; parallel deferred to Phase 9.** Resolves the contradiction in the deleted context (sequential type vs parallel multi-domain pattern). MVP chains implement doc 03 §6.2's six heuristic triggers. Router split: RuleBasedRouter (unchanged) + new ELMChainBuilder.

## Area 4: Configuration surface

**Selected: `elms` section in existing JSON config; no new CLI flags.** Consistent with Phase 2 D-09. Rejected the deleted context's 10 per-ELM CLI flags as unwieldy. Lazy default, per-ELM eager opt-in.

## Area 5: Grounding + Tool-Support

**Selected: GroundingELM wraps existing `knowledge/` pipeline; ToolSupportELM is a stub until Phase 10.** No duplicate retrieval implementation; tool safety belongs to Phase 10's Tool Intermediary.

---

## Deferred Ideas Captured

- Parallel multi-domain dispatch → Phase 9
- Learned classifier router → Phase 7.5
- Cognitive planner / execution graphs → Phase 8+
- Real tool-call logic → Phase 10
- Additional domain ELMs (Legal, Finance, etc.) → future
