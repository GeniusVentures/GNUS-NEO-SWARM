add_library(neoswarm_knowledge STATIC
    knowledge_retrieval.cpp
    context_injection.cpp
    fact_validation.cpp
)

target_include_directories(neoswarm_knowledge PUBLIC
    $<BUILD_INTERFACE:${PROJECT_ROOT}/src>
    $<INSTALL_INTERFACE:include>
)

target_link_libraries(neoswarm_knowledge PUBLIC neoswarm_common)
