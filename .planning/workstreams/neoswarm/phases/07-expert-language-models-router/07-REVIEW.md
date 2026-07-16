---
phase: 07-expert-language-models-router
reviewed: 2026-07-16T00:00:00Z
depth: standard
files_reviewed: 5
files_reviewed_list:
  - src/elm/i_elm.hpp
  - src/elm/CMakeLists.txt
  - src/elm/elm_stub.cpp
  - src/common/types.hpp
  - src/CMakeLists.txt
findings:
  critical: 0
  warning: 1
  info: 7
  total: 8
status: issues_found
---

# Phase 07: Code Review Report — Wave 1 (ELM Core Types & Interface)

**Reviewed:** 2026-07-16
**Depth:** standard
**Files Reviewed:** 5
**Status:** issues_found (1 warning, 7 info — zero critical)

## Summary

Reviewed Phase 7 Wave 1 deliverables: the `IELM` abstract interface (`src/elm/i_elm.hpp`), new ELM core types in `src/common/types.hpp` (`ELMRole`, `ELMContext`, `ChainStep`, `ExecutionChain`, `ExecutionMode::ElmAssisted`, and two new `PromptFeatures` flags), the `neoswarm_elm` CMake library target, the compile-time verification stub, and the parent CMakeLists addition.

**Overall assessment:** Wave 1 is structurally sound. The `IELM` interface correctly delivers all 6 pure virtuals per decision D-05, mirrors the existing `ISpecialist` pattern, and has correct virtual destructor, const-correctness, and Doxygen. The new types in `types.hpp` honor decisions D-08 (types in common/types.hpp) and D-09 (flat chain with DAG-extensible struct shape). CMake is consistent with existing module conventions. No blockers for merge.

**Key concern (WR-01):** The `Process()` method has a redundant double-accounting of the previous step's output — it arrives as both the `input` parameter and `context.m_lastOutput`. This creates a synchronization burden on callers and ambiguity for ELM implementers. Should be resolved before Waves 2–6 add real implementations.

---

## Warnings

### WR-01: Redundant `m_lastOutput` in `ELMContext` vs `Process()` input parameter

**File:** `src/common/types.hpp:159` and `src/elm/i_elm.hpp:50`

**Issue:** The `Process()` method signature receives the previous step's output through two channels — the explicit `input` parameter (`const std::string& input`) and the context field `ELMContext::m_lastOutput`. The chain executor (per D-13: "output of each step feeds the next via ELMContext") must set `ctx.m_lastOutput` before each call so the two are always equal, creating a silent invariant that callers are responsible for maintaining.

If a future chain executor or test harness passes `context.m_lastOutput` that differs from the `input` argument, ELM implementations have no way to determine which is authoritative. Similarly, ELM implementers in Waves 2–6 have an ambiguous contract: should they use `input` or `context.m_lastOutput`?

**Recommended resolution — pick one of:**

1. **Remove `m_lastOutput` from ELMContext** — let the `input` parameter carry the previous output exclusively. Simplest fix, preserves the Process signature, removes the redundancy. The chain executor updates its own local variable for the next iteration, not the context struct.
   ```cpp
   // ELMContext without m_lastOutput:
   struct ELMContext
   {
       std::string m_originalTask;
       std::vector<std::pair<ELMRole, float>> m_stepConfidences;
       std::vector<KnowledgeFact> m_groundingFacts;
   };
   ```
2. **Remove the `input` parameter** — let Process read from `context.m_lastOutput`. Requires changing `context` from `const ELMContext&` to `ELMContext&` (the ELM should not mutate it, but the chain executor mutates it between calls anyway). Less clean — adds mutability to the context.
3. **Keep both but add a runtime assertion** — `assert(input == context.m_lastOutput)` in a debug build of Process. Least disruptive but hides a design smell.

**Recommendation:** Option 1 (remove `m_lastOutput`). It's the cleanest and incurs the smallest contract change. The chain executor maintains its own `std::string lastOutput` local variable; `ELMContext` carries only the aggregate state (original task, confidence history, grounding facts).

---

## Info

### IN-01: Pre-existing naming inconsistency — `PromptFeatures` uses underscore suffix instead of `m_` prefix

**File:** `src/common/types.hpp:103-108`

**Issue:** `PromptFeatures` fields use trailing-underscore naming (`numeric_density_`, `has_code_syntax_`, `complexity_`, `token_count_`, `has_math_keywords_`, `has_grammar_request_`) rather than the project-standard `m_` prefix. The two new Phase 7 fields (`has_grounding_request_`, `has_formatting_request_` at lines 109–110) correctly follow the pre-existing local convention for consistency.

