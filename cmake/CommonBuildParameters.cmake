
# --------------------------------------------------------
# Set config of GTest
if(BUILD_TESTING)
    set(GTest_DIR "${THIRDPARTY_BUILD_DIR}/GTest/lib/cmake/GTest")
    set(GTest_INCLUDE_DIR "${THIRDPARTY_BUILD_DIR}/GTest/include")
    find_package(GTest CONFIG REQUIRED)
    include_directories(${GTest_INCLUDE_DIR})
endif()

# zlib
find_package(zlib CONFIG REQUIRED)

# absl
if(NOT DEFINED absl_DIR)
    set(absl_DIR "${_THIRDPARTY_BUILD_DIR}/protobuf/lib/cmake/absl")
endif()

# utf8_range
if(NOT DEFINED utf8_range_DIR)
    set(utf8_range_DIR "${_THIRDPARTY_BUILD_DIR}/protobuf/lib/cmake/utf8_range")
endif()

include(${PROJECT_ROOT}/cmake/functions.cmake)

# --------------------------------------------------------
# Set config of openssl project
set(OPENSSL_DIR "${_THIRDPARTY_BUILD_DIR}/openssl/build/${CMAKE_SYSTEM_NAME}${ABI_SUBFOLDER_NAME}" CACHE PATH "Path to OpenSSL install folder")
set(OPENSSL_USE_STATIC_LIBS ON CACHE BOOL "OpenSSL use static libs")
set(OPENSSL_MSVC_STATIC_RT ON CACHE BOOL "OpenSSL use static RT")
set(OPENSSL_ROOT_DIR "${OPENSSL_DIR}" CACHE PATH "Path to OpenSSL install root folder")
set(OPENSSL_INCLUDE_DIR "${OPENSSL_DIR}/include" CACHE PATH "Path to OpenSSL include folder")
set(OPENSSL_LIBRARIES "${OPENSSL_DIR}/lib" CACHE PATH "Path to OpenSSL lib folder")
set(OPENSSL_CRYPTO_LIBRARY ${OPENSSL_LIBRARIES}/libcrypto${CMAKE_STATIC_LIBRARY_SUFFIX} CACHE PATH "Path to OpenSSL crypto lib")
set(OPENSSL_SSL_LIBRARY ${OPENSSL_LIBRARIES}/libssl${CMAKE_STATIC_LIBRARY_SUFFIX} CACHE PATH "Path to OpenSSL ssl lib")
find_package(OpenSSL REQUIRED)
include_directories(${OPENSSL_INCLUDE_DIR})

# snappy
set(Snappy_DIR "${_THIRDPARTY_BUILD_DIR}/snappy/lib/cmake/Snappy")
set(Snappy_INCLUDE_DIR "${THIRDPARTY_BUILD_DIR}/snappy/include")
find_package(Snappy CONFIG REQUIRED)
include_directories(${Snappy_INCLUDE_DIR})

# --------------------------------------------------------
# Set config of Microsoft.GSL
set(GSL_INCLUDE_DIR "${_THIRDPARTY_BUILD_DIR}/Microsoft.GSL/include")
include_directories(${GSL_INCLUDE_DIR})

# --------------------------------------------------------
# Set config of fmt
set(fmt_DIR "${_THIRDPARTY_BUILD_DIR}/fmt/lib/cmake/fmt")
set(fmt_INCLUDE_DIR "${_THIRDPARTY_BUILD_DIR}/fmt/include")
find_package(fmt CONFIG REQUIRED)
include_directories(${fmt_INCLUDE_DIR})

# --------------------------------------------------------
# Set config of spdlog v1.4.2
set(spdlog_DIR "${_THIRDPARTY_BUILD_DIR}/spdlog/lib/cmake/spdlog")
set(spdlog_INCLUDE_DIR "${_THIRDPARTY_BUILD_DIR}/spdlog/include")
find_package(spdlog CONFIG REQUIRED)
include_directories(${spdlog_INCLUDE_DIR})
add_compile_definitions("SPDLOG_FMT_EXTERNAL")

# --------------------------------------------------------
# Set config of soralog
set(soralog_DIR "${_THIRDPARTY_BUILD_DIR}/soralog/lib/cmake/soralog")
set(soralog_INCLUDE_DIR "${_THIRDPARTY_BUILD_DIR}/soralog/include")
find_package(soralog CONFIG REQUIRED)
include_directories(${soralog_INCLUDE_DIR})

