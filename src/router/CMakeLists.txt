add_library(genius_router STATIC
    PromptAnalyzer.cpp
    RuleBasedRouter.cpp
)

target_include_directories(genius_router PUBLIC
    $<BUILD_INTERFACE:${CMAKE_SOURCE_DIR}/src>
    $<INSTALL_INTERFACE:include>
)

target_link_libraries(genius_router PUBLIC genius_common)
