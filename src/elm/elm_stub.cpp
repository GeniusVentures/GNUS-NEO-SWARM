/**
 * @file       elm_stub.cpp
 * @brief      Minimal compilation unit for the neoswarm_elm library (Wave 1).
 *
 * The neoswarm_elm library is header-only in Wave 1 (i_elm.hpp, types in common/types.hpp).
 * This file is present only to satisfy CMake's requirement that STATIC libraries have
 * at least one source file. It also serves as a compile-time verification that the IELM
 * interface header is syntactically correct and compiles against its dependencies.
 *
 * NOTE: This file will be removed in Wave 2 when real .cpp implementations are added.
 * @date       2026-07-16
 */

#include "elm/i_elm.hpp"

// -----------------------------------------------------------------------
// Compile-time verification stub
//
// This ensures IELM, ELMRole, ELMContext, and all outcome::result types
// resolve correctly. The function is intentionally dead code — it exists
// only to produce an object file for the static library archive.
// -----------------------------------------------------------------------
namespace
{
    void elm_stub_compile_check() noexcept
    {
        // Force instantiation of the abstract class vtable via a pointer cast.
        // This verifies all pure virtual signatures are well-formed.
        static_cast<void>( sizeof( sgns::neoswarm::elm::IELM ) );
    }
} // namespace
