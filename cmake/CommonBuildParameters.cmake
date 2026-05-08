# CommonBuildParameters.cmake — GNUS-NEO-SWARM
# Called from build/<Platform>/CMakeLists.txt after CommonCompilerOptions.cmake.
# Sets up all thirdparty dependencies and adds the project source/test trees.

# ---------------------------------------------------------------------------
# Boost version
# ---------------------------------------------------------------------------
set(BOOST_MAJOR_VERSION "1" CACHE STRING "Boost Major Version")
set(BOOST_MINOR_VERSION "80" CACHE STRING "Boost Minor Version")
set(BOOST_PATCH_VERSION "0" CACHE STRING "Boost Patch Version")
set(BOOST_VERSION    "${BOOST_MAJOR_VERSION}.${BOOST_MINOR_VERSION}.${BOOST_PATCH_VERSION}")
set(BOOST_VERSION_2U "${BOOST_MAJOR_VERSION}_${BOOST_MINOR_VERSION}")

# ---------------------------------------------------------------------------
# GTest
# ---------------------------------------------------------------------------
set(GTest_DIR         "${_THIRDPARTY_BUILD_DIR}/GTest/lib/cmake/GTest")
set(GTest_INCLUDE_DIR "${_THIRDPARTY_BUILD_DIR}/GTest/include")
find_package(GTest CONFIG REQUIRED)
include_directories(${GTest_INCLUDE_DIR})

include(${PROJECT_ROOT}/cmake/functions.cmake)

# ---------------------------------------------------------------------------
# OpenSSL
# ---------------------------------------------------------------------------
# Thirdparty builds OpenSSL directly at openssl/build/ (no platform subdir)
set(OPENSSL_DIR "${_THIRDPARTY_BUILD_DIR}/openssl/build"
    CACHE PATH "OpenSSL install folder")
set(OPENSSL_USE_STATIC_LIBS   ON  CACHE BOOL "")
set(OPENSSL_MSVC_STATIC_RT    ON  CACHE BOOL "")
set(OPENSSL_ROOT_DIR          "${OPENSSL_DIR}"          CACHE PATH "")
set(OPENSSL_INCLUDE_DIR       "${OPENSSL_DIR}/include"  CACHE PATH "")
set(OPENSSL_LIBRARIES         "${OPENSSL_DIR}/lib"      CACHE PATH "")
set(OPENSSL_CRYPTO_LIBRARY    "${OPENSSL_LIBRARIES}/libcrypto${CMAKE_STATIC_LIBRARY_SUFFIX}" CACHE PATH "")
set(OPENSSL_SSL_LIBRARY       "${OPENSSL_LIBRARIES}/libssl${CMAKE_STATIC_LIBRARY_SUFFIX}"   CACHE PATH "")
find_package(OpenSSL REQUIRED)
include_directories(${OPENSSL_INCLUDE_DIR})

# ---------------------------------------------------------------------------
# Microsoft.GSL
# ---------------------------------------------------------------------------
set(GSL_INCLUDE_DIR "${_THIRDPARTY_BUILD_DIR}/Microsoft.GSL/include")
include_directories(${GSL_INCLUDE_DIR})

# ---------------------------------------------------------------------------
# fmt
# ---------------------------------------------------------------------------
set(fmt_DIR         "${_THIRDPARTY_BUILD_DIR}/fmt/lib/cmake/fmt")
set(fmt_INCLUDE_DIR "${_THIRDPARTY_BUILD_DIR}/fmt/include")
find_package(fmt CONFIG REQUIRED)
include_directories(${fmt_INCLUDE_DIR})

# ---------------------------------------------------------------------------
# spdlog
# ---------------------------------------------------------------------------
set(spdlog_DIR         "${_THIRDPARTY_BUILD_DIR}/spdlog/lib/cmake/spdlog")
set(spdlog_INCLUDE_DIR "${_THIRDPARTY_BUILD_DIR}/spdlog/include")
find_package(spdlog CONFIG REQUIRED)
include_directories(${spdlog_INCLUDE_DIR})
add_compile_definitions(SPDLOG_FMT_EXTERNAL GENIUS_HAS_SPDLOG)

# ---------------------------------------------------------------------------
# Boost
# ---------------------------------------------------------------------------
# Thirdparty builds Boost with cmake config files at boost/build/lib/cmake/
set(_BOOST_ROOT    "${_THIRDPARTY_BUILD_DIR}/boost/build")
set(Boost_LIB_DIR  "${_BOOST_ROOT}/lib")
set(Boost_INCLUDE_DIR "${_BOOST_ROOT}/include")

