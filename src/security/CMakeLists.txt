add_library(genius_security STATIC
    NodeIdentity.cpp
    MessageSigning.cpp
)

target_include_directories(genius_security PUBLIC
    $<BUILD_INTERFACE:${PROJECT_ROOT}/src>
    $<INSTALL_INTERFACE:include>
)

target_link_libraries(genius_security PUBLIC genius_common)

# Fallback: try to find/create secp256k1 target if CommonBuildParameters didn't
if(NOT TARGET secp256k1)
    find_package(libsecp256k1 CONFIG QUIET)
    if(libsecp256k1_FOUND AND TARGET libsecp256k1::secp256k1)
        add_library(secp256k1 ALIAS libsecp256k1::secp256k1)
        message(STATUS "secp256k1 target created from libsecp256k1 (fallback)")
    endif()
endif()

if(TARGET secp256k1)
    target_link_libraries(genius_security PUBLIC secp256k1)
    target_compile_definitions(genius_security PUBLIC GENIUS_HAS_SECP256K1)
endif()

find_package(OpenSSL QUIET)
if(OpenSSL_FOUND)
    target_link_libraries(genius_security PUBLIC OpenSSL::SSL OpenSSL::Crypto)
    target_compile_definitions(genius_security PUBLIC GENIUS_HAS_OPENSSL)
endif()
