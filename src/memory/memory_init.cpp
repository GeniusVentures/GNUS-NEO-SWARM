/**
 * @file       memory_init.cpp
 * @brief      Placeholder — sources added in plans 08-02 through 08-04
 *
 * This file exists solely so that neoswarm_memory can be registered
 * as a STATIC library target in CMake before any implementation sources
 * are committed.  The real sources arrive in subsequent Phase 8 plans.
 */

namespace sgns::neoswarm::memory
{
    // Plan 08-02: memory_storage.cpp
    // Plan 08-03: fact_extraction.cpp, context_mapping.cpp, write_evaluation.cpp
    // Plan 08-04: memory_governor.cpp

    // External-linkage placeholder symbol: libtool drops symbol-less object
    // files from archives, which left this transitional library empty and
    // made ranlib warn on every build. Removed when the Phase 8 sources land.
    const char* kMemoryModulePlaceholder = "neoswarm_memory";
} // namespace sgns::neoswarm::memory
