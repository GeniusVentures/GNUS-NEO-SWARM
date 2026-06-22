---
phase: 01-foundation-bug-fixes
plan: 01
subsystem: gnus-poc
tags: [bug-fix, chat-template, skip-logic, tokenizer, metadata-validation]
requires: [01-02]
provides: [tokenizer-utils, fixed-chat-template, fixed-skip-logic]
affects: [gnus-poc/training, gnus-poc/data/scripts]
tech-stack:
  added: [tokenizer_utils]
  patterns: [tokenizer.apply_chat_template, TDD, force-retrain, milestone-check]
key-files:
  created:
    - gnus-poc/training/tokenizer_utils.py
    - gnus-poc/tests/test_skip_logic.py
  modified:
    - gnus-poc/data/scripts/prepare_datasets.py
    - gnus-poc/training/train_specialists_mlx.py
    - gnus-poc/tests/test_chat_template.py
decisions:
  - "Use HuggingFace AutoTokenizer for chat template (not mlx_lm)"
  - "3-phase skip logic: force-retrain → milestone file → metadata validation"
  - "TRAINING_STATUS.json with iters_completed for skip check"
  - "Metadata field validation (Pitfall #4): RuntimeError on schema mismatch"
  - "Pitfall #16: Check metadata for StackExchange question/answer keys"
metrics:
  duration: 00:30
  completed_date: 2026-05-27
---

# Phase 1 Plan 01: Bug Fixes (FOUND-01, FOUND-02)

**One-liner:** Fixed two silent data-corrupting bugs: chat template mismatch (Qwen2.5 vs Qwen3) and skip-on-existing false completions.

## Completed Tasks

| # | Task | Status | Commit | Files |
|---|------|--------|--------|-------|
| 1 | Create tokenizer_utils.py and fix chat template (TDD) | ✓ | 75e3043 (RED), 43504fb (GREEN) | tokenizer_utils.py, prepare_datasets.py |
| 2 | Fix skip-on-existing logic and --force-retrain (TDD) | ✓ | b2ab7f3 (RED), f659236 (GREEN) | train_specialists_mlx.py |

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] False positive in <|im_start|> detection verification**
- **Found during:** End-to-end verification
- **Issue:** The docstring in `format_for_training()` explains the fix by referencing `<|im_start|>` — the detection script flags this as a hardcode
- **Fix:** Verified it's in a docstring (not actual code). All 5 niches use `format_chat()` exclusively.
- **Files affected:** prepare_datasets.py (line 162, inside docstring)

## Threat Flags

None — threat model mitigations were applied: metadata validation (T-01-02), status field in skip logic (T-01-03).

## Self-Check: PASSED

All 8 fast tests pass (4 tokenizer_utils + 4 skip_logic), all scripts compile cleanly.
