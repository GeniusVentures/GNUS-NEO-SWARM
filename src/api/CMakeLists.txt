add_library(neoswarm_api STATIC
    api_server.cpp
)

target_include_directories(neoswarm_api PUBLIC
    $<BUILD_INTERFACE:${PROJECT_ROOT}/src>
    $<INSTALL_INTERFACE:include>
)

target_link_libraries(neoswarm_api PUBLIC
    neoswarm_common
    neoswarm_core
    neoswarm_specialists
    neoswarm_router
    neoswarm_reputation
    neoswarm_network
    neoswarm_knowledge
    neoswarm_security
)

# gRPC (optional)
if(TARGET gRPC::grpc++)
    target_link_libraries(neoswarm_api PUBLIC gRPC::grpc++)
    target_compile_definitions(neoswarm_api PUBLIC GENIUS_HAS_GRPC)
endif()

# UUID (POSIX — Linux only, macOS uses its own API)
if(UNIX AND NOT APPLE)
    target_link_libraries(neoswarm_api PUBLIC uuid)
endif()
