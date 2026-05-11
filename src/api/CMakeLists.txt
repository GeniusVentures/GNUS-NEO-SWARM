add_library(genius_api STATIC
    GeniusAPIServer.cpp
)

target_include_directories(genius_api PUBLIC
    $<BUILD_INTERFACE:${CMAKE_SOURCE_DIR}/src>
    $<INSTALL_INTERFACE:include>
)

target_link_libraries(genius_api PUBLIC
    genius_common
    genius_core
    genius_specialists
    genius_router
    genius_reputation
    genius_network
    genius_knowledge
    genius_security
)

# gRPC (optional)
if(TARGET gRPC::grpc++)
    target_link_libraries(genius_api PUBLIC gRPC::grpc++)
    target_compile_definitions(genius_api PUBLIC GENIUS_HAS_GRPC)
endif()

# UUID (POSIX — Linux only, macOS uses its own API)
if(UNIX AND NOT APPLE)
    target_link_libraries(genius_api PUBLIC uuid)
endif()
