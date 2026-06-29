---
phase: 04-benchmark-evaluation
reviewed: 2026-06-28T19:30:00Z
depth: standard
files_reviewed: 22
files_reviewed_list:
  - gnus-poc/eval/benchmark_mlx_model.py
  - gnus-poc/eval/benchmark_runner.py
  - gnus-poc/eval/benchmark_config.py
  - gnus-poc/eval/benchmark_tasks.py
  - gnus-poc/eval/benchmark_fingerprint.py
  - gnus-poc/eval/benchmark_trends.py
  - gnus-poc/eval/benchmark_repair.py
  - gnus-poc/eval/benchmarker.py
  - gnus-poc/eval/metric_store.py
  - gnus-poc/distill/synthetic.py
  - gnus-poc/config/benchmarks/mmlu.yaml
  - gnus-poc/config/benchmarks/humaneval.yaml
  - gnus-poc/config/benchmarks/medmcqa.yaml
  - gnus-poc/config/benchmarks/gpqa.yaml
  - gnus-poc/config/benchmarks/pubmedqa.yaml
  - gnus-poc/config/benchmarks/bigpatent.yaml
  - gnus-poc/config/benchmarks/specialist_mapping.yaml
  - gnus-poc/config/pipeline.yaml
  - gnus-poc/tests/test_benchmark_runner.py
  - gnus-poc/tests/test_benchmark_fingerprint.py
  - gnus-poc/tests/test_benchmark_trends.py
  - gnus-poc/tests/test_benchmark_repair.py
  - gnus-poc/tests/test_benchmarker.py
findings:
  critical: 6
  warning: 11
  info: 5
  total: 22
status: issues_found
---

# Phase 04: Code Review Report

**Reviewed:** 2026-06-28T19:30:00Z
**Depth:** standard
**Files Reviewed:** 22 (10 modules, 8 YAML configs, 5 test files)
**Status:** issues_found

## Summary

Phase 4 wires EleutherAI `lm-evaluation-harness` into the POC distillation pipeline via an `MLXBenchmarkModel` wrapper, per-benchmark YAML configs, a fingerprint module, additive benchmark gating on `Benchmarker`, MetricStore benchmark persistence, bootstrap-CI trend analysis, and an advisory-only repair reporter. The D-10 invariant holds: `benchmark_repair.py` contains no config-writing code (grep-verified). The D-02/D-09/D-11 abstractions are sound, and security posture is good (`yaml.safe_load` exclusively, manifest SHA256 streaming with size cap, fail-open corruption handling, no eval/exec/shell).

However, six blockers will prevent the benchmark gate from working end-to-end as shipped. The most serious is a **filename-contract mismatch** between `MetricStore.record_benchmark_results` / `BenchmarkRunner.run_benchmarks` (which write `{niche}_{benchmark}_{ts}.json`) and `Benchmarker._find_canonical_results` / `_find_previous_canonical` / `_sgfp4_regression_check` (which glob `{niche}_canonical_*.json`). The gate will therefore always report "No canonical benchmark results available yet" when consuming production outputs. On top of that, the `MLXBenchmarkModel` has a **tokenization off-by-one** in `loglikelihood`/`loglikelihood_rolling` (reads `logits[i]` instead of `logits[i-1]`), a **context-overflow bug** that returns `-inf` for every long multiple-choice request, and `simple_evaluate()` is called with a single `num_fewshot` derived from the first task only — silently breaking the per-benchmark shot protocol that D-02 depends on.

Other notable defects: `_extract_primary_score` does not recognize `rouge1`/`rougeL` (so the patents blocking benchmark always scores `None` → defaults to `0.0` → fails the hard floor); `is_degradation_significant` can declare a "significant" regression from a single aggregate delta (n=1, no variance); and the runner populates the D-02 fingerprint with hardcoded `"stub"` / `"n/a"` placeholders that `validate_fingerprint` accepts as valid, defeating reproducibility tracking.

## Critical Issues

### CR-01: Filename-contract mismatch — Benchmarker gate never sees MetricStore/runner output

