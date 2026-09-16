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

# GeniusSDK — hard required: GcsGlobalDb::Initialize() calls GeniusSDKGetNode().
# Static target first (no runtime shared-lib search path); shared is the fallback.
if(TARGET sgns::GeniusSDK)
    target_link_libraries(neoswarm_storage PUBLIC sgns::GeniusSDK)
    message(STATUS "GeniusSDK (static) linked to neoswarm_storage")
elseif(TARGET sgns::GeniusSDK_shared)
    target_link_libraries(neoswarm_storage PUBLIC sgns::GeniusSDK_shared)
    message(STATUS "GeniusSDK (shared) linked to neoswarm_storage")
else()
    message(FATAL_ERROR "sgns::GeniusSDK / sgns::GeniusSDK_shared target not found — GeniusSDK package must be configured before neoswarm_storage")
endif()

# SuperGenius account headers (mirrors src/network/CMakeLists.txt)
target_include_directories(neoswarm_storage PUBLIC
    "${SUPERGENIUS_BUILD_DIR}/SuperGenius/include"
)

# Direct deps of gcs_global_db.cpp not re-exported by sgns::crdt_globaldb's interface.
target_include_directories(neoswarm_storage PUBLIC
    "${THIRDPARTY_BUILD_DIR}/ipfs-pubsub/include"
    "${THIRDPARTY_BUILD_DIR}/ipfs-lite-cpp/include"
    "${THIRDPARTY_BUILD_DIR}/libp2p/include"
    "${THIRDPARTY_BUILD_DIR}/boost/build/include"
)

# GeniusSDK.hpp is not installed by the GeniusSDK build; consume it from the source tree.
target_include_directories(neoswarm_storage PUBLIC
    "${GENIUS_SDK_DIR}/src"
)

# Transitive headers pulled in by GeniusSDK.hpp's account/GeniusNode.hpp chain.
target_include_directories(neoswarm_storage PUBLIC
    "${THIRDPARTY_BUILD_DIR}/wallet-core/include"
    "${SUPERGENIUS_BUILD_DIR}/SuperGenius/include/evmrelay"
    "${MNN_INCLUDE_DIR}"
)
if(DEFINED ZKLLVM_BUILD_DIR AND NOT ZKLLVM_BUILD_DIR STREQUAL "")
    target_include_directories(neoswarm_storage PUBLIC
        "${ZKLLVM_BUILD_DIR}/zkLLVM/include"
    )
endif()
