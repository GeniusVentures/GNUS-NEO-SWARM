---
phase: 03-fp4-quantization-artifact-integrity
plan: 01
subsystem: quantization
tags: [sgfp4, quadtree, laplacian, fp4, dual-mode, adaptive-quantization]
requires: []
provides: [laplacian.py, quadtree.py, fp4_exporter.py (v2)]
affects: [quantize/, tests/]
tech-stack:
  added: [scipy.ndimage.gaussian_filter]
  patterns: [QuadtreeEncoder, LaplacianWeightedError, adaptive binary format, ManifestBuilder integration]
key-files:
  created:
    - gnus-poc/quantize/laplacian.py
    - gnus-poc/quantize/quadtree.py
    - gnus-poc/tests/test_laplacian.py
    - gnus-poc/tests/test_quadtree.py
  modified:
    - gnus-poc/quantize/fp4_exporter.py
    - gnus-poc/quantize/__init__.py
    - gnus-poc/tests/test_fp4_exporter.py
decisions:
  - "D-01: Full quadtree (64->32->16->8->4) with Laplacian-weighted error for split decision"
  - "D-02: Layout enum 0-5 per superblock identifying block structure"
  - "D-03: Variable payload scaling with block area"
  - "D-04: Dual-mode FP4_AFFINE + T158_AFFINE with error comparison"
  - "D-05: Log mode deferred, flag bit reserved"
  - "D-06: Packed uint32 per-block header with 4 LSB flags"
  - "D-07: Laplacian encode-side only"
  - "D-10: ManifestBuilder used as-is for manifest generation"
metrics:
  duration: 5.7m
  completed_date: 2026-06-27T23:49:03Z
---

# Phase 03 Plan 01: SGFP4 v2 Adaptive Quadtree Quantization Summary

**One-liner:** Upgraded FP4Exporter from fixed 64x64 to adaptive quadtree (4-64 block sizes) with encode-side Laplacian error analysis, dual-mode per-block encoding, superblock layout enum, variable payloads, and backward-compatible v1 path.

## Tasks Completed

| # | Task | Status | Commit | Key Files |
|---|------|--------|--------|-----------|
| 1 | Create Laplacian error analysis and quadtree algorithm modules | Complete | 3880db5 | laplacian.py, quadtree.py, __init__.py, test_laplacian.py, test_quadtree.py |
| 2 | Upgrade FP4Exporter to SGFP4 v2 with variable blocks and backward compatibility | Complete | d86b81e | fp4_exporter.py, test_fp4_exporter.py |

## What Was Built

### laplacian.py — LaplacianWeightedError
- `compute(original_2d, reconstructed_2d, block_size) -> float` public API
- Adaptive pyramid levels per block size: skips Laplacian for 4x4/8x8 (plain MSE), 1 level for 16x16, 2 for 32x32, 3 for 64x64
- Uses `scipy.ndimage.gaussian_filter` with `sigma=2**level`, `mode='reflect'`
- Constructor accepts `sigma` and `mode` kwargs for tunability
- All operations in float32; returns plain Python float
- 10 passing tests

### quadtree.py — QuadtreeEncoder
- `encode(superblock_64x64) -> List[dict]` entry point
- Recursive `_try_block`: tries 64x64 first, splits into 4 children when error exceeds threshold
- Dual-mode selection per D-04: T158 preferred when `err_t158 <= (1.0 + delta) * err_fp4`
- Per-weight max error guard (Pitfall 4): rejects T158 when any weight error exceeds `5 * scale`
- Hysteresis (Pitfall 1): 20% improvement required for child split after parent acceptance; 10% slack
- Max recursion depth = 4, min_block_size = 4 (configurable)
- Accepts `fit_fp4` and `fit_t158` callable hooks for encoding
- 11 passing tests

### fp4_exporter.py — FP4Exporter v2
- **v1 backward compatibility preserved**: `export_weights(..., adaptive=False)` produces identical output
- **v2 adaptive export**: `export_weights(..., adaptive=True)` with magic header `b'SGF4'`, version byte `0x02`, superblock offset table
- `_encode_fp4_affine_variable` and `_encode_t158_affine_variable` for variable block sizes (4x4-64x64)
- `_payload_u32(size, mode)` returns correct uint32 counts per D-03
- Layout enum constants (0-5) per D-02; `_classify_layout(blocks)` method
- Superblock header: layout enum with reserved bits
- Per-block header: `_pack_half2(scale, bias)` with 4 LSB flags (mode, log reserved, reserved)
- 16-byte payload alignment per RESEARCH.md Pitfall 3
- `.sgfp4` extension for v2, `.fp4` for v1
- `export_to_file` writes manifest.json via ManifestBuilder for v2
- Stats include `effective_bpw` and `layout_distribution`
- CLI: `--adaptive` flag activates v2; default is v1
- 32 tests (8 v1 + 24 v2) passing

## Verification Results

```bash
python3 -m pytest gnus-poc/tests/test_laplacian.py gnus-poc/tests/test_quadtree.py \
  gnus-poc/tests/test_fp4_exporter.py gnus-poc/tests/test_manifest.py -x -q
# 56 passed in 0.89s
```

## Deviations from Plan

### Pre-committed Files

**1. Task 1 files already committed by parallel process**
- **Found during:** Task 1 commit attempt
- **Issue:** laplacian.py, quadtree.py, __init__.py, test_laplacian.py, test_quadtree.py were already committed at 3880db5 (by a parallel 03-03 plan execution that included these files)
- **Resolution:** Verified committed implementation matches plan requirements exactly. No re-commit needed. Task 1 is complete at 3880db5.

## Threat Flags

No new threat surface beyond what the plan's threat model covers (T-03-01 through T-03-05). All mitigations implemented:
- T-03-01: Tensor dimension validation + max recursion depth enforced in QuadtreeEncoder
- T-03-02: pathlib path construction in export_to_file
- T-03-03: SGF4 magic header + version byte for format detection
- T-03-04: Stats contain only aggregates, no weight values exposed
- T-03-05: ManifestBuilder unchanged per D-10, uses stdlib hashlib

## Self-Check: PASSED

- [x] `gnus-poc/quantize/laplacian.py` — FOUND
- [x] `gnus-poc/quantize/quadtree.py` — FOUND
- [x] `gnus-poc/quantize/fp4_exporter.py` — FOUND (upgraded)
- [x] `gnus-poc/quantize/__init__.py` — FOUND (updated exports)
- [x] `gnus-poc/tests/test_laplacian.py` — FOUND
- [x] `gnus-poc/tests/test_quadtree.py` — FOUND
- [x] `gnus-poc/tests/test_fp4_exporter.py` — FOUND (v2 tests added)
- [x] Commit 3880db5 — FOUND
- [x] Commit d86b81e — FOUND
