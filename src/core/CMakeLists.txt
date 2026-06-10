add_library(neoswarm_core STATIC
    fp4/fp4_codec.cpp
    engine/mnn_inference_engine.cpp
    tokenizer/sentence_piece_tokenizer.cpp
    sgprocessing/sg_processing_bridge.cpp
    sgprocessing/tensor_interpreter.cpp
)

target_include_directories(neoswarm_core PUBLIC
    $<BUILD_INTERFACE:${PROJECT_ROOT}/src>
    $<INSTALL_INTERFACE:include>
    "${_THIRDPARTY_BUILD_DIR}/boost/build/include"
    "${_THIRDPARTY_BUILD_DIR}/json/include"
)

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
    target_compile_definitions(neoswarm_core PUBLIC GENIUS_HAS_MNN)
endif()

# Check early if SGProcessingManager will be linked (used to skip SentencePiece)
set(_SGPROC_LIB_DIR "${_THIRDPARTY_BUILD_DIR}/SGProcessingManager/lib")
find_library(_SGPROC_PROCESSING_BASE ProcessingBase PATHS "${_SGPROC_LIB_DIR}" NO_DEFAULT_PATH)

# ---------------------------------------------------------------------------
# SentencePiece tokenizer (+ Abseil transitive deps)
# Skip when SGProcessingManager is linked (avoids protobuf duplicate symbols)
# When skipped, the tokenizer falls back to whitespace mode — MNN's built-in
# tokenizer (tokenizer.mtok) is used in the LLM path instead.
# ---------------------------------------------------------------------------
if(NOT _SGPROC_PROCESSING_BASE AND TARGET sentencepiece)
    target_link_libraries(neoswarm_core PUBLIC sentencepiece)
    target_compile_definitions(neoswarm_core PUBLIC GENIUS_HAS_SENTENCEPIECE)

    # Abseil static libs bundled in the SentencePiece build tree
    set(_SPM_BUILD_DIR "${_THIRDPARTY_BUILD_DIR}/../../../sentencepiece/build")
    file(GLOB_RECURSE _ABSL_LIBS
        "${_SPM_BUILD_DIR}/third_party/abseil-cpp/**/*.a"
    )
    if(_ABSL_LIBS)
        target_link_libraries(neoswarm_core PUBLIC ${_ABSL_LIBS})
    endif()
elseif(_SGPROC_PROCESSING_BASE AND TARGET sentencepiece)
    message(STATUS "SentencePiece skipped — protobuf conflict with SGProcessingManager. Using MNN built-in tokenizer.")
endif()

# ---------------------------------------------------------------------------
# Vulkan / MoltenVK (GPU acceleration — cross-platform)
# ---------------------------------------------------------------------------
find_package(Vulkan QUIET)
if(Vulkan_FOUND)
    target_link_libraries(neoswarm_core PUBLIC Vulkan::Vulkan)
    target_compile_definitions(neoswarm_core PUBLIC GENIUS_HAS_VULKAN)
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
# SGProcessingManager headers from SuperGenius sibling repo
set(_SGPROC_INCLUDE "${PROJECT_ROOT}/../SuperGenius/SGProcessingManager/include")
set(_SGPROC_GEN_INCLUDE "${PROJECT_ROOT}/../SuperGenius/SGProcessingManager/generated")
set(_SGPROC_LIB_DIR "${_THIRDPARTY_BUILD_DIR}/SGProcessingManager/lib")

