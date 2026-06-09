add_library(genius_specialists STATIC
    GrammarSpecialist.cpp
    MathSpecialist.cpp
    SymbolicFallback.cpp
)

target_include_directories(genius_specialists PUBLIC
    $<BUILD_INTERFACE:${PROJECT_ROOT}/src>
    $<INSTALL_INTERFACE:include>
)

target_link_libraries(genius_specialists PUBLIC genius_common genius_core)
