# functions.cmake — GNUS-NEO-SWARM
# Minimal CMake utility functions used by CommonBuildParameters.cmake

function(print)
    message(STATUS "[${CMAKE_PROJECT_NAME}] ${ARGV}")
endfunction()

function(add_flag flag)
    include(CheckCXXCompilerFlag)
    check_cxx_compiler_flag(${flag} FLAG_${flag})
    if(FLAG_${flag})
        add_compile_options(${flag})
    endif()
endfunction()

function(disable_clang_tidy target)
    set_target_properties(${target} PROPERTIES
        C_CLANG_TIDY   ""
        CXX_CLANG_TIDY ""
    )
endfunction()
