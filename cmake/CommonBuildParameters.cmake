# CommonBuildParameters.cmake — GNUS-NEO-SWARM
# Called from build/<Platform>/CMakeLists.txt via build/CommonBuildParameters.cmake.
# Sets up all thirdparty dependencies and adds the project source/test trees.
#
# At this point, CommonCompilerOptions.cmake has already set:
#   - PROJECT_ROOT (via get_default_root)
#   - _THIRDPARTY_BUILD_DIR
#   - ZKLLVM_BUILD_DIR (if applicable)
#   - C++17, GNUInstallDirs, CompilationFlags, etc.

# ---------------------------------------------------------------------------
# Convenience alias (source CMakeLists use THIRDPARTY_BUILD_DIR)
# ---------------------------------------------------------------------------
set(THIRDPARTY_BUILD_DIR "${THIRDPARTY_BUILD_DIR}/Release" CACHE PATH "" FORCE)

# ---------------------------------------------------------------------------
# Boost version
# ---------------------------------------------------------------------------
set(BOOST_MAJOR_VERSION "1" CACHE STRING "Boost Major Version")
set(BOOST_MINOR_VERSION "85" CACHE STRING "Boost Minor Version")
set(BOOST_PATCH_VERSION "0" CACHE STRING "Boost Patch Version")
set(BOOST_VERSION    "${BOOST_MAJOR_VERSION}.${BOOST_MINOR_VERSION}.${BOOST_PATCH_VERSION}")
set(BOOST_VERSION_2U "${BOOST_MAJOR_VERSION}_${BOOST_MINOR_VERSION}")

# ---------------------------------------------------------------------------
# GTest
# ---------------------------------------------------------------------------
set(GTest_DIR         "${THIRDPARTY_BUILD_DIR}/GTest/lib/cmake/GTest")
set(GTest_INCLUDE_DIR "${THIRDPARTY_BUILD_DIR}/GTest/include")
find_package(GTest CONFIG REQUIRED)
include_directories(${GTest_INCLUDE_DIR})

# ---------------------------------------------------------------------------
# Project-specific functions
# ---------------------------------------------------------------------------
include(${PROJECT_ROOT}/cmake/functions.cmake)

