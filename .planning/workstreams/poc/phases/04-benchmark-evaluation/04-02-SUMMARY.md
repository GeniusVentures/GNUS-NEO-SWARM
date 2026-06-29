---
phase: 04-benchmark-evaluation
plan: 02
subsystem: eval
tags: [lm-eval-harness, benchmark-config, specialist-mapping, custom-yaml-tasks, d-04, d-05]
requires: []
provides:
  - Custom lm-eval YAML task definitions for PubMedQA and BIGPATENT
  - Per-benchmark config schema validation (validate_benchmarks_config)
  - D-05 specialist-to-benchmark mapping loader (load_specialist_mapping)
  - create_task_manager factory registering custom tasks
affects:
  - gnus-poc/config/benchmarks/
  - gnus-poc/eval/
tech-stack:
  added:
    - lm-eval TaskManager include_path (custom task registration)
  patterns:
    - Single YAML carries both lm-eval task fields AND per-benchmark config fields
      (lm-eval ignores unknown keys, ConfigLoader reads per-benchmark keys)
    - yaml.safe_load exclusively (T-04-06 mitigation)
    - Lazy TaskManager registration — invalid dataset_path surfaces at load time only
key-files:
  created:
    - gnus-poc/config/benchmarks/mmlu.yaml (16 lines)
    - gnus-poc/config/benchmarks/humaneval.yaml (16 lines)
    - gnus-poc/config/benchmarks/medmcqa.yaml (16 lines)
    - gnus-poc/config/benchmarks/gpqa.yaml (16 lines)
    - gnus-poc/config/benchmarks/pubmedqa.yaml (38 lines, merged task + config)
    - gnus-poc/config/benchmarks/bigpatent.yaml (40 lines, merged task + config)
    - gnus-poc/config/benchmarks/specialist_mapping.yaml (49 lines)
    - gnus-poc/eval/benchmark_tasks.py (124 lines)
    - gnus-poc/eval/benchmark_config.py (310 lines)
    - gnus-poc/tests/test_benchmark_tasks.py (167 lines)
    - gnus-poc/tests/test_benchmark_config.py (325 lines)
decisions:
  - "D-04: MMLU config has blocking=false (diagnostic only); 5 domain benchmarks have blocking=true"
  - "D-05: 5 specialists mapped; encyclopedic blocking_benchmarks=[] because RAG eval deferred to Phase 5"
  - "D-08: per-benchmark hard_floor values: mmlu/gpqa=0.25, humaneval/medmcqa=0.30, pubmedqa=0.35, bigpatent=0.20"
  - "Merged schema: pubmedqa.yaml and bigpatent.yaml carry both lm-eval `task:` fields and per-benchmark config fields in one file"
  - "Lazy validation contract: TaskManager creation never fails on invalid dataset_path; fail-fast surfaces only at task-load time"
metrics:
  duration: ~30min
  completed_date: 2026-06-28
  tests_passing: 39
---

# Phase 04 Plan 02: Custom YAML Tasks + Per-Benchmark Configs + Specialist Mapping

**One-liner:** Created 6 per-benchmark YAML configs (with `hard_floor` and `blocking` per D-04), the D-05 specialist-to-benchmark mapping, two custom lm-eval task definitions for PubMedQA (3-way yes/no/maybe) and BIGPATENT (summarization with rouge), and a `ConfigLoader` extension that validates all benchmark YAMLs at load time with descriptive field-level errors.

## Tasks Completed

