if ("${CMAKE_CXX_COMPILER_ID}" MATCHES "^(AppleClang|Clang|GNU)$")
  # enable those flags
  add_flag(-Wall)
  add_flag(-Wextra)
  add_flag(-Woverloaded-virtual)     # warn if you overload (not override) a virtual function
  add_flag(-Wformat=2)               # warn on security issues around functions that format output (ie printf)
  add_flag(-Wmisleading-indentation) # (only in GCC >= 6.0) warn if indentation implies blocks where blocks do not exist
  add_flag(-Wduplicated-cond)        # (only in GCC >= 6.0) warn if if / else chain has duplicated conditions
  add_flag(-Wduplicated-branches)    # (only in GCC >= 7.0) warn if if / else branches have duplicated code
  add_flag(-Wnull-dereference)       # (only in GCC >= 6.0) warn if a null dereference is detected
  add_flag(-Wsign-compare)
  add_flag(-Wtype-limits)            # size_t - size_t >= 0 -> always true
  add_flag(-Wnon-virtual-dtor) # warn the user if a class with virtual functions has a non-virtual destructor. This helps catch hard to track down memory errors

  # disable those flags
  add_flag(-Wno-unused-command-line-argument)    # clang: warning: argument unused during compilation: '--coverage' [-Wunused-command-line-argument]
  add_flag(-Wno-unused-variable)    # prints too many useless warnings
  add_flag(-Wno-double-promotion)       # (GCC >= 4.6, Clang >= 3.8) warn if float is implicit promoted to double
  add_flag(-Wno-unused-parameter)    # prints too many useless warnings
  add_flag(-Wno-unused-function)    # prints too many useless warnings
  add_flag(-Wno-format-nonliteral)   # prints way too many warnings from spdlog
  add_flag(-Wno-gnu-zero-variadic-macro-arguments)   # https://stackoverflow.com/questions/21266380/is-the-gnu-zero-variadic-macro-arguments-safe-to-ignore

  # promote to errors
  #add_flag(-Werror=unused-lambda-capture)  # error if lambda capture is unused
  #add_flag(-Werror=return-type)      # warning: control reaches end of non-void function [-Wreturn-type]
  #add_flag(-Werror=sign-compare)     # warn the user if they compare a signed and unsigned numbers
  #add_flag(-Werror=reorder)          # field '$1' will be initialized after field '$2'
endif()

# ---------------------------------------------------------------------------
# Per-platform application link settings — standalone fallback only.
# Canonical definitions live in the parent repo's cmake/CompilationFlags.cmake
# (via the build submodule forwarder); when NEO-SWARM is built standalone the
# parent file never runs, so define them here from the build dir name.
# ---------------------------------------------------------------------------
if(NOT DEFINED APP_RPATH_EXE)
if(NOT BUILD_PLATFORM_NAME)
    get_filename_component(BUILD_PLATFORM_NAME ${CMAKE_CURRENT_SOURCE_DIR} NAME)
endif()
if(BUILD_PLATFORM_NAME MATCHES "^(OSX|iOS)$")
    set(APP_RUNTIME_LIB_DIR "lib")
    set(APP_LINK_OPTIONS "LINKER:-no_warn_duplicate_libraries")
    set(APP_LINK_LIBRARIES "")
    set(APP_RPATH_EXE "@executable_path/../${APP_RUNTIME_LIB_DIR}")
    set(APP_RPATH_LIB "@loader_path")
elseif(BUILD_PLATFORM_NAME STREQUAL "Linux")
    set(APP_RUNTIME_LIB_DIR "lib")
    set(APP_LINK_OPTIONS "")
    set(APP_LINK_LIBRARIES "uuid")
    set(APP_RPATH_EXE "\$ORIGIN/../${APP_RUNTIME_LIB_DIR}")
    set(APP_RPATH_LIB "$ORIGIN")
elseif(BUILD_PLATFORM_NAME STREQUAL "Windows")
    set(APP_RUNTIME_LIB_DIR "bin")
    set(APP_LINK_OPTIONS "")
    set(APP_LINK_LIBRARIES "")
    set(APP_RPATH_EXE "")
    set(APP_RPATH_LIB "")
else() # Android/iOS — mobile app packaging, no installed exe layout
    set(APP_RUNTIME_LIB_DIR "lib")
    set(APP_LINK_OPTIONS "")
    set(APP_LINK_LIBRARIES "")
    set(APP_RPATH_EXE "")
    set(APP_RPATH_LIB "")
endif()
endif()