# ---------------------------------------------------------------------------
# OpenSSL
# ---------------------------------------------------------------------------
set(OPENSSL_DIR "${THIRDPARTY_BUILD_DIR}/openssl/build"
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
set(GSL_INCLUDE_DIR "${THIRDPARTY_BUILD_DIR}/Microsoft.GSL/include")
include_directories(${GSL_INCLUDE_DIR})

# ---------------------------------------------------------------------------
# fmt
# ---------------------------------------------------------------------------
set(fmt_DIR         "${THIRDPARTY_BUILD_DIR}/fmt/lib/cmake/fmt")
set(fmt_INCLUDE_DIR "${THIRDPARTY_BUILD_DIR}/fmt/include")
find_package(fmt CONFIG REQUIRED)
include_directories(${fmt_INCLUDE_DIR})

# ---------------------------------------------------------------------------
# spdlog
# ---------------------------------------------------------------------------
set(spdlog_DIR         "${THIRDPARTY_BUILD_DIR}/spdlog/lib/cmake/spdlog")
set(spdlog_INCLUDE_DIR "${THIRDPARTY_BUILD_DIR}/spdlog/include")
find_package(spdlog CONFIG REQUIRED)
include_directories(${spdlog_INCLUDE_DIR})
add_compile_definitions(SPDLOG_FMT_EXTERNAL GENIUS_HAS_SPDLOG)

# ---------------------------------------------------------------------------
# Boost
# ---------------------------------------------------------------------------
set(_BOOST_ROOT    "${THIRDPARTY_BUILD_DIR}/boost/build")
set(Boost_LIB_DIR  "${_BOOST_ROOT}/lib")
set(Boost_INCLUDE_DIR "${_BOOST_ROOT}/include")

# Use cmake config mode (works with CMake 4.x where FindBoost is removed)
set(Boost_DIR "${Boost_LIB_DIR}/cmake/Boost-${BOOST_VERSION}")
list(APPEND CMAKE_PREFIX_PATH "${Boost_LIB_DIR}/cmake")

set(Boost_USE_MULTITHREADED  ON)
set(Boost_USE_STATIC_LIBS    ON)
set(Boost_USE_STATIC_RUNTIME ON)
set(Boost_NO_SYSTEM_PATHS    ON)

if(POLICY CMP0167)
    cmake_policy(SET CMP0167 OLD)
endif()
find_package(Boost ${BOOST_VERSION} CONFIG REQUIRED COMPONENTS
    date_time filesystem random regex system thread log log_setup program_options)
include_directories(${Boost_INCLUDE_DIRS})

# ---------------------------------------------------------------------------
# nlohmann/json (header-only)
# ---------------------------------------------------------------------------
set(nlohmann_json_DIR "${THIRDPARTY_BUILD_DIR}/json/share/cmake/nlohmann_json")
find_package(nlohmann_json CONFIG QUIET)
set(_JSON_INCLUDE "${THIRDPARTY_BUILD_DIR}/json/include")
if(EXISTS "${_JSON_INCLUDE}/nlohmann/json.hpp")
    include_directories(${_JSON_INCLUDE})
    message(STATUS "nlohmann/json: ${_JSON_INCLUDE}")
else()
    message(WARNING "nlohmann/json not found at ${_JSON_INCLUDE}")
endif()

# ---------------------------------------------------------------------------
# secp256k1
# ---------------------------------------------------------------------------
set(libsecp256k1_DIR         "${THIRDPARTY_BUILD_DIR}/libsecp256k1/lib/cmake/libsecp256k1")
set(libsecp256k1_INCLUDE_DIR "${THIRDPARTY_BUILD_DIR}/libsecp256k1/include")
set(libsecp256k1_LIBRARY_DIR "${THIRDPARTY_BUILD_DIR}/libsecp256k1/lib")
find_package(libsecp256k1 CONFIG QUIET)
if(libsecp256k1_FOUND)
    include_directories(${libsecp256k1_INCLUDE_DIR})
    if(TARGET libsecp256k1::secp256k1 AND NOT TARGET secp256k1)
        add_library(secp256k1 ALIAS libsecp256k1::secp256k1)
    elseif(NOT TARGET secp256k1)
        find_library(_SECP256K1_LIB secp256k1
            PATHS "${libsecp256k1_LIBRARY_DIR}" NO_DEFAULT_PATH)
        if(_SECP256K1_LIB)
            add_library(secp256k1 UNKNOWN IMPORTED)
            set_target_properties(secp256k1 PROPERTIES
                IMPORTED_LOCATION "${_SECP256K1_LIB}"
                INTERFACE_INCLUDE_DIRECTORIES "${libsecp256k1_INCLUDE_DIR}"
            )
        endif()
    endif()
    message(STATUS "secp256k1 found")
endif()

# ---------------------------------------------------------------------------
# MNN
# ---------------------------------------------------------------------------
set(_MNN_LIB "${THIRDPARTY_BUILD_DIR}/MNN/lib/libMNN${CMAKE_STATIC_LIBRARY_SUFFIX}")
if(NOT EXISTS "${_MNN_LIB}")
    set(_MNN_LIB "${THIRDPARTY_BUILD_DIR}/MNN/lib/libMNN.dylib")
endif()
if(EXISTS "${_MNN_LIB}")
    add_library(MNN UNKNOWN IMPORTED)
    set_target_properties(MNN PROPERTIES
        IMPORTED_LOCATION "${_MNN_LIB}"
        INTERFACE_INCLUDE_DIRECTORIES "${THIRDPARTY_BUILD_DIR}/MNN/include"
    )
    message(STATUS "MNN: ${_MNN_LIB}")
else()
    message(STATUS "MNN not found — inference engine runs in stub mode")
endif()

# ---------------------------------------------------------------------------
# SentencePiece
# ---------------------------------------------------------------------------
find_library(SENTENCEPIECE_LIB sentencepiece
    PATHS "${THIRDPARTY_BUILD_DIR}/sentencepiece/lib" NO_DEFAULT_PATH)
if(SENTENCEPIECE_LIB)
    add_library(sentencepiece UNKNOWN IMPORTED)
    set_target_properties(sentencepiece PROPERTIES
        IMPORTED_LOCATION "${SENTENCEPIECE_LIB}"
        INTERFACE_INCLUDE_DIRECTORIES "${THIRDPARTY_BUILD_DIR}/sentencepiece/include"
    )
    message(STATUS "SentencePiece: ${SENTENCEPIECE_LIB}")
else()
    message(STATUS "SentencePiece not found — tokenizer runs in whitespace stub mode")
endif()

# ---------------------------------------------------------------------------
# RocksDB
# ---------------------------------------------------------------------------
set(RocksDB_DIR "${THIRDPARTY_BUILD_DIR}/rocksdb/lib/cmake/rocksdb")
find_package(RocksDB CONFIG QUIET)
if(NOT RocksDB_FOUND)
    find_library(ROCKSDB_LIB rocksdb
        PATHS "${THIRDPARTY_BUILD_DIR}/rocksdb/lib" NO_DEFAULT_PATH)
    if(ROCKSDB_LIB)
        add_library(rocksdb UNKNOWN IMPORTED)
        set_target_properties(rocksdb PROPERTIES
            IMPORTED_LOCATION "${ROCKSDB_LIB}"
            INTERFACE_INCLUDE_DIRECTORIES "${THIRDPARTY_BUILD_DIR}/rocksdb/include"
        )
        message(STATUS "RocksDB: ${ROCKSDB_LIB}")
    endif()
endif()

# Snappy (RocksDB dependency)
set(Snappy_DIR "${THIRDPARTY_BUILD_DIR}/snappy/lib/cmake/Snappy")
find_package(Snappy CONFIG QUIET)
if(NOT TARGET Snappy::snappy)
    find_library(_SNAPPY_LIB snappy
        PATHS "${THIRDPARTY_BUILD_DIR}/snappy/lib" NO_DEFAULT_PATH)
    if(_SNAPPY_LIB)
        add_library(Snappy::snappy UNKNOWN IMPORTED)
        set_target_properties(Snappy::snappy PROPERTIES
            IMPORTED_LOCATION "${_SNAPPY_LIB}"
            INTERFACE_INCLUDE_DIRECTORIES "${THIRDPARTY_BUILD_DIR}/snappy/include"
        )
        message(STATUS "Snappy: ${_SNAPPY_LIB}")
    endif()
endif()

# ---------------------------------------------------------------------------
# libp2p (optional) and transitive dependencies
# ---------------------------------------------------------------------------
foreach(_tp_pkg protobuf yaml-cpp tsl_hat_trie soralog Boost.DI
                ed25519 sr25519-donna xxhash cares ipfs-lite-cpp
                ipfs-pubsub ipfs-bitswap-cpp sqlite3 SQLiteModernCpp)
    list(APPEND CMAKE_PREFIX_PATH "${THIRDPARTY_BUILD_DIR}/${_tp_pkg}/lib/cmake/${_tp_pkg}")
    list(APPEND CMAKE_PREFIX_PATH "${THIRDPARTY_BUILD_DIR}/${_tp_pkg}/lib/cmake")
endforeach()
list(APPEND CMAKE_PREFIX_PATH "${THIRDPARTY_BUILD_DIR}")

set(libp2p_DIR "${THIRDPARTY_BUILD_DIR}/libp2p/lib/cmake/libp2p")
find_package(libp2p CONFIG QUIET)
if(libp2p_FOUND)
    include_directories("${THIRDPARTY_BUILD_DIR}/libp2p/include")
    message(STATUS "libp2p found")
else()
    message(STATUS "libp2p not found — P2P networking runs in stub mode")
endif()

# ---------------------------------------------------------------------------
# Threads
# ---------------------------------------------------------------------------
find_package(Threads REQUIRED)

# ---------------------------------------------------------------------------
# Vulkan
# ---------------------------------------------------------------------------
find_package(Vulkan QUIET)
if(NOT Vulkan_FOUND)
    set(_VULKAN_LOADER_LIB "${THIRDPARTY_BUILD_DIR}/Vulkan-Loader/lib/libvulkan.1.dylib")
    set(_VULKAN_HEADERS_DIR "${THIRDPARTY_BUILD_DIR}/Vulkan-Loader/include")
    if(EXISTS "${_VULKAN_LOADER_LIB}" AND EXISTS "${_VULKAN_HEADERS_DIR}/vulkan/vulkan_core.h")
        add_library(Vulkan::Vulkan SHARED IMPORTED)
        set_target_properties(Vulkan::Vulkan PROPERTIES
            IMPORTED_LOCATION "${_VULKAN_LOADER_LIB}"
            INTERFACE_INCLUDE_DIRECTORIES "${_VULKAN_HEADERS_DIR}"
        )
        set(Vulkan_FOUND TRUE)
        message(STATUS "Vulkan: ${_VULKAN_LOADER_LIB}")
    endif()
endif()

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
add_subdirectory(${PROJECT_ROOT}/src/common      ${CMAKE_BINARY_DIR}/src/common)
add_subdirectory(${PROJECT_ROOT}/src/core        ${CMAKE_BINARY_DIR}/src/core)
add_subdirectory(${PROJECT_ROOT}/src/specialists ${CMAKE_BINARY_DIR}/src/specialists)
add_subdirectory(${PROJECT_ROOT}/src/router      ${CMAKE_BINARY_DIR}/src/router)
add_subdirectory(${PROJECT_ROOT}/src/reputation  ${CMAKE_BINARY_DIR}/src/reputation)
add_subdirectory(${PROJECT_ROOT}/src/security    ${CMAKE_BINARY_DIR}/src/security)
add_subdirectory(${PROJECT_ROOT}/src/network     ${CMAKE_BINARY_DIR}/src/network)
add_subdirectory(${PROJECT_ROOT}/src/knowledge   ${CMAKE_BINARY_DIR}/src/knowledge)
add_subdirectory(${PROJECT_ROOT}/src/api         ${CMAKE_BINARY_DIR}/src/api)

# ---------------------------------------------------------------------------
# Main binary
# ---------------------------------------------------------------------------
add_executable(neo-swarm ${PROJECT_ROOT}/src/genius_chat_cli.cpp)
target_link_libraries(neo-swarm PRIVATE genius_api Threads::Threads)
if(UNIX AND NOT APPLE)
    target_link_libraries(neo-swarm PRIVATE uuid)
endif()

# ---------------------------------------------------------------------------
# FFI shared library (Flutter bridge)
# Links against genius_api so GeniusElmChatCompletionsCreate calls the real
# GeniusAPIServer pipeline instead of returning a hardcoded stub.
# ---------------------------------------------------------------------------
add_library(Genius-MOS-ELM-FFI SHARED ${PROJECT_ROOT}/src/genius_elm_chat_c.cpp)
target_include_directories(Genius-MOS-ELM-FFI PUBLIC ${PROJECT_ROOT}/src)
target_compile_definitions(Genius-MOS-ELM-FFI PRIVATE GENIUS_ELM_CHAT_C_EXPORTS)
target_link_libraries(Genius-MOS-ELM-FFI PRIVATE genius_api Threads::Threads)
if(APPLE)
    target_link_options(Genius-MOS-ELM-FFI PRIVATE
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
install(TARGETS neo-swarm RUNTIME DESTINATION bin)
install(TARGETS Genius-MOS-ELM-FFI LIBRARY DESTINATION lib)

install(TARGETS
    genius_common genius_core genius_specialists genius_router
    genius_reputation genius_security genius_network genius_knowledge genius_api
    EXPORT ${PROJECT_ROOT_NAME}Targets
    LIBRARY       DESTINATION ${CMAKE_INSTALL_LIBDIR}
    ARCHIVE       DESTINATION ${CMAKE_INSTALL_LIBDIR}
    RUNTIME       DESTINATION ${CMAKE_INSTALL_BINDIR}
    INCLUDES      DESTINATION ${CMAKE_INSTALL_INCLUDEDIR}
    PUBLIC_HEADER DESTINATION ${CMAKE_INSTALL_INCLUDEDIR}
)

install(DIRECTORY ${PROJECT_ROOT}/src/
    DESTINATION include/genius
    FILES_MATCHING PATTERN "*.hpp"
)
install(FILES ${PROJECT_ROOT}/src/genius_elm_chat_c.h DESTINATION include/genius)

# ---------------------------------------------------------------------------
# Package config export
# ---------------------------------------------------------------------------
install(
    EXPORT ${PROJECT_ROOT_NAME}Targets
    DESTINATION ${CMAKE_INSTALL_LIBDIR}/cmake/${PROJECT_ROOT_NAME}
    NAMESPACE genius::
)

configure_package_config_file(${PROJECT_ROOT}/cmake/config.cmake.in
    "${CMAKE_CURRENT_BINARY_DIR}/${PROJECT_ROOT_NAME}Config.cmake"
    INSTALL_DESTINATION ${CMAKE_INSTALL_LIBDIR}/cmake/${PROJECT_ROOT_NAME}
    NO_SET_AND_CHECK_MACRO
    NO_CHECK_REQUIRED_COMPONENTS_MACRO
)

install(FILES
    ${CMAKE_CURRENT_BINARY_DIR}/${PROJECT_ROOT_NAME}Config.cmake
    DESTINATION ${CMAKE_INSTALL_LIBDIR}/cmake/${PROJECT_ROOT_NAME}
)