**Fix (pre-existing; not this PR's scope):** Rename all `PromptFeatures` fields to `m_` prefix in a separate cleanup pass.

### IN-02: Pre-existing naming inconsistency — `RouteDecision::confidence_` uses underscore suffix

**File:** `src/common/types.hpp:93`

**Issue:** `RouteDecision::confidence_` uses trailing underscore instead of `m_` prefix. `m_reasoning` and `m_mode` in the same struct correctly use `m_`.

**Fix (pre-existing; not this PR's scope):** Rename to `m_confidence` in a separate cleanup pass.

### IN-03: Pre-existing naming inconsistency — `NodeOutput::reputation_` uses underscore suffix

**File:** `src/common/types.hpp:122`

**Issue:** `NodeOutput::reputation_` uses trailing underscore instead of `m_` prefix. All other fields in the struct (`m_nodeId`, `m_output`, `m_perplexity`, `m_latencyMs`) correctly use `m_`.

**Fix (pre-existing; not this PR's scope):** Rename to `m_reputation` in a separate cleanup pass.

### IN-04: No `noexcept` on `IELM` pure virtual methods

**File:** `src/elm/i_elm.hpp:29,32,35,42,50,56`

**Issue:** Per CLAUDE.md — "All functions should be declared noexcept unless explicitly required to throw." None of the 6 `IELM` pure virtual methods are marked `noexcept`. However, this is consistent with the existing `ISpecialist` and `IRouter` interfaces, which also omit `noexcept`. The project-wide convention appears to rely on `outcome::result<T>` for error handling rather than `noexcept` annotations on virtual methods.

**Fix (project-wide, not this PR's scope):** If the team wants to enforce the `noexcept` guideline, add it across all interface hierarchies simultaneously so callers don't get inconsistent guarantees.

### IN-05: `ELMContext` does not retain outputs of prior chain steps beyond the last one

**File:** `src/common/types.hpp:158-162`

**Issue:** `m_stepConfidences` records per-step confidence scores but not per-step *outputs*. For chains longer than 2 steps, an ELM can see the immediately prior step's output (via the `input` parameter) but not earlier steps' outputs. For example, in a `Planner → Draft → Verifier → Refiner` chain, the Refiner sees the Verifier's output but not the Planner's plan or the Draft's raw text.

This is a deliberate Phase 7 constraint per decision D-09 (flat sequential chain) and is not a bug. However, if any Wave 2–6 ELM needs cross-step context (e.g., the Verifier comparing the Draft against the Planner's plan), this limitation will surface.

**Fix (future enhancement):** Add `std::vector<std::pair<ELMRole, std::string>> m_stepOutputs` to ELMContext when needed. Not required for Phase 7.

### IN-06: Comment confusion — `ExecutionMode::ElmAssisted` value is 3 but comment says "Mode 2"

**File:** `src/common/types.hpp:26`

**Issue:** 
```cpp
ElmAssisted = 3 ///< Mode 2 (doc 07 §9.2) — ELM-assisted sequential chain (Phase 7+)
```
The comment calls this "Mode 2" but the numeric value is 3. In the execution-mode numbering scheme, 0=SingleNode (Mode 1), 1=Specialist (Mode 2), 2=Swarm (Mode 3), 3=ElmAssisted. The "Mode 2" in the comment refers to this being a variant of the Specialist (Mode 2) sequential pattern, not the numeric enum value. The doc reference disambiguates, but a quick read is confusing.

**Fix:** Clarify comment: `///< ELM-assisted sequential chain — extends Mode 2 Specialist pattern (doc 07 §9.2, Phase 7+)`

### IN-07: Missing debug-only runtime invariant check between `input` and `context.m_lastOutput`

**File:** `src/elm/elm_stub.cpp:25-30`

**Issue:** The compile-time verification stub only checks that `sizeof(IELM)` compiles. If WR-01 is resolved by keeping both `input` and `m_lastOutput` (option 3), adding a runtime invariant assertion in a debug build of the stub (or a dedicated test) would catch caller mistakes early:
```cpp
#include <cassert>
// ...
static_assert(sizeof(sgns::neoswarm::elm::IELM) > 0, "IELM must be instantiable");
```
The current `sizeof` check does validate template instantiation but `static_assert` with a message string would be more self-documenting.

**Fix:** Replace `static_cast<void>(sizeof(...))` with `static_assert(sizeof(...) > 0, "...")` for better diagnostics. Alternatively, add a dedicated `static_assert` elsewhere — the stub's purpose is satisfied either way.

---

_Reviewed: 2026-07-16_
_Reviewer: OpenCode (gsd-code-reviewer)_
_Depth: standard_