# --------------------------------------------------------
# Set config of yaml-cpp
set(yaml-cpp_DIR "${_THIRDPARTY_BUILD_DIR}/yaml-cpp/lib/cmake/yaml-cpp")
set(yaml-cpp_INCLUDE_DIR "${_THIRDPARTY_BUILD_DIR}/yaml-cpp/include")
find_package(yaml-cpp CONFIG REQUIRED)
include_directories(${yaml-cpp_INCLUDE_DIR})

# --------------------------------------------------------
# Set config of  tsl_hat_trie
set(tsl_hat_trie_DIR "${_THIRDPARTY_BUILD_DIR}/tsl_hat_trie/lib/cmake/tsl_hat_trie")
set(tsl_hat_trie_INCLUDE_DIR "${_THIRDPARTY_BUILD_DIR}/tsl_hat_trie/include")
find_package(tsl_hat_trie CONFIG REQUIRED)
include_directories(${tsl_hat_trie_INCLUDE_DIR})

# --------------------------------------------------------
# Set config of Boost.DI
set(Boost.DI_INCLUDE_DIR "${_THIRDPARTY_BUILD_DIR}/Boost.DI/include")
set(Boost.DI_DIR "${_THIRDPARTY_BUILD_DIR}/Boost.DI/lib/cmake/Boost.DI")
find_package(Boost.DI CONFIG REQUIRED)
include_directories(${Boost.DI_INCLUDE_DIR})

# Boost should be loaded before libp2p v0.1.2
# --------------------------------------------------------
# Boost project
set(_BOOST_ROOT "${_THIRDPARTY_BUILD_DIR}/boost/build")
set(Boost_LIB_DIR "${_BOOST_ROOT}/lib")
set(Boost_INCLUDE_DIR "${_BOOST_ROOT}/include/boost-${BOOST_VERSION_2U}")
set(Boost_DIR "${Boost_LIB_DIR}/cmake/Boost-${BOOST_VERSION}")
set(boost_atomic_DIR "${Boost_LIB_DIR}/cmake/boost_atomic-${BOOST_VERSION}")
set(boost_chrono_DIR "${Boost_LIB_DIR}/cmake/boost_chrono-${BOOST_VERSION}")
set(boost_container_DIR "${Boost_LIB_DIR}/cmake/boost_container-${BOOST_VERSION}")
set(boost_context_DIR "${Boost_LIB_DIR}/cmake/boost_context-${BOOST_VERSION}")
set(boost_date_time_DIR "${Boost_LIB_DIR}/cmake/boost_date_time-${BOOST_VERSION}")
set(boost_filesystem_DIR "${Boost_LIB_DIR}/cmake/boost_filesystem-${BOOST_VERSION}")
set(boost_headers_DIR "${Boost_LIB_DIR}/cmake/boost_headers-${BOOST_VERSION}")
set(boost_json_DIR "${Boost_LIB_DIR}/cmake/boost_json-${BOOST_VERSION}")
set(boost_log_DIR "${Boost_LIB_DIR}/cmake/boost_log-${BOOST_VERSION}")
set(boost_log_setup_DIR "${Boost_LIB_DIR}/cmake/boost_log_setup-${BOOST_VERSION}")
set(boost_program_options_DIR "${Boost_LIB_DIR}/cmake/boost_program_options-${BOOST_VERSION}")
set(boost_random_DIR "${Boost_LIB_DIR}/cmake/boost_random-${BOOST_VERSION}")
set(boost_regex_DIR "${Boost_LIB_DIR}/cmake/boost_regex-${BOOST_VERSION}")
set(boost_system_DIR "${Boost_LIB_DIR}/cmake/boost_system-${BOOST_VERSION}")
set(boost_thread_DIR "${Boost_LIB_DIR}/cmake/boost_thread-${BOOST_VERSION}")
set(boost_context_DIR "${Boost_LIB_DIR}/cmake/boost_context-${BOOST_VERSION}")
set(boost_coroutine_DIR "${Boost_LIB_DIR}/cmake/boost_coroutine-${BOOST_VERSION}")
set(boost_unit_test_framework_DIR "${Boost_LIB_DIR}/cmake/boost_unit_test_framework-${BOOST_VERSION}")
set(Boost_USE_MULTITHREADED ON)
set(Boost_USE_STATIC_LIBS ON)
set(Boost_NO_SYSTEM_PATHS ON)
option(Boost_USE_STATIC_RUNTIME "Use static runtimes" ON)
set(_BOOST_CACHE_ARGS
        -DBOOST_ROOT:PATH=${_BOOST_ROOT}
        -DBoost_DIR:PATH=${Boost_DIR}/Boost-${BOOST_VERSION}
        -DBoost_INCLUDE_DIR:PATH=${Boost_INCLUDE_DIR}
        -Dboost_headers_DIR:PATH=${Boost_DIR}/boost_headers-${BOOST_VERSION}
        -Dboost_date_time_DIR:PATH=${Boost_DIR}/boost_date_time-${BOOST_VERSION}
        -Dboost_filesystem_DIR:PATH=${Boost_DIR}/boost_filesystem-${BOOST_VERSION}
        -Dboost_program_options_DIR:PATH=${Boost_DIR}/boost_program_options-${BOOST_VERSION}
        -Dboost_random_DIR:PATH=${Boost_DIR}/boost_random-${BOOST_VERSION}
        -Dboost_regex_DIR:PATH=${Boost_DIR}/boost_regex-${BOOST_VERSION}
        -Dboost_system_DIR:PATH=${Boost_DIR}/boost_system-${BOOST_VERSION}
        -Dboost_context_DIR:PATH=${Boost_DIR}/boost_context-${BOOST_VERSION}
        -Dboost_coroutine_DIR:PATH=${Boost_DIR}/boost_coroutine-${BOOST_VERSION}
        -Dboost_thread_DIR:PATH=${Boost_DIR}/boost_thread-${BOOST_VERSION}
        -Dboost_log_DIR:PATH=${Boost_DIR}/boost_log-${BOOST_VERSION}
        -Dboost_log_setup_DIR:PATH=${Boost_DIR}/boost_log_setup-${BOOST_VERSION}
        -Dboost_unit_test_framework_DIR:PATH=${Boost_DIR}/boost_unit_test_framework-${BOOST_VERSION}
        -Dboost_json_DIR:PATH=${Boost_DIR}/boost_json-${BOOST_VERSION}
        -DBoost_USE_STATIC_RUNTIME:BOOL=ON
        -DBoost_NO_SYSTEM_PATHS:BOOL=ON
        -DBoost_USE_MULTITHREADED:BOOL=ON
        -DBoost_USE_STATIC_LIBS:BOOL=ON
        -DBoost_USE_STATIC_RUNTIME:BOOL=ON
)

