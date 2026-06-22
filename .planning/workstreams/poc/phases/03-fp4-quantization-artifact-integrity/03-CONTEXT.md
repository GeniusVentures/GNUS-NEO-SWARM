# Phase 3: FP4 Quantization & Artifact Integrity - Context

**Gathered:** 2026-06-21
**Status:** Ready for planning

<domain>
## Phase Boundary

Delivers SGFP4 v2 adaptive macroblock quantization — a variable effective bitrate weight codec with block sizes from 4×4 to 64×64, encode-side Laplacian error analysis for block-size selection, quadtree layout with superblock container, dual-mode per-block encoding (FP4_AFFINE + T158_AFFINE + Log mode), and provenance manifests with content hashing. Upgrades the existing fixed 64×64 SGFP4 exporter (`quantize/fp4_exporter.py`) to full adaptive SGFP4 v2 per PTDS v4 §6.

**Requirements:** QUANT-01 through QUANT-03 (updated to SGFP4 v2 spec)
</domain>

<decisions>
## Implementation Decisions

### Adaptive Macroblock Architecture
- **D-01:** Full quadtree implementation — encode tries largest block first (64×64), measures Laplacian-weighted error, splits into 4 children if error exceeds configurable threshold, recurses down to 4×4 minimum. Per PTDS v4 §6.1 and GNUS NEO Swarm Feasibility §11.
- **D-02:** Layout enum per 64×64 superblock: 0 = one 64×64, 1 = four 32×32s, 2 = sixteen 16×16s, 3 = sixty-four 8×8s, 4 = mixed quadtree, 5 = full 4×4 stamps. Per feasibility study layout enum design.
- **D-03:** Payload scales with block area — NOT fixed 2048 bytes. 4×4 FP4 = 8 bytes, 64×64 FP4 = 2048 bytes. Variable effective bitrate: smooth regions ~1.6 bpw (T158 large blocks), average ~2.7-3.3 bpw. Fixed payload only within the 64×64 superblock container for paging.

### Encoding Modes
- **D-04:** Dual-mode per block: FP4_AFFINE (4-bit signed codes [-8,7]) and T158_AFFINE (ternary {-1,0,+1}). Mode selected by error comparison: prefer T158 when `err_t158 <= (1.0 + delta) * err_fp4`. Per PTDS v4 §6.4.
- **D-05:** Log mode (bit 1 of offset): `x = sign(q) * exp(scale * q + bias)` in addition to Linear mode `x = scale * q + bias`. Per PTDS v4 §6.4. GPU/Vulkan shader performs fused decode+matmul with shared LUT.
- **D-06:** Per-block header: packed uint32 with FP16 scale + FP16 bias, 4 LSB offset flags (bit 0 = format, bit 1 = mode, bits 2-3 reserved).

### Error & Validation
- **D-07:** Laplacian pyramid analysis is encode-side only — NOT decoded at runtime. Separates low-frequency structure from high-frequency residual error, prevents outliers from dominating per-block scale, makes T158 more viable on residuals near zero. Per feasibility study.
- **D-08:** Error tolerance thresholds per macroblock size, configurable in `pipeline.yaml` under `fp4_export:`. Different thresholds per block size since larger blocks accumulate more error.
- **D-09:** Quantization results feed back into Phase 2 evaluation gating (`MetricStore` / `evaluate_and_persist`). SGFP4 error metrics (per-block MSE, effective bitrate, T158 ratio) become gate dimensions in `eval_gates`. Enables selecting distillation paths that map well to SGFP4.

### Provenance
- **D-10:** Existing `quantize/manifest.py` (ManifestBuilder) is sufficient for Phase 3 — no changes needed to provenance depth. Manifest already includes: model identity, adapter identity, quantization params, encoder version, timestamp, SHA256 content hash.

### Claude's Discretion
- Laplacian pyramid implementation (encode-side only — how to compute smooth field, residual)
- Quadtree split/merge algorithm specifics
- Error threshold defaults per block size
- Layout enum encoding in superblock header
- SGFP4 gate dimension design (how quantization error becomes an eval gate)
- Backward compatibility with existing SGFP4 v1 format
</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Project Planning
- `.planning/workstreams/poc/ROADMAP.md` — Phase 3 goal and updated success criteria (SGFP4 v2)
- `.planning/workstreams/poc/REQUIREMENTS.md` — QUANT-01 through QUANT-03

### SGFP4 v2 Spec
- `docs/PTSDV4_Training_Distillation.md` §6 — SGFP4 Hybrid v2 Adaptive Macroblock (full spec)
- `docs/GNUS NEO Swarm Feasibility.md` §11 (lines 262-418) — Adaptive macroblock design discussion, quadtree, layout enum, Laplacian encode, variable bitrate analysis
- `docs/architecture/16-sgfp4-format.md` — Original SGFP4 v1 spec (reference for backward compatibility)

