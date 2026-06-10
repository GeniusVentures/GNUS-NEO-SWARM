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
set(THIRDPARTY_BUILD_DIR "${_THIRDPARTY_BUILD_DIR}" CACHE PATH "" FORCE)

# ---------------------------------------------------------------------------
# Boost version
# ---------------------------------------------------------------------------
set(BOOST_MAJOR_VERSION "1" CACHE STRING "Boost Major Version")
set(BOOST_MINOR_VERSION "85" CACHE STRING "Boost Minor Version")
set(BOOST_PATCH_VERSION "0" CACHE STRING "Boost Patch Version")
set(BOOST_VERSION    "${BOOST_MAJOR_VERSION}.${BOOST_MINOR_VERSION}.${BOOST_PATCH_VERSION}")
set(BOOST_VERSION_2U "${BOOST_MAJOR_VERSION}_${BOOST_MINOR_VERSION}")

# absl
if(NOT DEFINED absl_DIR)
    set(absl_DIR "${_THIRDPARTY_BUILD_DIR}/protobuf/lib/cmake/absl")
endif()

# utf8_range
if(NOT DEFINED utf8_range_DIR)
    set(utf8_range_DIR "${_THIRDPARTY_BUILD_DIR}/protobuf/lib/cmake/utf8_range")
endif()

# --------------------------------------------------------
# Set config of protobuf project
if (NOT DEFINED Protobuf_DIR)
    set(Protobuf_DIR "${THIRDPARTY_BUILD_DIR}/protobuf/lib/cmake/protobuf")
endif()
if (NOT DEFINED Protobuf_INCLUDE_DIR)
    set(Protobuf_INCLUDE_DIR "${THIRDPARTY_BUILD_DIR}/protobuf/protobuf")
endif()
if (NOT DEFINED PROTOC_EXECUTABLE)
    set(PROTOC_EXECUTABLE "${THIRDPARTY_BUILD_DIR}/protobuf/bin/protobuf${CMAKE_EXECUTABLE_SUFFIX}")
endif()

find_package(Protobuf CONFIG REQUIRED )

if (NOT DEFINED PROTOC_EXECUTABLE)
    set(PROTOC_EXECUTABLE "${THIRDPARTY_BUILD_DIR}/protobuf/bin/protoc${CMAKE_EXECUTABLE_SUFFIX}")
endif()

set(Protobuf_PROTOC_EXECUTABLE ${PROTOC_EXECUTABLE} CACHE PATH "Initial cache" FORCE)
if(NOT TARGET protobuf::protoc)
    add_executable(protobuf::protoc IMPORTED)
endif()
if(EXISTS "${Protobuf_PROTOC_EXECUTABLE}")
    set_target_properties(protobuf::protoc PROPERTIES
            IMPORTED_LOCATION ${Protobuf_PROTOC_EXECUTABLE})
endif()

# protoc definition #####################################################################################
get_target_property(PROTOC_LOCATION protobuf::protoc IMPORTED_LOCATION)
print("PROTOC_LOCATION: ${PROTOC_LOCATION}")
if ( Protobuf_FOUND )
    message( STATUS "Protobuf version : ${Protobuf_VERSION}" )
    message( STATUS "Protobuf compiler : ${Protobuf_PROTOC_EXECUTABLE}")
endif()

# ---------------------------------------------------------------------------
# Project-specific functions
# ---------------------------------------------------------------------------
include(${PROJECT_ROOT}/cmake/functions.cmake)

# ============================================================================
# Thirdparty dependencies — follow build/CommonBuildParameters.cmake.example
# ============================================================================

# ---------------------------------------------------------------------------
# GTest
# ---------------------------------------------------------------------------
set(GTest_DIR         "${THIRDPARTY_BUILD_DIR}/GTest/lib/cmake/GTest")
set(GTest_INCLUDE_DIR "${THIRDPARTY_BUILD_DIR}/GTest/include")
find_package(GTest CONFIG REQUIRED)
include_directories(${GTest_INCLUDE_DIR})

# ---------------------------------------------------------------------------
# OpenSSL
# ---------------------------------------------------------------------------
set(OPENSSL_DIR "${THIRDPARTY_BUILD_DIR}/openssl/build" CACHE PATH "OpenSSL install folder")
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

# --------------------------------------------------------
# Set config of soralog
set(soralog_DIR "${THIRDPARTY_BUILD_DIR}/soralog/lib/cmake/soralog")
set(soralog_INCLUDE_DIR "${THIRDPARTY_BUILD_DIR}/soralog/include")
find_package(soralog CONFIG REQUIRED)
include_directories(${soralog_INCLUDE_DIR})

