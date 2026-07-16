add_library(neoswarm_elm STATIC
    # Wave 1 stub — header-only library, this source file exists only because
    # CMake requires at least one source for STATIC libraries. It also serves
    # as a compile-time verification that i_elm.hpp is well-formed.
    # This file will be removed in Wave 2 when real .cpp implementations are added.
    elm_stub.cpp
)

target_include_directories(neoswarm_elm PUBLIC
    $<BUILD_INTERFACE:${PROJECT_ROOT}/src>
    $<INSTALL_INTERFACE:include>
)

target_link_libraries(neoswarm_elm PUBLIC neoswarm_common)