option (SGNS_STACKTRACE_BACKTRACE "Use BOOST_STACKTRACE_USE_BACKTRACE in stacktraces, for POSIX" OFF)
if (SGNS_STACKTRACE_BACKTRACE)
	add_definitions(-DSGNS_STACKTRACE_BACKTRACE=1)
	if (BACKTRACE_INCLUDE)
		add_definitions(-DBOOST_STACKTRACE_BACKTRACE_INCLUDE_FILE=${BACKTRACE_INCLUDE})
	endif()
endif ()

# header only libraries must not be added here
find_package(Boost REQUIRED COMPONENTS date_time filesystem random regex system thread log log_setup program_options)
include_directories(${Boost_INCLUDE_DIRS})

# secp256k1
set(libsecp256k1_DIR "${_THIRDPARTY_BUILD_DIR}/libsecp256k1/lib/cmake/libsecp256k1")
find_package(libsecp256k1 CONFIG REQUIRED)

# xxHash
set(xxHash_DIR "${_THIRDPARTY_BUILD_DIR}/xxhash/lib/cmake/xxHash")
find_package(xxHash CONFIG REQUIRED)

# libssh2
set(Libssh2_DIR "${_THIRDPARTY_BUILD_DIR}/libssh2/lib/cmake/libssh2")
find_package(Libssh2 CONFIG REQUIRED)

# AsyncIOManager
set(AsyncIOManager_INCLUDE_DIR "${_THIRDPARTY_BUILD_DIR}/AsyncIOManager/include")
set(AsyncIOManager_DIR "${_THIRDPARTY_BUILD_DIR}/AsyncIOManager/lib/cmake/AsyncIOManager")
find_package(AsyncIOManager CONFIG REQUIRED)

# --------------------------------------------------------
# Set config of crypto3
add_library(crypto3::algebra INTERFACE IMPORTED)
add_library(crypto3::block INTERFACE IMPORTED)
add_library(crypto3::blueprint INTERFACE IMPORTED)
add_library(crypto3::codec INTERFACE IMPORTED)
add_library(crypto3::math INTERFACE IMPORTED)
add_library(crypto3::multiprecision INTERFACE IMPORTED)
add_library(crypto3::pkpad INTERFACE IMPORTED)
add_library(crypto3::pubkey INTERFACE IMPORTED)
add_library(crypto3::random INTERFACE IMPORTED)
add_library(crypto3::zk INTERFACE IMPORTED)
add_library(marshalling::core INTERFACE IMPORTED)
add_library(marshalling::crypto3_algebra INTERFACE IMPORTED)
add_library(marshalling::crypto3_multiprecision INTERFACE IMPORTED)
add_library(marshalling::crypto3_zk INTERFACE IMPORTED)

