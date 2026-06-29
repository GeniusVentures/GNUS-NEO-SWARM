---
phase: 04-benchmark-evaluation
fixed_at: 2026-06-28
review_path: .planning/workstreams/poc/phases/04-benchmark-evaluation/04-REVIEW.md
iteration: 1
findings_in_scope: 17
fixed: 18
skipped: 0
status: all_fixed
---

# Phase 04: Code Review Fix Report

**Fixed at:** 2026-06-28
**Source review:** `.planning/workstreams/poc/phases/04-benchmark-evaluation/04-REVIEW.md`
**Iteration:** 1 (gsd-code-fixer) + manual verification pass

**Summary:**
- Findings in scope: 17 (6 Critical + 11 Warning)
- Fixed: 17 findings across 16 atomic fixer commits + 2 manual follow-up commits
- Extra bug found & fixed during verification: `mx.log_softmax` does not exist (would crash any real MLX run)
- Skipped: 0

## How fixes were applied

1. **gsd-code-fixer** applied all 17 in-scope findings (16 commits) in an isolated worktree, fast-forwarded to `gsd/phase-04-benchmark-evaluation`. Per fixer rules, logic/algorithm findings were marked "requires human verification" (Tier 1/2 syntax checks cannot prove semantic correctness).
2. **Manual verification pass** (the deferred human role) added real-MLX + integration tests proving the high-risk logic fixes and caught one additional latent bug.

## Fixed Issues

| ID | Title | Commit | Verification |
|----|-------|--------|--------------|
| CR-01 | Filename-contract mismatch (gate inert) | 59fc319 | **Proven** — integration tests drive real producer payload + filename pattern through real consumer (af0a0ad) |
| CR-02 | MLX loglikelihood off-by-one | 54a3b96 | **Proven** — real-MLX test: only `logits[pos-1]` yields high logprob + greedy=True (39dcaa9) |
| CR-03 | Long-context returns -inf | e9601c3 | **Proven** — real-MLX test: long context tail-truncated, continuation scored, never -inf (39dcaa9) |
| CR-04 | Per-benchmark num_fewshot ignored | 34750a7 | Grouped tasks by shot count, simple_evaluate per group — syntax-verified; needs live lm-eval run to fully confirm |
| CR-05 | BIGPATENT scores None→0.0 | b8caf65 | Fixed — rouge1/rougeL/rouge added to preferred metrics |
| CR-06 | n=1 false "significant regression" | 4af1ba7 | Fixed — requires ≥2 bootstrap samples; existing 4-category test still passes |
| (new) | `mx.log_softmax` AttributeError | 39dcaa9 | **Found during verification** — not a valid mlx.core API; replaced with `mx.log(mx.softmax(...))`. Proven by real-MLX tests |
| WR-01..WR-11 | 11 warnings (fingerprint stubs, dead gen-params, not-implemented scoring, report_id precision, SGFP4 block, pubmedqa contexts, previous-run grouping, composite evaluated flag, None fingerprint hash, bootstrap truncation bias, generate_until context) | da7ba5d..9845c65 | Applied per REVIEW.md guidance; syntax-verified |

## Verification tests added (the missing safety net)

The reviewer's central finding: the test suite was green but mocked every boundary, so producer→consumer contracts and MLX scoring were unverified. Added:

- `tests/test_benchmark_mlx_model.py::test_loglikelihood_reads_logits_at_pos_minus_one` — real MLX, controlled logits, proves CR-02.
- `tests/test_benchmark_mlx_model.py::test_loglikelihood_long_context_does_not_return_neg_inf` — real MLX, proves CR-03.
- `tests/test_benchmarker.py::test_find_canonical_results_discovers_real_producer_files` — real producer→consumer, proves CR-01.
- `tests/test_benchmarker.py::test_find_canonical_results_quantized_discriminator` — payload-based quantized/unquantized discrimination.

## Test results

```
319 passed, 0 failed  (was 315 before verification pass; +4 new tests)
```

## Still recommended before ship

- A live `simple_evaluate()` run (even on a tiny model) to confirm CR-04 fewshot grouping and end-to-end runner→gate flow with real lm-eval, not just mocked `_run_lm_eval`.

---
_Fixed: 2026-06-28_
_Fixer: gsd-code-fixer + manual verification (Claude)_
