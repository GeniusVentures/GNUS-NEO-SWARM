add_library(neoswarm_specialists STATIC
    grammar_specialist.cpp
    math_specialist.cpp
    symbolic_fallback.cpp
)

target_include_directories(neoswarm_specialists PUBLIC
    $<BUILD_INTERFACE:${PROJECT_ROOT}/src>
    $<INSTALL_INTERFACE:include>
)

target_link_libraries(neoswarm_specialists PUBLIC neoswarm_common neoswarm_core)
