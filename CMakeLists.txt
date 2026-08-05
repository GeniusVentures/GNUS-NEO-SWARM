cmake_minimum_required(VERSION 3.16)

# This root CMakeLists is used when the parent GeniusCogntiveSystem repo does
# add_subdirectory(GNUS-NEO-SWARM). Standalone builds go through
# build/<Platform>/CMakeLists.txt instead, which reaches the same
# cmake/CommonBuildParameters.cmake via the cmaketemplate chain.
#
# We skip build/CommonCompilerOptions.cmake here: that file does platform /
# thirdparty discovery assuming it is the top-level project (BUILD_PLATFORM_NAME
# from CMAKE_CURRENT_SOURCE_DIR, get_default_root, etc.), which breaks when
# nested. The parent build chain has already resolved _THIRDPARTY_BUILD_DIR and
# PROJECT_SUPER_ROOT, so this file only needs the dependency/target setup.

project(GNUS-NEO-SWARM
    VERSION 0.1.0
    DESCRIPTION "GNUS.ai NEO-SWARM C++ inference engine library"
    LANGUAGES C CXX
)

# Common functions (print, add_flag, addtest, add_proto_library, ...)
include(${CMAKE_CURRENT_SOURCE_DIR}/build/cmake/functions.cmake)

# Full thirdparty dependency setup + src/ targets + install/export.
# Uses NEOSWARM_ROOT (derived from its own location) for all self-references,
# and the parent-provided _THIRDPARTY_BUILD_DIR / PROJECT_SUPER_ROOT.
include(${CMAKE_CURRENT_SOURCE_DIR}/cmake/CommonBuildParameters.cmake)
