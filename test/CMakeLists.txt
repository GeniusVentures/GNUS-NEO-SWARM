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
# Used by test_sgprocessing_pipeline for Phase 1 integration tests
set(SUPERGENIUS_TEST_DATA_DIR
    "${CMAKE_SOURCE_DIR}/../SuperGenius/test/src"
    CACHE PATH "Path to SuperGenius test/src directory containing processing_datatypes/")

# Helper macro
macro(neoswarm_test name sources libs)
    add_executable(${name} ${sources})
    target_link_libraries(${name} PRIVATE
        ${libs}
        GTest::GTest
        GTest::Main
    )
    target_compile_definitions(${name} PRIVATE
        SUPERGENIUS_TEST_DATA_DIR="${SUPERGENIUS_TEST_DATA_DIR}"
    )
    add_test(NAME ${name} COMMAND ${name})
endmacro()

neoswarm_test(test_fp4_codec             core/test_fp4_codec.cpp                          "neoswarm_core")
neoswarm_test(test_router                router/test_router.cpp                           "neoswarm_router;neoswarm_common")
neoswarm_test(test_reputation            reputation/test_reputation.cpp                   "neoswarm_reputation;neoswarm_common")
neoswarm_test(test_pipeline              integration/test_pipeline.cpp                    "neoswarm_api")
neoswarm_test(test_sgprocessing_pipeline integration/test_sgprocessing_pipeline.cpp       "neoswarm_api")
neoswarm_test(test_node_identity     security/test_node_identity.cpp        "neoswarm_security;neoswarm_common")
neoswarm_test(test_message_signing   security/test_message_signing.cpp      "neoswarm_security;neoswarm_common")
neoswarm_test(test_genius_slm_ffi    ffi/test_genius_elm_ffi.cpp             "neoswarm_api")
target_sources(test_genius_slm_ffi PRIVATE "${PROJECT_ROOT}/src/genius_elm_chat_completions.cpp")
neoswarm_test(test_fact_validation   knowledge/test_fact_validation.cpp      "neoswarm_knowledge;neoswarm_common")
neoswarm_test(test_network           network/test_network.cpp                "neoswarm_network;neoswarm_security;neoswarm_common")

# P0 — Specialists
neoswarm_test(test_symbolic_fallback  specialists/test_symbolic_fallback.cpp  "neoswarm_specialists;neoswarm_common")

# Benchmarks (not part of CTest — run manually)
add_subdirectory(benchmark)
