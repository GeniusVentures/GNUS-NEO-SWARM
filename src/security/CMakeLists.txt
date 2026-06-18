add_library(neoswarm_security STATIC
    node_identity.cpp
    message_signing.cpp
)

target_include_directories(neoswarm_security PUBLIC
    $<BUILD_INTERFACE:${PROJECT_ROOT}/src>
    $<INSTALL_INTERFACE:include>
)

target_link_libraries(neoswarm_security PUBLIC neoswarm_common)

# Fallback: try to find/create secp256k1 target if CommonBuildParameters didn't
if(NOT TARGET secp256k1)
    find_package(libsecp256k1 CONFIG QUIET)
    if(libsecp256k1_FOUND AND TARGET libsecp256k1::secp256k1)
        add_library(secp256k1 ALIAS libsecp256k1::secp256k1)
        message(STATUS "secp256k1 target created from libsecp256k1 (fallback)")
    endif()
endif()

if(TARGET secp256k1)
    target_link_libraries(neoswarm_security PUBLIC secp256k1)
endif()

find_package(OpenSSL QUIET)
if(OpenSSL_FOUND)
    target_link_libraries(neoswarm_security PUBLIC OpenSSL::SSL OpenSSL::Crypto)
endif()
