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

# Nested mode: the parent build's PROJECT_ROOT points at GeniusCognitiveSystem,
# but module CMakeLists resolve their include root as ${PROJECT_ROOT}/src. This
# is a subdirectory-scoped set — it shadows the inherited value for the src tree
# below and does not leak back to the parent.
set(PROJECT_ROOT "${CMAKE_CURRENT_LIST_DIR}")

# Standalone builds get nlohmann/json via include_directories() in this repo's
# own cmake/CommonBuildParameters.cmake; nested builds never run that file, and
# common/types.hpp (consumed across modules) includes <nlohmann/json.hpp>
# without a per-target link.
include_directories(${THIRDPARTY_BUILD_DIR}/json/include)

add_subdirectory(${CMAKE_CURRENT_LIST_DIR}/src src)