find_library(_SGPROC_PROCESSING_BASE ProcessingBase PATHS "${_SGPROC_LIB_DIR}" NO_DEFAULT_PATH)
find_library(_SGPROC_PROCESSORS SGProcessors PATHS "${_SGPROC_LIB_DIR}" NO_DEFAULT_PATH)
find_library(_SGPROC_DATASPLITTER DataSplitter PATHS "${_SGPROC_LIB_DIR}" NO_DEFAULT_PATH)
find_library(_SGPROC_LOGGER sgprocmanagerlogger PATHS "${_SGPROC_LIB_DIR}" NO_DEFAULT_PATH)
find_library(_SGPROC_TYPES sgprocmanagertypes PATHS "${_SGPROC_LIB_DIR}" NO_DEFAULT_PATH)
find_library(_SGPROC_SHA sgprocmanagersha PATHS "${_SGPROC_LIB_DIR}" NO_DEFAULT_PATH)

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
    )
    # AsyncIOManager (transitive dependency of ProcessingBase)
    find_library(_ASYNCIO_LIB AsyncIOManager
        PATHS "${_THIRDPARTY_BUILD_DIR}/AsyncIOManager/lib" NO_DEFAULT_PATH)
    if(_ASYNCIO_LIB)
        target_link_libraries(neoswarm_core PUBLIC "${_ASYNCIO_LIB}")
        target_include_directories(neoswarm_core PUBLIC
            "${_THIRDPARTY_BUILD_DIR}/AsyncIOManager/include")
    endif()

    # Transitive dependencies of AsyncIOManager/SGProcessingManager
    # (ipfs-bitswap, ipfs-lite, libp2p, etc.)
    file(GLOB _IPFS_BITSWAP_LIBS "${_THIRDPARTY_BUILD_DIR}/ipfs-bitswap-cpp/lib/*.a")
    file(GLOB _IPFS_LITE_LIBS "${_THIRDPARTY_BUILD_DIR}/ipfs-lite-cpp/lib/*.a")
    file(GLOB _IPFS_PUBSUB_LIBS "${_THIRDPARTY_BUILD_DIR}/ipfs-pubsub/lib/*.a")
    file(GLOB _LIBP2P_LIBS "${_THIRDPARTY_BUILD_DIR}/libp2p/lib/*.a")
    find_library(_SORALOG_LIB soralog PATHS "${_THIRDPARTY_BUILD_DIR}/soralog/lib" NO_DEFAULT_PATH)
    find_library(_CARES_LIB cares PATHS "${_THIRDPARTY_BUILD_DIR}/cares/lib" NO_DEFAULT_PATH)
    find_library(_ED25519_LIB ed25519 PATHS "${_THIRDPARTY_BUILD_DIR}/ed25519/lib" NO_DEFAULT_PATH)
    find_library(_XXHASH_LIB xxhash PATHS "${_THIRDPARTY_BUILD_DIR}/xxhash/lib" NO_DEFAULT_PATH)
    find_library(_TSL_LIB tsl PATHS "${_THIRDPARTY_BUILD_DIR}/tsl_hat_trie/lib" NO_DEFAULT_PATH)
    find_library(_SQLITE3_LIB sqlite3 PATHS "${_THIRDPARTY_BUILD_DIR}/sqlite3/lib" NO_DEFAULT_PATH)
    find_library(_ROCKSDB_LIB rocksdb PATHS "${_THIRDPARTY_BUILD_DIR}/rocksdb/lib" NO_DEFAULT_PATH)
    find_library(_SNAPPY_LIB snappy PATHS "${_THIRDPARTY_BUILD_DIR}/snappy/lib" NO_DEFAULT_PATH)

    target_link_libraries(neoswarm_core PUBLIC
        ${_IPFS_BITSWAP_LIBS}
        ${_IPFS_LITE_LIBS}
        ${_IPFS_PUBSUB_LIBS}
        ${_LIBP2P_LIBS}
    )
    foreach(_dep_lib _SORALOG_LIB _CARES_LIB _ED25519_LIB _XXHASH_LIB _TSL_LIB _SQLITE3_LIB _ROCKSDB_LIB _SNAPPY_LIB)
        if(${_dep_lib})
            target_link_libraries(neoswarm_core PUBLIC "${${_dep_lib}}")
        endif()
    endforeach()

    target_compile_definitions(neoswarm_core PUBLIC GENIUS_HAS_SGPROCESSING)
    set(GENIUS_HAS_SGPROCESSING TRUE)
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
