# Phase 03: FP4 Quantization & Artifact Integrity - Research

**Researched:** 2026-06-27
**Domain:** Adaptive weight quantization codec (SGFP4 v2) with quadtree block partitioning, Laplacian error analysis, dual-mode per-block encoding
**Confidence:** MEDIUM

## Summary

Phase 03 upgrades the existing `FP4Exporter` (fixed 64x64 macroblock, 2048-byte payload) to SGFP4 v2 adaptive macroblock quantization per PTDS v4 section 6. The upgrade transforms the exporter from "4-bit fixed quantization" into a **variable effective bitrate weight codec** with adaptive block sizing (4x4 through 64x64), encode-side Laplacian pyramid error analysis for block-size selection, quadtree-driven superblock layout, and dual-mode per-block encoding (FP4_AFFINE + T158_AFFINE with per-block error comparison).

The existing codebase provides a strong foundation: `FP4Exporter` already implements dual-mode encoding, half2 header packing, offset flags, and 2048-byte fixed payloads. The v2 upgrade adds quadtree recursion, Laplacian error analysis, variable block sizes with layout enum, and variable payloads that scale with block area. The manifest builder requires no changes (D-10).

All locked decisions (D-01 through D-10) are technically feasible with Python/numpy/scipy - no external C++ or GPU dependencies needed for encode. The primary risk is getting the quadtree split-merge logic and Laplacian pyramid computation correct, but both are well-understood algorithms with established numpy implementations.

**Primary recommendation:** Extend `fp4_exporter.py` incrementally - add Laplacian analysis first, then quadtree recursion on top of existing dual-mode blocks, then variable payload serialization with superblock layout enum. Validate against the existing fixed-64x64 path as a regression baseline.

## User Constraints (from CONTEXT.md)

### Locked Decisions

- **D-01:** Full quadtree implementation -- encode tries largest block first (64x64), measures Laplacian-weighted error, splits into 4 children if error exceeds configurable threshold, recurses down to 4x4 minimum. Per PTDS v4 section 6.1 and GNUS NEO Swarm Feasibility section 11.
- **D-02:** Layout enum per 64x64 superblock: 0 = one 64x64, 1 = four 32x32s, 2 = sixteen 16x16s, 3 = sixty-four 8x8s, 4 = mixed quadtree, 5 = full 4x4 stamps. Per feasibility study layout enum design.
- **D-03:** Payload scales with block area -- NOT fixed 2048 bytes. 4x4 FP4 = 8 bytes, 64x64 FP4 = 2048 bytes. Variable effective bitrate: smooth regions ~1.6 bpw (T158 large blocks), average ~2.7-3.3 bpw. Fixed payload only within the 64x64 superblock container for paging.
- **D-04:** Dual-mode per block: FP4_AFFINE (4-bit signed codes [-8,7]) and T158_AFFINE (ternary {-1,0,+1}). Mode selected by error comparison: prefer T158 when `err_t158 <= (1.0 + delta) * err_fp4`. Per PTDS v4 section 6.4.
- **D-05:** Log mode (bit 1 of offset) -- deferred to Phase 5, Phase 3 reserves flag bit
- **D-06:** Per-block header: packed uint32 with FP16 scale + FP16 bias, 4 LSB offset flags
- **D-07:** Laplacian pyramid analysis is encode-side only -- not decoded at runtime
- **D-08:** Error tolerance thresholds per macroblock size, configurable in pipeline.yaml
- **D-09:** SGFP4 error metrics become gate dimensions in eval_gates
- **D-10:** Existing manifest.py (ManifestBuilder) is sufficient -- no changes needed

### Claude's Discretion

- Laplacian pyramid implementation (encode-side only -- how to compute smooth field, residual)
- Quadtree split/merge algorithm specifics
- Error threshold defaults per block size
- Layout enum encoding in superblock header
- SGFP4 gate dimension design (how quantization error becomes an eval gate)
- Backward compatibility with existing SGFP4 v1 format

### Deferred Ideas (OUT OF SCOPE)

- Log mode (bit 1): Implementation deferred to Phase 5. Phase 3 reserves the flag bit.
- GPU/Vulkan shader decode: Out of scope for gnus-poc Python POC.
- NVFP4 comparison benchmarking: Deferred to Phase 4.
- Full Laplacian pyramid decode at runtime: Encode-side only per D-07.

## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| QUANT-01 | Ultra FP4 Format Compliance -- produce weight tensors with correct macroblock partitioning, headers, offsets, and codes_blob | Variable payload + superblock container with layout enum (section: Architecture Patterns) |
| QUANT-02 | Dual-Mode Support -- evaluate FP4_AFFINE and T158_AFFINE per block, select better mode | Existing dual-mode logic in fp4_exporter.py extended to variable block sizes (section: Code Examples) |
| QUANT-03 | Model Manifest with Provenance -- include source model, adapter, quantization params, version, timestamp, hash | D-10: ManifestBuilder sufficient as-is (section: Standard Stack) |

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Quadtree block partitioning | Python Encode (CPU) | -- | Encode-side only (D-07). No runtime decode of quadtree needed. |
| Laplacian error analysis | Python Encode (CPU) | -- | Encode-side only per D-07. Gaussian smoothing + residual computation at encode time. |
| FP4_AFFINE encoding | Python Encode (CPU) | -- | Per-block scale/bias fit + int4 packing. Already exists in v1. |
| T158_AFFINE encoding | Python Encode (CPU) | -- | Per-block ternary thresholding + 2-bit packing. Already exists in v1. |
| Superblock container layout | Python Encode (CPU) | -- | Serialization of layout enum + variable payloads into superblock pages. |
| Manifest generation | Python Encode (CPU) | -- | D-10: ManifestBuilder unchanged. SHA256 hashing of binary output. |
| SGFP4 eval gating | Python Encode (CPU) | -- | D-09: Quantization error metrics fed into eval gate dimensions. |
| Decode/Inference | GPU (Vulkan) | -- | OUT OF SCOPE for gnus-poc Python POC. Deferred to C++ parent repo. |
| Per-block-size config | YAML Config (static) | -- | D-08: Thresholds per block size in pipeline.yaml, loaded by ConfigLoader. |

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| numpy | 1.26.4 (verified) | Array math, block slicing, quantized code packing/unpacking | Already used by fp4_exporter.py; universal for numerical Python |
| scipy | 1.16.1 (verified) | `scipy.ndimage.gaussian_filter` for Laplacian pyramid smoothing | Only dependency needed for Gaussian convolution in pyramid construction; widely trusted |
| struct (stdlib) | -- | FP16 packing (half2 header) | Already used by fp4_exporter.py; no external dependency |
| yaml (PyYAML) | 6.0.2 (verified) | Config parsing for error thresholds | Already used by ConfigLoader; project standard |
| hashlib (stdlib) | -- | SHA256 content hashing for manifest | Already used by ManifestBuilder |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| pathlib (stdlib) | -- | File path handling for output artifacts | Already used throughout codebase |
| json (stdlib) | -- | Manifest and stats serialization | Already used by fp4_exporter.py and ManifestBuilder |
| logging (stdlib) | -- | Encode progress and warning logging | Project standard via spdlog-equivalent Python logging |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| scipy.ndimage.gaussian_filter | skimage.transform.pyramid_laplacian | skimage adds heavy dependency (scikit-image pulls in networkx, pillow, tifffile, imageio); scipy already installed |
| scipy.ndimage.gaussian_filter | Manual numpy convolution | More code to maintain; scipy's implementation is battle-tested and optimized |
| Custom quadtree from scratch | Existing quadtree libraries (pyquadtree) | No well-maintained Python quadtree library for numerical arrays; custom implementation is ~50 lines and simpler than dependency management |

**Installation:**
```bash
# No new packages required beyond what's already installed:
# numpy 1.26.4, scipy 1.16.1, pyyaml 6.0.2
# scipy.ndimage.gaussian_filter is imported at module level
```

**Version verification:**
```bash
python3 -c "import numpy; print('numpy', numpy.__version__)"  # 1.26.4
python3 -c "import scipy; print('scipy', scipy.__version__)"  # 1.16.1
python3 -c "import yaml; print('yaml', yaml.__version__)"      # 6.0.2
```

## Package Legitimacy Audit

| Package | Registry | Age | Downloads | Source Repo | slopcheck | Disposition |
|---------|----------|-----|-----------|-------------|-----------|-------------|
| numpy | PyPI | 19+ yrs | 100M+/wk | github.com/numpy/numpy | [OK] | Approved |
| scipy | PyPI | 20+ yrs | 50M+/wk | github.com/scipy/scipy | [OK] | Approved |
| pyyaml | PyPI | 15+ yrs | 80M+/wk | github.com/yaml/pyyaml | [OK] | Approved |

**Packages removed due to slopcheck [SLOP] verdict:** none

**Packages flagged as suspicious [SUS]:** none

All packages are mature, widely-used, and verified against PyPI via slopcheck. No new external dependencies are introduced beyond what the project already uses.

## Architecture Patterns

### System Architecture Diagram

```
                              ENCODE-SIDE (Python / CPU)
                              ==========================

  Weight Tensor (O x I float32)
           |
           v
  [Pad to 64×64 multiples]
           |
           v
  [Split into 64×64 superblocks]
           |
           v
  For each superblock:
  +-----------------------------------------------------------+
  |                                                           |
  |  1. Try 64×64 block                                       |
  |     - fit FP4_AFFINE and T158_AFFINE                      |
  |     - compute Laplacian-weighted error                    |
  |     - if error <= threshold: ACCEPT block at this size    |
  |                                                           |
  |  2. If error > threshold: SPLIT into 4 equal quadrants    |
  |     - recurse on each 32×32 child                         |
  |     - repeat down to 4×4 minimum                          |
  |                                                           |
  |  3. Determine layout enum from resulting tree             |
  |     - uniform size -> enum 0-3 or 5                       |
  |     - mixed sizes   -> enum 4 (mixed quadtree)            |
  |                                                           |
  +-----------------------------------------------------------+
           |
           v
  [Serialize superblock]
    - superblock header (uint32): layout enum + scale/bias
    - per-block headers (uint32 each): FP16 scale + FP16 bias
    - per-block payloads: variable-sized codes in codes_blob
           |
           v
  [Build SGFP4 v2 binary: superblocks concatenated]
           |
           v
  [ManifestBuilder.build() -> manifest.json]
           |
           v
  Output: {niche}.sgfp4 + manifest.json + stats.json


                              DECODE-SIDE (Vulkan GPU)
                              ========================
                              OUT OF SCOPE for gnus-poc
                              Belongs to C++ parent repo
```

