# bench_mnn_llm needs MNN's LLM API, which thirdparty only ships where MNN was
# built with it (e.g. OSX). Skip the benchmark on platforms whose MNN lacks
# llm.hpp instead of failing the whole build on the missing header.
if(EXISTS "${_THIRDPARTY_BUILD_DIR}/MNN/include/MNN/llm/llm.hpp")

add_executable(bench_mnn_llm bench_mnn_llm.cpp)

target_include_directories(bench_mnn_llm PRIVATE
    ${_THIRDPARTY_BUILD_DIR}/MNN/include
)

target_link_libraries(bench_mnn_llm PRIVATE
    MNN
    Threads::Threads
)

if(Vulkan_FOUND)
    target_link_libraries(bench_mnn_llm PRIVATE Vulkan::Vulkan)
endif()

if(TARGET MoltenVK)
    target_link_libraries(bench_mnn_llm PRIVATE MoltenVK)
endif()

if(APPLE)
    target_link_libraries(bench_mnn_llm PRIVATE
        "-framework CoreFoundation"
        "-framework CoreGraphics"
        "-framework CoreServices"
        "-framework IOKit"
        "-framework IOSurface"
        "-framework Metal"
        "-framework QuartzCore"
        "-framework Foundation"
    )
    if(CMAKE_SYSTEM_NAME STREQUAL "Darwin")
        target_link_libraries(bench_mnn_llm PRIVATE "-framework AppKit")
    endif()
endif()

endif()
