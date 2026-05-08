add_library(genius_reputation STATIC
    ReputationScoring.cpp
    WeightedConsensus.cpp
    ReputationStorage.cpp
    ReputationCRDT.cpp
)

target_include_directories(genius_reputation PUBLIC
    $<BUILD_INTERFACE:${CMAKE_SOURCE_DIR}/src>
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

# RocksDB dependencies (snappy, zlib)
foreach(_dep snappy z)
    find_library(_lib_${_dep} ${_dep}
        PATHS "${THIRDPARTY_BUILD_DIR}/snappy/lib"
              "${THIRDPARTY_BUILD_DIR}/zlib/lib"
        NO_DEFAULT_PATH)
    if(_lib_${_dep})
        target_link_libraries(genius_reputation PUBLIC "${_lib_${_dep}}")
    endif()
endforeach()
