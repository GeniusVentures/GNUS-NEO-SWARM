# Proto library using add_proto_library from build/cmake/functions.cmake
# Following SuperGenius pattern with relative paths
# Second arg is this repo's src root — proto import paths resolve against it.
# Normalized to an absolute path: protoc matches --proto_path by exact prefix.
get_filename_component(NEOSWARM_SRC_ROOT "${CMAKE_CURRENT_SOURCE_DIR}/.." ABSOLUTE)
add_proto_library(neoswarm_proto
    ${NEOSWARM_SRC_ROOT}
    genius_reputation.proto
    genius_api.proto
    genius_internal.proto
)
