# FindThirdparty.cmake
# Locates pre-built thirdparty libraries from the GeniusVentures thirdparty repo.
# Expects thirdparty/ as a sibling directory to GNUS-NEO-SWARM/.
#
# Usage:
#   include(FindThirdparty)
#   find_thirdparty_libs()

cmake_minimum_required(VERSION 3.22)

# Determine platform build directory
if(NOT THIRDPARTY_ROOT)
    set(THIRDPARTY_ROOT "${CMAKE_SOURCE_DIR}/../thirdparty")
endif()

if(APPLE)
    set(_PLATFORM "OSX")
elseif(WIN32)
    set(_PLATFORM "Windows")
elseif(ANDROID)
    set(_PLATFORM "Android")
elseif(IOS)
    set(_PLATFORM "iOS")
else()
    set(_PLATFORM "Linux")
endif()

if(NOT THIRDPARTY_BUILD_TYPE)
    set(THIRDPARTY_BUILD_TYPE "Release")
endif()

set(THIRDPARTY_BUILD_DIR "${THIRDPARTY_ROOT}/build/${_PLATFORM}/${THIRDPARTY_BUILD_TYPE}"
    CACHE PATH "Thirdparty build output directory")

message(STATUS "Thirdparty build dir: ${THIRDPARTY_BUILD_DIR}")

# Add thirdparty include and lib paths
list(APPEND CMAKE_PREFIX_PATH "${THIRDPARTY_BUILD_DIR}")
list(APPEND CMAKE_PREFIX_PATH "${THIRDPARTY_BUILD_DIR}/fmt/src/fmt-build")
list(APPEND CMAKE_INCLUDE_PATH "${THIRDPARTY_BUILD_DIR}/include")
list(APPEND CMAKE_LIBRARY_PATH "${THIRDPARTY_BUILD_DIR}/lib")

# Helper: find a library in thirdparty
macro(find_thirdparty_lib TARGET_NAME LIB_NAME)
    find_library(${TARGET_NAME}_LIB ${LIB_NAME}
        PATHS "${THIRDPARTY_BUILD_DIR}/lib"
        NO_DEFAULT_PATH
    )
    if(${TARGET_NAME}_LIB)
        message(STATUS "Found thirdparty ${LIB_NAME}: ${${TARGET_NAME}_LIB}")
    else()
        message(STATUS "Thirdparty ${LIB_NAME} not found (optional)")
    endif()
endmacro()

