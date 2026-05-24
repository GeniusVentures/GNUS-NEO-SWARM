add_library(genius_network STATIC
    P2PNode.cpp
    ResultAggregation.cpp
)

target_include_directories(genius_network PUBLIC
    $<BUILD_INTERFACE:${PROJECT_ROOT}/src>
    $<INSTALL_INTERFACE:include>
)

target_link_libraries(genius_network PUBLIC genius_common genius_security)

# nlohmann/json
if(TARGET nlohmann_json::nlohmann_json)
    target_link_libraries(genius_network PUBLIC nlohmann_json::nlohmann_json)
elseif(TARGET nlohmann_json)
    target_link_libraries(genius_network PUBLIC nlohmann_json)
endif()

# libp2p — requires thirdparty fmt (Homebrew fmt must be unlinked)
if(TARGET p2p::p2p)
    # fmt from thirdparty (must come before any system fmt)
    find_library(FMT_LIB fmt
        PATHS "${THIRDPARTY_BUILD_DIR}/fmt/lib"
        NO_DEFAULT_PATH)
    if(FMT_LIB AND NOT TARGET fmt::fmt)
        add_library(fmt::fmt UNKNOWN IMPORTED)
        set_target_properties(fmt::fmt PROPERTIES
            IMPORTED_LOCATION "${FMT_LIB}"
            INTERFACE_INCLUDE_DIRECTORIES "${THIRDPARTY_BUILD_DIR}/fmt/include"
        )
    endif()

    # soralog (libp2p logging dependency)
    find_library(SORALOG_LIB soralog
        PATHS "${THIRDPARTY_BUILD_DIR}/soralog/lib/soralog"
        NO_DEFAULT_PATH)
    if(SORALOG_LIB AND NOT TARGET soralog::soralog)
        add_library(soralog::soralog UNKNOWN IMPORTED)
        set_target_properties(soralog::soralog PROPERTIES
            IMPORTED_LOCATION "${SORALOG_LIB}"
            INTERFACE_INCLUDE_DIRECTORIES "${THIRDPARTY_BUILD_DIR}/soralog/include"
        )
    endif()

    target_link_libraries(genius_network PUBLIC p2p::p2p)
    if(TARGET fmt::fmt)
        target_link_libraries(genius_network PUBLIC fmt::fmt)
    endif()
    if(TARGET soralog::soralog)
        target_link_libraries(genius_network PUBLIC soralog::soralog)
    endif()

    target_include_directories(genius_network PUBLIC
        "${THIRDPARTY_BUILD_DIR}/libp2p/include"
        "${THIRDPARTY_BUILD_DIR}/boost/build/include"
        "${THIRDPARTY_BUILD_DIR}/fmt/include"
        "${THIRDPARTY_BUILD_DIR}/soralog/include"
        "${THIRDPARTY_BUILD_DIR}/Microsoft.GSL/include"
    )
    # Use external fmt so spdlog's bundled fmt doesn't conflict
    target_compile_definitions(genius_network PUBLIC
        GENIUS_HAS_LIBP2P
        SPDLOG_FMT_EXTERNAL
    )
    message(STATUS "libp2p enabled for genius_network")
endif()
