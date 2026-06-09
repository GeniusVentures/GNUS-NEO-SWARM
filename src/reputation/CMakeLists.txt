add_library(genius_reputation STATIC
    ReputationScoring.cpp
    WeightedConsensus.cpp
    ReputationStorage.cpp
    ReputationCRDT.cpp
)

target_include_directories(genius_reputation PUBLIC
    $<BUILD_INTERFACE:${PROJECT_ROOT}/src>
    $<INSTALL_INTERFACE:include>
)

target_link_libraries(genius_reputation PUBLIC genius_common)

if(TARGET RocksDB::rocksdb)
    target_link_libraries(genius_reputation PUBLIC RocksDB::rocksdb)
    target_compile_definitions(genius_reputation PUBLIC GENIUS_HAS_ROCKSDB)
elseif(TARGET rocksdb)
    target_link_libraries(genius_reputation PUBLIC rocksdb)
    target_compile_definitions(genius_reputation PUBLIC GENIUS_HAS_ROCKSDB)
endif()