set_target_properties(crypto3::algebra PROPERTIES
        INTERFACE_INCLUDE_DIRECTORIES "${ZKLLVM_BUILD_DIR}/zkLLVM/include"
)
set_target_properties(crypto3::block PROPERTIES
        INTERFACE_INCLUDE_DIRECTORIES "${ZKLLVM_BUILD_DIR}/zkLLVM/include"
)
set_target_properties(crypto3::blueprint PROPERTIES
        INTERFACE_INCLUDE_DIRECTORIES "${ZKLLVM_BUILD_DIR}/zkLLVM/include"
)
set_target_properties(crypto3::codec PROPERTIES
        INTERFACE_INCLUDE_DIRECTORIES "${ZKLLVM_BUILD_DIR}/zkLLVM/include"
)
set_target_properties(crypto3::math PROPERTIES
        INTERFACE_INCLUDE_DIRECTORIES "${ZKLLVM_BUILD_DIR}/zkLLVM/include"
)
set_target_properties(crypto3::multiprecision PROPERTIES
        INTERFACE_INCLUDE_DIRECTORIES "${ZKLLVM_BUILD_DIR}/zkLLVM/include"
)
set_target_properties(crypto3::pkpad PROPERTIES
        INTERFACE_INCLUDE_DIRECTORIES "${ZKLLVM_BUILD_DIR}/zkLLVM/include"
)
set_target_properties(crypto3::pubkey PROPERTIES
        INTERFACE_INCLUDE_DIRECTORIES "${ZKLLVM_BUILD_DIR}/zkLLVM/include"
)
set_target_properties(crypto3::random PROPERTIES
        INTERFACE_INCLUDE_DIRECTORIES "${ZKLLVM_BUILD_DIR}/zkLLVM/include"
)
set_target_properties(crypto3::zk PROPERTIES
        INTERFACE_INCLUDE_DIRECTORIES "${ZKLLVM_BUILD_DIR}/zkLLVM/include"
)
set_target_properties(marshalling::core PROPERTIES
        INTERFACE_INCLUDE_DIRECTORIES "${ZKLLVM_BUILD_DIR}/zkLLVM/include"
)
set_target_properties(marshalling::crypto3_algebra PROPERTIES
        INTERFACE_INCLUDE_DIRECTORIES "${ZKLLVM_BUILD_DIR}/zkLLVM/include"
)
set_target_properties(marshalling::crypto3_multiprecision PROPERTIES
        INTERFACE_INCLUDE_DIRECTORIES "${ZKLLVM_BUILD_DIR}/zkLLVM/include"
)
set_target_properties(marshalling::crypto3_zk PROPERTIES
        INTERFACE_INCLUDE_DIRECTORIES "${ZKLLVM_BUILD_DIR}/zkLLVM/include"
)

# zkLLVM
set(zkLLVM_INCLUDE_DIR "${ZKLLVM_BUILD_DIR}/zkLLVM/include")
include_directories(${zkLLVM_INCLUDE_DIR})


# circifier
set(LLVM_DIR "${ZKLLVM_BUILD_DIR}/zkLLVM/lib/cmake/llvm")
find_package(LLVM CONFIG REQUIRED)


# gnus_upnp
set(gnus_upnp_DIR "${_THIRDPARTY_BUILD_DIR}/gnus_upnp/lib/cmake/gnus_upnp")
find_package(gnus_upnp CONFIG REQUIRED)

#json.hpp
set(nlohmann_json_DIR "${_THIRDPARTY_BUILD_DIR}/json/share/cmake/nlohmann_json")
find_package(nlohmann_json CONFIG REQUIRED)

# wallet-core
set(TrustWalletCore_LIBRARY_DIR "${_THIRDPARTY_BUILD_DIR}/wallet-core/lib")
set(TrustWalletCore_INCLUDE_DIR "${_THIRDPARTY_BUILD_DIR}/wallet-core/include")

find_library(TrezorCrypto_PATH TrezorCrypto PATHS ${TrustWalletCore_LIBRARY_DIR} REQUIRED)
find_library(wallet_core_rs_PATH wallet_core_rs PATHS ${TrustWalletCore_LIBRARY_DIR} REQUIRED)
find_library(TrustWalletCore_PATH TrustWalletCore PATHS ${TrustWalletCore_LIBRARY_DIR} REQUIRED)