**File:** `gnus-poc/eval/benchmarker.py:466`, `gnus-poc/eval/benchmarker.py:584`, `gnus-poc/eval/benchmarker.py:813`
**Issue:**
`MetricStore.record_benchmark_results` (metric_store.py:237-241) writes files named `{niche}_{benchmark}_{YYYYMMDD-HHMMSS-microseconds}.json` (e.g. `medical_mmlu_20260628-143000-000001.json`), and `BenchmarkRunner.run_benchmarks` (benchmark_runner.py:326) writes `{niche}_{task_name}_{ts}.json` (e.g. `medical_mmlu_20260628-143000.json`). Neither filename contains the literal token `canonical` or `quantized`.

But the three Benchmarker consumers glob for those literal tokens:
- `_find_canonical_results`: `pattern = f"{niche_name}_canonical_*.json"` (line 466)
- `_sgfp4_regression_check`: `pattern = f"{niche_name}_canonical_*unquantized*.json"` (line 584)
- `_find_previous_canonical`: `pattern = f"{niche_name}_canonical_*.json"` (line 813)

Result: `gate_check_benchmarks` always falls through to the `"No canonical benchmark results available yet"` branch (line 681) for any file produced by the runner or MetricStore, so the entire D-08 gate is inert in production. The test suite passes only because `test_benchmarker.py::_write_benchmark_result` (line 291) hand-crafts filenames with the `_canonical_quantized` / `_canonical_unquantized_adapter` tokens that match the benchmarker's glob — a test fixture that does not reflect the real producer contract.

**Fix:** Pick one filename contract and make producers + consumers honor it. Minimal change is to update the consumers to glob the actual producer pattern and filter by the `mode` field (D-03 already requires `mode == "canonical"` filtering, which the code does defensively at line 479 and 597):
```python
def _find_canonical_results(self, niche_name: str, quantized_only: bool = False):
    pattern = f"{niche_name}_*_*.json"
    candidates = sorted(
        (p for p in self._benchmarks_dir.glob(pattern)
         if "_baseline" not in p.stem and "_comparison" not in p.stem
         and "_sgfp4_metrics" not in p.stem),
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )
    for path in candidates:
        try:
            with path.open("r", encoding="utf-8") as f:
                payload = json.load(f)
        except (json.JSONDecodeError, OSError):
            continue
        if payload.get("mode") != "canonical":
            continue
        # quantized vs unquantized must come from a payload field, not the filename.
        # Add a "quantized": bool field at write time, OR embed the token in the filename.
        if quantized_only and payload.get("quantized") is False:
            continue
        return payload
    return None
```
This requires adding a `quantized` field to the runner/MetricStore payloads (or embedding `canonical`/`quantized`/`unquantized` tokens in the producer filenames). Either way the contract must be reconciled before the gate can fire.

### CR-02: MLX loglikelihood reads logits at wrong position (off-by-one)

**File:** `gnus-poc/eval/benchmark_mlx_model.py:160-175`, `250-253`, `392-395`
**Issue:**
For a causal LM, `logits[0, i, :]` is the next-token distribution conditioned on input tokens `[0..i]` — i.e. it predicts the token at position `i+1`. To get the log-probability of the token *at* position `i`, you must read `logits[0, i-1, :]`.

Both code paths read the wrong index:
- `loglikelihood` (line 251): `pos = context_len + i; target = token_ids[pos]; self._tok_logprob(logits, pos, target)` — reads `logits[0, pos, :]`, which predicts `token_ids[pos+1]`, not `token_ids[pos]`.
- `loglikelihood_rolling` (line 392-394): `for i in range(1, len(token_ids)): target = token_ids[i]; self._tok_logprob(logits, i, target)` — same off-by-one.

Effect: every loglikelihood score (and every `is_greedy` flag, computed the same way at line 189) is shifted by one token. For multiple-choice tasks (MMLU, MedMCQA, GPQA, PubMedQA) this corrupts the per-continuation logprob sums that drive `acc`/`acc_norm`, making benchmark scores meaningless. The bug is silent because no test exercises real MLX inference (all runner tests mock `_run_lm_eval`).

