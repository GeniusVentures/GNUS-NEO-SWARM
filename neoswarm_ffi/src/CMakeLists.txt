# The Flutter tooling requires that developers have CMake 3.10 or later
# installed. You should not increase this version, as doing so will cause
# the plugin to fail to compile for some customers of the plugin.
cmake_minimum_required(VERSION 3.10)

project(flutter_slm_bridge_library VERSION 0.0.1 LANGUAGES C)

add_library(flutter_slm_bridge SHARED
  "flutter_slm_bridge.c"
)

set_target_properties(flutter_slm_bridge PROPERTIES
  PUBLIC_HEADER flutter_slm_bridge.h
  OUTPUT_NAME "flutter_slm_bridge"
)

target_compile_definitions(flutter_slm_bridge PUBLIC DART_SHARED_LIB)

if (ANDROID)
  # Support Android 15 16k page size
  target_link_options(flutter_slm_bridge PRIVATE "-Wl,-z,max-page-size=16384")
endif()
