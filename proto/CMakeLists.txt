# proto/CMakeLists.txt — Protobuf compilation for GNUS-NEO-SWARM

# Generate C++ sources from .proto files
set(PROTO_FILES
    ${CMAKE_CURRENT_SOURCE_DIR}/genius_reputation.proto
    ${CMAKE_CURRENT_SOURCE_DIR}/genius_api.proto
    ${CMAKE_CURRENT_SOURCE_DIR}/genius_internal.proto
)

set(PROTO_GENERATED_DIR "${CMAKE_CURRENT_BINARY_DIR}/generated")
file(MAKE_DIRECTORY ${PROTO_GENERATED_DIR})

set(PROTO_SRCS "")
set(PROTO_HDRS "")

foreach(PROTO_FILE ${PROTO_FILES})
    get_filename_component(PROTO_NAME ${PROTO_FILE} NAME_WE)
    list(APPEND PROTO_SRCS "${PROTO_GENERATED_DIR}/${PROTO_NAME}.pb.cc")
    list(APPEND PROTO_HDRS "${PROTO_GENERATED_DIR}/${PROTO_NAME}.pb.h")
endforeach()

# Custom command to generate protobuf sources
add_custom_command(
    OUTPUT ${PROTO_SRCS} ${PROTO_HDRS}
    COMMAND ${Protobuf_PROTOC_EXECUTABLE}
        --cpp_out=${PROTO_GENERATED_DIR}
        --proto_path=${CMAKE_CURRENT_SOURCE_DIR}
        ${PROTO_FILES}
    DEPENDS ${PROTO_FILES} protobuf::protoc
    COMMENT "Generating protobuf C++ sources"
    VERBATIM
)

# Create a static library with the generated protobuf sources
add_library(neoswarm_proto STATIC ${PROTO_SRCS} ${PROTO_HDRS})

target_include_directories(neoswarm_proto PUBLIC
    $<BUILD_INTERFACE:${PROTO_GENERATED_DIR}>
    $<BUILD_INTERFACE:${Protobuf_INCLUDE_DIR}>
    $<INSTALL_INTERFACE:include/genius/proto>
)

target_link_libraries(neoswarm_proto PUBLIC
    protobuf::libprotobuf
)

# Suppress warnings in generated code
if(MSVC)
    target_compile_options(neoswarm_proto PRIVATE /W0)
else()
    target_compile_options(neoswarm_proto PRIVATE -w)
endif()

message(STATUS "Protobuf generation configured:")
message(STATUS "  - Source dir: ${CMAKE_CURRENT_SOURCE_DIR}")
message(STATUS "  - Output dir: ${PROTO_GENERATED_DIR}")
message(STATUS "  - Protoc: ${Protobuf_PROTOC_EXECUTABLE}")