# Locate key libraries
function(find_thirdparty_libs)
    # MNN
    find_library(MNN_LIB MNN
        PATHS "${THIRDPARTY_BUILD_DIR}/MNN/lib"
        NO_DEFAULT_PATH)
    if(MNN_LIB)
        add_library(MNN UNKNOWN IMPORTED)
        set_target_properties(MNN PROPERTIES
            IMPORTED_LOCATION "${MNN_LIB}"
            INTERFACE_INCLUDE_DIRECTORIES "${THIRDPARTY_BUILD_DIR}/MNN/include"
        )
        message(STATUS "Found MNN: ${MNN_LIB}")
    endif()

    # RocksDB
    find_library(ROCKSDB_LIB rocksdb
        PATHS "${THIRDPARTY_BUILD_DIR}/rocksdb/lib"
        NO_DEFAULT_PATH)
    if(ROCKSDB_LIB)
        add_library(rocksdb UNKNOWN IMPORTED)
        set_target_properties(rocksdb PROPERTIES
            IMPORTED_LOCATION "${ROCKSDB_LIB}"
            INTERFACE_INCLUDE_DIRECTORIES "${THIRDPARTY_BUILD_DIR}/rocksdb/include"
        )
        message(STATUS "Found RocksDB: ${ROCKSDB_LIB}")
    endif()

    # secp256k1
    find_library(SECP256K1_LIB secp256k1
        PATHS "${THIRDPARTY_BUILD_DIR}/libsecp256k1/lib"
              "${THIRDPARTY_BUILD_DIR}/secp256k1/lib"
        NO_DEFAULT_PATH)
    if(SECP256K1_LIB)
        add_library(secp256k1 UNKNOWN IMPORTED)
        set_target_properties(secp256k1 PROPERTIES
            IMPORTED_LOCATION "${SECP256K1_LIB}"
            INTERFACE_INCLUDE_DIRECTORIES "${THIRDPARTY_BUILD_DIR}/libsecp256k1/include"
        )
        message(STATUS "Found secp256k1: ${SECP256K1_LIB}")
    endif()

    # spdlog
    find_library(SPDLOG_LIB spdlog
        PATHS "${THIRDPARTY_BUILD_DIR}/spdlog/lib"
        NO_DEFAULT_PATH)
    if(SPDLOG_LIB)
        add_library(spdlog::spdlog UNKNOWN IMPORTED)
        set_target_properties(spdlog::spdlog PROPERTIES
            IMPORTED_LOCATION "${SPDLOG_LIB}"
            INTERFACE_INCLUDE_DIRECTORIES "${THIRDPARTY_BUILD_DIR}/spdlog/include"
        )
        message(STATUS "Found spdlog: ${SPDLOG_LIB}")
    endif()

    # nlohmann/json (header-only)
    find_path(NLOHMANN_JSON_INCLUDE nlohmann/json.hpp
        PATHS "${THIRDPARTY_BUILD_DIR}/json/include"
              "${THIRDPARTY_ROOT}/json/include"
              "${THIRDPARTY_ROOT}/json/single_include"
        NO_DEFAULT_PATH)
    if(NLOHMANN_JSON_INCLUDE)
        add_library(nlohmann_json INTERFACE IMPORTED)
        set_target_properties(nlohmann_json PROPERTIES
            INTERFACE_INCLUDE_DIRECTORIES "${NLOHMANN_JSON_INCLUDE}"
        )
        message(STATUS "Found nlohmann/json: ${NLOHMANN_JSON_INCLUDE}")
    endif()

    # GTest
    find_library(GTEST_LIB gtest
        PATHS "${THIRDPARTY_BUILD_DIR}/GTest/lib"
        NO_DEFAULT_PATH)
    find_library(GTEST_MAIN_LIB gtest_main
        PATHS "${THIRDPARTY_BUILD_DIR}/GTest/lib"
        NO_DEFAULT_PATH)
    if(GTEST_LIB AND GTEST_MAIN_LIB)
        add_library(GTest::GTest UNKNOWN IMPORTED)
        set_target_properties(GTest::GTest PROPERTIES
            IMPORTED_LOCATION "${GTEST_LIB}"
            INTERFACE_INCLUDE_DIRECTORIES "${THIRDPARTY_BUILD_DIR}/GTest/include"
        )
        add_library(GTest::Main UNKNOWN IMPORTED)
        set_target_properties(GTest::Main PROPERTIES
            IMPORTED_LOCATION "${GTEST_MAIN_LIB}"
        )
        message(STATUS "Found GTest: ${GTEST_LIB}")
    endif()

    # libp2p
    find_library(LIBP2P_LIB p2p
        PATHS "${THIRDPARTY_BUILD_DIR}/libp2p/lib"
        NO_DEFAULT_PATH)
    if(LIBP2P_LIB)
        add_library(p2p::p2p UNKNOWN IMPORTED)
        set_target_properties(p2p::p2p PROPERTIES
            IMPORTED_LOCATION "${LIBP2P_LIB}"
            INTERFACE_INCLUDE_DIRECTORIES
                "${THIRDPARTY_BUILD_DIR}/libp2p/include;${THIRDPARTY_BUILD_DIR}/boost/build/include;${THIRDPARTY_BUILD_DIR}/soralog/include"
        )
        message(STATUS "Found libp2p: ${LIBP2P_LIB}")
    endif()

    # OpenSSL (from thirdparty)
    set(OPENSSL_ROOT_DIR "${THIRDPARTY_BUILD_DIR}/openssl/build" CACHE PATH "" FORCE)
    find_package(OpenSSL QUIET)
endfunction()