**Fix:**
```python
# loglikelihood (around line 250):
for i in range(cont_len):
    pos = context_len + i            # token position we want the logprob OF
    target = token_ids[pos]
    # logits[pos-1] predicts token at pos (causal next-token convention)
    self._tok_logprob(logits, pos - 1, target)
    if not self._is_greedy(logits, pos - 1, target):
        all_greedy = False

# loglikelihood_rolling (around line 392):
for i in range(1, len(token_ids)):
    target = token_ids[i]
    self._tok_logprob(logits, i - 1, target)
    if not self._is_greedy(logits, i - 1, target):
        all_greedy = False
```
Also gate `pos - 1 >= 0` (it always is here because `context_len + i >= 1`), but add an explicit assert to lock in the invariant.

### CR-03: Long-context loglikelihood requests silently return -inf

**File:** `gnus-poc/eval/benchmark_mlx_model.py:225-237`
**Issue:**
```python
token_ids = self._encode(full_text)
context_ids = self._encode(context)

if len(token_ids) > self._max_length:
    token_ids = token_ids[:self._max_length]    # truncated

context_len = len(context_ids)                   # NOT truncated
cont_len = len(token_ids) - context_len

if cont_len <= 0:
    results.append((float("-inf"), False))
    continue
```
`context_ids` is computed from the untruncated context. If `len(context) >= self._max_length` (very common for 5-shot MMLU and multi-document MedMCQA prompts), then after truncation `len(token_ids) == self._max_length <= len(context_ids)`, so `cont_len = max_length - context_len < 0`, and EVERY request in the batch returns `logprob = -inf, is_greedy = False`. The model effectively scores all continuations as impossible, so `argmax` over `-inf == -inf` picks the first choice — benchmark accuracy collapses to ~25% (random for 4-choice) at best, and the gate fails every blocking benchmark on every specialist.

The same bug pattern exists in spirit for the truncation strategy itself: truncating from the front of `token_ids` would discard the context-continuation boundary entirely. The current head-truncation also drops the *beginning* of the context, which for many-shot prompts removes the few-shot examples — defeating D-02's shot protocol.

**Fix:** Truncate symmetrically with the continuation preserved, and recompute `context_len` against the truncated context:
```python
full_ids = self._encode(full_text)
context_ids = self._encode(context)

# Reserve room for the continuation; truncate the CONTEXT from the left
# (keep the most recent context tokens + the full continuation).
cont_len_guess = max(1, len(full_ids) - len(context_ids))
if len(full_ids) > self._max_length:
    keep_ctx = self._max_length - cont_len_guess
    if keep_ctx < 1:
        keep_ctx = 1
    # left-truncate context, keep continuation intact
    context_ids = context_ids[-keep_ctx:]
    token_ids = context_ids + full_ids[len(context_ids) - len(context_ids):]
    # simpler & robust: re-slice full_ids so that its tail (continuation) is preserved
    token_ids = full_ids[-self._max_length:]
    context_len = len(context_ids)
else:
    token_ids = full_ids
    context_len = len(context_ids)
cont_len = len(token_ids) - context_len
```
Note also that independent re-encoding of `context` and `context+continuation` is itself unsound for tokenizers where `encode(a+b) != encode(a)+encode(b)` (BPE merges at the boundary). The robust pattern is to find `context_ids` as the longest common prefix of `encode(context)` and `encode(context+continuation)`.

### CR-04: Per-benchmark num_fewshot is ignored — only the first task's shot count is applied

**File:** `gnus-poc/eval/benchmark_runner.py:360-371`
**Issue:**
`lm_eval.simple_evaluate()` accepts a single scalar `num_fewshot` for the whole run. The runner loops over tasks and calls `eval_kwargs.setdefault("num_fewshot", fewshot)` per task — but `setdefault` is a no-op once the key exists, so only the first task with `fewshot > 0` wins:
```python
for task_name in tasks:
    fewshot = kBenchmarkFewShot.get(task_name, kDefaultFewShot)
    if fewshot > 0:
        eval_kwargs.setdefault("num_fewshot", fewshot)   # first task sets it; rest ignored
```
For the `medical` specialist the task list is `["medmcqa", "pubmedqa", "medhelm"(skipped), "mmlu"]`. `medmcqa` is 5-shot, `pubmedqa` is 0-shot, `mmlu` is 5-shot — so `pubmedqa` is silently evaluated 5-shot, contradicting D-02 ("Each benchmark uses its established shot count") and the `kBenchmarkFewShot` table. 0-shot tasks that happen to be first in a list would also be overridden by a later 5-shot task only if the later task comes first in iteration order with a non-zero value.

