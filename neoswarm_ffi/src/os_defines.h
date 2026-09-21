/**
 * @file       os_defines.h
 * @brief      Platform abstraction for flutter_slm_bridge
 * @date       2026-06-18
 *
 * Centralizes all OS-specific includes and macros so the main
 * public header (flutter_slm_bridge.h) contains zero #ifdef gates.
 */

#ifndef FLUTTER_SLM_BRIDGE_OS_DEFINES_H
#define FLUTTER_SLM_BRIDGE_OS_DEFINES_H

#if _WIN32
#include <windows.h>
#define FFI_PLUGIN_EXPORT __declspec( dllexport )
#define PLATFORM_SLEEP_MS( ms ) Sleep( ms )
#else
#include <pthread.h>
#include <unistd.h>
#define FFI_PLUGIN_EXPORT
#define PLATFORM_SLEEP_MS( ms ) usleep( ( ms ) * 1000 )
#endif

#endif // FLUTTER_SLM_BRIDGE_OS_DEFINES_H