# Use cmake config mode (works with CMake 4.x where FindBoost is removed)
set(Boost_DIR "${Boost_LIB_DIR}/cmake/Boost-1.85.0")
list(APPEND CMAKE_PREFIX_PATH "${Boost_LIB_DIR}/cmake")

set(Boost_USE_MULTITHREADED  ON)
set(Boost_USE_STATIC_LIBS    ON)
set(Boost_USE_STATIC_RUNTIME ON)
set(Boost_NO_SYSTEM_PATHS    ON)

find_package(Boost 1.85.0 CONFIG REQUIRED COMPONENTS
    date_time filesystem random regex system thread log log_setup program_options)
include_directories(${Boost_INCLUDE_DIRS})

# ---------------------------------------------------------------------------
# nlohmann/json (header-only)
# ---------------------------------------------------------------------------
set(_JSON_INCLUDE "${_THIRDPARTY_BUILD_DIR}/json/include")
if(EXISTS "${_JSON_INCLUDE}/nlohmann/json.hpp")
    include_directories(${_JSON_INCLUDE})
    message(STATUS "nlohmann/json: ${_JSON_INCLUDE}")
else()
    message(WARNING "nlohmann/json not found at ${_JSON_INCLUDE}")
endif()

# ---------------------------------------------------------------------------
# secp256k1
# ---------------------------------------------------------------------------
set(libsecp256k1_DIR         "${_THIRDPARTY_BUILD_DIR}/libsecp256k1/lib/cmake/libsecp256k1")
set(libsecp256k1_INCLUDE_DIR "${_THIRDPARTY_BUILD_DIR}/libsecp256k1/include")
set(libsecp256k1_LIBRARY_DIR "${_THIRDPARTY_BUILD_DIR}/libsecp256k1/lib")
find_package(libsecp256k1 CONFIG QUIET)
if(libsecp256k1_FOUND)
    include_directories(${libsecp256k1_INCLUDE_DIR})
    message(STATUS "secp256k1 found")
endif()

# ---------------------------------------------------------------------------
# MNN
# ---------------------------------------------------------------------------
set(_MNN_LIB "${_THIRDPARTY_BUILD_DIR}/MNN/lib/libMNN${CMAKE_STATIC_LIBRARY_SUFFIX}")
if(NOT EXISTS "${_MNN_LIB}")
    set(_MNN_LIB "${_THIRDPARTY_BUILD_DIR}/MNN/lib/libMNN.dylib")
endif()
if(EXISTS "${_MNN_LIB}")
    add_library(MNN UNKNOWN IMPORTED)
    set_target_properties(MNN PROPERTIES
        IMPORTED_LOCATION "${_MNN_LIB}"
        INTERFACE_INCLUDE_DIRECTORIES "${_THIRDPARTY_BUILD_DIR}/MNN/include"
    )
    message(STATUS "MNN: ${_MNN_LIB}")
else()
    message(STATUS "MNN not found — inference engine runs in stub mode")
endif()

# ---------------------------------------------------------------------------
# RocksDB
# ---------------------------------------------------------------------------
find_library(ROCKSDB_LIB rocksdb
    PATHS "${_THIRDPARTY_BUILD_DIR}/rocksdb/lib" NO_DEFAULT_PATH)
if(ROCKSDB_LIB)
    add_library(rocksdb UNKNOWN IMPORTED)
    set_target_properties(rocksdb PROPERTIES
        IMPORTED_LOCATION "${ROCKSDB_LIB}"
        INTERFACE_INCLUDE_DIRECTORIES "${_THIRDPARTY_BUILD_DIR}/rocksdb/include"
    )
    message(STATUS "RocksDB: ${ROCKSDB_LIB}")
endif()

# ---------------------------------------------------------------------------
# libp2p (optional)
# ---------------------------------------------------------------------------
# libp2p has many transitive dependencies — add all thirdparty cmake dirs
# to CMAKE_PREFIX_PATH so find_dependency() calls inside libp2pConfig.cmake
# can resolve them automatically.
foreach(_tp_pkg protobuf yaml-cpp tsl_hat_trie soralog Boost.DI
                ed25519 sr25519-donna xxhash cares ipfs-lite-cpp
                ipfs-pubsub ipfs-bitswap-cpp sqlite3 SQLiteModernCpp)
    list(APPEND CMAKE_PREFIX_PATH "${_THIRDPARTY_BUILD_DIR}/${_tp_pkg}/lib/cmake/${_tp_pkg}")
    list(APPEND CMAKE_PREFIX_PATH "${_THIRDPARTY_BUILD_DIR}/${_tp_pkg}/lib/cmake")
