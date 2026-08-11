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

# Headers for direct deps of gcs_global_db.cpp that sgns::crdt_globaldb does not
# re-export via INTERFACE_INCLUDE_DIRECTORIES (its interface carries only the
# SuperGenius install include dir). The ipfs-pubsub imported target is a stub
# (cmake/CommonBuildParameters.cmake), so include its headers directly.
target_include_directories(neoswarm_storage PUBLIC
    "${THIRDPARTY_BUILD_DIR}/ipfs-pubsub/include"
    "${THIRDPARTY_BUILD_DIR}/ipfs-lite-cpp/include"
    "${THIRDPARTY_BUILD_DIR}/libp2p/include"
    "${THIRDPARTY_BUILD_DIR}/boost/build/include"
)

# GeniusSDK.hpp (C++ API exposing GeniusSDKGetNode, added in GeniusSDK d550800) is not
# yet installed into ${GENIUS_SDK_BUILD_DIR}/GeniusSDK/include (the build only exports
# the C header). Consume it directly from the GeniusSDK source tree.
target_include_directories(neoswarm_storage PUBLIC
    "${GENIUS_SDK_DIR}/src"
)

# GeniusSDK.hpp -> account/GeniusNode.hpp -> WalletCore/PrivateKey.h. TrustWalletCore
# is a stub-imported target in cmake/CommonBuildParameters.cmake, so expose its
# headers explicitly here.
target_include_directories(neoswarm_storage PUBLIC
    "${THIRDPARTY_BUILD_DIR}/wallet-core/include"
)

# GeniusNode.hpp transitively pulls ProofSystem/EthereumKeyPairParams.hpp which
# requires crypto3 (zkLLVM). ZKLLVM_BUILD_DIR is set by CommonCompilerOptions.cmake.
if(DEFINED ZKLLVM_BUILD_DIR AND NOT ZKLLVM_BUILD_DIR STREQUAL "")
    target_include_directories(neoswarm_storage PUBLIC
        "${ZKLLVM_BUILD_DIR}/zkLLVM/include"
    )
endif()

# GeniusNode.hpp -> account/BridgeRelayer.hpp -> eth/eth_watch_service.hpp. evmrelay's
# headers live under the SuperGenius install include dir at /evmrelay, not at the top.
target_include_directories(neoswarm_storage PUBLIC
    "${SUPERGENIUS_BUILD_DIR}/SuperGenius/include/evmrelay"
)

# GeniusNode.hpp -> processing_processor_mnn_image.hpp -> MNN/ImageProcess.hpp.
# MNN_INCLUDE_DIR is set in cmake/CommonBuildParameters.cmake.
target_include_directories(neoswarm_storage PUBLIC
    "${MNN_INCLUDE_DIR}"
)