### Recommended Project Structure

For the v2 upgrade, the existing file structure is sufficient. Add new modules for quadtree and Laplacian analysis:
```
gnus-poc/quantize/
├── __init__.py
├── fp4_exporter.py        # Upgrade to v2: quadtree + Laplacian + variable blocks
├── laplacian.py            # NEW: encode-side Laplacian pyramid analysis
├── quadtree.py             # NEW: quadtree split-merge algorithm
├── manifesto.py            # NEW: v2 container format serialization (optional, could stay in exporter)
└── manifest.py             # UNCHANGED per D-10
```

Alternatively, keep all logic in `fp4_exporter.py` with internal helper methods, following the existing pattern where both encode modes and header packing are methods of `FP4Exporter`.

### Pattern 1: Quadtree Adaptive Block Encoding

**What:** Recursive split algorithm that tries the largest block size first, measures error, and splits into 4 children if error exceeds threshold. Produces a tree of block regions at varying sizes (64x64 down to 4x4).

**When to use:** Core encode loop for every 64x64 superblock. Called once per superblock during export.

**Example (pseudocode from PTDS v4 section 6.1 + feasibility study section 11):**
```python
# Source: PTDS v4 §6.1, GNUS NEO Swarm Feasibility §11
def _encode_quadtree(self, block_64x64, thresholds):
    """Try largest block first, split if error exceeds threshold."""
    return self._try_block(block_64x64, 0, 0, 64, thresholds)

def _try_block(self, superblock, y, x, size, thresholds):
    """Recursive quadtree encode. Returns list of (y, x, size, mode, payload, header)."""
    region = superblock[y:y+size, x:x+size]
    threshold = thresholds.get(size, thresholds[4])  # default to 4x4 threshold

    # Try both modes
    fp4_result = self._encode_fp4_affine_variable(region)
    t158_result = self._encode_t158_affine_variable(region)

    # Select better mode (D-04)
    if t158_result["laplacian_error"] <= (1.0 + self._ternary_delta) * fp4_result["laplacian_error"]:
        selected = t158_result
        mode = MODE_T158_AFFINE
    else:
        selected = fp4_result
        mode = MODE_FP4_AFFINE

    # Check error threshold
    if selected["laplacian_error"] <= threshold["max_mse"] or size <= self._kMinBlockSize:
        # Accept block at this size
        return [(y, x, size, mode, selected["payload"], self._pack_half2(selected["scale"], selected["bias"]))]

    # Split into 4 children
    half = size // 2
    results = []
    for dy in (0, half):
        for dx in (0, half):
            results.extend(self._try_block(superblock, y + dy, x + dx, half, thresholds))
    return results
```

### Pattern 2: Laplacian Pyramid Error Analysis

**What:** Encode-side only. Separates low-frequency structure from high-frequency residual. Uses Gaussian smoothing to compute a "smooth base" layer, then measures quantization error on the residual rather than raw weights.

**When to use:** Called during `_try_block` to compute Laplacian-weighted error for block-size selection.

**Example:**
```python
# Source: PTDS v4 §6.7, feasibility study Laplacian discussion
# [ASSUMED] Exact alpha/levels parameters not specified in docs; defaults below
import numpy as np
from scipy.ndimage import gaussian_filter

def laplacian_weighted_error(self, original_2d, reconstructed_2d, levels=3):
    """Compute Laplacian pyramid-weighted error.
    
    W ≈ smooth_base + quantized_residual
    Separates low-freq structure from high-freq residual error.
    Prevents outliers from dominating per-block scale.
    
    Args:
        original_2d: 2D numpy array of original weights
        reconstructed_2d: 2D numpy array of quantized+dequantized weights
        levels: Number of pyramid levels (3 = 64x64->32x32->16x16 smooth)
    Returns:
        float: Laplacian-weighted MSE
    """
    residual = original_2d - reconstructed_2d
    smooth = original_2d.copy()
    
    total_error = 0.0
    weight_sum = 0.0
    
    for level in range(levels):
        # Compute smooth base via Gaussian
        sigma = 2.0 ** level  # increasing sigma per level
        smooth_base = gaussian_filter(smooth, sigma=sigma, mode='reflect')
        
        # High-frequency detail = smooth - smooth_base
        # Weight error by level importance (lower levels = more important)
        level_weight = 1.0 / (2.0 ** level)
        level_error = np.mean(residual ** 2)  # MSE of residual at this scale
        total_error += level_weight * level_error
        weight_sum += level_weight
        
        # Move to next level
        smooth = smooth_base[::2, ::2]  # downsample
        # Downsample residual to match
        if residual.shape[0] > 2:
            residual = residual[::2, ::2]
    
    return total_error / weight_sum if weight_sum > 0 else float(np.mean(residual ** 2))
```

### Pattern 3: Variable Payload Serialization with Superblock Container

**What:** Each 64x64 superblock has a layout enum header, followed by per-block headers and variable-length payloads. Total superblock size varies but is computed at encode time.

**When to use:** Final serialization step after quadtree encode completes for all superblocks.

