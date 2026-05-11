add_library(genius_security STATIC
    NodeIdentity.cpp
    MessageSigning.cpp
)

target_include_directories(genius_security PUBLIC
    $<BUILD_INTERFACE:${CMAKE_SOURCE_DIR}/src>
    $<INSTALL_INTERFACE:include>
)

target_link_libraries(genius_security PUBLIC genius_common)

if(TARGET secp256k1)
    target_link_libraries(genius_security PUBLIC secp256k1)
    target_compile_definitions(genius_security PUBLIC GENIUS_HAS_SECP256K1)
endif()

find_package(OpenSSL QUIET)
if(OpenSSL_FOUND)
    target_link_libraries(genius_security PUBLIC OpenSSL::SSL OpenSSL::Crypto)
    target_compile_definitions(genius_security PUBLIC GENIUS_HAS_OPENSSL)
endif()
