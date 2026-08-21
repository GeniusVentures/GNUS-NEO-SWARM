---
status: resolved
trigger: "Multiple test targets fail to link with error LNK2019: unresolved external symbol \"class boost::unit_test::test_suite * __cdecl init_unit_test_suite(int,char * * const)\" referenced in function main, from libboost_unit_test_framework-vc143-mt-s-x64-1_85.lib(unit_test_main.obj). Affected targets (from a full outer build, cmake --build build/Windows/Release --parallel 8 --config Release, run from W:\\gnus\\GeniusCognitiveSystem): test_network, test_sg_connectivity, test_sg_client, test_elm, test_pipeline, test_sgprocessing_pipeline."
created: 2026-08-19
updated: 2026-08-19
---

## Symptoms

**Expected behavior:** These test targets link and run cleanly. This project's convention (per user, this session) is GTest — GTest is used throughout, so these targets pulling in Boost.Test at all is itself suspicious and worth questioning, not just working around.

**Actual behavior:** Each of the 6 targets listed above fails at link time with the identical error:
```
libboost_unit_test_framework-vc143-mt-s-x64-1_85.lib(unit_test_main.obj) : error LNK2019: unresolved external symbol "class boost::unit_test::test_suite * __cdecl init_unit_test_suite(int,char * * const)" (?init_unit_test_suite@@YAPEAVtest_suite@unit_test@boost@@HQEAPEAD@Z) referenced in function main
<target>.exe : fatal error LNK1120: 1 unresolved externals
```

**Error messages:** Exact linker output above, identical shape across all 6 targets — same missing symbol (`init_unit_test_suite`), same source (`unit_test_main.obj` inside the static Boost.Test lib), same referencing function (`main`).

