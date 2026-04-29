cmake_minimum_required(VERSION 3.16)
project(GNUS-NEO-SWARM)

set(CMAKE_CXX_STANDARD 17)

<<<<<<< Updated upstream
add_library(Genius-MOS-SLM STATIC src/slm_base.cpp)

add_library(Genius-MOS-SLM-FFI SHARED src/genius_slm_chat_c.cpp)

target_include_directories(Genius-MOS-SLM-FFI PUBLIC ${CMAKE_CURRENT_SOURCE_DIR}/src)

target_compile_definitions(Genius-MOS-SLM-FFI PRIVATE GENIUS_SLM_CHAT_C_EXPORTS)

=======
add_library(GNUS-NEO-SWARM STATIC src/slm_base.cpp)

install(TARGETS GNUS-NEO-SWARM EXPORT ${PROJECT_NAME}Targets
        LIBRARY       DESTINATION ${CMAKE_INSTALL_LIBDIR}
)
>>>>>>> Stashed changes
