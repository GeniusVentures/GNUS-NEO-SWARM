add_library(neoswarm_core STATIC
    engine/mnn_inference_engine.cpp
    sgprocessing/sg_processing_bridge.cpp
    sgprocessing/tensor_interpreter.cpp
)

target_include_directories(neoswarm_core PUBLIC
    $<BUILD_INTERFACE:${PROJECT_ROOT}/src>
    $<INSTALL_INTERFACE:include>
    "${THIRDPARTY_BUILD_DIR}/boost/build/include"
    "${THIRDPARTY_BUILD_DIR}/json/include"
)

# SuperGenius account headers (TokenID.hpp — via network/sg_client/super_genius_client.hpp)
if(TARGET sgns::GeniusSDK_shared OR TARGET sgns::GeniusSDK)
    target_include_directories(neoswarm_core PUBLIC
        "${SUPERGENIUS_BUILD_DIR}/SuperGenius/include"
    )
endif()

target_link_libraries(neoswarm_core PUBLIC neoswarm_common)

# Boost (needed by SGProcessingManager generated headers and ASIO)
find_library(BOOST_SYSTEM_LIB boost_system
    PATHS "${THIRDPARTY_BUILD_DIR}/boost/build/lib" NO_DEFAULT_PATH)
if(BOOST_SYSTEM_LIB)
    target_link_libraries(neoswarm_core PUBLIC "${BOOST_SYSTEM_LIB}")
endif()

# ---------------------------------------------------------------------------
# MNN — standard Interpreter API (cross-platform, Vulkan via MoltenVK)
# ---------------------------------------------------------------------------
if(TARGET MNN)
    target_link_libraries(neoswarm_core PUBLIC MNN)
endif()

# MoltenVK — Vulkan-to-Metal translation layer (macOS/iOS only, but still Vulkan API)
set(_MOLTENVK_LIB "${THIRDPARTY_BUILD_DIR}/MoltenVK/build/lib/MoltenVK.xcframework/macos-arm64_x86_64/libMoltenVK.a")
if(EXISTS "${_MOLTENVK_LIB}")
    target_link_libraries(neoswarm_core PUBLIC
        "${_MOLTENVK_LIB}"
        "-framework Metal"
        "-framework Foundation"
        "-framework QuartzCore"
        "-framework IOSurface"
        "-framework CoreGraphics"
        "-framework IOKit"
        "-framework AppKit"
        "-framework CoreFoundation"
    )
    message(STATUS "Linked MoltenVK: ${_MOLTENVK_LIB}")
endif()

# ---------------------------------------------------------------------------
# SGProcessingManager integration (pre-built from SuperGenius)
# ---------------------------------------------------------------------------
# Resolution order (union of the app-restructure and phase-04 strategies):
#   1. GeniusNetwork checkout (GENIUSNETWORK_SUPERGENIUS_DIR) — dev layout,
#      libs from that checkout's own install tree.
#   2. SuperGenius sibling source checkout (${PROJECT_ROOT}/../SuperGenius)
#      with thirdparty-built libs.
#   3. SuperGenius prebuilt release (CI) — same subpaths one level under
#      ${SUPERGENIUS_BUILD_DIR}/SuperGenius.
set(GENIUSNETWORK_SUPERGENIUS_DIR "${PROJECT_ROOT}/../../GeniusNetwork/SuperGenius"
    CACHE PATH "Path to GeniusNetwork's SuperGenius checkout (dev_childwallet)")
cmake_path(SET GENIUSNETWORK_SUPERGENIUS_DIR NORMALIZE "${GENIUSNETWORK_SUPERGENIUS_DIR}")

set(_SGPROC_INCLUDE "${GENIUSNETWORK_SUPERGENIUS_DIR}/SGProcessingManager/include")
set(_SGPROC_GEN_INCLUDE "${GENIUSNETWORK_SUPERGENIUS_DIR}/SGProcessingManager/generated")
set(_SGPROC_LIB_DIR "${GENIUSNETWORK_SUPERGENIUS_DIR}/build/${BUILD_PLATFORM_NAME}/${CMAKE_BUILD_TYPE}${ABI_SUBFOLDER_NAME}/SuperGenius/lib/SGProcessingManager")

if(NOT EXISTS "${_SGPROC_INCLUDE}")
    # SuperGenius sibling source checkout (standalone dev layout)
    set(_SGPROC_INCLUDE "${PROJECT_ROOT}/../SuperGenius/SGProcessingManager/include")
    set(_SGPROC_GEN_INCLUDE "${PROJECT_ROOT}/../SuperGenius/SGProcessingManager/generated")
    set(_SGPROC_LIB_DIR "${THIRDPARTY_BUILD_DIR}/SGProcessingManager/lib")
