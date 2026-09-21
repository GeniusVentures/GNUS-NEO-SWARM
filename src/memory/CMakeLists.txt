add_library(neoswarm_memory STATIC
    memory_init.cpp
    # Additional sources added in plans 08-02 (memory_storage.cpp),
    # 08-03 (fact_extraction.cpp, context_mapping.cpp, write_evaluation.cpp),
    # 08-04 (memory_governor.cpp)
)

target_include_directories(neoswarm_memory PUBLIC
    $<BUILD_INTERFACE:${PROJECT_ROOT}/src>
    $<INSTALL_INTERFACE:include>
)

target_link_libraries(neoswarm_memory PUBLIC
    neoswarm_common
)

if(TARGET RocksDB::rocksdb)
    target_link_libraries(neoswarm_memory PUBLIC RocksDB::rocksdb)
elseif(TARGET rocksdb)
    target_link_libraries(neoswarm_memory PUBLIC rocksdb)
endif()

if(TARGET nlohmann_json::nlohmann_json)
    target_link_libraries(neoswarm_memory PUBLIC nlohmann_json::nlohmann_json)
endif()
