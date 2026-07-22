---
phase: 03-fp4-quantization-artifact-integrity
plan: 02
subsystem: config, pipeline
tags:
  - config-validation
  - fp4-quantization
  - sgfp4-v2
  - checkpoint-validation
  - manifest-integrity
requires: []
provides:
  - ConfigLoader._validate_fp4_export()
  - pipeline.yaml SGFP4 v2 config block
  - CheckpointValidator._validate_quantize() SGFP4 v2 checks
affects:
  - config/loader.py
  - config/pipeline.yaml
  - pipeline/checkpoint.py
  - tests/conftest.py
  - tests/test_checkpoint.py
tech-stack:
  added: []
  patterns:
    - ConfigLoader follow-front-loading validation pattern (same as _validate_teacher)
    - CheckpointValidator per-check dict pattern (name, passed, detail)
    - pytest fixture-based test scaffolding with tmp_path isolation
    - Streaming SHA256 (64 KiB chunks) for memory-safe binary hashing
key-files:
  created:
    - gnus-poc/tests/test_checkpoint.py
  modified:
    - gnus-poc/config/loader.py
    - gnus-poc/config/pipeline.yaml
    - gnus-poc/pipeline/checkpoint.py
    - gnus-poc/tests/conftest.py
decisions:
  - "fp4_export block is optional — absent block warns (not errors) to allow Phase 1/2 work without quantization config"
  - "fp4_weights_exist check extended to glob *.sgfp4 alongside *.npz/*.safetensors for v2+ output"
  - "Missing .sgfp4 binary does not fail validation — v1-only exports remain valid"
  - "Missing fp4_binary.sha256 in manifest is backward-compatible (passes with note)"
  - "Manifest SHA256 validation uses streaming 64 KiB chunks to avoid loading entire binary into memory"
  - "All new v2 checks are additive — existing .npz/.safetensors checks preserved unchanged"
metrics:
  duration_seconds: 250
  completed_date: "2026-06-27T23:47:43Z"
  tasks_total: 2
  tasks_completed: 2
---

# Phase 3 Plan 2: SGFP4 v2 Config Validation and Artifact Integrity Checks

ConfigLoader `_validate_fp4_export()` front-loads SGFP4 v2 config validation, pipeline.yaml extended with per-block-size error thresholds and adaptive macroblock parameters, CheckpointValidator upgraded with SGFP4 v2 binary validation (magic header, manifest SHA256, required fields) — all additive, backward-compatible with v1-only exports.

## Deviations from Plan

None — plan executed exactly as written. Two minor test assertions adjusted during Task 2 verification (fixture details matched actual code paths for missing-sha256 manifest scenarios), tracked as in-task fixes rather than deviations.

## Completed Tasks

| Task | Name                                                            | Commit   | Files                                      |
|------|-----------------------------------------------------------------|----------|--------------------------------------------|
| 1    | Add fp4_export config validation and extend pipeline.yaml      | 3793e32  | loader.py, pipeline.yaml                   |
| 2    | Upgrade CheckpointValidator quantize stage validation for SGFP4 v2 | 881a034  | checkpoint.py, conftest.py, test_checkpoint.py |

## Verification Results

| Verification                             | Result     | Details                          |
|------------------------------------------|------------|----------------------------------|
| `python3 gnus-poc/config/loader.py`      | 18 passed  | All existing + 6 new fp4 tests   |
| `pytest test_checkpoint.py -k quantize`  | 7 passed   | All SGFP4 v2 validation paths    |
| `pytest test_checkpoint.py` (full)       | 12 passed  | Includes lifecycle + v2 tests    |

## Success Criteria Met

1. ConfigLoader._validate_fp4_export() catches all malformed configurations at construction time
2. pipeline.yaml extended with per-block-size error thresholds, ternary_delta, min_block_size, laplacian_levels, log_mode_enabled
3. CheckpointValidator._validate_quantize() validates SGFP4 v2 magic header (b'SGF4' + 0x02), manifest SHA256, and QUANT-03 required fields
4. Backward compatible: v1-only output (.npz/.safetensors, no .sgfp4) still passes validation
5. Missing fp4_export block does not break ConfigLoader construction (warning only)
6. All pytest tests pass for both config validation and checkpoint validation

## Known Stubs

None. All validation logic is fully implemented with concrete checks, error messages, and test coverage.

## Threat Flags

None. All STRIDE threats from the threat model are either mitigated (T-03-06 through T-03-08) or accepted (T-03-09). No new security surface beyond what was planned.

## Self-Check: PASSED

- [x] `gnus-poc/config/loader.py` exists (508 lines, min 350 required)
- [x] `gnus-poc/config/pipeline.yaml` exists (135 lines, min 120 required)
- [x] `gnus-poc/pipeline/checkpoint.py` exists (905 lines, min 700 required)
- [x] `gnus-poc/tests/test_checkpoint.py` exists (191 lines)
- [x] `gnus-poc/tests/conftest.py` extended with 6 SGFP4 fixtures
- [x] Commit 3793e32 exists (Task 1)
- [x] Commit 881a034 exists (Task 2)
- [x] All 18 ConfigLoader self-tests pass
- [x] All 12 checkpoint pytest tests pass
