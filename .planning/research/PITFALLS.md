# Domain Pitfalls: ELM Training & Distillation Pipeline

**Domain:** ML training/distillation pipeline for specialist SLMs
**Researched:** 2026-05-27
**Sources:** Codebase audit (gnus-poc/**/*.py), ChatGPT vetting doc, Grok vetting doc, .planning/ codebase analysis

---

## Critical Pitfalls

Mistakes that cause rewrites, silent data corruption, or project-killing cost overruns.

### Pitfall 1: Chat Template Mismatch Between Data Prep and Training

**What goes wrong:** `prepare_datasets.py` hardcodes the Qwen2.5 `<|im_start|>` / `<|im_end|>` chat template format, but `train_specialists_mlx.py` loads Qwen3-30B-A3B models which use a different chat template. The model receives tokens it does not understand as instruction boundaries, causing it to treat system/user/assistant markers as literal text rather than structural delimiters.

**Evidence in code:** `prepare_datasets.py` lines 128-154 format every niche with `<|im_start|>system\n...<|im_end|>\n<|im_start|>user\n...<|im_end|>\n<|im_start|>assistant\n...<|im_end|>`. `train_specialists_mlx.py` lines 35-41 use `Qwen3-30B-A3B-Instruct-2507-bf16` which uses Qwen3's template (different from Qwen2.5).

**Why it happens:** The data preparation was written for Qwen2.5 (the original train_specialists.py used Qwen3-7B), then the MLX script was upgraded to 30B-A3B models without updating the format.

**Consequences:** The specialist learns to parrot control tokens instead of understanding the instruction format. Perplexity looks fine during training but generation quality is garbage: the model emits `<|im_start|>` tags in responses. Silent failure: no error is raised.

**Prevention:**
1. Use `tokenizer.apply_chat_template()` from the actual loaded tokenizer instead of hand-rolling format strings.
2. After format change, run a smoke test: load tokenizer, apply template to a known prompt, decode back, verify it contains model-appropriate tokens.
3. Store the chat template hash in training metadata so you know which format was used.

**Detection:** Load a trained adapter, run `tokenizer.apply_chat_template([{"role": "user", "content": "test"}])` on the actual base model tokenizer, and compare the token IDs to what is in your JSONL files. If they differ significantly, you have a mismatch.

**Phase to address:** Phase 1 (Data Pipeline) -- before any new specialist training starts.

---

### Pitfall 2: Skip-On-Existing Logic Produces False Training Completions

**What goes wrong:** `train_specialists_mlx.py` (lines 218-230) checks if `adapters.safetensors` exists and skips training if it does. But a partial/corrupt training run that crashed at iteration 200/1000 still wrote `adapters.safetensors` (and milestone checkpoints). The skip logic incorrectly treats this as "done" and moves on, producing a severely undertrained specialist with no warning.

**Evidence in code:** The check at line 223 tests only for file existence: `if final_adapter.exists():`. The `save_every: 200` setting at line 59 means milestone files (`0000200_adapters.safetensors`, etc.) are written. An interrupted run at iteration 400 would have both `adapters.safetensors` and `0000400_adapters.safetensors` but only 40% of training complete.

**Consequences:** Specialists are deployed with 20-60% of their intended training iterations. They appear to work (model loads, generates text) but perform significantly below baseline. Silent corruption: no error, no warning, just bad models masquerading as complete.

**Prevention:**
1. Check for the milestone file matching `iters` (e.g., `0001000_adapters.safetensors`) rather than just the generic `adapters.safetensors`.
2. Validate `training_metadata.json` exists AND its `iters` field matches the current config's `iters`.
3. Add a `--force-retrain` flag that deletes existing adapters before starting.
4. Write a post-training validation script that runs the specialist on held-out test data and checks metrics.

**Detection:** Check each specialist's `training_metadata.json`: if `iters` < configured `iters` (1000), the training was incomplete.

