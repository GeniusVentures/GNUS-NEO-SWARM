add_library(neoswarm_elm STATIC
    role_elm.cpp
)

target_include_directories(neoswarm_elm PUBLIC
    $<BUILD_INTERFACE:${PROJECT_ROOT}/src>
    $<INSTALL_INTERFACE:include>
)

target_link_libraries(neoswarm_elm PUBLIC neoswarm_common neoswarm_core)
