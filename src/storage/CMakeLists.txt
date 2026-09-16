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

# GeniusSDK — hard required: GcsGlobalDb::Initialize() calls GeniusSDKGetPubSub() (D-16a).
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

# NOTE: gcs_global_db.cpp includes only the plain-C GeniusSDK.h (never GeniusSDK.hpp,
# which never existed — see resolved debug session neoswarm-geniussdk-missing). GeniusSDK.h
# has zero C++ header dependencies (stdint.h/stdbool.h only) and is already available via
# the linked GeniusSDK target's own INTERFACE_INCLUDE_DIRECTORIES (both sgns::GeniusSDK and
# sgns::GeniusSDK_shared export the same ${GENIUS_SDK_BUILD_DIR}/GeniusSDK/include, confirmed
# installed), so no additional include directories are needed for it — this also means the
# previously-required WalletCore/zkLLVM/evmrelay/MNN transitive-include workarounds (only
# needed for GeniusSDK.hpp's assumed account/GeniusNode.hpp chain) are no longer needed and
# have been removed.
