# common — shared types, error codes, logging
# Error.cpp registers the Boost.Outcome error category so it must be compiled.
add_library(genius_common STATIC
    Error.cpp
)

target_include_directories(genius_common PUBLIC
    $<BUILD_INTERFACE:${PROJECT_ROOT}/src>
    $<INSTALL_INTERFACE:include>
)

target_compile_features(genius_common PUBLIC cxx_std_17)

# spdlog — required for sgns::base::Logger
if(TARGET spdlog::spdlog)
    target_link_libraries(genius_common PUBLIC spdlog::spdlog)
endif()

# fmt — required by spdlog
if(TARGET fmt::fmt)
    target_link_libraries(genius_common PUBLIC fmt::fmt)
    target_compile_definitions(genius_common PUBLIC SPDLOG_FMT_EXTERNAL)
endif()

# outcome — required for outcome::result<>
# libp2p ships its own outcome header; include path only, no link needed
target_include_directories(genius_common PUBLIC "${THIRDPARTY_BUILD_DIR}/libp2p/include")