| # | Task | Status | Commit | Key Files |
|---|------|--------|--------|-----------|
| 1 | Custom YAML task definitions for PubMedQA and BIGPATENT | Complete | 02b485a, e591de8 | pubmedqa.yaml, bigpatent.yaml, benchmark_tasks.py, test_benchmark_tasks.py |
| 2 | Per-benchmark configs, specialist mapping, ConfigLoader validation | Complete | 11819e4, b154edf | mmlu/humaneval/medmcqa/gpqa/*.yaml, specialist_mapping.yaml, benchmark_config.py, test_benchmark_config.py |

## What Was Built

### Custom lm-eval Task YAMLs
- **pubmedqa.yaml** — overrides lm-eval's built-in PubMedQA task with the explicit 3-way yes/no/maybe choice list (RESEARCH.md OQ4). `dataset_path: qiaojin/PubMedQA`, `pqa_labeled` config, `test_split: train` (PubMedQA has no dedicated test split, per RESEARCH.md Pitfall 4).
- **bigpatent.yaml** — defines the patent abstract summarization task (NOT natively in lm-eval). `output_type: generate_until`, frozen canonical `generation_kwargs` per D-03 (temperature=0.0, do_sample=false, max_gen_toks=512), rouge1+rougeL metrics.

### benchmark_tasks.py — `create_task_manager()`
- Returns an `lm_eval.tasks.TaskManager` with `include_path` pointing at `config/benchmarks/`.
- Files without a `task:` key (per-benchmark config YAMLs and `specialist_mapping.yaml`) are silently skipped by TaskManager — only task YAMLs are registered.

### Per-benchmark config YAMLs (config/benchmarks/)
All 6 benchmarks carry: `name`, `task_name`, `num_fewshot`, `output_type`, `blocking`, `hard_floor`, `regression_max_pct: 0.10` (D-08), `deviation_max_pct: 0.20` (D-08), `dataset_revision: null`.

| Benchmark | blocking (D-04) | hard_floor | num_fewshot |
|-----------|-----------------|------------|-------------|
| mmlu | false | 0.25 | 5 |
| humaneval | true | 0.30 | 0 |
| medmcqa | true | 0.30 | 5 |
| gpqa | true | 0.25 | 0 |
| pubmedqa | true | 0.35 | 0 |
| bigpatent | true | 0.20 | 0 |

### specialist_mapping.yaml (D-05)
Maps all 5 specialists to `blocking_benchmarks` + `diagnostic_benchmarks`:
- code: HumanEval (blocking), MMLU (diagnostic)
- medical: MedMCQA + PubMedQA (blocking), MMLU (diagnostic)
- qa_technical: GPQA (blocking), MMLU (diagnostic)
- encyclopedic: `[]` blocking (RAG eval deferred Phase 5), MMLU (diagnostic)
- patents: BIGPATENT (blocking), MMLU (diagnostic)

Deferred benchmarks (LiveCodeBench, MedHELM, RAG pipeline, USPTO classification) are noted as comments in the YAML per RESEARCH.md OQ1/OQ2/OQ3.

### benchmark_config.py — ConfigLoader extension
- **`validate_benchmarks_config(config_dir)`** — reads all `*.yaml` in `config/benchmarks/` except `specialist_mapping.yaml`; validates each against `BENCHMARK_REQUIRED_FIELDS` (8 fields with strict type checks); enforces threshold range (0.0, 1.0]; returns `{name: config}` dict.
- **`load_specialist_mapping(config_dir)`** — validates `specialist_mapping.yaml` schema (top-level `specialists` key, each specialist has `blocking_benchmarks`/`diagnostic_benchmarks` lists); cross-validates referenced benchmark names against the validated per-benchmark set (T-04-08 mitigation).
- **`get_benchmarks_for_specialist(specialist, mapping)`** — returns `(blocking, diagnostic)` tuple; raises `KeyError` on unknown specialist.
- Strict type validation: `bool` rejected for `int` fields (catches `num_fewshot: true`); `int`/`float` accepted for thresholds but `bool` rejected; `str` rejected for `bool` fields (catches `blocking: "false"`).

## Verification Results

```
$ python3 -m pytest tests/test_benchmark_tasks.py tests/test_benchmark_config.py -q
.......................................                                  [100%]
39 passed in 39.52s

$ python3 eval/benchmark_tasks.py    # 10/10 self-test checks pass
$ python3 eval/benchmark_config.py   # 12/12 self-test checks pass
$ python3 -m pytest tests/test_benchmark_runner.py tests/test_benchmark_mlx_model.py -q
................................         [100%]
32 passed in 1.11s    # Plan 04-01 regression: clean
```

The 39s Task 1 runtime is dominated by `test_invalid_dataset_path_raises_descriptive_error`, which calls `TaskManager.load()` on a guaranteed-nonexistent dataset path — lm-eval attempts a network round-trip to the HuggingFace Hub before raising `DatasetNotFoundError`. This is the intended fail-fast contract.

## Deviations from Plan

### [Rule 2 - Schema] Merged lm-eval task YAML and per-benchmark config YAML into a single file
- **Found during:** Task 2 implementation
- **Issue:** The plan lists `pubmedqa.yaml` and `bigpatent.yaml` in both Task 1 (lm-eval task definition) and Task 2 (per-benchmark config schema). These have different schemas (`task:`+`output_type:`+`metric_list:` vs `name:`+`task_name:`+`hard_floor:`+`blocking:`). Creating two files per benchmark would conflict with the plan's `files_modified` list (which lists each YAML once) and split benchmark metadata across two locations.
- **Fix:** Verified empirically that `lm_eval.tasks.TaskManager` ignores unknown YAML keys (it stores the full parsed YAML dict as `Entry.cfg`, but only consults the lm-eval-defined fields). The two custom task YAMLs (`pubmedqa.yaml`, `bigpatent.yaml`) now carry BOTH the lm-eval task fields and the per-benchmark config fields in a single file. `ConfigLoader.validate_benchmarks_config` reads the per-benchmark fields from the same file.
- **Files modified:** `pubmedqa.yaml`, `bigpatent.yaml`
- **Commit:** b154edf

### [Rule 2 - Schema] Specialist mapping key naming
- **Found during:** Task 2 implementation
- **Issue:** Plan's example YAML uses `blocking:`/`diagnostic:` keys, but the behavior spec and test contract call for `blocking_benchmarks`/`diagnostic_benchmarks` (more explicit, harder to confuse with the per-benchmark `blocking:` flag).
- **Fix:** Used the explicit `blocking_benchmarks`/`diagnostic_benchmarks` keys throughout. The behavior contract in the plan ("each specialist has blocking_benchmarks and diagnostic_benchmarks lists") governs.
- **Files:** `specialist_mapping.yaml`, `benchmark_config.py`, `test_benchmark_config.py`
- **Commit:** b154edf

### Test refinement during TDD GREEN
- **[Bug]** Initial Task 1 Test 5 used the deprecated `TaskManager.load_task_or_group()`. The newer `TaskManager.load()` API is preferred.
- **Fix:** Switched to `getattr(tm, "load", None) or tm.load_task_or_group` for forward/backward compatibility. Confirmed `load()` raises the same `DatasetNotFoundError` with a descriptive message naming the broken dataset path.
- **Commit:** e591de8

## Threat Flags

None beyond the plan's threat model. All 6 mitigations from the plan's `<threat_model>` are implemented:
- T-04-06 (Tampering, YAML parsing): `yaml.safe_load` exclusively in `benchmark_config.py`. ✓
- T-04-07 (Spoofing, dataset_path): `dataset_revision: null` in all 6 per-benchmark YAMLs (placeholder for canonical pinning per D-02). ✓
- T-04-08 (Tampering, specialist_mapping): `load_specialist_mapping` cross-validates every referenced benchmark name against the validated per-benchmark set. ✓
- T-04-09 (Info Disclosure, dataset provenance): accepted per plan — benchmark configs contain no PII. ✓
- T-04-10 (DoS, datasets.load_dataset): not in scope for this plan — runner (04-01) handles caching. ✓
- T-04-SC (Tampering, pip install): no new packages introduced. ✓

## Self-Check: PASSED

- [x] `gnus-poc/config/benchmarks/pubmedqa.yaml` — FOUND (38 lines, min 20)
- [x] `gnus-poc/config/benchmarks/bigpatent.yaml` — FOUND (40 lines, min 20)
- [x] `gnus-poc/config/benchmarks/specialist_mapping.yaml` — FOUND (49 lines, min 25)
- [x] `gnus-poc/eval/benchmark_config.py` — FOUND (310 lines, min 80)
- [x] `gnus-poc/eval/benchmark_tasks.py` — FOUND (124 lines)
- [x] `gnus-poc/tests/test_benchmark_tasks.py` — FOUND (167 lines)
- [x] `gnus-poc/tests/test_benchmark_config.py` — FOUND (325 lines)
- [x] Commit 02b485a — FOUND (Task 1 RED test)
- [x] Commit e591de8 — FOUND (Task 1 GREEN impl)
- [x] Commit 11819e4 — FOUND (Task 2 RED test)
- [x] Commit b154edf — FOUND (Task 2 GREEN impl)
- [x] 39 tests passing (11 Task 1 + 28 Task 2)
- [x] Plan 04-01 regression: 32 tests still passing