# --------------------------------------------------------
# Set config of yaml-cpp
set(yaml-cpp_DIR "${THIRDPARTY_BUILD_DIR}/yaml-cpp/lib/cmake/yaml-cpp")
set(yaml-cpp_INCLUDE_DIR "${THIRDPARTY_BUILD_DIR}/yaml-cpp/include")
find_package(yaml-cpp CONFIG REQUIRED)
include_directories(${yaml-cpp_INCLUDE_DIR})

# --------------------------------------------------------
# Set config of  tsl_hat_trie
set(tsl_hat_trie_DIR "${THIRDPARTY_BUILD_DIR}/tsl_hat_trie/lib/cmake/tsl_hat_trie")
set(tsl_hat_trie_INCLUDE_DIR "${THIRDPARTY_BUILD_DIR}/tsl_hat_trie/include")
find_package(tsl_hat_trie CONFIG REQUIRED)
include_directories(${tsl_hat_trie_INCLUDE_DIR})

# --------------------------------------------------------
# Set config of Boost.DI
set(Boost.DI_INCLUDE_DIR "${THIRDPARTY_BUILD_DIR}/Boost.DI/include")
set(Boost.DI_DIR "${THIRDPARTY_BUILD_DIR}/Boost.DI/lib/cmake/Boost.DI")
find_package(Boost.DI CONFIG REQUIRED)
include_directories(${Boost.DI_INCLUDE_DIR})

if(CMP0169)
    cmake_policy(SET CMP0169 OLD)
endif()
# ---------------------------------------------------------------------------
# Boost
# ---------------------------------------------------------------------------
set(_BOOST_ROOT       "${THIRDPARTY_BUILD_DIR}/boost/build")
set(Boost_LIB_DIR     "${_BOOST_ROOT}/lib")
set(Boost_INCLUDE_DIR "${_BOOST_ROOT}/include")
set(Boost_DIR         "${Boost_LIB_DIR}/cmake/Boost-${BOOST_VERSION}")
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

# --------------------------------------------------------
# Set config of SQLiteModernCpp project
set(SQLiteModernCpp_ROOT_DIR "${THIRDPARTY_BUILD_DIR}/SQLiteModernCpp")
set(SQLiteModernCpp_DIR "${SQLiteModernCpp_ROOT_DIR}/lib/cmake/SQLiteModernCpp")
set(SQLiteModernCpp_LIB_DIR "${SQLiteModernCpp_ROOT_DIR}/lib")
set(SQLiteModernCpp_INCLUDE_DIR "${SQLiteModernCpp_ROOT_DIR}/include")

# --------------------------------------------------------
# Set config of SQLiteModernCpp project
set(sqlite3_ROOT_DIR "${THIRDPARTY_BUILD_DIR}/sqlite3")
set(sqlite3_DIR "${sqlite3_ROOT_DIR}/lib/cmake/sqlite3")
set(sqlite3_LIB_DIR "${sqlite3_ROOT_DIR}/lib")
set(sqlite3_INCLUDE_DIR "${sqlite3_ROOT_DIR}/include")

# ---------------------------------------------------------------------------
# nlohmann/json (header-only)
# ---------------------------------------------------------------------------
set(nlohmann_json_DIR "${THIRDPARTY_BUILD_DIR}/json/share/cmake/nlohmann_json")
set(_JSON_INCLUDE     "${THIRDPARTY_BUILD_DIR}/json/include")
find_package(nlohmann_json CONFIG REQUIRED)
include_directories(${_JSON_INCLUDE})

# ---------------------------------------------------------------------------
# secp256k1
# ---------------------------------------------------------------------------
set(libsecp256k1_DIR "${THIRDPARTY_BUILD_DIR}/libsecp256k1/lib/cmake/libsecp256k1")
set(libsecp256k1_INCLUDE_DIR "${THIRDPARTY_BUILD_DIR}/libsecp256k1/include")
find_package(libsecp256k1 CONFIG REQUIRED)
include_directories(${libsecp256k1_INCLUDE_DIR})
if(TARGET libsecp256k1::secp256k1 AND NOT TARGET secp256k1)
    add_library(secp256k1 ALIAS libsecp256k1::secp256k1)
endif()