**Example (layout enum from D-02 + D-06):**
```python
# Source: D-02, D-03, D-06; fp4_ultra_spec_v0_2_adaptive_ascii.md
# Per-block header: uint32 = packed half2 (FP16 scale | FP16 bias)
# 4 LSB offset flags: bit 0 = format, bit 1 = log mode (reserved), bits 2-3 = reserved

LAYOUT_UNIFORM_64 = 0    # one 64x64 block
LAYOUT_UNIFORM_32 = 1    # four 32x32 blocks
LAYOUT_UNIFORM_16 = 2    # sixteen 16x16 blocks
LAYOUT_UNIFORM_8  = 3    # sixty-four 8x8 blocks
LAYOUT_MIXED      = 4    # mixed quadtree
LAYOUT_FULL_4x4   = 5    # full 4x4 stamps (256 blocks)

# Payload sizes per block size and mode:
# 64x64 (4096 weights): FP4 = 2048 bytes (512 uint32), T158 = 1024 bytes (256 uint32)
# 32x32 (1024 weights): FP4 = 512 bytes (128 uint32), T158 = 256 bytes (64 uint32)
# 16x16 (256 weights):  FP4 = 128 bytes (32 uint32), T158 = 64 bytes (16 uint32)
# 8x8 (64 weights):     FP4 = 32 bytes (8 uint32), T158 = 16 bytes (4 uint32)
# 4x4 (16 weights):     FP4 = 8 bytes (2 uint32), T158 = 4 bytes (1 uint32)
```

### Pattern 4: Configurable Error Thresholds (D-08)

**What:** Per-block-size thresholds in pipeline.yaml under fp4_export. Larger blocks use relaxed thresholds (accumulate more total error), smaller blocks use tighter thresholds.

**When to use:** Loaded at encode time, passed to quadtree recursion.

**Example config extension:**
```yaml
# config/pipeline.yaml — extended fp4_export section
fp4_export:
  target_bits: 4
  block_size: 64
  # SGFP4 v2 adaptive macroblock thresholds (D-08)
  error_thresholds:
    64: { max_mse: 0.01, max_relative: 0.05 }
    32: { max_mse: 0.005, max_relative: 0.03 }
    16: { max_mse: 0.002, max_relative: 0.02 }
    8:  { max_mse: 0.001, max_relative: 0.01 }
    4:  { max_mse: 0.0005, max_relative: 0.005 }
  ternary_delta: 0.10       # D-04: prefer T158 when err_t158 <= (1+delta)*err_fp4
  min_block_size: 4         # D-01: recurse down to 4x4 minimum
  laplacian_levels: 3       # D-07: pyramid levels for error analysis
  log_mode_enabled: false   # D-05: reserved, Phase 5
```

### Pattern 5: SGFP4 Eval Gate Dimensions (D-09)

**What:** Quantization error metrics become dimensions in eval_gates, following the auto-gating pattern from Phase 2. Metrics include per-block MSE, effective bitrate, and T158 selection ratio.

**When to use:** After quantize stage completes; metrics are computed from export stats and fed into gate_check.

**Example gate config:**
```yaml
# Extension to eval section — SGFP4 gate dimensions
eval_gates:
  fp4_mse:
    max: 0.01
    consecutive_failures_to_block: 3
  fp4_effective_bitrate:
    max: 4.0
    consecutive_failures_to_block: 2
  fp4_t158_ratio:
    min: 0.05                  # At least 5% ternary utilization
    consecutive_failures_to_block: 2
```

### Anti-Patterns to Avoid

- **Computing Laplacian pyramid at decode time:** D-07 mandates encode-side only. Decode is simple table-driven dispatch. Do not add pyramid reconstruction to the decode path.
- **Fixed payload assumption in serialization:** D-03 mandates variable payload scaling with block area. Do not hardcode 2048-byte payloads in the v2 exporter.
- **Separate encode paths for v1 and v2:** Backward compatibility should be a simple flag or separate export method, not scattered conditionals throughout the encode logic.
- **Hardcoded error thresholds:** D-08 mandates configurable thresholds per block size. All threshold values must come from pipeline.yaml, not constants.
- **Mixing quadtree logic with serialization:** Keep the quadtree split-merge algorithm separate from payload packing. The quadtree decides what blocks exist; the serializer packs them.
- **Modifying ManifestBuilder:** D-10 explicitly says no changes needed. Do not add SGFP4 v2-specific fields to manifest.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Gaussian smoothing for Laplacian pyramid | Custom numpy convolution kernel | `scipy.ndimage.gaussian_filter` | Edge cases (boundary handling, mode selection, multi-dimensional), numerical stability, already installed |
| Quadtree spatial indexing | Custom grid-to-tree index | Simple recursive function with numpy slicing | Problem domain is 64x64 max, superblock-level; no need for general-purpose spatial index |
| FP16 packing | Custom bit manipulation | `struct.pack('<e', value)` + `struct.unpack('<H', ...)` | IEEE 754 half-precision is subtle; Python's struct module handles it correctly. Already used in v1. |
| Config validation | Custom YAML schema validator | Extend existing `ConfigLoader._validate_*()` pattern | Project convention; keeps validation logic centralized |
| Content hashing for manifest | Custom hash | `hashlib.sha256()` | Already used by ManifestBuilder; cryptographically standard |