This cannot be fixed inside a single `simple_evaluate()` call. The runner must either (a) call `simple_evaluate()` once per task (or once per unique `num_fewshot` value), or (b) configure fewshot via per-task YAML `num_fewshot` metadata (lm-eval honors `num_fewshot` inside a task config when `num_fewshot` is not passed at the call site).

**Fix:** Drop the call-site `num_fewshot` entirely and let lm-eval pick it up from the per-task YAML (the configs in `config/benchmarks/*.yaml` already declare `num_fewshot`, but lm-eval reads `num_fewshot` from the *task* YAML, not the per-benchmark config — so the field needs to be in the task YAML registered by `TaskManager`). The minimum correct fix is to group tasks by shot count and call `simple_evaluate()` once per group:
```python
from collections import defaultdict
groups = defaultdict(list)
for t in tasks:
    groups[kBenchmarkFewShot.get(t, kDefaultFewShot)].append(t)

lm_eval_results = {"results": {}}
for fewshot, group_tasks in groups.items():
    if not group_tasks:
        continue
    out = self._run_lm_eval(
        model=model, tasks=group_tasks, mode=mode,
        gen_params=gen_params, force_download=force_download,
        num_fewshot=fewshot,
    )
    lm_eval_results["results"].update(out.get("results", {}))
```
Pass `num_fewshot` explicitly into `_run_lm_eval` and set it unconditionally (`eval_kwargs["num_fewshot"] = num_fewshot`), not via `setdefault`.

### CR-05: BIGPATENT (patents blocking benchmark) always scores None → 0.0 → fails hard floor

**File:** `gnus-poc/eval/benchmark_runner.py:488`, `gnus-poc/config/benchmarks/bigpatent.yaml:34-39`
**Issue:**
`bigpatent.yaml` declares `metric_list: [rouge1, rougeL]`, so lm-eval returns keys `rouge1` and `rougeL`. But `_extract_primary_score` (line 488) only knows `["acc_norm", "acc", "pass@1", "f1", "exact_match"]` — none of which exist in the BIGPATENT result dict. The method returns `None`, which `Benchmarker._extract_score` (benchmarker.py:528-530) then coerces to `0.0` (it falls through all candidate keys and returns `0.0`). With `hard_floor: 0.20` the patents gate fails on every run, blocking pipeline promotion forever.

**Fix:** Add ROUGE to the preferred-metrics list, ideally driven by the per-benchmark YAML rather than a hardcoded ordering:
```python
preferred_metrics = ["acc_norm", "acc", "pass@1", "f1", "exact_match", "rouge1", "rougeL", "rouge"]
```
Better: read the primary metric from the per-benchmark config (`benchmark_config.validate_benchmarks_config` already loads the YAMLs) and use it as the lookup key, so adding a new metric does not require editing this list.

### CR-06: is_degradation_significant flags "significant" regression from a single aggregate delta

**File:** `gnus-poc/eval/benchmark_trends.py:325-341`
**Issue:**
When `per_category` is empty, the code falls back to `diffs = [curr_score - prev_score]` (a single-element list). `bootstrap_ci` on a single-element list returns `(value, value)` for both bounds (the `_percentile` early-return at line 259-260 makes lower == upper == the one sample). Then:
```python
excludes_zero = (upper < 0.0) or (lower > 0.0)
significant = bool(excludes_zero and mean_delta < 0.0)
```
A single negative delta of any magnitude (e.g. -0.001) yields `upper < 0` → `significant: True`. This directly contradicts D-09 ("A regression is significant when the CI excludes zero, not when a magic number is crossed. Per-benchmark sample sizes and variance are automatically accounted for") — with n=1 there is no variance to estimate, so the CI is meaningless and the test is vacuous. Benchmarks without per-category breakdowns (HumanEval, BIGPATENT, GPQA, PubMedQA — all the non-MMLU blocking gates) will frequently trigger spurious "significant regression" flags.

