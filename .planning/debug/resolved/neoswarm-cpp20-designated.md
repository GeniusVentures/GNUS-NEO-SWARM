---
status: resolved
trigger: "test_common_types.cpp(165,9): error C7555: use of designated initializers requires at least '/std:c++20', in test_common_types.vcxproj, during a full outer build (cmake --build build/Windows/Release --parallel 8 --config Release from W:\\gnus\\GeniusCognitiveSystem)."
created: 2026-08-19
updated: 2026-08-19
---

## Symptoms

**Expected behavior:** `test_common_types.vcxproj` compiles cleanly under this project's mandated C++17 standard (per GNUS-NEO-SWARM/CLAUDE.md: "Always make sure to only use C++17 features and below").

**Actual behavior:**
```
W:\gnus\GeniusCognitiveSystem\GNUS-NEO-SWARM\test\common\test_types.cpp(165,9): error C7555: use of designated initializers requires at least '/std:c++20' [W:\gnus\GeniusCognitiveSystem\build\Windows\Release\test\test_common_types.vcxproj]
```

**Error messages:** Exact compiler output above — MSVC rejecting a C++20-only designated-initializer syntax under this project's C++17 language standard.

**Timeline:** First seen in a full outer-build attempt on 2026-08-18/19, after fixing an unrelated, earlier-blocking MNN header/linkage issue that had prevented the build from reaching this test target before. Not yet known whether `test_types.cpp:165`'s designated-initializer usage is new/recent or has been present for a while without ever being compiled in this outer-build configuration.

**Reproduction:**
```
cd W:\gnus\GeniusCognitiveSystem
cmake --build build/Windows/Release --target test_common_types --config Release
```

## Context

This is a fresh debug session split out from a broader `neoswarm-mnn-llm-header` debug session (now resolved and archived) that surfaced several distinct, unrelated build failures in the same full-build log. This one is scoped ONLY to this single C++20/C++17 language-standard violation in `test/common/test_types.cpp:165`. Do not touch MNN-related files, the Boost.Test linkage issue (separate session `neoswarm-boost-test-gtest`), the missing `GeniusSDK.hpp` include issue, or the `dllimport` issue in `test_genius_elm_ffi.vcxproj` — those are separate, independently-tracked debug sessions.

This is likely the simplest of the 4 remaining issues: either (a) rewrite the designated-initializer struct construction at line 165 using ordinary positional/named-constructor initialization compatible with C++17, or (b) if designated initializers are load-bearing for readability there, evaluate with the user whether this specific test file could opt into `/std:c++20` locally — but per CLAUDE.md's project-wide C++17-only rule, (a) is almost certainly the correct minimal fix.

## Current Focus

reasoning_checkpoint:
  hypothesis: "test_types.cpp:164-173 uses C++20 designated-initializer syntax (`CognitiveAsset a{ .m_id = ..., .m_entity = ..., ... }`) to construct a `CognitiveAsset` aggregate; MSVC under /std:c++17 rejects this with C7555. Replacing it with default-construction + member assignment (all C++17-legal) removes the C++20 dependency while producing bit-identical field values."
  confirming_evidence:
    - "Compiler error is exactly C7555 'use of designated initializers requires at least /std:c++20' at test_types.cpp(165,9), which is the `.m_id = \"test-001\"` line inside `TEST(CognitiveAsset, DesignatedInitialization)`."
    - "CognitiveAsset (src/common/types.hpp:180-191) is a plain aggregate struct (no user-declared constructors) with members in order: m_id, m_entity, m_type, m_payload, m_timestamp, m_sourceNode, m_confidence, m_provenance, m_trustClass. The test's designated-init list names m_id, m_entity, m_type, m_timestamp, m_sourceNode, m_confidence, m_provenance, m_trustClass in that same relative order (m_payload omitted, defaults to `{}` json), consistent with valid C++20 designated-init semantics."
  falsification_test: "If replacing the designated-init block with default-construction + assignment still fails to compile, or the C7555 error persists/moves, the hypothesis is wrong. If it compiles and EXPECT_EQ assertions on a.m_id/m_entity/m_type/m_timestamp/m_confidence/m_sourceNode still pass with the same values, hypothesis is confirmed."
  fix_rationale: "Root cause is a single non-conforming syntax usage (project mandates C++17-and-below per CLAUDE.md), not a build-config gap. Fix addresses the actual violation (the syntax itself) rather than relaxing the language standard for this file/target."
  blind_spots: "Have not yet run the isolated target build to confirm no other latent C++20 usages exist in this same test file beyond line 165-173."