### Existing Implementation
- `gnus-poc/quantize/fp4_exporter.py` — FP4Exporter (v1 — fixed 64×64, dual-mode, 2048-byte payload). Upgrade to v2, don't rewrite from scratch.
- `gnus-poc/quantize/manifest.py` — ManifestBuilder (keep as-is per D-10)
- `gnus-poc/config/pipeline.yaml` — Existing `fp4_export:` section (extend with error thresholds, layout config)
- `gnus-poc/eval/metric_store.py` — MetricStore from Phase 2 (extend with SGFP4 gate dimensions)

### Phase 2 Context (dependencies)
- `.planning/workstreams/poc/phases/02-training-distillation-quality/02-CONTEXT.md` — Evaluation gating (D-14 through D-17), auto-gating pattern to extend for SGFP4 metrics
</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- **`FP4Exporter`** (`quantize/fp4_exporter.py`): Already implements FP4_AFFINE + T158_AFFINE dual-mode, 64×64 macroblock partitioning, header packing (half2 scale+bias), offset flags. Extend with variable block sizes, Laplacian error analysis, quadtree recursion.
- **`ManifestBuilder`** (`quantize/manifest.py`): Keep as-is. Already covers SHA256 hashing, catalog generation, training metadata integration.
- **`MetricStore`** (`eval/metric_store.py`): Phase 2 structured persistence. Extend with SGFP4 gate dimensions (quantization error, effective bitrate, T158 ratio).
- **`Benchmarker.gate_check()`** (`eval/benchmarker.py`): Phase 2 auto-gating. Extend to include SGFP4 error thresholds.

### Established Patterns
- Two-layer config (endpoints/models) → quantization params in `pipeline.yaml` under `fp4_export:`
- Per-specialist overrides → quantization mode selection per specialist (Phase 1 D-02)
- Checkpoint validation per stage → quantize stage already validated by CheckpointValidator
- Auto-gating with consecutive failures → SGFP4 error gates follow same pattern

### Integration Points
- **Pipeline runner** (`pipeline/runner.py`): Quantize stage invokes `fp4_exporter.py`
- **Checkpoint validator** (`pipeline/checkpoint.py`): Validates FP4 directory + manifest.json — extend for SGFP4 v2 output validation
- **Evaluation gating** (`eval/benchmarker.py`): SGFP4 metrics become gate dimensions
- **Config loader** (`config/loader.py`): Extend `_validate_fp4_export()` for error thresholds per block size
</code_context>

<specifics>
## Specific Ideas

- **Layout enum encoding:** Superblock header stores layout enum (3 bits for values 0-5) alongside scale/bias.
  ```
  superblock_header (uint32): layout[2:0] | reserved | scale[15:?] | bias[15:?]
  ```
- **Error threshold config example:**
  ```yaml
  fp4_export:
    error_thresholds:
      64x64: { max_mse: 0.01, max_relative: 0.05 }
      32x32: { max_mse: 0.005, max_relative: 0.03 }
      16x16: { max_mse: 0.002, max_relative: 0.02 }
      8x8:   { max_mse: 0.001, max_relative: 0.01 }
      4x4:   { max_mse: 0.0005, max_relative: 0.005 }
    ternary_delta: 0.10
    log_mode_enabled: false  # Phase 5 Unsloth integration
  ```
- **SGFP4 gate dimensions:**
  ```yaml
  eval_gates:
    fp4_mse: { max: 0.01, consecutive_failures_to_block: 3 }
    fp4_effective_bitrate: { max: 4.0, consecutive_failures_to_block: 2 }
    fp4_t158_ratio: { min: 0.1, consecutive_failures_to_block: 2 }
  ```
</specifics>

<deferred>
## Deferred Ideas

- **Log mode (bit 1):** Implementation deferred to Phase 5 (PTDS v4 Unsloth Integration). Phase 3 reserves the flag bit and decode path but defaults to Linear mode only.
- **GPU/Vulkan shader decode:** Out of scope for gnus-poc Python POC — belongs to parent C++ repo.
- **NVFP4 comparison benchmarking:** Deferred to Phase 4 (Benchmark Evaluation) where quantized models are scored against established suites.
- **Full Laplacian pyramid decode at runtime:** Encode-side only per D-07. Runtime decode is simple table dispatch.
</deferred>

---

*Phase: 03-fp4-quantization-artifact-integrity*
*Context gathered: 2026-06-21*
