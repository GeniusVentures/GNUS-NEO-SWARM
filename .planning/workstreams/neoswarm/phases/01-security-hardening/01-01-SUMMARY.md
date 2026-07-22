# Plan 01-01 Summary: Cryptographic Foundation

**Phase:** 01-security-hardening
**Status:** Complete
**Requirements:** SEC-01, SEC-06

## What Was Built

Activated real secp256k1 cryptographic identity linkage and converted all security stubs to fail-close (reject instead of accept).

### Task 1: Enable secp256k1 Linkage
- Added `find_package(libsecp256k1 CONFIG QUIET)` fallback before `if(TARGET secp256k1)` in `src/security/CMakeLists.txt`
- Created ALIAS target `secp256k1` from `libsecp256k1::secp256k1` when available
- Modeled after existing `find_package(OpenSSL QUIET)` pattern in same file
- Ensures `GENIUS_HAS_SECP256K1` is reachable in any build context

### Task 2: Fail-Close Stubs
- `MessageSigning::Verify()` — changed from `return true` to `return false` when secp256k1 unavailable
- `NodeIdentity::Verify()` — changed from `return true` to `return false` when secp256k1 unavailable
- Log level changed from `warn` to `error` for missing crypto rejection messages

## Artifacts

| File | Status |
|------|--------|
| `src/security/CMakeLists.txt` | Modified — secp256k1 linkage |
| `src/security/NodeIdentity.cpp` | Modified — fail-close stub |
| `src/security/MessageSigning.cpp` | Modified — fail-close stub |

## Self-Check

- [x] secp256k1 ALIAS target created when library found
- [x] `MessageSigning::Verify` returns `false` in stub path
- [x] `NodeIdentity::Verify` returns `false` in stub path
- [x] Error-level logging for rejected signatures
- [x] Existing stub behavior preserved under `#ifdef GENIUS_HAS_SECP256K1` guard

## Deviations

None.
