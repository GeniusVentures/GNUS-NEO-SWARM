add_library(neoswarm_elm STATIC
    role_elm.cpp
    domain_elm.cpp
    specialist_adapter.cpp
    grounding_elm.cpp
    tool_support_elm.cpp
    elm_chain_builder.cpp
)

target_include_directories(neoswarm_elm PUBLIC
    $<BUILD_INTERFACE:${PROJECT_ROOT}/src>
    $<INSTALL_INTERFACE:include>
)

target_link_libraries(neoswarm_elm PUBLIC neoswarm_common neoswarm_core neoswarm_knowledge neoswarm_specialists)