**Timeline:** First seen in a full outer-build attempt (`cmake --build build/Windows/Release --parallel 8 --config Release` from `W:\gnus\GeniusCognitiveSystem`) on 2026-08-18/19, after fixing an unrelated, earlier-blocking MNN header/linkage issue (see resolved session `.planning/debug/resolved/neoswarm-mnn-llm-header.md`) that had prevented the build from reaching this far before. Not yet known whether this is a pre-existing latent bug (most likely, since it's unrelated to MNN) or something that changed recently — needs git history/blame investigation on these specific test targets' CMakeLists.txt and main-providing source files.

**Reproduction:**
```
cd W:\gnus\GeniusCognitiveSystem
cmake --build build/Windows/Release --target test_network --config Release
```
(or substitute any of: test_sg_connectivity, test_sg_client, test_elm, test_pipeline, test_sgprocessing_pipeline)

## Context

This is a fresh debug session split out from a broader `neoswarm-mnn-llm-header` debug session (now resolved and archived) that surfaced several distinct, unrelated build failures in the same full-build log. This one is scoped ONLY to the Boost.Test linkage problem across these 6 test targets. Do not touch MNN-related files, the C++20 designated-initializer issue in `test/common/test_types.cpp`, the missing `GeniusSDK.hpp` include in `src/storage/gcs_global_db.cpp`, or the `dllimport` issue in `test_genius_elm_ffi.vcxproj` — those are separate, independently-tracked debug sessions.

**Important user-provided lead:** This project uses GTest as its standard test framework (per GNUS-NEO-SWARM/CLAUDE.md: "Prefer Google Test... in tests"). The presence of Boost.Test (`libboost_unit_test_framework`, `init_unit_test_suite`) in these 6 targets at all is unusual and should be questioned, not just patched around. Investigate: are these targets *supposed* to use Boost.Test (e.g. because they test boost-asio-heavy networking code and there's a project convention for that), or is this leftover/mistaken scaffolding that should actually be GTest? Check how other, working test targets in this codebase declare their `main()`/test entry point for comparison, and check whether these 6 targets' own source files use `#define BOOST_TEST_MODULE` (which auto-generates a `main()` and would NOT need `init_unit_test_suite`, meaning linking against a Boost.Test variant that expects manual registration would itself be the bug) or manual Boost.Test registration (which DOES need `init_unit_test_suite` defined somewhere, and its absence would be the direct bug).

## Current Focus

reasoning_checkpoint:
  hypothesis: "MSVC's link.exe resolves the special `main` entry-point symbol from the FIRST static-library object in link order that defines it. Because SuperGenius's exported `sgns::transfer_proof`/`sgns::processing_proof` targets PUBLICLY declare `Boost::unit_test_framework` in their `INTERFACE_LINK_LIBRARIES` (supergeniusTargets.cmake), and these get pulled transitively into neoswarm_network/neoswarm_api via sgns::GeniusSDK_shared -> genius_node -> transfer_proof/processing_proof, the real `libboost_unit_test_framework-...lib` (containing `unit_test_main.obj`, which defines `main()` calling `init_unit_test_suite()`) ends up placed EARLY in the generated link line — before `GTest::Main` (whose `gtest_main.obj` also defines `main()`). Because `${libs}` is listed before `GTest::Main`/`GTest::GTest` in the shared `neoswarm_test` CMake macro, Boost's `main()` wins symbol resolution over gtest's, and its call to `init_unit_test_suite()` (never defined anywhere in this GTest-only codebase) goes unresolved -> LNK2019."
  confirming_evidence:
    - "All 6 failing targets' .cpp files use exclusively `#include <gtest/gtest.h>` + `TEST(...)`/`TEST_F(...)` — zero occurrences of BOOST_TEST_MODULE/BOOST_AUTO_TEST_CASE/BOOST_AUTO_TEST_SUITE in any of them (grep confirmed). Rules out 'these targets intentionally use Boost.Test'."
    - "Inspected generated test_network.vcxproj <AdditionalDependencies>: libboost_unit_test_framework-vc143-mt-s-x64-1_85.lib at list position 34/376; gtest_main.lib at position 364/376 — Boost.Test lib linked far earlier than GTest."
    - "Working targets (test_router, test_reputation, test_node_identity, test_message_signing) have NO libboost_unit_test_framework in their link line at all — they don't transitively depend on the sgns::GeniusSDK/genius_node chain."
    - "Two OTHER targets (test_gcs_global_db, test_genius_elm_ffi) also transitively link libboost_unit_test_framework early (positions 35/377, 39/384) — same pattern as the 6 failing ones — but are excluded from the reported failure list only because each has its own earlier, separately-tracked compile-time blocker (missing GeniusSDK.hpp include; dllimport issue) that prevents them from ever reaching the link stage. Strongly corroborates this is a systemic transitive-linkage issue, not specific to the 6 named targets."
    - "Root cause located at source: W:\\gnus\\GeniusNetwork\\SuperGenius\\build\\Windows\\Release\\SuperGenius\\lib\\cmake\\SuperGenius\\supergeniusTargets.cmake lines 419-433 — sgns::transfer_proof and sgns::processing_proof both declare INTERFACE_LINK_LIBRARIES \"sgns::basic_proof;Boost::unit_test_framework\", leaking a Boost.Test dependency PUBLICLY into any consumer. This is in SuperGenius (external sibling repo at W:\\gnus\\GeniusNetwork\\SuperGenius, NOT part of GNUS-NEO-SWARM or GeniusCognitiveSystem) — out of scope to modify directly."
    - "Directly reproduced: `cmake --build build/Windows/Release --target test_network --config Release` from W:\\gnus\\GeniusCognitiveSystem produces the exact reported LNK2019 error, confirming reproducibility independent of the original full-build log."
  falsification_test: "If GTest::Main/GTest::GTest are reordered to link BEFORE ${libs} in the neoswarm_test macro and the target still fails with the identical LNK2019, this hypothesis is wrong (would mean MSVC doesn't resolve `main` by first-match archive order, or some other mechanism is at play)."
  fix_rationale: "The root cause (SuperGenius's CMake export leaking Boost::unit_test_framework as a PUBLIC dependency) lives in an external repo outside GNUS-NEO-SWARM's scope and should not be patched here. The correct in-scope fix is to make GNUS-NEO-SWARM's own shared test-linking macro resilient to this upstream leak: link GTest::Main/GTest::GTest FIRST so gtest_main.obj's main() always wins `main` symbol resolution regardless of what transitive Boost.Test leakage exists further down the link line. This is a one-line reorder in a single macro — no source file changes, no target migration, no hand-written init_unit_test_suite — addressing the actual mechanism (link-order-dependent main() resolution), not just silencing the symptom."
  blind_spots: "Have not verified whether MSVC's linker could, in some configuration, treat two `main` definitions as LNK2005 (duplicate symbol) rather than silently preferring the first — if so the reorder could trade one link error for another; this will be checked directly via rebuild. Have not exhaustively confirmed EVERY consumer of sgns::transfer_proof/processing_proof in the wider build is unaffected by this reorder (only neoswarm_test-macro-based targets are in scope here). Have not checked why SuperGenius's transfer_proof/processing_proof link Boost::unit_test_framework in the first place (likely their own internal proof-verification test utility mistakenly marked PUBLIC instead of PRIVATE) — flagged as an upstream issue worth reporting to whoever owns SuperGenius, but not fixed here since it's out of repo scope."

hypothesis: SuperGenius's exported sgns::transfer_proof/sgns::processing_proof CMake targets PUBLICLY leak Boost::unit_test_framework, which lands earlier than GTest::Main in the link line for these 6 targets, causing Boost's unit_test_main.obj (main() -> init_unit_test_suite()) to shadow GTest's main().

test: Reorder neoswarm_test macro's target_link_libraries call (GTest::Main/GTest::GTest before ${libs}), reconfigure, rebuild test_network, check LNK2019 gone and .exe runs.

expecting: If hypothesis correct, gtest_main.obj resolves main() first, Boost's unit_test_main.obj is never pulled in, link succeeds, and running the .exe executes GTest's normal test runner output.

next_action: Fix applied and self-verified (all 6 targets link + run as GTest). Awaiting human confirmation that this resolves the original full-outer-build failure end-to-end before archiving the session.

## Evidence

- timestamp: 2026-08-19T00:00:00Z
  checked: GNUS-NEO-SWARM/test/CMakeLists.txt (full file)
  found: All 6 affected targets (and every other test target) are declared via a single shared `neoswarm_test(name sources libs)` macro that uniformly links `${libs} GTest::GTest GTest::Main` for every target — no per-target Boost.Test scaffolding exists in this file.
  implication: The differential failure (6 targets fail, others don't) is NOT caused by anything unique to these 6 targets' own CMake declarations — must come from what's inside `${libs}` (transitive linkage), not the macro itself as originally written.

- timestamp: 2026-08-19T00:05:00Z
  checked: First ~30 lines of test/network/test_network.cpp, test/network/test_sg_client.cpp, test/integration/test_sg_connectivity.cpp, test/elm/test_elm.cpp, test/integration/test_pipeline.cpp, test/integration/test_sgprocessing_pipeline.cpp
  found: All 6 files `#include <gtest/gtest.h>` and use GTest's `TEST(...)` macro. Zero occurrences of BOOST_TEST_MODULE, BOOST_AUTO_TEST_CASE, BOOST_AUTO_TEST_SUITE, or manual init_unit_test_suite in any of them.
  implication: These targets are 100% GTest-based, matching project convention. Boost.Test presence is definitely accidental/transitive, not an intentional-but-incomplete Boost.Test setup. Rules out "needs BOOST_TEST_MODULE" and "needs hand-written init_unit_test_suite" as fixes.

- timestamp: 2026-08-19T00:10:00Z
  checked: GNUS-NEO-SWARM/cmake/CommonBuildParameters.cmake lines ~420-447 (_MISSING_DEPS stub list)
  found: "Boost::unit_test_framework" is listed among other stub targets (ProofSystem::ProofSystem, MNN::MNN, xxHash::xxhash, etc.) that get a dummy `add_library(... INTERFACE IMPORTED)` created ONLY `if(NOT TARGET ${_dep})` — i.e. only if no real target already exists, to let `find_package(SuperGenius CONFIG)` configure without erroring on genuinely-missing external deps.
  implication: This stub is a red herring for the ROOT cause (since the actual .lib file appears in the link line, meaning the REAL Boost::unit_test_framework target already exists by the time this code runs, so the stub guard is skipped) — but it does show whoever wrote this file was already aware Boost::unit_test_framework shows up as a SuperGenius dependency somewhere, likely without realizing it leaks all the way into GNUS-NEO-SWARM's own test executables.

- timestamp: 2026-08-19T00:15:00Z
  checked: build/Windows/Release/test/test_network.vcxproj `<AdditionalDependencies>` (generated link line, all 4 config blocks identical)
  found: "libboost_unit_test_framework-vc143-mt-s-x64-1_85.lib" at list position 34 of 376; "gtest_main.lib" at position 364; "gtest.lib" at position 365.
  implication: Directly confirms the REAL Boost.Test static library (not a stub) is linked into this executable, and appears far EARLIER in link order than GTest's own libraries — consistent with MSVC resolving `main` from Boost's unit_test_main.obj before ever reaching gtest_main.obj.

- timestamp: 2026-08-19T00:20:00Z
  checked: build/Windows/Release/test/{test_router,test_reputation,test_node_identity,test_message_signing,test_gcs_global_db,test_genius_elm_ffi}.vcxproj `<AdditionalDependencies>`
  found: test_router, test_reputation, test_node_identity, test_message_signing have NO libboost_unit_test_framework entry at all (small dependency lists, 16-103 items, no transitive sgns::GeniusSDK/genius_node chain). test_gcs_global_db and test_genius_elm_ffi DO have libboost_unit_test_framework early (positions 35/377 and 39/384) — same pattern as the 6 reported failures — but are excluded from the reported failure list, matching the fact both have their own independently-tracked, earlier compile-time blockers (missing GeniusSDK.hpp include for gcs_global_db's neoswarm_storage lib; dllimport issue for genius_elm_ffi) that stop the build before it ever reaches the link stage for them.
  implication: Confirms the differentiator is exactly "does this target transitively link the sgns::GeniusSDK/genius_node dependency chain" (which pulls in transfer_proof/processing_proof) — not anything about the 6 targets' own declarations. Also confirms this is a systemic issue likely affecting 8 targets total (6 reported + 2 currently masked by unrelated compile errors), not an isolated one-off.

- timestamp: 2026-08-19T00:25:00Z
  checked: W:\gnus\GeniusNetwork\SuperGenius\build\Windows\Release\SuperGenius\lib\cmake\SuperGenius\supergeniusTargets.cmake (grepped for "unit_test_framework")
  found: Lines 419-433 — `sgns::transfer_proof` and `sgns::processing_proof` (SuperGenius's own exported CMake targets, part of its ProofSystem/zk-proof components) both declare `INTERFACE_LINK_LIBRARIES "sgns::basic_proof;Boost::unit_test_framework"`.
  implication: FOUND THE SOURCE OF THE LEAK. SuperGenius's own CMake export publicly attaches Boost::unit_test_framework to these two proof-system libraries — almost certainly a mistake in SuperGenius's own CMakeLists.txt (should be PRIVATE, or shouldn't be there if it's test-only tooling). This is in an external, sibling repository (W:\gnus\GeniusNetwork\SuperGenius) — completely outside GNUS-NEO-SWARM's and GeniusCognitiveSystem's own directory trees and version control — so it is out of scope to edit directly per this session's constraints.

- timestamp: 2026-08-19T00:30:00Z
  checked: Direct reproduction — `cd W:\gnus\GeniusCognitiveSystem && cmake --build build/Windows/Release --target test_network --config Release`
  found: Reproduces the EXACT reported error verbatim: "libboost_unit_test_framework-vc143-mt-s-x64-1_85.lib(unit_test_main.obj) : error LNK2019: unresolved external symbol ... init_unit_test_suite ... referenced in function main" followed by LNK1120 fatal error.
  implication: Confirms reproducibility independent of the original full-build log; safe to use this single-target rebuild as the verification loop for the fix.

- timestamp: 2026-08-19T00:40:00Z
  checked: Applied fix (reordered GTest::Main/GTest::GTest before ${libs} in the neoswarm_test macro, test/CMakeLists.txt), reconfigured, rebuilt test_network.
  found: Link succeeds cleanly (no LNK2019/LNK1120). Generated test_network.vcxproj now shows gtest_main.lib at position 3/376 and libboost_unit_test_framework at position 36/376 (order flipped from before: previously boost was at 34, gtest_main at 364). Running test_network.exe prints "Running main() from .../gtest_main.cc", runs 6 GTest tests across 2 suites, all PASSED, exit code 0.
  implication: Confirms the hypothesis and mechanism directly — once GTest::Main resolves `main` first, Boost's unit_test_main.obj is never pulled in and the target behaves as a normal GTest binary.

- timestamp: 2026-08-19T00:45:00Z
  checked: Rebuilt and ran the remaining 5 affected targets (test_sg_connectivity, test_sg_client, test_elm, test_pipeline, test_sgprocessing_pipeline) with the fix applied.
  found: All 5 link successfully (no LNK2019). All 5 run and print "Running main() from .../gtest_main.cc" followed by normal GTest suite output. test_sg_client (15/15), test_elm (22/22), test_pipeline (9/9) all PASSED. test_sgprocessing_pipeline: 11 PASSED, 4 SKIPPED (pre-existing, unrelated to linkage — these are functional integration tests gated behind hardware/model availability, e.g. "FloatModel_EndToEnd", "TensorModel_EndToEnd"). test_sg_connectivity: 7 PASSED, 1 FAILED (`SGConnectivity.BuildSchemaJsonFP4UltraFormatEmitsFP4Type`) — this is a genuine functional test assertion failure unrelated to Boost.Test/linker issues (test now runs at all, which it never did before), out of scope for this session per its explicit scoping to the link-error investigation only.
  implication: The LNK2019 Boost.Test linkage issue is fully resolved for all 6 originally-reported targets. One pre-existing, unrelated functional test failure (test_sg_connectivity) and some environment-gated skips (test_sgprocessing_pipeline) surfaced now that the targets can actually run — these are new/separate findings, not regressions from this fix, and are out of this session's scope.

- timestamp: 2026-08-19T00:50:00Z
  checked: Regression check — rebuilt 5 previously-passing targets (test_router, test_reputation, test_node_identity, test_message_signing, test_fp4_codec) with the fix applied.
  found: All 5 still link and build successfully with no new errors.
  implication: The macro reorder (applied uniformly to all test targets since it's a single shared macro) introduces no regression for targets unaffected by the original bug.

## Eliminated

- hypothesis: "These 6 targets are supposed to use Boost.Test (e.g. for boost-asio-heavy networking code) and are just missing a hand-written init_unit_test_suite()."
  evidence: All 6 targets' source files use exclusively GTest macros (`TEST(...)`) and `#include <gtest/gtest.h>`; zero Boost.Test macros present anywhere in them. Writing an init_unit_test_suite() would be pure scaffolding unrelated to any actual test code in these files, contradicting the project's own GTest convention (GNUS-NEO-SWARM/CLAUDE.md) with no corresponding test logic to justify it.
  timestamp: 2026-08-19T00:05:00Z

- hypothesis: "The `Boost::unit_test_framework` stub added in cmake/CommonBuildParameters.cmake's _MISSING_DEPS list is itself the direct cause (e.g., it's accidentally providing a real library reference instead of being an empty interface stub)."
  evidence: The stub is only created `if(NOT TARGET Boost::unit_test_framework)`, and the real `libboost_unit_test_framework-vc143-mt-s-x64-1_85.lib` (with `unit_test_main.obj`) appears directly in the linked .vcxproj — meaning a REAL target already existed before this code ran, so the guard was skipped and the stub was never created in the first place. The stub code is a coincidental red flag, not the direct mechanism.
  timestamp: 2026-08-19T00:15:00Z

## Resolution

root_cause: SuperGenius's exported CMake targets `sgns::transfer_proof` and `sgns::processing_proof` (in the external sibling repo W:\gnus\GeniusNetwork\SuperGenius, file lib/cmake/SuperGenius/supergeniusTargets.cmake) declare `INTERFACE_LINK_LIBRARIES` that PUBLICLY includes `Boost::unit_test_framework`. Because neoswarm_network (and transitively neoswarm_api) link `sgns::GeniusSDK_shared`/`sgns::genius_node`, which in turn depend on `sgns::transfer_proof`/`sgns::processing_proof`, the real `libboost_unit_test_framework-...lib` (containing `unit_test_main.obj`, whose `main()` calls `init_unit_test_suite()`) gets pulled into these test executables' link line FAR EARLIER than `GTest::Main`. MSVC's linker resolves the special `main` entry-point symbol from the first archive object that provides it — so Boost's `unit_test_main.obj` wins over GTest's `gtest_main.obj`, and its call to `init_unit_test_suite()` (which nothing in this GTest-only codebase defines, correctly) is left unresolved, producing LNK2019/LNK1120. This affects any test target that transitively links the sgns::GeniusSDK/genius_node chain (confirmed: 6 reported + 2 more currently masked by unrelated, separately-tracked compile errors). The 6 targets themselves are correctly GTest-based per project convention — Boost.Test's presence is a pure link-order side effect of an upstream (SuperGenius) CMake export mistake, not anything wrong in GNUS-NEO-SWARM's own test code.
fix: Reordered the `neoswarm_test` CMake macro in GNUS-NEO-SWARM/test/CMakeLists.txt so `GTest::Main`/`GTest::GTest` are linked BEFORE `${libs}` (previously `${libs} GTest::GTest GTest::Main`). This ensures GTest's `gtest_main.obj` always wins MSVC's `main` entry-point symbol resolution ahead of any transitively-leaked Boost.Test static library, regardless of what upstream (SuperGenius) dependencies end up in `${libs}`. Added an explanatory comment above the macro documenting the mechanism and pointing at this debug session file. No source (.cpp) files were touched — the 6 targets already correctly used GTest exclusively; no Boost.Test migration was needed or performed. The actual upstream root cause (SuperGenius's `sgns::transfer_proof`/`sgns::processing_proof` exported targets publicly linking `Boost::unit_test_framework` — see supergeniusTargets.cmake lines 419-433) lives in an external sibling repository (W:\gnus\GeniusNetwork\SuperGenius) outside GNUS-NEO-SWARM/GeniusCognitiveSystem's scope and was NOT modified.
verification: Self-verified by direct rebuild + run of all 6 originally-failing targets: all link cleanly (no LNK2019/LNK1120) and execute as normal GTest binaries ("Running main() from .../gtest_main.cc"). test_network (6/6 passed), test_sg_client (15/15 passed), test_elm (22/22 passed), test_pipeline (9/9 passed), test_sgprocessing_pipeline (11 passed, 4 skipped — pre-existing, environment-gated, unrelated), test_sg_connectivity (7 passed, 1 failed — pre-existing functional assertion failure, unrelated to linkage, out of this session's scope). Regression-checked 5 previously-passing targets (test_router, test_reputation, test_node_identity, test_message_signing, test_fp4_codec) — all still build fine. HUMAN-CONFIRMED 2026-08-19: coordinator reviewed the diff and the per-target pass/fail test-run evidence (not just link success) and confirmed the fix as resolving the original issue. Fix has NOT been committed (no commit permission given for this session); left as uncommitted working-tree change in GNUS-NEO-SWARM/test/CMakeLists.txt.
files_changed:
  - GNUS-NEO-SWARM/test/CMakeLists.txt (uncommitted)

follow_up_findings: (out of scope for this session — surfaced during verification, NOT investigated or fixed here, no new debug session opened by this agent; documenting for future tracking only)
  - "test_sg_connectivity has a genuine failing GTest assertion: `SGConnectivity.BuildSchemaJsonFP4UltraFormatEmitsFP4Type`. This test could never execute before this fix (the binary never linked), so this failure was previously invisible. It is unrelated to Boost.Test/linker mechanics — it's a functional bug in FP4-ultra-format schema-JSON generation. Worth a separate debug session."
  - "Upstream bug in SuperGenius (external sibling repo, W:\\gnus\\GeniusNetwork\\SuperGenius\\build\\Windows\\Release\\SuperGenius\\lib\\cmake\\SuperGenius\\supergeniusTargets.cmake, lines 419-433): the exported `sgns::transfer_proof` and `sgns::processing_proof` CMake targets declare `Boost::unit_test_framework` in their PUBLIC `INTERFACE_LINK_LIBRARIES`, when it's almost certainly meant to be a PRIVATE, test-only dependency of those proof-system libraries. This leaks Boost.Test into every downstream consumer's link line (GNUS-NEO-SWARM's fix here only compensates for the symptom via link order — the actual upstream CMake export should be corrected at the source, in the SuperGenius repo, by whoever owns it). Worth reporting/tracking separately; not fixed here since it's outside GNUS-NEO-SWARM's/GeniusCognitiveSystem's own repo scope."