**Phase to address:** Phase 2 (Training Pipeline hardening) -- before scaling beyond 5 specialists.

---

### Pitfall 3: DeepSeek API Cost Explosion Without Rate Limiting or Budget Control

**What goes wrong:** The current codebase has NO teacher model API calls. When synthetic data generation is added (Phase 3), calls to DeepSeek v4 pro API will be made without rate limiting, retry logic, or cost tracking. A bug in the prompt template loop could fire thousands of API calls before anyone notices, generating a $500-$5000 surprise bill.

**Why it happens:** The ChatGPT vetting doc explicitly warns that API costs for synthetic data can "quietly bankrupt a project." 1M training samples at 400 tokens output each = ~400M output tokens. At DeepSeek v4 pro pricing, this is potentially hundreds to thousands of dollars.

**Consequences:** Budget blowout. Worse: if a loop bug generates malformed prompts that the API rejects but still charges for, costs accrue with zero usable data.

**Prevention:**
1. Add a **hard budget cap**: a configurable dollar limit that stops all API calls when exceeded.
2. Implement **exponential backoff with jitter** on 429 (rate limit) responses, with `Retry-After` header parsing.
3. Add **dry-run mode** that counts how many API calls WOULD be made without actually calling.
4. Log every API call with: prompt token count, completion token count, cost estimate, timestamp. Write to a cost audit file.
5. Test with a small batch (10 prompts) first, verify cost, then scale.

**Detection:** Cost overrun is detected when the credit card is charged. Prevention is the only viable strategy. Add a pre-generation cost estimate.

**Phase to address:** Phase 3 (Distillation & Synthetic Data) -- before any API integration code is written.

---

### Pitfall 4: Common Pile Source Metadata Field Name Instability

**What goes wrong:** Both `prepare_datasets.py` (line 72) and `extract_source_niches.py` (lines 88-94) attempt to extract the source field with fallback logic: `meta.get('pile_set_name', meta.get('source', 'unknown'))`. But the Common Pile dataset metadata schema varies between `monology/pile-uncopyrighted` and `EleutherAI/pile`, AND between different versions. A field rename upstream silently causes ALL samples to be classified as `'unknown'` source.

**Evidence in code:** `extract_source_niches.py` lines 88-94 has fallback logic: first tries `pile_set_name`, then `source`, then `dataset`. If none match, source = `'unknown'`. The niche assignment at lines 103-111 checks `if source in niche_config['sources']`: if source is always `'unknown'`, zero samples get assigned to any niche.

**Consequences:** All niche extraction silently produces zero samples per niche. The "viable" check reports "Too small" for every niche. Users think the dataset is too small, but the real problem is invisible metadata drift.

**Prevention:**
1. After loading the dataset, inspect the first example's metadata keys and verify the expected field exists. If not, log ALL available metadata keys and abort with a clear error.
2. Store a `dataset_schema_version` in the saved niche JSON that captures which metadata field was used.
3. Add a CI-like validation: after extraction, assert that `unknown` source count is below a threshold (e.g., <10% of total). If above, fail loudly.

**Detection:** Check `source_counts` in `source_based_niches.json`: if `unknown` is the dominant source, metadata extraction failed.

**Phase to address:** Phase 1 (Data Pipeline) -- hardening existing extraction before adding new niches.

---

### Pitfall 5: Train/Validation/Test Contamination from Streaming Dataset Reseeding

**What goes wrong:** `prepare_datasets.py` streams from Common Pile with a fresh connection each time (lines 42-56). It extracts samples for a niche until reaching `target_size`, then moves to the next niche. No deduplication across niches. A StackExchange document could appear in both `qa_technical` AND `code` niches.

**Evidence in code:** `prepare_datasets.py` lines 63-64 stream from the beginning for EACH niche: `for i, example in enumerate(dataset)`. Each niche starts at index 0 and scans forward independently. No cross-niche deduplication.

