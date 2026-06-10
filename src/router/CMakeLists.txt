add_library(neoswarm_router STATIC
    prompt_analyzer.cpp
    rule_based_router.cpp
)

target_include_directories(neoswarm_router PUBLIC
    $<BUILD_INTERFACE:${PROJECT_ROOT}/src>
    $<INSTALL_INTERFACE:include>
)

target_link_libraries(neoswarm_router PUBLIC neoswarm_common)