**Fix:** Require a minimum sample count before declaring significance, and fall back to "insufficient_data" rather than a degenerate CI:
```python
_K_MIN_BOOTSTRAP_SAMPLES = 2  # or 5; anything below cannot support a CI

if len(diffs) < _K_MIN_BOOTSTRAP_SAMPLES:
    result[benchmark] = {
        "significant": False,
        "ci_lower": None,
        "ci_upper": None,
        "mean_delta": sum(diffs) / len(diffs) if diffs else 0.0,
        "n_samples": len(diffs),
        "reason": "insufficient_samples_for_ci",
    }
    continue
```
This also makes the existing tests (`test_is_degradation_significant_true_when_ci_excludes_zero_and_negative`, which uses 4-category MMLU samples) still pass while preventing the n=1 false positive.

## Warnings

### WR-01: Runner writes D-02 fingerprint as hardcoded placeholders that validate as valid

**File:** `gnus-poc/eval/benchmark_runner.py:135-147`, `423-433`
**Issue:**
`collect_fingerprint_fields` hardcodes `"stub"` for `model_manifest_sha256` / `sgfp4_manifest_sha256` and the call site (line 423-433) passes `task_revision="0"`, `dataset_revision="unknown"`, `prompt_hash="n/a"`, `chat_template_hash="n/a"`. Meanwhile `benchmark_fingerprint.compute_fingerprint` (the real implementation from Plan 04-03) is never invoked by the runner. `validate_fingerprint` only does a presence/non-None check, so these placeholder strings pass validation — every runner-produced record carries `fingerprint_valid: True` despite the fingerprint being non-reproducible. This defeats D-02's stated purpose ("Without this, trend analysis degrades over time").

**Fix:** Wire `benchmark_fingerprint.compute_fingerprint` into `_build_benchmark_entry`, passing the actual manifest paths from the specialist config and the rendered prompt template. If manifests are not yet available, fail closed by writing `fingerprint_valid: False` explicitly rather than silently embedding `"stub"`.

### WR-02: Canonical gen-params are computed then dropped (dead code)

**File:** `gnus-poc/eval/benchmark_runner.py:291-294`, `373-376`
**Issue:**
```python
if mode == "canonical":
    gen_params = dict(CANONICAL_PARAMS)
    gen_params.pop("num_fewshot", None)
...
if mode == "canonical" and gen_params:
    # Pass gen params through model_args or other mechanism
    pass
```
The `pass` block is a TODO that was never completed. `temperature`/`do_sample` from `CANONICAL_PARAMS` are never forwarded to `simple_evaluate()`, so the "frozen canonical params" guarantee of D-03 is unenforced. Diagnostic and canonical runs are indistinguishable to lm-eval beyond the per-task fewshot count (which is itself broken per CR-04).

**Fix:** Forward the params. lm-eval accepts `gen_kwargs` (or `apply_chat_template` + `fewshot_as_multiturn`); pick the appropriate kwarg and pass it through. If the work is deferred, mark the function with a `# TODO(04-XX):` and a tracking item rather than leaving dead `pass` blocks that imply the params are applied.

### WR-03: benchmark_repair flags not-implemented benchmarks as underperforming

**File:** `gnus-poc/eval/benchmark_repair.py:65-78`, `263-271`
**Issue:**
`_extract_score` returns `0.0` for any entry lacking `score`/`pass@1`/`acc`. Not-implemented benchmark entries (written by the runner with `score: None, status: "not_implemented"`) therefore score `0.0`, and `_build_underperforming_entries` compares `0.0 < hard_floor` → emits an underperformance entry with `below_threshold_pct = 100.0`, driving `_K_MAJOR_UNDERPERFORMANCE_PCT` suggestions and inflating severity. The repair report for `encyclopedic` (which has NO blocking benchmarks) would still flag any diagnostic MMLU below 0.25 as a major underperformance requiring config changes.

**Fix:** Skip entries with `status == "not_implemented"` (or `score is None`) before the threshold comparison:
```python
def _build_underperforming_entries(benchmark, results_entry, hard_floor, per_category_floors):
    entries = []
    if isinstance(results_entry, dict) and results_entry.get("status") == "not_implemented":
        return entries
    score = _extract_score(results_entry)
    ...
```

