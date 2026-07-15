# Proto library using add_proto_library from build/cmake/functions.cmake
# Following SuperGenius pattern with relative paths
add_proto_library(neoswarm_proto
    genius_reputation.proto
    genius_api.proto
    genius_internal.proto
)
