cmake_minimum_required(VERSION 3.30)
project(Genius-MOS-SLM)

set(CMAKE_CXX_STANDARD 17)

add_library(Genius-MOS-SLM STATIC src/slm_base.cpp)

add_library(Genius-MOS-SLM-FFI SHARED src/genius_slm_chat_c.cpp)

target_include_directories(Genius-MOS-SLM-FFI PUBLIC ${CMAKE_CURRENT_SOURCE_DIR}/src)

target_compile_definitions(Genius-MOS-SLM-FFI PRIVATE GENIUS_SLM_CHAT_C_EXPORTS)

