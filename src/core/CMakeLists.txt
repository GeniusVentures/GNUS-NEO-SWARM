
add_library(neoswarm_core STATIC
    fp4/fp4_codec.cpp
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

target_link_libraries(neoswarm_core
        PUBLIC
        neoswarm_common
        MNN::MNN
        Vulkan::Vulkan
        ProcessingBase
)