**What makes this critical:** If specialists share 15-30% of their training data, evaluations will overstate differentiation. You will think specialists are "learning their domain" when they are actually learning overlapping content. When deployed, overlapping specialists produce redundant outputs: the swarm's value proposition (specialization) collapses.

**Prevention:**
1. After extracting all niche samples, compute Jaccard overlap between niches (text hash or MinHash-based dedup). Report overlaps >5%.
2. If overlap is high, deduplicate: keep document in the niche with highest source-affinity match, remove from others.
3. For the POC at minimum: log the overlap percentage in metadata so evaluators know the contamination level.

**Detection:** Compute text hash collisions between `train.jsonl` files of different niches.

**Phase to address:** Phase 2 (Training Pipeline) -- before training next generation of specialists.

---

### Pitfall 6: Teacher Model Licensing Contamination of Student Models

**What goes wrong:** Using DeepSeek v4 pro API (a closed, commercial API) to generate synthetic training data for LoRA fine-tuning of open-source student models. Most frontier API Terms of Service explicitly prohibit using outputs to train competing models. The ChatGPT vetting doc documents this clearly: OpenAI, Anthropic, Google all forbid derivative training.

**Why it happens:** The project design specifies "DeepSeek v4 pro API" as the teacher model. The instructor acknowledged this risk: "now I might have to use only open source models as some APIs may limit or not allow retraining like this."

**Consequences:** If GNUS.ai becomes successful, API providers can issue cease-and-desist, demand model takedowns, or pursue legal action. All specialists trained on contaminated data become legal liabilities. This is a **project existential risk**, not just a technical bug.

**Prevention:**
1. **Use ONLY open-source models with permissive licenses for training data generation.** Recommended: DeepSeek-V3 distilled models, Llama 3.1 405B distilled, Qwen 2.5/3 series, Mixtral 8x7B.
2. If using DeepSeek API at all, limit to: prompt style inspiration, evaluation benchmarks only, routing validation. Never for direct training data.
3. Document the provenance chain for every training example: which model generated it, under what license, when.
4. Add a `data_provenance.json` alongside each specialist's training data.

**Detection:** This is a policy/compliance risk, not a runtime bug. Prevention is in the architecture decision.

**Phase to address:** Phase 3 (Distillation) -- this decision must be made BEFORE any API integration code is written.

---

## Moderate Pitfalls

### Pitfall 7: OOM on Apple Silicon During LoRA Training with 30B-A3B Models

**What goes wrong:** `train_specialists_mlx.py` uses `mlx-community/Qwen3-30B-A3B-Instruct-2507-bf16`, a ~30B parameter model (3B active with MoE). Even with LoRA (`rank: 16`, `num_layers: 16`), loading the full model into Apple Silicon unified memory can exhaust available RAM. On a Mac Studio M2 Ultra with 64GB, the base model alone occupies ~55GB in bf16, leaving ~9GB for activations, optimizer states (AdamW), and gradients.

**Evidence in code:** Line 54: `batch_size: 4`, line 60: `num_layers: 16`, line 53: `optimizer: "adamw"` (AdamW stores 2x parameter states). No memory estimation beyond `grad_checkpoint: True`.

**Consequences:** Training crashes with an MLX out-of-memory error 5-10 minutes in. No partial results saved. Must restart with smaller config.

**Prevention:**
1. Before training, run a memory estimator that accounts for base model size, LoRA parameters, optimizer states, and activation memory.
2. Start with `batch_size: 1`, verify it runs, then increase.
3. Reduce `num_layers` to 8 for first run.
4. Use `fine_tune_type: "qlora"` (4-bit base model quantization) to cut base model memory by ~75%.
5. Add a pre-flight check: estimate peak memory vs available, abort if >85% of available.

**Detection:** Loads model successfully, crashes during `train_model()` with "Out of memory" or "mmap failed".

**Phase to address:** Phase 2 (Training Pipeline) -- hardware-specific tuning.