endif()

# CI consumes the SuperGenius prebuilt release instead of a sibling source
# checkout. The release install tree keeps the same subpaths one level under
# ${SUPERGENIUS_BUILD_DIR}/SuperGenius (include/SGProcessingManager for the
# headers, lib/SGProcessingManager for the static libs), so fall back to
# it when the source-layout paths above are absent.
if(NOT EXISTS "${_SGPROC_INCLUDE}"
        AND EXISTS "${SUPERGENIUS_BUILD_DIR}/SuperGenius/include/SGProcessingManager")
    set(_SGPROC_INCLUDE "${SUPERGENIUS_BUILD_DIR}/SuperGenius/include/SGProcessingManager")
    set(_SGPROC_GEN_INCLUDE
        "${SUPERGENIUS_BUILD_DIR}/SuperGenius/include/SGProcessingManager/generated")
    set(_SGPROC_LIB_DIR "${SUPERGENIUS_BUILD_DIR}/SuperGenius/lib/SGProcessingManager")
endif()

find_library(_SGPROC_PROCESSING_BASE ProcessingBase PATHS "${_SGPROC_LIB_DIR}" NO_DEFAULT_PATH)
find_library(_SGPROC_PROCESSORS SGProcessors PATHS "${_SGPROC_LIB_DIR}" NO_DEFAULT_PATH)
find_library(_SGPROC_DATASPLITTER DataSplitter PATHS "${_SGPROC_LIB_DIR}" NO_DEFAULT_PATH)
find_library(_SGPROC_LOGGER sgprocmanagerlogger PATHS "${_SGPROC_LIB_DIR}" NO_DEFAULT_PATH)
find_library(_SGPROC_TYPES sgprocmanagertypes PATHS "${_SGPROC_LIB_DIR}" NO_DEFAULT_PATH)
find_library(_SGPROC_SHA sgprocmanagersha PATHS "${_SGPROC_LIB_DIR}" NO_DEFAULT_PATH)
find_library(_SGPROC_ARTIFACTS SGArtifacts PATHS "${_SGPROC_LIB_DIR}" NO_DEFAULT_PATH)
find_library(_SGPROC_CAPABILITY SGCapability PATHS "${_SGPROC_LIB_DIR}" NO_DEFAULT_PATH)
find_library(_SGPROC_SHADERCOMPILER SGShaderCompiler PATHS "${_SGPROC_LIB_DIR}" NO_DEFAULT_PATH)
find_library(_SGPROC_CAPTURE sgproccapture PATHS "${_SGPROC_LIB_DIR}" NO_DEFAULT_PATH)
find_library(_SGPROC_DIFF sgprocmanagerdiff PATHS "${_SGPROC_LIB_DIR}" NO_DEFAULT_PATH)
find_library(_SGPROC_QUANT sgprocmanagerquant PATHS "${_SGPROC_LIB_DIR}" NO_DEFAULT_PATH)

# Linux single-provider rule: the shared GeniusSDK exports the
# SGProcessingManager stack, so link the SDK instead of embedding these
# archives (see GCS cmake/CommonBuildParameters.cmake). The variables stay
# truthy, keeping the real-mode branch below intact.
if(GCS_SDK_SINGLE_PROVIDER)
    get_target_property(_SGPROC_SDK_LIB sgns::GeniusSDK_shared IMPORTED_LOCATION)
    if(NOT _SGPROC_SDK_LIB)
        get_target_property(_SGPROC_SDK_LIB sgns::GeniusSDK_shared IMPORTED_LOCATION_DEBUG)
    endif()
    set(_SGPROC_PROCESSING_BASE "${_SGPROC_SDK_LIB}")
    set(_SGPROC_PROCESSORS "${_SGPROC_SDK_LIB}")
    set(_SGPROC_DATASPLITTER "${_SGPROC_SDK_LIB}")
    set(_SGPROC_LOGGER "${_SGPROC_SDK_LIB}")
    set(_SGPROC_TYPES "${_SGPROC_SDK_LIB}")
    set(_SGPROC_SHA "${_SGPROC_SDK_LIB}")