**Key insight:** The quadtree algorithm for 64x64 superblocks is NOT a general-purpose spatial index. It's a fixed-dimension recursive split with at most 4 levels of depth (64->32->16->8->4). A simple recursive function with numpy array slicing is both simpler and more efficient than integrating a quadtree library. The total code for quadtree logic should be under 100 lines.

## Runtime State Inventory

> This is a greenfield phase with code modifications to existing files. No rename, rebrand, or refactor phase applies. No runtime state inventory needed.

**Verdict:** SKIPPED -- not a rename/refactor/migration phase.

## Common Pitfalls

### Pitfall 1: Quadtree Split Threshold Oscillation
**What goes wrong:** Block oscillates between accepting and rejecting at a given size because error is close to threshold. A 32x32 block that barely passes may have a 16x16 child that barely fails, causing unpredictable layout.

**Why it happens:** Fixed threshold with no hysteresis; Laplacian error on sub-blocks can exceed parent error due to local structure.

**How to avoid:** Apply hysteresis: if parent block was accepted, require child error to be significantly better (e.g., 20% improvement) before splitting. Accept parent block if `error <= threshold * 1.1` (10% slack) and minimum block size not yet reached.

**Warning signs:** Layout enum oscillating between 1 (four 32x32s) and 2 (sixteen 16x16s) across similar-weight superblocks.

### Pitfall 2: Laplacian Pyramid Over-smoothing Small Blocks
**What goes wrong:** Gaussian smoothing at 8x8 or 4x4 blocks erases all structure, making error measurement meaningless.

**Why it happens:** `gaussian_filter` with sigma >= 1.0 on a 4x4 array smooths to near-uniform values. The "residual" becomes essentially random noise.

**How to avoid:** Adapt Laplacian levels to block size. For blocks <= 8x8, skip Laplacian analysis entirely -- use plain L2 error. For 16x16 blocks, use 1 level. For 32x32, use 2 levels. For 64x64, use 3 levels.

**Warning signs:** All 4x4 and 8x8 blocks showing zero Laplacian error (because smoothing erased everything), causing split-or-not decisions to be random.

### Pitfall 3: Variable Payload Alignment Breaking GPU Decode
**What goes wrong:** Variable payload sizes create non-aligned offsets in codes_blob, breaking GPU memory access patterns.

**Why it happens:** Mixed block sizes in a superblock mean variable-length payloads. 16-byte alignment from v1 may not hold.

**How to avoid:** Pad each per-block payload to 16-byte alignment within the superblock. The layout enum tells the decoder how many blocks and what sizes to expect, so padding is invisible to decode. Store `(payload_size + 15) & ~15` per block.

**Warning signs:** Offsets not divisible by 16 in mixed-layout superblocks.

### Pitfall 4: T158 Dominance in High-Error Regions
**What goes wrong:** T158_AFFINE wins the error comparison on blocks where the residual has high variance but near-zero mean, producing large reconstruction errors on individual weights.

**Why it happens:** D-04 error comparison `err_t158 <= (1.0 + delta) * err_fp4` with high delta (0.10-0.20) favors T158. T158's ternary codes {-1,0,+1} can fit near-zero residuals well in aggregate but poorly on specific large-magnitude weights.

**How to avoid:** Add a per-weight max error check for T158: if any individual weight reconstruction error exceeds `kMaxPerWeightError` (e.g., 5 * scale), reject T158 regardless of aggregate error. This prevents outlier weights from being poorly represented.

**Warning signs:** T158 selected for blocks with max absolute weight > 3*scale, producing visible reconstruction artifacts.

### Pitfall 5: Config Loader Not Validating fp4_export Thresholds
**What goes wrong:** Malformed error_thresholds in pipeline.yaml cause runtime failures deep in the encode loop, with cryptic error messages.

**Why it happens:** ConfigLoader currently has no `_validate_fp4_export()` method. Invalid threshold values (negative MSE, missing block sizes) go undetected at load time.

**How to avoid:** Add `_validate_fp4_export()` to ConfigLoader following the existing pattern (e.g., `_validate_teacher()`). Validate: required block sizes (64,32,16,8,4), positive MSE values, ternary_delta in range [0.0, 1.0], min_block_size in {4,8,16,32,64}.

**Warning signs:** `KeyError` or `TypeError` during `_try_block` because thresholds dict is missing keys or has wrong types.

## Code Examples

Verified patterns from official sources:

### Existing Dual-Mode Encode (v1 - foundation for v2 extension)
```python
# Source: gnus-poc/quantize/fp4_exporter.py (existing v1 code)
# This block shows the existing dual-mode selection pattern that v2 extends
# with variable block sizes and Laplacian error

# In _encode_fp4_affine (existing):
flat = block.ravel().astype(np.float32)
scale, bias = self._fit_affine(flat)  # Scale search over 16 candidates
codes = np.clip(np.round((flat - bias) / scale), -8, 7).astype(np.int8)
w_hat = scale * codes.astype(np.float32) + bias
l2 = float(np.sqrt(np.mean((flat - w_hat) ** 2)))

# In _encode_t158_affine (existing):
centered = flat - bias
tau = 0.5 * scale
T = np.zeros(4096, dtype=np.int8)
T[centered > tau] = 1
T[centered < -tau] = -1

# Mode selection (existing - extends to variable sizes):
if t158_result["l2_error"] <= (1.0 + ternary_delta) * fp4_result["l2_error"]:
    mode = MODE_T158_AFFINE
```

