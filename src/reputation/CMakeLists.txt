add_library(neoswarm_reputation STATIC
    reputation_scoring.cpp
    weighted_consensus.cpp
    reputation_storage.cpp
    reputation_crdt.cpp
)

target_include_directories(neoswarm_reputation PUBLIC
    $<BUILD_INTERFACE:${PROJECT_ROOT}/src>
    $<INSTALL_INTERFACE:include>
)

target_link_libraries(neoswarm_reputation PUBLIC 
    neoswarm_common
    neoswarm_proto
)

if(TARGET RocksDB::rocksdb)
    target_link_libraries(neoswarm_reputation PUBLIC RocksDB::rocksdb)
elseif(TARGET rocksdb)
    target_link_libraries(neoswarm_reputation PUBLIC rocksdb)
endif()

