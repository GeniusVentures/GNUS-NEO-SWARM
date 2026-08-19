add_library(neoswarm_storage STATIC
    gcs_global_db.cpp
)

target_include_directories(neoswarm_storage PUBLIC
    $<BUILD_INTERFACE:${PROJECT_ROOT}/src>
    $<INSTALL_INTERFACE:include>
)

target_link_libraries(neoswarm_storage PUBLIC neoswarm_common neoswarm_proto)

# SuperGenius CRDT GlobalDB — hard required (project Conditional Compilation rule:
# missing required libraries fail at configure time, never degrade to a stub).
if(TARGET sgns::crdt_globaldb)
    target_link_libraries(neoswarm_storage PUBLIC sgns::crdt_globaldb)
else()
    message(FATAL_ERROR "sgns::crdt_globaldb target not found — SuperGenius package must be configured before neoswarm_storage")
endif()

# GeniusSDK — hard required: GcsGlobalDb::Initialize() calls GeniusSDKGetPubSub() (D-16a).
#
# Prefer the static target: avoids a runtime DLL search-path dependency on
# GeniusSDK_shared.dll for every executable that links neoswarm_storage.
#
# If only the shared target is available, note: its CMake-imported IMPORTED_LOCATION/IMPLIB
# point at the GeniusSDK install prefix (${GENIUS_SDK_BUILD_DIR}/GeniusSDK/{lib,bin}/...),
# which can lag the GeniusSDK build tree if `cmake --install`/`ninja install` hasn't been
# re-run there after a GeniusSDK.cpp/.h source change (e.g. a newly added accessor). Redirect
# to a newer build-tree dylib when one exists (Apple/.dylib layout only, currently); on other
# platforms (including this Windows build), re-run the GeniusSDK install step after any
# GeniusSDK source change so the installed .lib/.dll pick up new/changed exported symbols.
if(TARGET sgns::GeniusSDK)
    target_link_libraries(neoswarm_storage PUBLIC sgns::GeniusSDK)
    message(STATUS "GeniusSDK (static) linked to neoswarm_storage")
elseif(TARGET sgns::GeniusSDK_shared)
    set(_GENIUSSDK_BUILD_DYLIB "${GENIUS_SDK_BUILD_DIR}/src/libGeniusSDK_shared.dylib")
    if(EXISTS "${_GENIUSSDK_BUILD_DYLIB}")
        set_target_properties(sgns::GeniusSDK_shared PROPERTIES
            IMPORTED_LOCATION_DEBUG   "${_GENIUSSDK_BUILD_DYLIB}"
            IMPORTED_LOCATION_RELEASE "${_GENIUSSDK_BUILD_DYLIB}"
            IMPORTED_LOCATION         "${_GENIUSSDK_BUILD_DYLIB}"
        )
        message(STATUS "sgns::GeniusSDK_shared redirected to build-tree dylib: ${_GENIUSSDK_BUILD_DYLIB}")
    endif()
    target_link_libraries(neoswarm_storage PUBLIC sgns::GeniusSDK_shared)
    message(STATUS "GeniusSDK (shared) linked to neoswarm_storage")
else()
    message(FATAL_ERROR "sgns::GeniusSDK_shared / sgns::GeniusSDK target not found — GeniusSDK package must be configured before neoswarm_storage")
endif()

# SuperGenius account headers (mirrors src/network/CMakeLists.txt)
target_include_directories(neoswarm_storage PUBLIC
    "${SUPERGENIUS_BUILD_DIR}/SuperGenius/include"
)

# Headers for direct deps of gcs_global_db.cpp that sgns::crdt_globaldb does not
# re-export via INTERFACE_INCLUDE_DIRECTORIES (its interface carries only the
# SuperGenius install include dir). The ipfs-pubsub imported target is a stub
# (cmake/CommonBuildParameters.cmake), so include its headers directly.
target_include_directories(neoswarm_storage PUBLIC
    "${THIRDPARTY_BUILD_DIR}/ipfs-pubsub/include"
    "${THIRDPARTY_BUILD_DIR}/ipfs-lite-cpp/include"
    "${THIRDPARTY_BUILD_DIR}/libp2p/include"
    "${THIRDPARTY_BUILD_DIR}/boost/build/include"
)

# NOTE: gcs_global_db.cpp includes only the plain-C GeniusSDK.h (never GeniusSDK.hpp,
# which never existed — see resolved debug session neoswarm-geniussdk-missing). GeniusSDK.h
# has zero C++ header dependencies (stdint.h/stdbool.h only) and is already available via
# the linked GeniusSDK target's own INTERFACE_INCLUDE_DIRECTORIES (both sgns::GeniusSDK and
# sgns::GeniusSDK_shared export the same ${GENIUS_SDK_BUILD_DIR}/GeniusSDK/include, confirmed
# installed), so no additional include directories are needed for it — this also means the
# previously-required WalletCore/zkLLVM/evmrelay/MNN transitive-include workarounds (only
# needed for GeniusSDK.hpp's assumed account/GeniusNode.hpp chain) are no longer needed and
# have been removed.
