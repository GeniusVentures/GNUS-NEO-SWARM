# common — shared types, error codes, logging
# error.cpp registers the Boost.Outcome error category so it must be compiled.
add_library(neoswarm_common STATIC
    error.cpp
)

target_include_directories(neoswarm_common PUBLIC
    $<BUILD_INTERFACE:${PROJECT_ROOT}/src>
    $<INSTALL_INTERFACE:include>
)

target_compile_features(neoswarm_common PUBLIC cxx_std_17)

# spdlog — required for sgns::base::Logger
if(TARGET spdlog::spdlog)
    target_link_libraries(neoswarm_common PUBLIC spdlog::spdlog)
endif()

# fmt — required by spdlog
if(TARGET fmt::fmt)
    target_link_libraries(neoswarm_common PUBLIC fmt::fmt)
    target_compile_definitions(neoswarm_common PUBLIC SPDLOG_FMT_EXTERNAL)
endif()

# outcome — required for outcome::result<>
# libp2p ships its own outcome header; include path only, no link needed
target_include_directories(neoswarm_common PUBLIC "${THIRDPARTY_BUILD_DIR}/libp2p/include")
