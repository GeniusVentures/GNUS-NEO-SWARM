find_package(GTest QUIET)

if(NOT GTest_FOUND)
    find_path(GTEST_INCLUDE_DIR gtest/gtest.h
        PATHS ${THIRDPARTY_BUILD_DIR}/GTest/include
              ${CMAKE_SOURCE_DIR}/../thirdparty/GTest/googletest/include
    )
    find_library(GTEST_LIB gtest
        PATHS ${THIRDPARTY_BUILD_DIR}/GTest/lib
    )
    find_library(GTEST_MAIN_LIB gtest_main
        PATHS ${THIRDPARTY_BUILD_DIR}/GTest/lib
    )
    if(GTEST_INCLUDE_DIR AND GTEST_LIB)
        add_library(GTest::GTest UNKNOWN IMPORTED)
        set_target_properties(GTest::GTest PROPERTIES
            IMPORTED_LOCATION ${GTEST_LIB}
            INTERFACE_INCLUDE_DIRECTORIES ${GTEST_INCLUDE_DIR}
        )
        add_library(GTest::Main UNKNOWN IMPORTED)
        set_target_properties(GTest::Main PROPERTIES
            IMPORTED_LOCATION ${GTEST_MAIN_LIB}
        )
        set(GTest_FOUND TRUE)
    endif()
endif()

if(NOT GTest_FOUND)
    message(WARNING "GTest not found — skipping tests")
    return()
endif()

enable_testing()

# Path to SuperGenius processing_datatypes test data
# Used by test_sgprocessing_pipeline for Phase 1 integration tests.
# GENIUSNETWORK_SUPERGENIUS_DIR is defined as a CACHE variable in
# src/core/CMakeLists.txt, which is add_subdirectory'd before this file —
# fall back to the same default if it's somehow not yet defined.
if(NOT DEFINED GENIUSNETWORK_SUPERGENIUS_DIR)
    set(GENIUSNETWORK_SUPERGENIUS_DIR "${CMAKE_SOURCE_DIR}/../../GeniusNetwork/SuperGenius")
endif()
set(SUPERGENIUS_TEST_DATA_DIR
    "${GENIUSNETWORK_SUPERGENIUS_DIR}/test/src"
    CACHE PATH "Path to SuperGenius test/src directory containing processing_datatypes/")

# Helper macro
#
# NOTE on link order: GTest::Main/GTest::GTest are listed BEFORE ${libs}
# intentionally. Some of our libs (e.g. neoswarm_network, neoswarm_api)
# transitively depend on SuperGenius's sgns::transfer_proof/processing_proof
# targets, which incorrectly declare a PUBLIC dependency on
# Boost::unit_test_framework (see supergeniusTargets.cmake in the SuperGenius
# repo — out of scope to fix here). That pulls the real
# libboost_unit_test_framework-*.lib (containing unit_test_main.obj, whose
# main() calls init_unit_test_suite()) into the link line. MSVC's linker
# resolves the special `main` entry-point symbol from the first archive
# object that provides it, so GTest::Main must come first or Boost's
# unit_test_main.obj wins and fails with LNK2019 on init_unit_test_suite.
# See .planning/debug/resolved/neoswarm-boost-test-gtest.md for full analysis.
macro(neoswarm_test name sources libs)
    add_executable(${name} ${sources})
    target_link_libraries(${name} PRIVATE
        GTest::Main
        GTest::GTest
        ${libs}
    )
    target_compile_definitions(${name} PRIVATE
        SUPERGENIUS_TEST_DATA_DIR="${SUPERGENIUS_TEST_DATA_DIR}"
    )
    add_test(NAME ${name} COMMAND ${name})
endmacro()

neoswarm_test(test_fp4_codec             core/test_fp4_codec.cpp                          "neoswarm_core")
neoswarm_test(test_router                router/test_router.cpp                           "neoswarm_router;neoswarm_common")
neoswarm_test(test_reputation            reputation/test_reputation.cpp                   "neoswarm_reputation;neoswarm_common")
neoswarm_test(test_gcs_global_db         storage/test_gcs_global_db.cpp                   "neoswarm_storage;neoswarm_common;sgns::crdt_globaldb")
neoswarm_test(test_pipeline              integration/test_pipeline.cpp                    "neoswarm_api")
neoswarm_test(test_sgprocessing_pipeline integration/test_sgprocessing_pipeline.cpp       "neoswarm_api")
neoswarm_test(test_node_identity     security/test_node_identity.cpp        "neoswarm_security;neoswarm_common")
neoswarm_test(test_message_signing   security/test_message_signing.cpp      "neoswarm_security;neoswarm_common")
neoswarm_test(test_genius_elm_ffi    ffi/test_genius_elm_ffi.cpp             "neoswarm_api")
target_sources(test_genius_elm_ffi PRIVATE "${NEOSWARM_ROOT}/src/genius_elm_chat_completions.cpp")
target_compile_definitions(test_genius_elm_ffi PRIVATE NEOSWARM_CHAT_C_EXPORTS)
neoswarm_test(test_fact_validation   knowledge/test_fact_validation.cpp      "neoswarm_knowledge;neoswarm_common")
neoswarm_test(test_network           network/test_network.cpp                "neoswarm_network;neoswarm_security;neoswarm_common")
neoswarm_test(test_sg_client         network/test_sg_client.cpp              "neoswarm_network;neoswarm_common")
neoswarm_test(test_sg_connectivity   integration/test_sg_connectivity.cpp     "neoswarm_core;neoswarm_network;neoswarm_common")

# P0 — Specialists
neoswarm_test(test_math_specialist    specialists/test_math_specialist.cpp    "neoswarm_specialists;neoswarm_core;neoswarm_common")
neoswarm_test(test_grammar_specialist specialists/test_grammar_specialist.cpp "neoswarm_specialists;neoswarm_core;neoswarm_common")
neoswarm_test(test_symbolic_fallback  specialists/test_symbolic_fallback.cpp  "neoswarm_specialists;neoswarm_common")

# P1 — Core + Knowledge
neoswarm_test(test_context_injection   knowledge/test_context_injection.cpp    "neoswarm_knowledge;neoswarm_common")
neoswarm_test(test_knowledge_retrieval knowledge/test_knowledge_retrieval.cpp  "neoswarm_knowledge;neoswarm_common")

# P3 — Common types
neoswarm_test(test_common_types        common/test_types.cpp                   "neoswarm_common")

# Phase 7 — ELM tests
neoswarm_test(test_elm                 elm/test_elm.cpp                        "neoswarm_elm;neoswarm_core;neoswarm_knowledge;neoswarm_specialists;neoswarm_common;neoswarm_network")
#neoswarm_test(test_chain_builder       elm/test_chain_builder.cpp              "neoswarm_elm;neoswarm_common")


# Benchmarks (not part of CTest — run manually)
add_subdirectory(benchmark)
