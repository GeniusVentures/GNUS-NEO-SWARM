# Phase 7: FP4 Quantization & Deployment — Context

**Gathered:** 2026-05-27 | **Status:** Ready

## Phase Boundary

FP4 binary export matching FP4 Ultra spec (docs/fp4_ultra_spec_v0_2_adaptive_ascii.md), manifest catalog, and C++ round-trip validation.

**In scope:** DEPLOY-01 (FP4 exporter), DEPLOY-02 (manifest catalog), DEPLOY-03 (round-trip validation)
**FP4 Ultra spec:** 64x64 macroblocks, fixed 2048-byte payload, FP4_AFFINE and T158_AFFINE modes, headers (packed half2 scale+bias), offsets (16-byte aligned with flag bits)
**Decisions:** Use MLX native quantize for FP4 blocks, follow spec exactly for binary layout, manifest.json per specialist