---

### Pitfall 8: LoRA Rank Too High or Too Low for Niche Specialization

**What goes wrong:** The code uses `rank: 16` uniformly across all 5 specialists (line 68 of both training scripts). But niche complexity varies dramatically: `medical` (PubMed abstracts, dense terminology) needs more capacity than `encyclopedic` (Wikipedia, broad knowledge). A rank that is too low underfits complex niches; a rank too high wastes memory and overfits to noise.

**Evidence in code:** Lines 67-71 set identical `lora_parameters` for all specialists: `rank: 16, dropout: 0.05, scale: 20.0`. No per-specialist override. `scale: 20.0` is unusually high (typical is 1.0-4.0).

**Consequences:**
- **Rank too low (e.g., 4 on medical):** LoRA cannot capture enough domain-specific patterns. Specialist converges to near-base-model performance.
- **Rank too high (e.g., 64 on encyclopedic):** Overfits to training set surface patterns. Validation loss diverges from training loss.
- High `scale` value amplifies LoRA contributions vs base model, causing catastrophic forgetting of general language abilities.

**Prevention:**
1. Run A/B test: train same specialist at rank 4, 8, 16, 32 and compare validation loss. Pick the rank where validation loss stops improving.
2. Use per-niche rank configuration: `medical: 32, code: 24, qa_technical: 16, patents: 12, encyclopedic: 8`.
3. Drop `scale` to 2.0-4.0 range.
4. Monitor ratio `||LoRA_weights|| / ||base_weights||`: if >0.1, LoRA is too dominant.

**Detection:** Specialists where validation loss is flat or increasing after 200+ iterations, or where generated outputs are nonsensical.

**Phase to address:** Phase 2 (Training Pipeline) -- experimentation framework.

---

### Pitfall 9: Temperature Calibration Failure in Distillation

**What goes wrong:** When distilling teacher model outputs to student models, the temperature parameter controls softness of the probability distribution. Too high (T > 5) washes out knowledge: all tokens look equally likely. Too low (T < 1) makes distribution too sharp: student only learns teacher's top-1 predictions.

**Why it matters:** This pipeline will distill teacher knowledge into 1-3B student models. Temperature must be tuned per specialist: medical distillation needs different temperature than code distillation because output distributions have different entropy.

**Consequences:** Student model learns a degraded version of teacher knowledge. Student converges to producing safe-but-generic outputs (high T) or overconfident wrong answers (low T).

**Prevention:**
1. Run temperature sweep: T in {1, 2, 3, 5, 8, 10} on a calibration set. Measure KL divergence between teacher and student. Pick T that minimizes KL.
2. Use dynamic temperature: start at T=5 (broad knowledge transfer), anneal to T=1 (sharp specialization).
3. Log temperature schedule and KL divergence curves per specialist.

**Detection:** Student model outputs are overly generic or overly confident and wrong. KL divergence between teacher and student is above 0.5.

**Phase to address:** Phase 3 (Distillation) -- core implementation.

---

### Pitfall 10: Silent Failures in Long-Running Training Jobs

**What goes wrong:** Training 5 specialists sequentially takes 2.5-5 hours. If specialist 3 crashes at iteration 600, the `try/except` at lines 233-240 catches the exception, prints a traceback, and **continues to specialist 4**. The user sees a wall of training output, misses the single error line, and thinks all 5 specialists trained successfully.

**Evidence in code:** Lines 233-240:
```python
try:
    meta = train_specialist(niche)
    all_meta[niche] = meta
except Exception as e:
    print(f"Error training {niche}: {e}")
    traceback.print_exc()
    continue  # silently moves to next specialist
```

**Consequences:** Training appears to complete normally. User deploys specialists 1, 2, 4, 5 without realizing specialist 3 is missing or corrupted.

