add_library(genius_knowledge STATIC
    knowledge_retrieval.cpp
    context_injection.cpp
    fact_validation.cpp
)

target_include_directories(genius_knowledge PUBLIC
    $<BUILD_INTERFACE:${PROJECT_ROOT}/src>
    $<INSTALL_INTERFACE:include>
)

target_link_libraries(genius_knowledge PUBLIC genius_common)