endforeach()
# Also add the flat thirdparty build dir so cmake can scan all packages
list(APPEND CMAKE_PREFIX_PATH "${_THIRDPARTY_BUILD_DIR}")

set(libp2p_DIR "${_THIRDPARTY_BUILD_DIR}/libp2p/lib/cmake/libp2p")
find_package(libp2p CONFIG QUIET)
if(libp2p_FOUND)
    include_directories("${_THIRDPARTY_BUILD_DIR}/libp2p/include")
    message(STATUS "libp2p found")
else()
    message(STATUS "libp2p not found -- P2P networking runs in stub mode")
endif()

# ---------------------------------------------------------------------------
# Threads
# ---------------------------------------------------------------------------
find_package(Threads REQUIRED)

# ---------------------------------------------------------------------------
# Project include root
# ---------------------------------------------------------------------------
include_directories(${PROJECT_ROOT}/src)

print("CMAKE_HOST_SYSTEM_NAME: ${CMAKE_HOST_SYSTEM_NAME}")
print("CMAKE_SYSTEM_NAME:      ${CMAKE_SYSTEM_NAME}")
print("CMAKE_CXX_STANDARD:     ${CMAKE_CXX_STANDARD}")
print("THIRDPARTY BUILD DIR:   ${_THIRDPARTY_BUILD_DIR}")

# ---------------------------------------------------------------------------
# Source tree
# ---------------------------------------------------------------------------
add_subdirectory(${PROJECT_ROOT}/src/common     ${CMAKE_BINARY_DIR}/src/common)
add_subdirectory(${PROJECT_ROOT}/src/core       ${CMAKE_BINARY_DIR}/src/core)
add_subdirectory(${PROJECT_ROOT}/src/specialists ${CMAKE_BINARY_DIR}/src/specialists)
add_subdirectory(${PROJECT_ROOT}/src/router     ${CMAKE_BINARY_DIR}/src/router)
add_subdirectory(${PROJECT_ROOT}/src/reputation ${CMAKE_BINARY_DIR}/src/reputation)
add_subdirectory(${PROJECT_ROOT}/src/security   ${CMAKE_BINARY_DIR}/src/security)
add_subdirectory(${PROJECT_ROOT}/src/network    ${CMAKE_BINARY_DIR}/src/network)
add_subdirectory(${PROJECT_ROOT}/src/knowledge  ${CMAKE_BINARY_DIR}/src/knowledge)
add_subdirectory(${PROJECT_ROOT}/src/api        ${CMAKE_BINARY_DIR}/src/api)

# ---------------------------------------------------------------------------
# Main binary
# ---------------------------------------------------------------------------
add_executable(neo-swarm ${PROJECT_ROOT}/src/genius_node.cpp)
target_link_libraries(neo-swarm PRIVATE genius_api Threads::Threads)
if(UNIX AND NOT APPLE)
    target_link_libraries(neo-swarm PRIVATE uuid)
endif()

# ---------------------------------------------------------------------------
# FFI shared library (Flutter bridge)
# Links against genius_api so GeniusSlmChatCompletionsCreate calls the real
# GeniusAPIServer pipeline instead of returning a hardcoded stub.
# ---------------------------------------------------------------------------
add_library(Genius-MOS-SLM-FFI SHARED ${PROJECT_ROOT}/src/genius_slm_chat_c.cpp)
target_include_directories(Genius-MOS-SLM-FFI PUBLIC ${PROJECT_ROOT}/src)
target_compile_definitions(Genius-MOS-SLM-FFI PRIVATE GENIUS_SLM_CHAT_C_EXPORTS)
target_link_libraries(Genius-MOS-SLM-FFI PRIVATE genius_api Threads::Threads)
# On macOS a dylib only exports symbols it directly references unless we
# force-load the static archive.  target_link_options expands the generator
# expression correctly at link time.
if(APPLE)
    target_link_options(Genius-MOS-SLM-FFI PRIVATE
        "LINKER:-force_load,$<TARGET_FILE:genius_api>"
    )
endif()

# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------
if(TESTING)
    enable_testing()
    add_subdirectory(${PROJECT_ROOT}/test ${CMAKE_BINARY_DIR}/test)
endif()

# ---------------------------------------------------------------------------
# Install
# ---------------------------------------------------------------------------
install(TARGETS neo-swarm          RUNTIME DESTINATION bin)
install(TARGETS Genius-MOS-SLM-FFI LIBRARY DESTINATION lib)
install(DIRECTORY ${PROJECT_ROOT}/src/
    DESTINATION include/genius
    FILES_MATCHING PATTERN "*.hpp"
)
install(FILES ${PROJECT_ROOT}/src/genius_slm_chat_c.h DESTINATION include/genius)