**Prevention:**
1. After training loop, assert `len(all_meta) == len(SPECIALISTS)`. If not, print prominent error block at the bottom.
2. Write `TRAINING_STATUS.json` with per-specialist status: SUCCESS/FAILED/SKIPPED/CRASHED, with error details.
3. After training, load each adapter and run a single inference. Flag any specialist that fails to load or produces empty output.
4. Use structured logging (JSON lines) so errors are programmatically detectable.

**Detection:** After training: `ls models/specialists_mlx/*/adapters.safetensors | wc -l` should equal `len(SPECIALISTS)`.

**Phase to address:** Phase 2 (Training Pipeline) -- error handling hardening.

---

### Pitfall 11: Non-Reproducible Training Runs from Hardcoded Relative Paths

**What goes wrong:** Both training scripts use relative paths like `DATA_DIR = "data/specialists"` and `OUTPUT_DIR = "models/specialists_mlx"`. Running from a different CWD produces mysterious "file not found" errors.

**Evidence in code:** Lines 45-46 use bare relative paths. `prepare_datasets.py` line 27 loads from `'data/analysis/source_based_niches.json'` -- a relative path assuming CWD is `gnus-poc/`.

**Consequences:** Training succeeds from `gnus-poc/` but fails from `gnus-poc/models/`. CI/CD pipelines or orchestration scripts break.

**Prevention:**
1. Resolve all paths relative to script location: `SCRIPT_DIR = Path(__file__).resolve().parent`; `PROJECT_ROOT = SCRIPT_DIR.parent`.
2. Accept `--data-dir` and `--output-dir` CLI arguments as overrides.
3. Log absolute paths being used at startup.

**Detection:** Script fails with `FileNotFoundError` or `DatasetNotFoundError` when run from unexpected CWD.

**Phase to address:** Phase 1 (Data Pipeline) -- path hygiene.

---

### Pitfall 12: Training Metadata Does Not Capture Validation Metrics

**What goes wrong:** `training_metadata.json` saves only: niche, base_model, duration_minutes, iters, batch_size, num_layers, lora_parameters. **No validation loss, no perplexity, no accuracy metric, no final training loss.** You cannot determine if a specialist is good or bad from the metadata alone.

**Evidence in code:** Lines 187-198 show metadata structure: purely config capture, zero performance metrics.

**Consequences:** Six months later, comparing specialist v2 vs v3 or debugging performance differences requires re-evaluating from scratch. No way to detect training regressions without manual inspection.

**Prevention:**
1. Capture `final_train_loss`, `final_val_loss`, `best_val_loss` and the iteration where it was achieved.
2. Capture `perplexity` on a held-out validation set.
3. Save loss curve as JSON array for later plotting.
4. Run a quick benchmark after training: 10 responses on test prompts, compute BLEU/ROUGE, save results.

**Detection:** `training_metadata.json` has no `val_loss` field.

**Phase to address:** Phase 2 (Training Pipeline) -- before training the next batch.

---

## Minor Pitfalls

### Pitfall 13: `trust_remote_code=True` Security Risk

**What goes wrong:** Both training scripts pass `tokenizer_config={"trust_remote_code": True}` to `mlx_utils.load()`. This allows the model's `tokenizer_config.json` to execute arbitrary Python code during loading. A compromised model on HuggingFace could run arbitrary code on your machine.

**Prevention:** Inspect `tokenizer_config.json` before loading. Pin model versions with commit hashes.

**Phase to address:** Phase 1 (Security) -- low priority for POC internal use.

---

### Pitfall 14: Tokenizer/Model Loading Inconsistency Between Training and Inference

**What goes wrong:** Training loads models via MLX tokenizer. The deployed C++ engine loads via MNN with SentencePiece tokenizer. If tokenizers produce different token IDs for the same text, LoRA adapters are applied to wrong positions.

**Prevention:**
1. Export MLX tokenizer vocabulary and compare with SentencePiece model.
2. Test round-trip: encode with MLX, decode with SentencePiece, compare.
3. Verify that chat template special tokens map to same IDs in both tokenizers.