### WR-04: report_id uses seconds precision while the save filename uses microseconds

**File:** `gnus-poc/eval/benchmark_repair.py:301-302`, `336`
**Issue:**
`generate_repair_report` builds `report_id_ts = datetime.now(...).strftime("%Y%m%d-%H%M%S")` and uses it in `report_id`. `save_repair_report` independently computes `datetime.now(...).strftime("%Y%m%d-%H%M%S-%f")` for the filename. Two reports for the same niche within the same second get the SAME `report_id` but DIFFERENT filenames, so the `report_id` field cannot be used to locate the file on disk. The report's `timestamp_utc` is also captured at a third `datetime.now()` call (line 301), so `timestamp_utc`, `report_id`, and the filename timestamp can each differ slightly.

**Fix:** Capture the timestamp once at the top of `generate_repair_report` and thread it through both `report_id` and the save path. Use microsecond precision in both. (`save_repair_report` should accept the timestamp as an argument or read it from `report["report_id"]`.)

### WR-05: should_block_pipeline ignores the mandatory SGFP4 regression result

**File:** `gnus-poc/eval/benchmark_repair.py:345-372`
**Issue:**
D-08 makes the SGFP4 regression check "mandatory", but `should_block_pipeline` only inspects `consecutive_failures`. If the SGFP4 regression fails (e.g. quantization destroyed 15% of accuracy) but no individual benchmark has yet accumulated 3 consecutive hard-floor failures, the pipeline is not blocked. The SGFP4 regression result is surfaced in the repair report (`sgfp4_regression_summary`) but never participates in the block decision.

**Fix:** Either make the SGFP4 regression feed into `consecutive_failures` (as its own dimension tracked in `_save_bench_gate_state`), or extend `should_block_pipeline` to consult `gate_result["sgfp4_regression"]["passed"]`. If the placeholder behavior ("don't block on first run", `needs_bootstrap: True`) is intentional for Phase 4, document that explicitly in the function docstring and note it as a Phase 5 upgrade.

### WR-06: pubmedqa.yaml doc_to_text references {{context}} but the dataset field is contexts (list)

**File:** `gnus-poc/config/benchmarks/pubmedqa.yaml:22-26`
**Issue:**
The PubMedQA `pqa_labeled` config exposes `contexts` (a list of context strings), not `context`. The YAML's own ASSUMPTION A1 acknowledges field names "MUST be verified at runtime", but no test actually loads the dataset to confirm. As shipped, `{{context}}` will render empty, producing prompts like `"Question: ...\nContext: \nAnswer:"` and degrading PubMedQA scores. The `benchmark_tasks.py` self-test only checks `dataset_path`/`output_type`/`doc_to_choice`, not the prompt template.

**Fix:** Either change the template to `{{contexts | join("\n"}}` (Jinja2 join of the list) or `"{{contexts[0]}}"`, and add a runtime test that loads one example from `qiaojin/PubMedQA` / `pqa_labeled` and asserts the field exists.

### WR-07: _find_previous_canonical is the SECOND most-recent result, but regression semantics want the previous RUN (not previous file)

**File:** `gnus-poc/eval/benchmarker.py:808-831`
**Issue:**
`_find_previous_canonical` returns `canonical[1]` (second-most-recent by mtime). But a single benchmark *run* writes one file per task (runner line 326-330), so a run for `medical` produces 3 files (medmcqa, pubmedqa, mmlu) sharing roughly the same mtime. `canonical[1]` is likely a sibling task from the SAME run, not the previous run — so the regression dimension compares medmcqa-now against pubmedqa-just-now (or against another medmcqa file from milliseconds earlier). The regression delta is then meaningless.

**Fix:** Group candidates by run (e.g. by `timestamp_utc` truncated to second, or by an explicit `run_id` field), then take the most recent group as "current" and the next group as "previous". A run_id written into the payload at runner time is the cleanest fix.

### WR-08: composite_2_of_3 returns passed=True when 0 of 3 dims are evaluable on first run

