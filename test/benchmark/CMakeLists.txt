# bench_mnn_llm needs MNN's LLM API header. The vendored MNN installs it at
# include/llm/llm.hpp — a sibling of MNN/, not under it. Keep the existence
# check as a guard against MNN built without MNN_BUILD_LLM.
if(EXISTS "${_THIRDPARTY_BUILD_DIR}/MNN/include/llm/llm.hpp")

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
