# FP4 Ultra Specification (v0.2 - Adaptive Mixed-Bit, JPEG-like Macroblocks)

This spec defines **FP4 Ultra** as a GPU-friendly, macroblock (JPEG-like) weight codec with **adaptive per-block precision**.

Key ideas:

- Weights are tiled into **64x64 macroblocks**.
- Each block is encoded as either:
  - **FP4_AFFINE**: 4-bit signed codes with per-block **scale+bias** (half2), or
  - **T158_AFFINE**: ternary codes ("~1.58-bit class") with per-block **scale+bias** (half2).
- The encoder chooses FP4 vs ternary **per block** using an error test (optionally pyramid-weighted).
- Storage is content-addressable friendly (immutable blobs) and GPU-decoder friendly (fixed per-block payload).

> Important: "T158" in this spec means *ternary + scale+bias* (your scheme). It is **not** a BitNet compatibility mode.

---

## 0) Design Goals

- **Runs everywhere:** suitable for low-end devices; decode kernels can be written in Vulkan/MNN.
- **Consistent answers across devices:** devices differ in throughput/caching, not model precision tiers.
- **Fast decode:** prefer per-workgroup branching and vectorized bit-unpack.
- **Simple paging:** fixed per-block payload avoids variable-length scatter.

---

## 1) Tiling (Macroblocks)

Given a weight matrix `W` of shape `[O, I]`:

- Block size: `64x64`
- `tiles_y = ceil(O / 64)`
- `tiles_x = ceil(I / 64)`
- `B = tiles_y * tiles_x` blocks

`W` is **zero padded** to `(tiles_y*64, tiles_x*64)` then split into blocks.

Block `b` maps to `(by, bx)`:

```text
by = b // tiles_x
bx = b % tiles_x
block = W_padded[by*64:(by+1)*64, bx*64:(bx+1)*64]
```

---

## 2) Container Layout (On-Wire)

FP4 Ultra stores a quantized tensor as three parallel arrays plus a code blob:

- `headers[B]   : uint32`  (packed half2: scale_fp16 | bias_fp16)
- `offsets[B]   : uint32`  (byte offset into `codes_blob`, with **low 4 bits reserved as flags**)
- `codes_blob[] : bytes`   (concatenated per-block payloads)
- plus the original `(O, I)` shape in a higher-level container/manifest

### 2.1 Alignment & flags-in-offsets

Each block payload in `codes_blob` MUST start at a **16-byte aligned** address.

That guarantees `codesOffsetBytes % 16 == 0`, so the **low 4 bits** of the stored offset are free for flags.

- `offsets[b] = (codesOffsetBytes & ~0xF) | flags4`

On decode:

- `flags4 = offsets[b] & 0xF`
- `codesOffsetBytes = offsets[b] & ~0xF`

---

## 3) Header Definition (half2 scale+bias)

`headers[b] : uint32` stores two IEEE-754 FP16 values:

- high 16 bits: `scale_fp16` (S)
- low  16 bits: `bias_fp16`  (B)

In GLSL/Vulkan you can decode with:

```glsl
vec2 sb = unpackHalf2x16(headers[b]);
float S = sb.x;
float Bias = sb.y;
```

Semantics (both modes):

- `w_hat = S * code + Bias`

Notes:

- `S` SHOULD be non-negative.
- `Bias` is a learned/fit per-block offset (affine term).

---

## 4) Per-Block Flags (low 4 bits of offsets[b])

`flags4` bit layout:

- bit0 (0x1): **MODE**
  - 0 = FP4_AFFINE
  - 1 = T158_AFFINE
- bit1 (0x2): **ERROR_METRIC_HINT** (optional; informational)
  - 0 = L2-selected
  - 1 = Pyramid-selected
- bit2 (0x4): reserved
- bit3 (0x8): reserved

Only **bit0** is required for decoding.

---

## 5) Block Payload Formats

Every block stores a fixed **2048-byte payload** in `codes_blob` so kernels can use uniform addressing.

- Payload size per block: `2048 bytes = 512 * uint32`

### 5.1 FP4_AFFINE payload (MODE=0)

- Stores 4096 signed 4-bit codes `q in [-8, 7]`.
- Packing:
  - 8 codes per `uint32` word (4 bits each)
  - Total: `4096 * 4 bits = 16384 bits = 2048 bytes = 512 uint32`

Mapping:

- Each nibble is interpreted as int4 two's complement:
  - 0..7 => 0..7
  - 8..15 => -8..-1

Decode per element:

- `code = q`
- `w_hat = S * code + Bias`

### 5.2 T158_AFFINE payload (MODE=1)

T158 is a ternary codebook `t in {-1, 0, +1}` with affine decode.

To remain GPU-simple while still "~1.58-bit class", we store a fast packed ternary representation:

- **Canonical packing v0.2:** 2-bit codes per weight (fast decode)
  - 4096 weights x 2 bits = 8192 bits = **1024 bytes = 256 uint32**
- The remaining payload words `uint32[256..511]` MUST be 0.

2-bit mapping:

- `00` => 0
- `01` => +1
- `10` => -1
- `11` => reserved (decode as 0 for robustness)

Decode per element:

- `code = t` where `t in {-1,0,+1}`
- `w_hat = S * code + Bias`

Why this is still in the "1.58" family:

