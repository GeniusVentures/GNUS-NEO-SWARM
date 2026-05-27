"""
Structural tests for FOUND-02 skip-on-existing fix.

Validates that train_specialists_mlx.py has:
1. --force-retrain argument
2. Milestone file check (e.g., 0001000_adapters.safetensors)
3. Metadata iters validation
4. Status field in training_metadata.json
"""

import ast
import sys
from pathlib import Path

TRAIN_SCRIPT = Path(__file__).resolve().parent.parent / "training" / "train_specialists_mlx.py"


def _read_source():
    with open(TRAIN_SCRIPT) as f:
        return f.read()


def _parse_tree():
    source = _read_source()
    return ast.parse(source), source


def test_force_retrain_flag_exists():
    """Verify --force-retrain argument is parsed in main()."""
    _, source = _parse_tree()
    assert "--force-retrain" in source, (
        "--force-retrain flag must be present in train_specialists_mlx.py"
    )


def test_milestone_file_check_exists():
    """Verify skip logic checks for milestone file (not just adapters.safetensors)."""
    _, source = _parse_tree()
    source_lower = source.lower()
    assert "milestone" in source_lower or "{:07d}" in source, (
        "Skip logic must check for milestone file pattern (e.g., 0001000_adapters.safetensors)"
    )


def test_metadata_validation_exists():
    """Verify skip logic validates training_metadata.json iters field."""
    _, source = _parse_tree()
    # Must reference metadata and iters together (not just in metadata dict writing)
    lines = source.split("\n")
    meta_lines = [
        l.strip()
        for l in lines
        if "metadata" in l.lower() and ("iters" in l.lower() or "status" in l.lower())
    ]
    assert len(meta_lines) >= 1, (
        "Skip logic must validate metadata['iters'] or metadata.get('status') for completion"
    )


def test_status_field_in_metadata():
    """Verify training_metadata.json includes 'status' field."""
    _, source = _parse_tree()
    assert '"status"' in source or "'status'" in source, (
        "training_metadata.json must include 'status' field for skip logic validation"
    )