### Variable Payload Size Calculation (v2 new code)
```python
# Source: D-03, PTDS v4 §6.3
# Payload scales with block area

def _payload_u32(self, size: int, mode: int) -> int:
    """Return number of uint32 words needed for a block of given size and mode.
    
    Args:
        size: Block edge size (4, 8, 16, 32, or 64)
        mode: MODE_FP4_AFFINE (0) or MODE_T158_AFFINE (1)
    Returns:
        Number of uint32 words needed
    """
    n_weights = size * size
    if mode == MODE_FP4_AFFINE:
        # 8 codes per uint32 (4 bits each)
        return n_weights // 8
    else:  # MODE_T158_AFFINE
        # 16 codes per uint32 (2 bits each)
        return n_weights // 16

# Payload sizes per block size:
# 64x64 (4096): FP4=512 u32, T158=256 u32
# 32x32 (1024): FP4=128 u32, T158=64 u32
# 16x16 (256):  FP4=32 u32,  T158=16 u32
# 8x8 (64):     FP4=8 u32,   T158=4 u32
# 4x4 (16):     FP4=2 u32,   T158=1 u32
```

### Backward Compatibility Strategy
```python
# Source: fp4_ultra_spec_v0_2_adaptive_ascii.md, v1 fp4_exporter.py
# v1 compatibility: when all superblocks use layout=0 (uniform 64x64),
# output is identical to v1 format

def export_weights(self, weights, niche_name, **kwargs):
    """Export with v1 or v2 mode based on adaptive flag."""
    if kwargs.get('adaptive', False):
        return self._export_v2_adaptive(weights, niche_name, **kwargs)
    else:
        # v1: fixed 64x64, 2048-byte payload, no quadtree
        return self._export_v1_fixed(weights, niche_name, **kwargs)
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Fixed 64x64 macroblock, 2048-byte payload (SGFP4 v1) | Adaptive 4x4-64x64 quadtree blocks, variable payload (SGFP4 v2) | PTDS v4, June 2026 | ~33% smaller models (2.7-3.3 bpw vs 4.0 bpw), better outlier handling |
| L2 error for block selection | Laplacian pyramid-weighted error (encode-only) | PTDS v4 §6.7 | Better preserves low-frequency structure, makes T158 more viable on residuals |
| Fixed per-block payload | Variable payload scaling with block area | D-03 | Enables true variable bitrate; metadata overhead proportional to content complexity |
| Single layout (uniform 64x64) | Layout enum 0-5 per superblock | D-02 | Decoder dispatch via simple enum; enables mixed-size superblocks |

**Deprecated/outdated:**
- **Fixed 2048-byte payload assumption:** Replaced by variable payload in v2 (D-03). All new code must compute payload size from block dimensions.
- **L2-only error metric:** Still used as fallback for small blocks, but Laplacian-weighted error is primary for blocks >= 16x16.
- **Hardcoded block_size=64 constant:** Still valid for superblock outer page, but internal blocks are variable. Code referencing MACROBLOCK_SIZE must distinguish superblock (always 64) from internal block (variable).

## Assumptions Log

> All claims tagged [ASSUMED] in this research. Planner and discuss-phase use this to identify decisions needing user confirmation.

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | Laplacian pyramid uses Gaussian smoothing with sigma=2^level and 3 levels | Architecture Patterns: Pattern 2 | Pyramid may not effectively separate low/high frequency for weight tensors vs. images. Specific sigma values need empirical tuning. |
| A2 | Quadtree hysteresis of 10% slack prevents oscillation | Common Pitfalls: Pitfall 1 | Too much slack causes under-splitting (blocks too large, error too high). Too little slack causes over-splitting (too many small blocks, metadata overhead). |
| A3 | Per-weight max error check for T158 at 5*scale prevents outlier artifacts | Common Pitfalls: Pitfall 4 | Threshold too tight rejects valid T158 blocks, inflating bitrate. Threshold too loose allows visible artifacts. |
| A4 | Default error thresholds (0.01/0.005/0.002/0.001/0.0005) are reasonable for weight tensors | Architecture Patterns: Pattern 4 | Thresholds are speculative. Actual optimal values depend on weight distribution characteristics of trained specialists. |
| A5 | scipy.ndimage.gaussian_filter mode='reflect' is appropriate boundary handling for weight blocks | Architecture Patterns: Pattern 2 | 'reflect' may create artificial symmetry at block edges. 'constant' or 'nearest' might be better for weight tensors. |
| A6 | `MetricStore` (referenced in CONTEXT.md) does not yet exist in codebase | Standard Stack | If Phase 2 creates MetricStore before Phase 3 executes, integration path changes. Currently only evaluator.py and benchmarker.py exist in eval/. |
| A7 | Phase 2 will produce `eval/metric_store.py` with `evaluate_and_persist` method before Phase 3 needs it | Architecture Patterns: Pattern 5 | If Phase 2 does not implement MetricStore, Phase 3 must implement its own quantization metric persistence. |

## Open Questions

1. **Laplacian pyramid sigma and level parameters**
   - What we know: PTDS v4 §6.7 describes Laplacian pyramid conceptually but does not specify numerical parameters (sigma per level, number of levels)
   - What's unclear: Optimal sigma values for weight tensors vs natural images; whether to use fixed sigma or scale-dependent sigma
   - Recommendation: Start with sigma=2^level (2.0, 4.0, 8.0 for levels 0,1,2) and 3 levels. Make configurable via `laplacian_levels` in pipeline.yaml. Tune empirically.

2. **Error threshold defaults for weight tensors**
   - What we know: D-08 mandates per-block-size thresholds in config; CONTEXT.md provides example values
   - What's unclear: Whether example values (max_mse: 0.01 for 64x64, 0.0005 for 4x4) are appropriate for trained LoRA adapter weights which may have different magnitude distribution than full model weights
   - Recommendation: Ship with example defaults from CONTEXT.md. Tune during Phase 4 benchmark evaluation. Make easily configurable.

3. **Backward compatibility file format detection**
   - What we know: v1 uses fixed 64x64 with 2048-byte payloads; v2 uses variable superblock layout
   - What's unclear: Whether to use a different file extension (.sgfp4 vs .fp4), magic bytes, or version field in container header for format detection
   - Recommendation: Add a 4-byte magic header + version byte at start of binary output. Use `.sgfp4` extension for v2 to avoid ambiguity with v1 `.fp4` files. Old `.fp4` files remain readable by v1 decoder.

4. **Superblock total size computation for paging**
   - What we know: D-03 states fixed payload within 64x64 superblock for paging
   - What's unclear: Whether to pad each superblock to a fixed total size (wasteful but simpler paging) or allow truly variable superblock sizes (efficient but requires an offset table)
   - Recommendation: Use a superblock offset table at the start of the file: `superblock_offsets[B]` as uint32 array, where each offset points to the start of that superblock's data. This achieves both paging and variable-size efficiency.

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| Python 3.11+ | Entire phase | Yes | 3.11.6 | -- |
| numpy | Array math, block slicing, code packing | Yes | 1.26.4 | -- |
| scipy | scipy.ndimage.gaussian_filter for Laplacian | Yes | 1.16.1 | Manual numpy convolution if scipy unavailable |
| pyyaml | Config loading for error thresholds | Yes | 6.0.2 | -- |
| struct (stdlib) | FP16 packing for half2 headers | Yes | stdlib | -- |
| hashlib (stdlib) | SHA256 for manifest integrity | Yes | stdlib | -- |

**Missing dependencies with no fallback:** none

**Missing dependencies with fallback:** none

All required dependencies are already installed in the Python environment. No new package installations are needed.

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest (detected via project conventions; verify with `pip list | grep pytest`) |
| Config file | none -- see Wave 0 |
| Quick run command | `python -m pytest gnus-poc/tests/test_fp4_exporter.py -x -q` |
| Full suite command | `python -m pytest gnus-poc/tests/ -x -q` |

### Phase Requirements to Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| QUANT-01 | Export produces valid SGFP4 v2 binary with variable blocks, correct headers, offsets, codes_blob | unit | `pytest gnus-poc/tests/test_fp4_exporter.py::test_v2_adaptive_export -x` | No (Wave 0) |
| QUANT-01 | Quadtree split-merge produces correct block sizes for known-error inputs | unit | `pytest gnus-poc/tests/test_quadtree.py::test_split_on_high_error -x` | No (Wave 0) |
| QUANT-01 | Laplacian error analysis computes valid error for 64x64 block | unit | `pytest gnus-poc/tests/test_laplacian.py::test_error_computation -x` | No (Wave 0) |
| QUANT-02 | Dual-mode selection picks T158 when err_t158 <= (1+delta)*err_fp4 | unit | `pytest gnus-poc/tests/test_fp4_exporter.py::test_mode_selection_delta -x` | No (Wave 0) |
| QUANT-02 | FP4_AFFINE codes in range [-8,7]; T158_AFFINE codes in {-1,0,+1} | unit | `pytest gnus-poc/tests/test_fp4_exporter.py::test_code_ranges -x` | No (Wave 0) |
| QUANT-03 | Manifest includes required fields: model_name, niche, base_model_ref, adapter_ref, quantization_params, encoder_version, timestamp | unit | `pytest gnus-poc/tests/test_manifest.py::test_manifest_fields -x` | No (Wave 0) |
| QUANT-03 | Manifest SHA256 matches binary content | integration | `pytest gnus-poc/tests/test_manifest.py::test_manifest_integrity -x` | No (Wave 0) |

### Sampling Rate
- **Per task commit:** `python -m pytest gnus-poc/tests/test_fp4_exporter.py -x -q`
- **Per wave merge:** `python -m pytest gnus-poc/tests/ -x -q`
- **Phase gate:** Full suite green before `/gsd:verify-work`

### Wave 0 Gaps
- [ ] `gnus-poc/tests/test_fp4_exporter.py` -- covers QUANT-01, QUANT-02 (v2 adaptive export, mode selection)
- [ ] `gnus-poc/tests/test_quadtree.py` -- covers quadtree split-merge algorithm
- [ ] `gnus-poc/tests/test_laplacian.py` -- covers Laplacian error computation
- [ ] `gnus-poc/tests/test_manifest.py` -- covers QUANT-03 (manifest fields + integrity)
- [ ] `gnus-poc/tests/conftest.py` -- shared fixtures (dummy weight tensors, config loader)
- [ ] Framework install: `pip install pytest` -- verify availability

All test files are new (Wave 0). No existing test infrastructure covers quantization.

## Security Domain

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | no | -- |
| V3 Session Management | no | -- |
| V4 Access Control | no | -- |
| V5 Input Validation | yes | Validate weight tensor dimensions (non-negative, within bounds), config thresholds (positive, reasonable ranges), file paths (path traversal prevention) |
| V6 Cryptography | yes | SHA256 for manifest integrity (already implemented in ManifestBuilder). No custom crypto. |
| V7 Error Handling | yes | Config validation errors at load time (not mid-encode). Clear error messages for malformed inputs. |

### Known Threat Patterns for Python/numpy Quantization

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| Malformed weight tensor causing infinite quadtree recursion | Denial of Service | Validate tensor dimensions before encode; enforce max recursion depth (4 levels); timeout on encode |
| Path traversal in output file paths | Tampering | Validate niche_name against allowed specialist list; use pathlib for safe path construction |
| YAML config injection via pipeline.yaml | Tampering | PyYAML safe_load (already used by ConfigLoader); validate all numeric fields are within expected ranges |
| Integer overflow in payload size calculation | Tampering | Use Python's arbitrary-precision ints (no overflow by default); validate block sizes are powers of 2 in [4,64] |
| SHA256 collision in manifest integrity | Spoofing | SHA256 is collision-resistant for this use case; manifest is integrity check, not authentication |

## Sources

### Primary (HIGH confidence)

- `docs/PTSDV4_Training_Distillation.md` §6 -- SGFP4 Hybrid v2 Adaptive Macroblock full spec (section 6.1-6.8). Defines macroblock hierarchy, layout enum, block payload sizes, per-block header format, effective bitrate table, encode-side Laplacian error selection, NVFP4 comparison.
- `docs/GNUS NEO Swarm Feasibility.md` §11 (lines 262-461) -- Adaptive macroblock design discussion. Quadtree algorithm rationale, layout enum design, Laplacian pyramid explanation, variable bitrate analysis, superblock container concept.
- `docs/fp4_ultra_spec_v0_2_adaptive_ascii.md` -- Original FP4 Ultra v0.2 container spec. Defines headers/offsets/codes_blob layout, alignment & flags-in-offsets, half2 scale+bias, per-block flags, FP4_AFFINE/T158_AFFINE payload formats, encode/decode procedures.
- `gnus-poc/quantize/fp4_exporter.py` -- Existing FP4Exporter v1 implementation. Dual-mode encode, half2 packing, offset flags, 2048-byte fixed payload, export_to_file flow.
- `gnus-poc/quantize/manifest.py` -- ManifestBuilder (unchanged per D-10). SHA256 hashing, catalog generation, field structure.
- `gnus-poc/config/pipeline.yaml` -- Current fp4_export section with target_bits and block_size. Extension point for error_thresholds.
- `gnus-poc/config/loader.py` -- ConfigLoader with validation pattern to extend for fp4_export thresholds.
- `gnus-poc/pipeline/checkpoint.py` -- CheckpointValidator with _validate_quantize() to extend for v2 output.

### Secondary (MEDIUM confidence)

- `gnus-poc/eval/benchmarker.py` -- Benchmarker for gate dimensions. Needs SGFP4 metrics integration.
- `gnus-poc/eval/evaluator.py` -- SpecialistEvaluator. Provides context for how eval metrics flow.
- `gnus-poc/pipeline/runner.py` -- PipelineRunner integration point (line 56: quantize stage invokes fp4_exporter.py).
- `.planning/workstreams/poc/ROADMAP.md` -- Phase 3 success criteria and dependency on Phase 2.
- `.planning/workstreams/poc/REQUIREMENTS.md` -- QUANT-01 through QUANT-03 acceptance criteria.

### Tertiary (LOW confidence)

- WebSearch results for quadtree compression, Laplacian pyramid, and numpy binary serialization provided training-knowledge-level responses rather than specific paper citations. Concepts are well-established (quadtree dates to 1970s, Laplacian pyramid to Burt & Adelson 1983) but specific implementation parameters for weight quantization are novel to SGFP4.
- [ASSUMED] Laplacian pyramid sigma values, hysteresis thresholds, per-weight error bounds (see Assumptions Log A1-A5).

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH -- all packages verified on PyPI via slopcheck, already installed in project environment. No new dependencies.
- Architecture: MEDIUM -- quadtree and Laplacian pyramid are well-understood algorithms, but specific parameters (sigma, thresholds, hysteresis) for weight tensors are novel to SGFP4 and need empirical validation during Phase 4 benchmarking. Locked decisions D-01 through D-10 provide clear architectural constraints.
- Pitfalls: MEDIUM -- identified pitfalls are based on analysis of algorithm behavior and existing codebase patterns. Actual quantization artifacts depend on specialist weight distributions which won't be available until Phase 2 completes.

**Research date:** 2026-06-27
**Valid until:** 2026-07-27 (30 days; stable domain, no fast-moving external dependencies)
