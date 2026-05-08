add_library(genius_core STATIC
    fp4/FP4Codec.cpp
    engine/MNNInferenceEngine.cpp
    tokenizer/SentencePieceTokenizer.cpp
    sgprocessing/SGProcessingBridge.cpp
    sgprocessing/TensorInterpreter.cpp
)

target_include_directories(genius_core PUBLIC
    $<BUILD_INTERFACE:${CMAKE_SOURCE_DIR}/src>
    $<INSTALL_INTERFACE:include>
    "${THIRDPARTY_BUILD_DIR}/boost/build/include"
    "${THIRDPARTY_BUILD_DIR}/json/include"
)

target_link_libraries(genius_core PUBLIC genius_common)

# Boost (needed by SGProcessingManager generated headers and ASIO)
find_library(BOOST_SYSTEM_LIB boost_system
    PATHS "${THIRDPARTY_BUILD_DIR}/boost/build/lib" NO_DEFAULT_PATH)
if(BOOST_SYSTEM_LIB)
    target_link_libraries(genius_core PUBLIC "${BOOST_SYSTEM_LIB}")
endif()

# MNN integration
if(TARGET MNN)
    target_link_libraries(genius_core PUBLIC MNN)
    target_compile_definitions(genius_core PUBLIC GENIUS_HAS_MNN)
endif()

# SentencePiece integration
if(TARGET sentencepiece)
    target_link_libraries(genius_core PUBLIC sentencepiece)
    target_compile_definitions(genius_core PUBLIC GENIUS_HAS_SENTENCEPIECE)
endif()

# Vulkan / MoltenVK (GPU acceleration)
find_package(Vulkan QUIET)
if(Vulkan_FOUND)
    target_link_libraries(genius_core PUBLIC Vulkan::Vulkan)
    target_compile_definitions(genius_core PUBLIC GENIUS_HAS_VULKAN)
endif()

# MoltenVK — link when MNN is built with Vulkan backend
set(_MOLTENVK_LIB "${THIRDPARTY_BUILD_DIR}/MoltenVK/build/lib/MoltenVK.xcframework/macos-arm64_x86_64/libMoltenVK.a")
if(EXISTS "${_MOLTENVK_LIB}")
    target_link_libraries(genius_core PUBLIC
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

# SGProcessingManager integration
set(_SGPROC_INCLUDE "${CMAKE_SOURCE_DIR}/../SuperGenius/SGProcessingManager/include")
set(_SGPROC_GEN_INCLUDE "${CMAKE_SOURCE_DIR}/../SuperGenius/SGProcessingManager/generated")
set(_SGPROC_LIB_DIR "${THIRDPARTY_BUILD_DIR}/SGProcessingManager/lib")

find_library(SGPROCESSING_LIB SGProcessingManager
    PATHS "${_SGPROC_LIB_DIR}"
    NO_DEFAULT_PATH)

if(SGPROCESSING_LIB AND EXISTS "${_SGPROC_INCLUDE}" AND EXISTS "${_SGPROC_GEN_INCLUDE}")
    add_library(SGProcessingManager UNKNOWN IMPORTED)
    set_target_properties(SGProcessingManager PROPERTIES
        IMPORTED_LOCATION "${SGPROCESSING_LIB}"
        INTERFACE_INCLUDE_DIRECTORIES "${_SGPROC_INCLUDE};${_SGPROC_GEN_INCLUDE}"
    )
    target_link_libraries(genius_core PUBLIC SGProcessingManager)
    target_compile_definitions(genius_core PUBLIC GENIUS_HAS_SGPROCESSING)
    message(STATUS "Found SGProcessingManager: ${SGPROCESSING_LIB}")
else()
    # Headers available even without a pre-built lib (build from source)
    if(EXISTS "${_SGPROC_INCLUDE}" AND EXISTS "${_SGPROC_GEN_INCLUDE}")
        target_include_directories(genius_core PUBLIC
            "${_SGPROC_INCLUDE}"
            "${_SGPROC_GEN_INCLUDE}"
        )
        message(STATUS "SGProcessingManager headers found (no pre-built lib — stub mode)")
    else()
        message(STATUS "SGProcessingManager not found — SGProcessingBridge runs in stub mode")
    endif()
endif()