- The *semantic* codebook is ternary (3 states), and the affine sideband (scale+bias) improves fidelity.
- Packing is 2-bit for speed; future versions may introduce denser trit packing or entropy coding, but v0.2 prioritizes kernel simplicity.

---

## 6) Encoding (Quantization) Algorithm

Encoder runs per 64x64 block.

### 6.1 Candidate 1: FP4_AFFINE (v3-style)

Given block values `w` (4096 floats):

1) Choose an initial scale guess `S0`:

```python
abs_max = max(abs(w))
S0 = abs_max / 7.0 if abs_max > 0 else 1.0
```

2) Choose bias `Bias0`:

```python
Bias0 = mean(w)   # common starting point for affine fit
```

3) Optionally search over scale candidates (and optionally bias candidates) to minimize error.

A simple scale-only search (holding Bias fixed or recomputing it) is:

```python
cands = logspace(0.5*S0, 1.5*S0, 32)
for S in cands:
    q = clip(round((w - Bias)/S), -8, 7)
    w_hat = S*q + Bias
    err = metric(w, w_hat)
    keep best
```

4) Pack int4 codes to `uint32[512]`.

### 6.2 Candidate 2: T158_AFFINE (ternary)

Compute `S` and `Bias` to fit ternary codes.

A practical baseline:

- Set `Bias = median(w)` or `mean(w)`
- Work on centered values `u = w - Bias`
- Fit `S` from magnitude of centered values

Example:

```python
Bias = mean(w)
u = w - Bias
S = max(eps, mean(abs(u)))

# choose ternary codes by thresholding
# tau can be tuned; start with tau = 0.5*S
T = zeros_like(u)
T[u > +tau] = +1
T[u < -tau] = -1
w_hat = S*T + Bias
err = metric(w, w_hat)
```

Then pack `T` to 2-bit codes in `uint32[256]` and zero-fill the remaining 256 words.

### 6.3 Error Metric & Selection

Compute an error for each candidate:

- Default: L2

```python
err = norm(w_hat - w)
```

- Optional: Pyramid-weighted error (Gaussian/Laplacian), useful when you want to preserve low-frequency structure:

```python
err = pyramid_weighted_error(block2d, w_hat2d, levels=3, alphas=[...])
```

Selection rule (example):

```python
# Prefer ternary when it's close enough
if err_t158 <= (1.0 + delta) * err_fp4:
    choose T158_AFFINE
else:
    choose FP4_AFFINE
```

Recommended initial `delta`: 0.05 to 0.20.

---

## 7) Decode Procedure (Reference)

For block `b`:

1) Load:

- `h = headers[b]` => `S,Bias` via `unpackHalf2x16(h)`
- `off = offsets[b]`
- `flags4 = off & 0xF`
- `base = off & ~0xF` (byte offset)
- `mode = flags4 & 0x1`

2) Load payload `uint32 payload[512]` from `codes_blob` at `base`.

3) If `mode == 0` (FP4_AFFINE):

- Unpack int4 codes `q in [-8,7]`.
- `w_hat = S*q + Bias`.

4) If `mode == 1` (T158_AFFINE):

- Unpack 2-bit codes from `payload[0..255]`.
- Map to `t in {-1,0,+1}`.
- `w_hat = S*t + Bias`.

5) Write decoded 64x64 block into the padded tensor, then crop back to `(O,I)`.

---

## 8) Reference Pack/Unpack Code (Conceptual)

### 8.1 Pack T158 (2-bit)

```python
# T: int8[4096] in {-1,0,+1}
# returns uint32[256]

def pack_t158_2bit(T):
    out = np.zeros(256, dtype=np.uint32)
    for i in range(4096):
        t = int(T[i])
        if t == 0:
            bits = 0b00
        elif t == 1:
            bits = 0b01
        elif t == -1:
            bits = 0b10
        else:
            bits = 0b00

        word = i // 16
        shift = 2 * (i % 16)
        out[word] |= (np.uint32(bits) << np.uint32(shift))
    return out
```

### 8.2 Unpack T158 (2-bit)

```python
# payload: uint32[256]
# returns int8[4096] in {-1,0,+1}

def unpack_t158_2bit(payload):
    T = np.zeros(4096, dtype=np.int8)
    for i in range(4096):
        word = i // 16
        shift = 2 * (i % 16)
        bits = int((payload[word] >> np.uint32(shift)) & np.uint32(0b11))
        if bits == 0b00:
            T[i] = 0
        elif bits == 0b01:
            T[i] = 1
        elif bits == 0b10:
            T[i] = -1
        else:
            T[i] = 0
    return T
```

---

## 9) Notes on Gaussian/Laplacian Pyramids

Pyramids can be used for:

- scale search scoring inside FP4_AFFINE,
- and/or selection scoring between FP4_AFFINE and T158_AFFINE.

In prior experiments, pyramid-weighted scoring has been marginal vs plain L2 in some cases, but it remains a useful knob for structured real weights.

---

## 10) Versioning / Compatibility

- A decoder must support:
  - FP4_AFFINE (mode bit 0)
  - T158_AFFINE (mode bit 1)
- Future versions may add new modes using additional flag bits or reserved values.
- Keep the fixed 2048-byte payload for GPU simplicity unless/until compression pressure justifies variable-length.
