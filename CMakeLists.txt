cmake_minimum_required(VERSION 3.16)
project(GNUS-NEO-SWARM)

set(CMAKE_CXX_STANDARD 17)

add_library(GNUS-NEO-SWARM STATIC src/slm_base.cpp)

install(TARGETS GNUS-NEO-SWARM EXPORT ${PROJECT_NAME}Targets
        LIBRARY       DESTINATION ${CMAKE_INSTALL_LIBDIR}
)