**File:** `gnus-poc/eval/benchmarker.py:533-557`, `742-760`
**Issue:**
On a specialist's first run, there is no previous run (regression dimension default-passes, line 727) and no internal baseline (deviation default-passes via `MissingBaselineError`, line 758-760). Combined with hard floors passing, the composite reports `passed_count = 3` even though two of the three dimensions were never actually evaluated. The gate can report "all green" without having measured regression or deviation at all.

**Fix:** Track an `evaluated` flag per dimension and either downgrade the composite when fewer than 2 dims were actually evaluated, or surface `dimensions[...]["evaluated"]: False` so downstream consumers (`gate_check_benchmarks` return value, repair report) can distinguish "passed by measurement" from "passed by absence of data".

### WR-09: load_benchmark_run_by_fingerprint silently tolerates missing fingerprint_hash

**File:** `gnus-poc/eval/metric_store.py:310-336`
**Issue:**
If `fingerprint_hash` computation failed at write time (line 229-230 sets it to `None`), `load_benchmark_run_by_fingerprint` compares `payload.get("fingerprint_hash") == fingerprint_hash_value`. A caller passing `None` as the hash value would match every record with `fingerprint_hash: None`, returning an arbitrary (first-iterated) record. More importantly, the API has no way to signal "no fingerprint hash on record" vs "no matching record" — both return `None`.

**Fix:** Reject `None`/empty input explicitly:
```python
if not fingerprint_hash_value:
    return None
```
And skip records whose `fingerprint_hash` is `None` rather than letting them spuriously match a `None` query.

### WR-10: bootstrap_ci truncates input silently to 10_000 samples

**File:** `gnus-poc/eval/benchmark_trends.py:231-233`
**Issue:**
When input exceeds `_K_MAX_INPUT_SAMPLES`, the code silently takes `samples[:_K_MAX_INPUT_SAMPLES]` — a head truncation that biases the CI toward the first-observed samples. The docstring says "Truncate deterministically to the cap (T-04-18)" but does not surface the truncation to the caller, so a benchmark with 50k per-item deltas reports a CI computed from only the first 10k. If items are ordered (e.g. by difficulty, by category), the CI is systematically skewed.

**Fix:** Either random-sample (seeded) from the input instead of head-truncating, or return a flag/warning in the result tuple so consumers know the CI was computed on a subset. At minimum, log the truncation.

### WR-11: MLXBenchmarkModel.generate_until re-evaluates the full window every step (correctness, not perf)

**File:** `gnus-poc/eval/benchmark_mlx_model.py:309-321`
**Issue:**
(This is flagged as a correctness issue, not the out-of-scope O(n²) cost.) Each decode step runs `mx.array([current_ids[-self._max_length:]])` and forwards the entire window. Once `len(current_ids) > self._max_length`, the window slides so the oldest tokens drop out of the attention context. For models relying on long-range context (BIGPATENT patent descriptions, MedMCQA long prompts), the model's distribution at later steps is conditioned on a DIFFERENT context than it was at earlier steps — the generation becomes inconsistent with greedy decode on the full sequence. Stop sequences that depend on early context may never trigger.

**Fix:** Either cap `max_gen_toks` so the prompt + generation fits in `_max_length` (the current `min(requested_max, self._max_length)` cap does NOT account for prompt length — see line 300-303), or use MLX's native `mlx_lm.generate` / KV-cache API which handles sliding correctly. At minimum, set `max_gen_toks = min(requested_max, self._max_length - len(prompt_ids))` and fail/skip when `len(prompt_ids) >= self._max_length`.

## Info

### IN-01: Self-tests use global mutable state for pass/fail counters

**File:** `gnus-poc/eval/benchmark_config.py:384-391`, `gnus-poc/eval/benchmark_tasks.py:80-87`
**Issue:**
The `__main__` self-test blocks use `global passed, failed` inside a nested `check()` closure. This works but is fragile and not test-framework-compatible (cannot be invoked from pytest). The duplication between the two files is also a maintenance smell.

**Fix:** Extract a tiny `run_self_checks(checks: list[tuple[str, bool, str]])` helper, or convert these to proper pytest tests.

### IN-02: specialist_mapping.yaml's `encyclopedic` specialist has an empty blocking list