# ---------------------------------------------------------------------------
# MNN
# ---------------------------------------------------------------------------
set(MNN_INCLUDE_DIR "${THIRDPARTY_BUILD_DIR}/MNN/include")
find_library(MNN_LIBRARY MNN PATHS "${THIRDPARTY_BUILD_DIR}/MNN/lib" REQUIRED)
add_library(MNN UNKNOWN IMPORTED)
set_target_properties(MNN PROPERTIES
    IMPORTED_LOCATION "${MNN_LIBRARY}"
    INTERFACE_INCLUDE_DIRECTORIES "${MNN_INCLUDE_DIR}"
)
message(STATUS "MNN: ${MNN_LIBRARY}")

# ---------------------------------------------------------------------------
# SentencePiece (optional — not yet built in all thirdparty configs)
# ---------------------------------------------------------------------------
set(SentencePiece_INCLUDE_DIR "${THIRDPARTY_BUILD_DIR}/sentencepiece/include")
find_library(SENTENCEPIECE_LIB sentencepiece
    PATHS "${THIRDPARTY_BUILD_DIR}/sentencepiece/lib" NO_DEFAULT_PATH)
if(SENTENCEPIECE_LIB)
    add_library(sentencepiece UNKNOWN IMPORTED)
    set_target_properties(sentencepiece PROPERTIES
        IMPORTED_LOCATION "${SENTENCEPIECE_LIB}"
        INTERFACE_INCLUDE_DIRECTORIES "${SentencePiece_INCLUDE_DIR}"
    )
    include_directories(${SentencePiece_INCLUDE_DIR})
    message(STATUS "SentencePiece: ${SENTENCEPIECE_LIB}")
else()
    include_directories(${PROJECT_ROOT}/src/core/tokenizer/stub)
    message(STATUS "SentencePiece not found — tokenizer runs in whitespace stub mode")
endif()

# ---------------------------------------------------------------------------
# SGProcessingManager (from SuperGenius submodule)
# ---------------------------------------------------------------------------
set(SGPROCESSING_DIR "${PROJECT_SUPER_ROOT}/SuperGenius/SGProcessingManager")
if(EXISTS "${SGPROCESSING_DIR}/generated/InputFormat.hpp")
    include_directories("${SGPROCESSING_DIR}/generated")
    include_directories("${SGPROCESSING_DIR}/src")
    include_directories("${SGPROCESSING_DIR}/include")
    message(STATUS "SGProcessingManager: ${SGPROCESSING_DIR}")
else()
    message(STATUS "SGProcessingManager not found — SGProcessing bridge runs in stub mode")
endif()

# ---------------------------------------------------------------------------
# RocksDB + Snappy
# ---------------------------------------------------------------------------
set(Snappy_DIR         "${THIRDPARTY_BUILD_DIR}/snappy/lib/cmake/Snappy")
set(Snappy_INCLUDE_DIR "${THIRDPARTY_BUILD_DIR}/snappy/include")
find_package(Snappy CONFIG REQUIRED)
include_directories(${Snappy_INCLUDE_DIR})

set(RocksDB_DIR         "${THIRDPARTY_BUILD_DIR}/rocksdb/lib/cmake/rocksdb")
set(RocksDB_INCLUDE_DIR "${THIRDPARTY_BUILD_DIR}/rocksdb/include")
find_package(RocksDB CONFIG REQUIRED)
include_directories(${RocksDB_INCLUDE_DIR})

# --------------------------------------------------------
# Set config of cares
set(c-ares_DIR "${THIRDPARTY_BUILD_DIR}/cares/lib/cmake/c-ares" CACHE PATH "Path to c-ares install folder")
set(c-ares_INCLUDE_DIR "${THIRDPARTY_BUILD_DIR}/cares/include" CACHE PATH "Path to c-ares include folder")

# ---------------------------------------------------------------------------
# ZLIB (required by protobuf / libp2p)
# ---------------------------------------------------------------------------
set(ZLIB_DIR "${THIRDPARTY_BUILD_DIR}/zlib/lib/cmake/zlib")
find_package(ZLIB CONFIG REQUIRED)

# --------------------------------------------------------
# Set config of libp2p
set(libp2p_DIR "${THIRDPARTY_BUILD_DIR}/libp2p/lib/cmake/libp2p")
set(libp2p_LIBRARY_DIR "${THIRDPARTY_BUILD_DIR}/libp2p/lib")
set(libp2p_INCLUDE_DIR    "${THIRDPARTY_BUILD_DIR}/libp2p/include")
find_package(libp2p CONFIG REQUIRED)
include_directories(${libp2p_INCLUDE_DIR})

