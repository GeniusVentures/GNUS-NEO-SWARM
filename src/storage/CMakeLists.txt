add_library(neoswarm_storage STATIC
    gcs_global_db.cpp
)

target_include_directories(neoswarm_storage PUBLIC
    $<BUILD_INTERFACE:${PROJECT_ROOT}/src>
    $<INSTALL_INTERFACE:include>
)

target_link_libraries(neoswarm_storage PUBLIC neoswarm_common neoswarm_proto)

# SuperGenius CRDT GlobalDB — hard required (project Conditional Compilation rule:
# missing required libraries fail at configure time, never degrade to a stub).
if(TARGET sgns::crdt_globaldb)
    target_link_libraries(neoswarm_storage PUBLIC sgns::crdt_globaldb)
else()
    message(FATAL_ERROR "sgns::crdt_globaldb target not found — SuperGenius package must be configured before neoswarm_storage")
endif()

# GeniusSDK — hard required: GcsGlobalDb::Initialize() calls GeniusSDKGetNode() (D-16a).
if(TARGET sgns::GeniusSDK_shared)
    target_link_libraries(neoswarm_storage PUBLIC sgns::GeniusSDK_shared)
    message(STATUS "GeniusSDK linked to neoswarm_storage")
elseif(TARGET sgns::GeniusSDK)
    target_link_libraries(neoswarm_storage PUBLIC sgns::GeniusSDK)
    message(STATUS "GeniusSDK (static) linked to neoswarm_storage")
else()
    message(FATAL_ERROR "sgns::GeniusSDK_shared / sgns::GeniusSDK target not found — GeniusSDK package must be configured before neoswarm_storage")
endif()

# SuperGenius account headers (mirrors src/network/CMakeLists.txt)
target_include_directories(neoswarm_storage PUBLIC
    "${SUPERGENIUS_BUILD_DIR}/SuperGenius/include"
)