**File:** `gnus-poc/config/benchmarks/specialist_mapping.yaml:42`
**Issue:**
`encyclopedic.blocking_benchmarks: []` means the gate has nothing to enforce for this specialist — `gate_check_benchmarks` returns `passed: True` vacuously (the hard-floor loop iterates over an empty list). D-05 lists "RAG pipeline eval" as encyclopedic's blocking benchmark, but it is deferred to Phase 5. This is documented but worth surfacing: until Phase 5 ships, encyclopedic has no quality gate at all.

**Fix:** Add a comment in `pipeline.yaml` or a startup warning so operators know encyclopedic is currently un-gated.

### IN-03: eval_gates key is misspelled "sfgp4_regression" (transposed letters)

**File:** `gnus-poc/config/pipeline.yaml:149-152`, `gnus-poc/eval/benchmarker.py:612-614`
**Issue:**
The config key is `sfgp4_regression` (note: s-f-g-p-4, not s-g-f-p-4). The benchmarker reads it via `self._config.get("eval_gates", {}).get("sfgp4_regression", {})` — so the typo is consistent and the code works, but it contradicts the "SGFP4" naming used everywhere else in the codebase and will confuse anyone grepping for "sgfp4".

**Fix:** Rename to `sgfp4_regression` in both `pipeline.yaml` and `benchmarker.py`. Low priority because the code is internally consistent, but the misspelling will propagate.

### IN-04: ConfigError inherits from Exception, not ValueError

**File:** `gnus-poc/eval/benchmark_config.py:39-44`
**Issue:**
`ConfigError(Exception)` is fine, but callers expecting `ValueError` (the rest of the codebase's error-propagation convention per the project's outcome/error pattern) will not catch it. Not a bug, just an inconsistency.

**Fix:** Consider `class ConfigError(ValueError):` for closer alignment with existing error-handling patterns, or document the deviation.

### IN-05: synthetic.py fold-in fix is correct but undocumented in the diff

**File:** `gnus-poc/distill/synthetic.py:59`, `74`
**Issue:**
The fix `domain = _DOMAIN_MAP.get(niche_name, self._default_domain)` then `self._client.generate_with_cascade(messages, domain=domain)` correctly passes the mapped cascade domain (e.g. `medical`, `coding`) instead of the raw niche name (e.g. `cardiology`). This is the right fix per the context brief. No defect — noting that the change is small, correct, and lacks an inline comment explaining why the indirection exists.

**Fix:** Add a one-line comment: `# D-XX: cascade routes by domain, not niche — map before dispatch`.

---

## Structural Notes

- **D-10 invariant verified:** `benchmark_repair.py` contains no config-writing code. `_generate_config_suggestions` returns plain dicts only. The module imports `json`, `logging`, `datetime`, `Path` — no `yaml.dump`, no `ConfigLoader` write paths. Invariant holds.
- **Phase 3 preservation verified:** `gate_check()` (benchmarker.py:108-203) and the SGFP4 MetricStore methods (record_sgfp4_metrics / load_sgfp4_metrics / list_all_metrics) are unchanged in behavior. The benchmark gate uses a separate state file (`{niche}_bench_gate_state.json`) so SGFP4 counters are not disturbed. Additive as specified.
- **Bootstrap determinism verified:** `bootstrap_ci` uses a fresh `random.Random(seed)` (line 245), does not touch global `random` state, and `test_bootstrap_ci_deterministic_with_seed` confirms reproducibility.
- **YAML safety verified:** All `yaml.safe_load` usages (benchmark_config.py, benchmark_tasks.py docstring, benchmarker.py:366, metric_store via benchmarker). No `yaml.load` / `full_load` anywhere in scope.
- **Manifest streaming verified:** `benchmark_fingerprint._sha256_file` streams in 64KB chunks with a 10MB hard ceiling (T-04-15).
- **Test coverage gaps:** No test exercises (a) `BenchmarkRunner` writing a file that `Benchmarker.gate_check_benchmarks` then reads (the CR-01 contract bug is invisible to the suite), (b) real MLX inference (CR-02/CR-03 are silent), or (c) a multi-fewshot task list (CR-04 is silent). The mocks in `test_benchmark_runner.py::_make_mock_simple_evaluate_results` paper over all three.

---

_Reviewed: 2026-06-28T19:30:00Z_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
