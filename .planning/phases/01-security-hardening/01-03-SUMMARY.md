# Plan 01-03 Summary: Key Encryption at Rest

**Phase:** 01-security-hardening
**Status:** Complete
**Requirements:** SEC-04

## What Was Built

Encrypted private key storage using AES-256-GCM with PBKDF2 key derivation.
The private key is no longer stored as plain hex on disk.

### Task 1: Declare SaveEncrypted / LoadEncrypted
- Added `SaveEncrypted(path, passphrase)` and `LoadEncrypted(path, passphrase)` to `NodeIdentity.hpp`
- Full Doxygen-compatible documentation for both methods

### Task 2: SaveEncrypted Implementation
- 32-byte random salt via OpenSSL `RAND_bytes`
- PBKDF2-HMAC-SHA256 with 600,000 iterations for key derivation
- 12-byte random IV per encryption
- AES-256-GCM encryption via OpenSSL EVP API
- 16-byte GCM authentication tag for integrity verification
- Self-describing binary format: `[4B salt_len][salt][12B IV][ciphertext][16B tag]`

### Task 3: LoadEncrypted Implementation
- Reads binary format, extracts salt/IV/ciphertext/tag
- Re-derives key from passphrase via PBKDF2
- AES-256-GCM decryption with GCM tag verification
- Wrong passphrase → tag mismatch → returns IdentityError
- Derives public key from decrypted private key
- Fails safely when OpenSSL unavailable

### Task 4: Failing Tests (RED)
- Encrypted roundtrip test (written, expected to fail before implementation)
- Wrong passphrase rejection test

## Artifacts

| File | Status |
|------|--------|
| `src/security/NodeIdentity.hpp` | Modified — SaveEncrypted + LoadEncrypted declarations |
| `src/security/NodeIdentity.cpp` | Modified — 268 lines of AES-256-GCM + PBKDF2 implementation |

## Self-Check

- [x] AES-256-GCM encryption via OpenSSL EVP (not deprecated `AES_encrypt`)
- [x] PBKDF2-HMAC-SHA256 key derivation (600K iterations)
- [x] 32-byte random salt per encryption
- [x] 12-byte random IV per encryption
- [x] 16-byte GCM tag for authenticity
- [x] Wrong passphrase returns IdentityError (not crash)
- [x] Fails with error when OpenSSL unavailable (not stub accept)
- [x] C++17 compliance, Allman bracing, outcome::result<T> error propagation

## Deviations

None.