add_library(TrezorCrypto STATIC IMPORTED)
add_library(wallet_core_rs STATIC IMPORTED)
add_library(TrustWalletCore STATIC IMPORTED)

set_target_properties(TrezorCrypto PROPERTIES IMPORTED_LOCATION "${TrezorCrypto_PATH}")
set_target_properties(wallet_core_rs PROPERTIES IMPORTED_LOCATION "${wallet_core_rs_PATH}")
set_target_properties(TrustWalletCore PROPERTIES IMPORTED_LOCATION "${TrustWalletCore_PATH}")

target_include_directories(TrustWalletCore INTERFACE "${TrustWalletCore_INCLUDE_DIR}")

if (APPLE)
    find_library(CORE_FOUNDATION CoreFoundation)
    find_library(SECURITY_FRAMEWORK Security)
endif()

if(${IOS})
    target_link_libraries(TrustWalletCore INTERFACE ${SECURITY_FRAMEWORK})
endif()
# --------------------------------------------------------
include_directories(
  ${PROJECT_ROOT}/include
)

ADD_DEFINITIONS(-D_HAS_AUTO_PTR_ETC=1)

print("CMAKE_HOST_SYSTEM_NAME: ${CMAKE_HOST_SYSTEM_NAME}")
print("CMAKE_SYSTEM_NAME: ${CMAKE_SYSTEM_NAME}")
print("CMAKE_CXX_STANDARD: ${CMAKE_CXX_STANDARD}")
print("CMAKE_CXX_STANDARD_REQUIRED: ${CMAKE_CXX_STANDARD_REQUIRED}")
print("C flags: ${CMAKE_C_FLAGS}")
print("CXX flags: ${CMAKE_CXX_FLAGS}")
print("C Debug flags: ${CMAKE_C_FLAGS_DEBUG}")
print("CXX Debug flags: ${CMAKE_CXX_FLAGS_DEBUG}")
print("C Release flags: ${CMAKE_C_FLAGS_RELEASE}")
print("CXX Release flags: ${CMAKE_CXX_FLAGS_RELEASE}")

# --------------------------------------------------------
link_directories(
  ${Boost_LIB_DIR}
  ${ipfs-lite-cpp_LIB_DIR}
)

# Add root directory
add_subdirectory(${PROJECT_ROOT} ${CMAKE_BINARY_DIR}/src)

# Add test directory (if testing enabled)
if(BUILD_TESTING)
  enable_testing()
  if(IS_DIRECTORY "${PROJECT_ROOT}/test")
    add_subdirectory(${PROJECT_ROOT}/test ${CMAKE_BINARY_DIR}/test)
  endif()
endif()

# Add examples directory (if building examples)
if(BUILD_EXAMPLES)
    if(IS_DIRECTORY "${PROJECT_ROOT}/examples")
      add_subdirectory(${PROJECT_ROOT}/examples ${CMAKE_BINARY_DIR}/examples)
    endif()
endif()

install(
        EXPORT ${PROJECT_NAME}Targets
        DESTINATION ${CMAKE_INSTALL_LIBDIR}/cmake/${PROJECT_NAME}
        NAMESPACE ${PROJECT_NAME}::
)

# generate the config file that is includes the exports
configure_package_config_file(${PROJECT_ROOT}/cmake/config.cmake.in
        "${CMAKE_CURRENT_BINARY_DIR}/${PROJECT_NAME}Config.cmake"
        INSTALL_DESTINATION ${CMAKE_INSTALL_LIBDIR}/cmake/${PROJECT_NAME}
        NO_SET_AND_CHECK_MACRO
        NO_CHECK_REQUIRED_COMPONENTS_MACRO
)

# generate the version file for the config file
write_basic_package_version_file(
        "${CMAKE_CURRENT_BINARY_DIR}/${PROJECT_NAME}ConfigVersion.cmake"
        VERSION "${CPACK_PACKAGE_VERSION_MAJOR}.${CPACK_PACKAGE_VERSION_MINOR}.${CPACK_PACKAGE_VERSION_PATCH}"
        COMPATIBILITY AnyNewerVersion
)

# install the configuration file
install(FILES
        ${CMAKE_CURRENT_BINARY_DIR}/${PROJECT_NAME}Config.cmake
        DESTINATION ${CMAKE_INSTALL_LIBDIR}/cmake/${PROJECT_NAME}
)

install(FILES
        ${CMAKE_CURRENT_BINARY_DIR}/${PROJECT_NAME}ConfigVersion.cmake
        DESTINATION ${CMAKE_INSTALL_LIBDIR}/cmake/${PROJECT_NAME}
)