endif()
if(_SGPROC_PROCESSING_BASE AND EXISTS "${_SGPROC_INCLUDE}" AND EXISTS "${_SGPROC_GEN_INCLUDE}")
    target_include_directories(neoswarm_core PUBLIC
        "${_SGPROC_INCLUDE}"
        "${_SGPROC_GEN_INCLUDE}"
    )
    target_link_libraries(neoswarm_core PUBLIC
        "${_SGPROC_PROCESSING_BASE}"
        "${_SGPROC_PROCESSORS}"
        "${_SGPROC_DATASPLITTER}"
        "${_SGPROC_LOGGER}"
        "${_SGPROC_TYPES}"
        "${_SGPROC_SHA}"
        "${_SGPROC_ARTIFACTS}"
        "${_SGPROC_CAPABILITY}"
        "${_SGPROC_SHADERCOMPILER}"
        "${_SGPROC_CAPTURE}"
        "${_SGPROC_DIFF}"
        "${_SGPROC_QUANT}"
    )
    # AsyncIOManager (transitive dependency of ProcessingBase)
    find_library(_ASYNCIO_LIB AsyncIOManager
        PATHS "${THIRDPARTY_BUILD_DIR}/AsyncIOManager/lib" NO_DEFAULT_PATH)
    if(_ASYNCIO_LIB)
        target_link_libraries(neoswarm_core PUBLIC "${_ASYNCIO_LIB}")
        target_include_directories(neoswarm_core PUBLIC
            "${THIRDPARTY_BUILD_DIR}/AsyncIOManager/include")
    endif()

    # Transitive dependencies of AsyncIOManager/SGProcessingManager.
    # ipfs-bitswap-cpp, ipfs-lite-cpp, and libp2p are resolved as real imported
    # targets via find_package() in cmake/CommonBuildParameters.cmake — link the
    # top-level targets and let their interfaces pull the rest transitively.
    # Linking the raw *.a globs here instead would duplicate every archive that
    # sgns::genius_node / p2p::* already pull in.
    file(GLOB _IPFS_PUBSUB_LIBS "${THIRDPARTY_BUILD_DIR}/ipfs-pubsub/lib/*.a")
    find_library(_SORALOG_LIB soralog PATHS "${THIRDPARTY_BUILD_DIR}/soralog/lib" NO_DEFAULT_PATH)
    find_library(_CARES_LIB cares PATHS "${THIRDPARTY_BUILD_DIR}/cares/lib" NO_DEFAULT_PATH)
    find_library(_ED25519_LIB ed25519 PATHS "${THIRDPARTY_BUILD_DIR}/ed25519/lib" NO_DEFAULT_PATH)
    find_library(_XXHASH_LIB xxhash PATHS "${THIRDPARTY_BUILD_DIR}/xxhash/lib" NO_DEFAULT_PATH)
    find_library(_TSL_LIB tsl PATHS "${THIRDPARTY_BUILD_DIR}/tsl_hat_trie/lib" NO_DEFAULT_PATH)
    find_library(_SQLITE3_LIB sqlite3 PATHS "${THIRDPARTY_BUILD_DIR}/sqlite3/lib" NO_DEFAULT_PATH)
    # The shared GeniusSDK provides rocksdb on Linux (single-provider rule,
    # see GCS cmake/CommonBuildParameters.cmake); skip embedding librocksdb.a.
    # find_library caches its result, so clear a stale pre-guard entry too.
    if(NOT GCS_SDK_SINGLE_PROVIDER)
        find_library(_ROCKSDB_LIB rocksdb PATHS "${THIRDPARTY_BUILD_DIR}/rocksdb/lib" NO_DEFAULT_PATH)
    else()
        unset(_ROCKSDB_LIB CACHE)
    endif()
    find_library(_SNAPPY_LIB snappy PATHS "${THIRDPARTY_BUILD_DIR}/snappy/lib" NO_DEFAULT_PATH)

    target_link_libraries(neoswarm_core PUBLIC
        ipfs-bitswap-cpp
        ipfs-lite-cpp::ipfs_merkledag_service
        p2p::p2p
        ${_IPFS_PUBSUB_LIBS}
    )
    foreach(_dep_lib _SORALOG_LIB _CARES_LIB _ED25519_LIB _XXHASH_LIB _TSL_LIB _SQLITE3_LIB _ROCKSDB_LIB _SNAPPY_LIB)
        if(${_dep_lib})
            target_link_libraries(neoswarm_core PUBLIC "${${_dep_lib}}")
        endif()
    endforeach()

    # Static libs in the SGProcessing chain share protobuf symbols.
    # Allow the linker to pick one copy without erroring on duplicates.
    if(APPLE)
        target_link_options(neoswarm_core PUBLIC "LINKER:-ld_classic")
    endif()
    message(STATUS "SGProcessingManager: linked (${_SGPROC_LIB_DIR})")
else()
    # Headers only — stub mode
    if(EXISTS "${_SGPROC_INCLUDE}" AND EXISTS "${_SGPROC_GEN_INCLUDE}")
        target_include_directories(neoswarm_core PUBLIC
            "${_SGPROC_INCLUDE}"
            "${_SGPROC_GEN_INCLUDE}"
        )
        message(STATUS "SGProcessingManager headers found (stub mode)")
    else()
        message(STATUS "SGProcessingManager not found — stub mode")
    endif()
endif()
