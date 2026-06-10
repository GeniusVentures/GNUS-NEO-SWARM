add_library(genius_router STATIC
    prompt_analyzer.cpp
    rule_based_router.cpp
)

target_include_directories(genius_router PUBLIC
    $<BUILD_INTERFACE:${PROJECT_ROOT}/src>
    $<INSTALL_INTERFACE:include>
)

target_link_libraries(genius_router PUBLIC genius_common)