**Phase to address:** Phase 4 (Integration) -- when MLX-trained adapters are ported to MNN.

---

### Pitfall 15: FP4 Quantization Compatibility with MLX-Trained LoRA Weights

**What goes wrong:** FP4 pyramid-based quantization (from Grok vetting doc) assumes weight matrices can be treated as 2D images. MLX LoRA weights are low-rank decomposition matrices (A x B), not full-rank. Their structure may not be amenable to pyramid-based quantization.

**Prevention:**
1. Test FP4 quantization on MLX-trained LoRA weights before building an automated pipeline.
2. Measure MSE between FP16 LoRA output and FP4-quantized LoRA output on a calibration set.
3. If degradation >5% MSE, consider quantizing AFTER merging LoRA into base weights.

**Phase to address:** Phase 5 (Quantization) -- depends on completing FP4 codec integration.

---

### Pitfall 16: Hardcoded Niche Format Strings Produce Brittle Training Data

**What goes wrong:** `prepare_datasets.py` uses fragile string splitting for `qa_technical` niche: `if 'Q:' in text and 'A:' in text`. This fails when "Q:" or "A:" appears in the content body. The fallback treats the entire text as an assistant response, losing Q&A structure.

**Evidence:** Lines 135-141. Any StackExchange post where "Q:" or "A:" appears in body text is incorrectly split.

**Consequences:** Garbled instruction/response pairs. Specialist learns to produce truncated or reversed responses.

**Prevention:**
1. Use source metadata to determine format (StackExchange has structured `question`/`answer` fields).
2. Define `NichelFormatter` class per niche instead of inline conditionals.
3. After formatting, validate each example has non-empty user and assistant sections.

**Phase to address:** Phase 1 (Data Pipeline) -- alongside chat template fix.

---

### Pitfall 17: No Versioning for Datasets or Adapters

**What goes wrong:** Datasets and adapters are saved without version numbers. Re-running `prepare_datasets.py` silently overwrites previous datasets. Training runs on new data, old adapters still exist: you cannot determine which dataset version produced which adapter.

**Evidence:** `prepare_datasets.py` line 172-183: `niche_dir = f"{OUTPUT_DIR}/{niche_name}"` with no version. `train_specialists_mlx.py` line 156: `adapter_path = f"{OUTPUT_DIR}/{niche}"` with no version.

**Consequences:** Cannot reproduce results. Cannot roll back. Cannot A/B test dataset versions. Adapter-dataset provenance is lost.

**Prevention:**
1. Include version (date or hash) in paths: `data/specialists/<niche>/v20260527/`.
2. Store dataset hash (SHA256 of concatenated JSONL files) in training metadata.
3. Add `--version` flag to both scripts.

**Phase to address:** Phase 1 (Data Pipeline) -- before any re-extraction or re-training.

---

## Integration-Specific Pitfalls (Python POC to C++ Engine)

### Pitfall 18: Chat Template Format Incompatibility Between Python and C++

**What goes wrong:** Python pipeline uses MLX tokenizer with Qwen3 chat template. C++ engine uses SentencePiece with a `.model` file. If tokenization does not match byte-for-byte, C++ engine feeds tokens to the model that do not correspond to what LoRA adapters were trained on.

**Prevention:**
1. Export MLX tokenizer full vocabulary as JSON.
2. Generate identical token sequences in Python and C++ for 100 test prompts. Diff token ID sequences: any mismatch is a problem.
3. Use the EXACT SAME tokenizer model file in both Python and C++.

**Phase to address:** Phase 4 (Integration) -- when adapters are first loaded in C++.

---

### Pitfall 19: LoRA Adapter Format Compatibility with MNN

**What goes wrong:** MLX saves LoRA adapters as safetensors with MLX-specific key naming. MNN expects weights in its own format. No off-the-shelf MLX-LoRA to MNN converter exists.

