# sgfp4_tiny.mnn — Provenance Recipe (Phase 13, Plan 13-02, D-06 / T-13-03)

Committed fixture: `sgfp4_tiny.mnn` (26,448 bytes — inline weights only, ~5 orders of
magnitude below MNN's 2 GB `_largeModel()` externalization threshold, so weights can
never be silently externalized into a `.weight` sidecar).

## Source model

`sgfp4_tiny_src.onnx` (not committed; reproducible from the spec below):

- Architecture: `Conv(1→8, 9×9)` → `Conv(8→8, 9×9)` → `Relu`
- Input: `input` FLOAT32 `[1, 1, 76, 76]` (5,776 elements)
- Output: `output` FLOAT32 `[1, 8, 60, 60]`
- Conv weights: 648 and **5,184** elements — the second exceeds the >4096-element
  requirement (D-06/A2) so the `InsertSGFP4Dequant` graph-rewrite pass has at least
  one full 64×64 macroblock to encode
- Weights: deterministic `numpy.random.RandomState(42/43)` normal × 0.1; zero biases
- Built with Python `onnx` 1.18.0 (opset 13, IR version 8), `onnx.checker`-validated

## Conversion command (manual, one-time — 2026-09-02)

```
W:\gnus\GeniusNetwork\thirdparty\MNN\.build\Release\MNNConvert.exe \
    -f ONNX \
    --modelFile sgfp4_tiny_src.onnx \
    --MNNModel sgfp4_tiny.mnn \
    --sgfp4
```

Notes:

- `--sgfp4` is the quadtree-adaptive SGFP4 v2 weight-quantization pass
  (`tools/converter/source/common/cli.cpp:230`, mutually exclusive with
  `--weightQuantBits`/`--hqq`/`--fp16`).
- The vendored build at `thirdparty/MNN/.build/Release/MNNConvert.exe` carries the
  `--sgfp4` flag; the older `C:\MNNTools\MNNConvert.exe` does NOT — always use the
  vendored one.
- Verification that the flag took effect: byte-level comparison against a plain
  (no `--sgfp4`) conversion of the same source differs (26,448 vs 24,284 bytes), and
  the op-list flatbuffer contains exactly one `OpType_SGFP4Dequant` (= 605) entry
  (see `AssertModelContainsSgfp4DequantOp` in `test_sgprocessing_pipeline.cpp`,
  which asserts this at test time per D-07 — a silently all-FP32 fixture cannot
  pass vacuously).

## Input fixture

`sgfp4_tiny_input.raw` — 23,104 bytes = 5,776 FLOAT32 values
(`numpy.random.RandomState(7)`, uniform ±0.1), matching the model's declared
`[1, 1, 76, 76]` input shape. The schema declares FLOAT32 input format (the SGFP4
quantization lives in the model weights, NOT the input encoding — D-08: never
conflate the SGFP4 weight format with an input `format` value).