hypothesis: CONFIRMED — see reasoning_checkpoint above.

test: Replace designated-initializer aggregate construction with default-construction + explicit member assignment (C++17-legal), then rebuild target test_common_types.

expecting: C7555 error at test_types.cpp:165 disappears; test assertions (lines 174-179) still pass with identical field values.

next_action: DONE — fix applied and self-verified. Awaiting user confirmation before archiving session (do not commit without explicit user permission per session instructions).

## Evidence

- timestamp: 2026-08-18
  checked: GNUS-NEO-SWARM/test/common/test_types.cpp lines 100-200
  found: |
    Line 162-173:
    ```cpp
    TEST(CognitiveAsset, DesignatedInitialization)
    {
        CognitiveAsset a{
            .m_id = "test-001",
            .m_entity = "physics",
            .m_type = MemoryObjectType::FACT,
            .m_timestamp = 1000,
            .m_sourceNode = "node-1",
            .m_confidence = 0.85f,
            .m_provenance = 0.6f,
            .m_trustClass = TrustClass::VERIFIED,
        };
        EXPECT_EQ(a.m_id, "test-001");
        EXPECT_EQ(a.m_entity, "physics");
        EXPECT_EQ(a.m_type, MemoryObjectType::FACT);
        EXPECT_EQ(a.m_timestamp, 1000);
        EXPECT_FLOAT_EQ(a.m_confidence, 0.85f);
        EXPECT_EQ(a.m_sourceNode, "node-1");
    }
    ```
  implication: This is the exact C7555 site. Designated-initializer list uses C++20 syntax; struct is a plain aggregate.

- timestamp: 2026-08-18
  checked: GNUS-NEO-SWARM/src/common/types.hpp lines 180-191 (CognitiveAsset struct definition)
  found: |
    ```cpp
    struct CognitiveAsset
    {
        std::string m_id;
        std::string m_entity;
        MemoryObjectType m_type = MemoryObjectType::FACT;
        nlohmann::json m_payload;
        int64_t m_timestamp = 0;
        std::string m_sourceNode;
        float m_confidence = 0.0f;
        float m_provenance = 0.0f;
        TrustClass m_trustClass = TrustClass::UNVERIFIED;
    };
    ```
  implication: No user-declared constructors — plain aggregate. Positional C++17 aggregate init would require listing all 9 members in exact order including m_payload; default-construct + member assignment is smaller/safer and semantically identical (unset members equal their in-class defaults either way).

## Eliminated

(none — single hypothesis, confirmed directly from code inspection; no alternative causes plausible given the errort text names the exact designated-init syntax)

## Resolution

root_cause: test_types.cpp:164-173 (TEST(CognitiveAsset, DesignatedInitialization)) uses C++20 designated-initializer syntax to construct a CognitiveAsset aggregate. The project mandates C++17-and-below (per CLAUDE.md) and the build's MSVC /std:c++17 setting correctly rejects this with C7555.
fix: Replaced the designated-initializer aggregate-init block with default-construction of `CognitiveAsset a;` followed by explicit per-member assignment of the same 8 fields (m_id, m_entity, m_type, m_timestamp, m_sourceNode, m_confidence, m_provenance, m_trustClass), in the same order, with identical literal values. No change to struct definition, test assertions, or any other file.
verification: |
  Ran `cmake --build build/Windows/Release --target test_common_types --config Release` from
  W:\gnus\GeniusCognitiveSystem — 2026-08-18. Output: `test_types.cpp` compiled,
  `test_common_types.vcxproj -> ...test_common_types.exe` linked. No C7555, no errors
  (confirmed via grep -i "error" on full rebuild output => "NO ERRORS FOUND").
  Ran `test_common_types.exe --gtest_filter="CognitiveAsset.*"` — all 3 tests passed,
  including `CognitiveAsset.DesignatedInitialization` (now default-construct + assignment)
  with identical assertions (a.m_id == "test-001", a.m_entity == "physics",
  a.m_type == FACT, a.m_timestamp == 1000, a.m_confidence == 0.85f, a.m_sourceNode == "node-1").
  Self-verified; awaiting user confirmation this resolves the outer full-build failure too.
files_changed:
  - GNUS-NEO-SWARM/test/common/test_types.cpp