**Prevention:**
1. Build and test MLX to MNN adapter conversion as a separate, well-tested component BEFORE integrating into the full pipeline.
2. After conversion, run inference on 50 test prompts in both MLX and MNN. Compare token-by-token output. Any divergence >0% is a bug.
3. Consider exporting full model (base + merged LoRA) to ONNX then to MNN, rather than loading LoRA adapters separately in MNN.

**Phase to address:** Phase 4 (Integration) -- key integration risk.

---

### Pitfall 20: FP4 Weight Layout Mismatch Between Pipeline and Engine

**What goes wrong:** Grok vetting doc describes JPEG-style macro-block FP4 with 64x64 tiles and 32-bit scale headers. Existing `FP4Codec.hpp` may use a different layout. If Python pipeline produces one format and C++ engine expects another, model produces garbage output without crashing (silent corruption).

**Prevention:**
1. Define FP4 format as a spec document (tile size, scale storage format, byte ordering, header structure).
2. Write round-trip test: Python quantizes, saves FP4, C++ loads, dequantizes, compare MSE against original FP16. Target: MSE < 1e-6.
3. Include format version byte in FP4 header.

**Phase to address:** Phase 5 (Quantization) -- before deploying FP4-quantized models.

---

## Phase-Specific Warnings

| Phase Topic | Likely Pitfall | Mitigation |
|-------------|---------------|------------|
| Data extraction (Phase 1) | Chat template mismatch (#1), metadata field drift (#4), cross-niche contamination (#5) | Use tokenizer template, validate metadata schema, run dedup |
| Data preparation (Phase 1) | Hardcoded formats (#16), no versioning (#17), relative paths (#11) | NichelFormatter classes, versioned directories, absolute paths |
| Training (Phase 2) | OOM (#7), LoRA rank wrong (#8), skip-on-existing (#2), silent failures (#10), missing metrics (#12) | Pre-flight memory check, A/B test ranks, check milestone files, structured logging, capture val loss |
| Distillation (Phase 3) | API cost explosion (#3), licensing contamination (#6), temperature miscalibration (#9) | Hard budget cap, open-source teacher only, temperature sweep |
| Evaluation (Phase 3) | No metrics in metadata (#12), overlapping eval data (#5) | Capture val loss per specialist, dedup before split |
| Integration (Phase 4) | Tokenizer mismatch (#18), adapter format incompatibility (#19), FP4 layout mismatch (#20) | Tokenizer export+diff, round-trip tests, format spec |
| Quantization (Phase 5) | LoRA-specific quantization (#15), format mismatch (#20) | Test on actual LoRA weights, define format spec first |

---

## Summary of Most Critical Pitfalls (by Impact x Likelihood)

1. **Chat template mismatch (Pitfall 1):** HIGH impact, HIGH likelihood -- already present in current code
2. **Skip-on-existing false completion (Pitfall 2):** HIGH impact, MEDIUM likelihood -- present in code, triggered by crash
3. **API cost explosion (Pitfall 3):** HIGH impact, HIGH likelihood -- when API code is added without safeguards
4. **Teacher licensing contamination (Pitfall 6):** EXISTENTIAL impact, HIGH likelihood -- if API is used for training data
5. **Silent training failures (Pitfall 10):** HIGH impact, MEDIUM likelihood -- present in code, easy to miss
6. **Cross-niche data contamination (Pitfall 5):** MEDIUM impact, HIGH likelihood -- undermines specialization value
7. **Missing validation metrics (Pitfall 12):** MEDIUM impact, HIGH likelihood -- no way to compare or detect regression
8. **OOM on Apple Silicon (Pitfall 7):** HIGH impact, MEDIUM likelihood -- 30B models push hardware limits

---

*Sources: codebase audit of gnus-poc/*.py (2026-05-27), ChatGPT Idea Vetting for Swarm SLMs (lines 1206-1343), Grok Vetting for Swarm SLMs, .planning/ codebase analysis*
