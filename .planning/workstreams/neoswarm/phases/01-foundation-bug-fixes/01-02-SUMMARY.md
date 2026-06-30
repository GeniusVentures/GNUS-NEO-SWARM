---
phase: 01-foundation-bug-fixes
plan: 02
subsystem: gnus-poc
tags: [restructure, directories, paths, modules]
requires: []
provides: [directory-tree, module-init-files, path-resolution]
affects: [gnus-poc/data, gnus-poc/training, gnus-poc/models]
tech-stack:
  added: []
  patterns: [pathlib.Path, __init__.py, PROJECT_ROOT]
key-files:
  created:
    - gnus-poc/training/__init__.py
    - gnus-poc/data/scripts/__init__.py
    - gnus-poc/pipeline/__init__.py
    - gnus-poc/distill/__init__.py
    - gnus-poc/eval/__init__.py
    - gnus-poc/quantize/__init__.py
    - gnus-poc/config/specialists/.gitkeep
    - gnus-poc/config/experiments/.gitkeep
    - gnus-poc/artifacts/.gitkeep
  modified:
    - gnus-poc/training/train_specialists_mlx.py (moved from models/)
    - gnus-poc/training/train_specialists.py (moved from models/)
    - gnus-poc/data/scripts/analyze_common_pile.py (moved from data/)
    - gnus-poc/data/scripts/extract_source_niches.py (moved from data/)
    - gnus-poc/data/scripts/prepare_datasets.py (moved from data/)
  deleted:
    - gnus-poc/models/train_specialists-old.py
decisions:
  - "Use Path(__file__).resolve().parent convention for all relative paths"
  - "PROJECT_ROOT = parent.parent for training/ scripts, parent.parent.parent for data/scripts/"
  - "Versioned output dirs: niche_vYYYYMMDDHHMM pattern"
  - "Delete train_specialists-old.py (exact duplicate of MLX script)"
metrics:
  duration: 00:15
  completed_date: 2026-05-27
---

# Phase 1 Plan 02: Directory Restructure (FOUND-03)

**One-liner:** Restructured gnus-poc from flat layout to 6-module organized layout with path resolution fix on all 5 scripts.

## Completed Tasks

| # | Task | Status | Commit | Files |
|---|------|--------|--------|-------|
| 1 | Create directory tree and __init__.py files | ✓ | 7acb9ba | 9 dirs, 6 __init__.py, 3 .gitkeep |
| 2 | Move scripts and fix relative paths | ✓ | 4e8af39 | 5 scripts moved, all paths fixed |
| 3 | Delete stale and duplicate files | ✓ | 86d0a65 | train_specialists-old.py deleted |

## Deviations from Plan

None — plan executed exactly as written.

## Threat Flags

None.

## Self-Check: PASSED

All directories exist, all scripts compile cleanly via py_compile.
