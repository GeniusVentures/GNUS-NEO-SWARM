cmake_minimum_required(VERSION 3.30)

project(Genius-MOS-SLM
    VERSION 1.0.0
    DESCRIPTION "GNUS NEO SWARM — Decentralised swarm of Nano Language Models"
    LANGUAGES CXX
)

# ---------------------------------------------------------------------------
# C++17
# ---------------------------------------------------------------------------
set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_CXX_EXTENSIONS OFF)

# ---------------------------------------------------------------------------
# Build options
# ---------------------------------------------------------------------------
option(GENIUS_BUILD_TESTS        "Build unit and integration tests"         ON)
option(GENIUS_BUILD_BENCHMARKS   "Build benchmarks"                         OFF)
option(GENIUS_ENABLE_NETWORK     "Enable P2P networking (libp2p)"           OFF)
option(GENIUS_ENABLE_GPU         "Enable GPU acceleration (Vulkan)"         ON)
option(GENIUS_ENABLE_SGPROCESSING "Enable SGProcessingManager integration"  OFF)

# ---------------------------------------------------------------------------
# Compiler flags
# ---------------------------------------------------------------------------
if(MSVC)
    add_compile_options(/W4 /WX- /MP)
else()
    add_compile_options(
        -Wall -Wextra -Wpedantic
        -Wno-unused-parameter
        -fvisibility=hidden
    )
    if(CMAKE_BUILD_TYPE STREQUAL "Release")
        add_compile_options(-O3 -DNDEBUG)
    endif()
endif()

# ---------------------------------------------------------------------------
# Thirdparty discovery
# ---------------------------------------------------------------------------
list(APPEND CMAKE_MODULE_PATH "${CMAKE_SOURCE_DIR}/cmake_genius")
include(FindThirdparty)
find_thirdparty_libs()

find_package(OpenSSL QUIET)
find_package(Threads REQUIRED)
find_package(Vulkan  QUIET)

# ---------------------------------------------------------------------------
# Protobuf (optional — gRPC API)
# ---------------------------------------------------------------------------
find_package(Protobuf QUIET)
if(Protobuf_FOUND)
    message(STATUS "Protobuf found: ${Protobuf_VERSION}")
    file(GLOB PROTO_FILES "${CMAKE_SOURCE_DIR}/proto/*.proto")
    protobuf_generate_cpp(PROTO_SRCS PROTO_HDRS ${PROTO_FILES})
    add_library(genius_proto STATIC ${PROTO_SRCS} ${PROTO_HDRS})
    target_include_directories(genius_proto PUBLIC
        ${CMAKE_CURRENT_BINARY_DIR}
        ${Protobuf_INCLUDE_DIRS}
    )
    target_link_libraries(genius_proto PUBLIC ${Protobuf_LIBRARIES})
endif()

# ---------------------------------------------------------------------------
# SGProcessingManager (optional — Phase 1 direct inference)
# ---------------------------------------------------------------------------
if(GENIUS_ENABLE_SGPROCESSING)
    set(SGPROCESSINGMANAGER_DIR "${CMAKE_SOURCE_DIR}/SGProcessingManager"
        CACHE PATH "Path to SGProcessingManager submodule")

    if(EXISTS "${SGPROCESSINGMANAGER_DIR}/CMakeLists.txt")
        add_subdirectory(${SGPROCESSINGMANAGER_DIR} sgprocessingmanager_build EXCLUDE_FROM_ALL)
        add_compile_definitions(GENIUS_HAS_SGPROCESSING)
        message(STATUS "SGProcessingManager: enabled (${SGPROCESSINGMANAGER_DIR})")
    else()
        message(WARNING "SGProcessingManager not found at ${SGPROCESSINGMANAGER_DIR} — "
                        "run: git submodule update --init SGProcessingManager")
    endif()
endif()

# ---------------------------------------------------------------------------
# Source modules
# ---------------------------------------------------------------------------
add_subdirectory(src/common)
add_subdirectory(src/core)
add_subdirectory(src/specialists)
add_subdirectory(src/router)
add_subdirectory(src/reputation)
add_subdirectory(src/security)
add_subdirectory(src/network)
add_subdirectory(src/knowledge)
add_subdirectory(src/api)

# ---------------------------------------------------------------------------
# Main binary
# ---------------------------------------------------------------------------
add_executable(neo-swarm src/genius_node.cpp)
target_link_libraries(neo-swarm PRIVATE genius_api Threads::Threads)
if(UNIX AND NOT APPLE)
    target_link_libraries(neo-swarm PRIVATE uuid)
endif()

# ---------------------------------------------------------------------------
# FFI shared library (Flutter bridge)
# Links against genius_api so GeniusSlmChatCompletionsCreate calls the real
# GeniusAPIServer pipeline instead of returning a hardcoded stub.
# ---------------------------------------------------------------------------
add_library(Genius-MOS-SLM-FFI SHARED src/genius_slm_chat_c.cpp)
target_include_directories(Genius-MOS-SLM-FFI PUBLIC ${CMAKE_CURRENT_SOURCE_DIR}/src)
target_compile_definitions(Genius-MOS-SLM-FFI PRIVATE GENIUS_SLM_CHAT_C_EXPORTS)
target_link_libraries(Genius-MOS-SLM-FFI PRIVATE genius_api Threads::Threads)
# On macOS a dylib only exports symbols it directly references unless we
# force-load the static archive.  Use target_link_options so CMake expands
# the generator expression correctly at link time.
if(APPLE)
    target_link_options(Genius-MOS-SLM-FFI PRIVATE
        "LINKER:-force_load,$<TARGET_FILE:genius_api>"
    )
endif()

# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------
if(GENIUS_BUILD_TESTS)
    enable_testing()
    add_subdirectory(test)
endif()

# ---------------------------------------------------------------------------
# Benchmarks
# ---------------------------------------------------------------------------
if(GENIUS_BUILD_BENCHMARKS)
    add_subdirectory(bench)
endif()

# ---------------------------------------------------------------------------
# Install
# ---------------------------------------------------------------------------
install(TARGETS neo-swarm RUNTIME DESTINATION bin)
install(TARGETS Genius-MOS-SLM-FFI LIBRARY DESTINATION lib)
install(DIRECTORY src/ DESTINATION include/genius FILES_MATCHING PATTERN "*.hpp")
install(FILES src/genius_slm_chat_c.h DESTINATION include/genius)

# ---------------------------------------------------------------------------
# Summary
# ---------------------------------------------------------------------------
message(STATUS "")
message(STATUS "=== Genius-MOS-SLM Configuration ===")
message(STATUS "  Build type:      ${CMAKE_BUILD_TYPE}")
message(STATUS "  C++ standard:    ${CMAKE_CXX_STANDARD}")
message(STATUS "  Tests:           ${GENIUS_BUILD_TESTS}")
message(STATUS "  GPU (Vulkan):    ${GENIUS_ENABLE_GPU}")
message(STATUS "  P2P Network:     ${GENIUS_ENABLE_NETWORK}")
message(STATUS "  SGProcessing:    ${GENIUS_ENABLE_SGPROCESSING}")
message(STATUS "  OpenSSL:         ${OpenSSL_FOUND}")
message(STATUS "  Protobuf:        ${Protobuf_FOUND}")
message(STATUS "  Vulkan:          ${Vulkan_FOUND}")
message(STATUS "  Thirdparty dir:  ${THIRDPARTY_BUILD_DIR}")
message(STATUS "")