# --------------------------------------------------------
# Find and include cares if libp2p have not included it
if (NOT TARGET c-ares::cares_static)
    find_package(c-ares CONFIG REQUIRED)
endif()
include_directories(${c-ares_INCLUDE_DIR})

# Vulkan
find_package(Vulkan)

if(NOT TARGET Vulkan::Vulkan)
    if(NOT DEFINED $ENV{VULKAN_SDK})
        set(ENV{VULKAN_SDK} "${_THIRDPARTY_BUILD_DIR}/Vulkan-Loader")
    endif()

    find_package(Vulkan REQUIRED)
endif()

# ---------------------------------------------------------------------------
# Threads
# ---------------------------------------------------------------------------
find_package(Threads REQUIRED)

# ---------------------------------------------------------------------------
# Project include root
# ---------------------------------------------------------------------------
include_directories(${PROJECT_ROOT}/src)

# ---------------------------------------------------------------------------
# GeniusSDK (dynamic library — transitive deps resolved at link time)
# ---------------------------------------------------------------------------
set(GENIUS_SDK_DIR "${PROJECT_SUPER_ROOT}/GeniusSDK")
set(GENIUS_SDK_INCLUDE_DIR "${GENIUS_SDK_DIR}/src")
set(GENIUS_SDK_BUILD_DIR "${GENIUS_SDK_DIR}/build/${BUILD_PLATFORM_NAME}/${CMAKE_BUILD_TYPE}${ABI_SUBFOLDER_NAME}")

find_library(GENIUS_SDK_LIB GeniusSDK_shared
    PATHS "${GENIUS_SDK_BUILD_DIR}/GeniusSDK/lib"
          "${GENIUS_SDK_BUILD_DIR}/src"
    NO_DEFAULT_PATH REQUIRED)

add_library(GeniusSDK SHARED IMPORTED)
set_target_properties(GeniusSDK PROPERTIES
    IMPORTED_LOCATION "${GENIUS_SDK_LIB}"
    INTERFACE_INCLUDE_DIRECTORIES "${GENIUS_SDK_INCLUDE_DIR}"
)
message(STATUS "GeniusSDK: ${GENIUS_SDK_LIB}")

# ============================================================================
# Build targets
# ============================================================================

# Source tree
add_subdirectory(${PROJECT_ROOT}/src ${CMAKE_BINARY_DIR}/src)

# Main binary
add_executable(neo-swarm ${PROJECT_ROOT}/src/main.cpp)
target_link_libraries(neo-swarm PRIVATE neoswarm_api Threads::Threads)
if(APPLE)
    target_link_options(neo-swarm PRIVATE "LINKER:-no_warn_duplicate_libraries")
endif()
if(UNIX AND NOT APPLE)
    target_link_libraries(neo-swarm PRIVATE uuid)
endif()

# FFI shared library (Flutter bridge)
add_library(Genius-MOS-ELM-FFI SHARED ${PROJECT_ROOT}/src/genius_elm_chat_completions.cpp)
target_include_directories(Genius-MOS-ELM-FFI PUBLIC ${PROJECT_ROOT}/src)
target_compile_definitions(Genius-MOS-ELM-FFI PRIVATE NEOSWARM_CHAT_C_EXPORTS)
target_link_libraries(Genius-MOS-ELM-FFI PRIVATE Threads::Threads)
# Note: neoswarm_api not linked — stub currently returns hardcoded responses.
# When wiring to real ApiServer, add: target_link_libraries(Genius-MOS-ELM-FFI PRIVATE neoswarm_api)

if(BUILD_TESTING)
    enable_testing()
    if(IS_DIRECTORY "${PROJECT_ROOT}/test")
        add_subdirectory(${PROJECT_ROOT}/test ${CMAKE_BINARY_DIR}/test)
    endif()
endif()

if(BUILD_EXAMPLES)
    if(IS_DIRECTORY "${PROJECT_ROOT}/example")
        add_subdirectory(${PROJECT_ROOT}/example ${CMAKE_BINARY_DIR}/example)
    endif()
endif()

# Install
install(TARGETS neo-swarm RUNTIME DESTINATION bin)
install(TARGETS Genius-MOS-ELM-FFI LIBRARY DESTINATION lib)

install(TARGETS
    neoswarm_common neoswarm_core neoswarm_specialists neoswarm_router
    neoswarm_reputation neoswarm_security neoswarm_network neoswarm_knowledge neoswarm_api
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
install(FILES ${PROJECT_ROOT}/src/genius_elm_chat_completions.h DESTINATION include/genius)

# Package config export
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
