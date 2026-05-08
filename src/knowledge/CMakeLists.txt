add_library(genius_knowledge STATIC
    KnowledgeRetrieval.cpp
    ContextInjection.cpp
    FactValidation.cpp
)

target_include_directories(genius_knowledge PUBLIC
    $<BUILD_INTERFACE:${CMAKE_SOURCE_DIR}/src>
    $<INSTALL_INTERFACE:include>
)

target_link_libraries(genius_knowledge PUBLIC genius_common)
