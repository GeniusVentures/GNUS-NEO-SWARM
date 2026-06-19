/**
 * @file       os_memory.hpp
 * @brief      Platform-specific peak-memory measurement for benchmarks
 * @date       2026-06-18
 *
 * Centralizes OS-specific memory APIs so benchmark source files
 * contain zero #ifdef gates.
 */

#ifndef BENCH_OS_MEMORY_HPP
#define BENCH_OS_MEMORY_HPP

#include <cstddef>

#ifdef __APPLE__
#include <mach/mach.h>

inline size_t GetCurrentMemoryMB()
{
    struct mach_task_basic_info info;
    mach_msg_type_number_t count = MACH_TASK_BASIC_INFO_COUNT;
    if ( task_info( mach_task_self(), MACH_TASK_BASIC_INFO,
                    reinterpret_cast<task_info_t>( &info ), &count ) == KERN_SUCCESS )
    {
        return info.resident_size / ( 1024 * 1024 );
    }
    return 0;
}
#else
inline size_t GetCurrentMemoryMB()
{
    return 0;
}
#endif

#endif // BENCH_OS_MEMORY_HPP
