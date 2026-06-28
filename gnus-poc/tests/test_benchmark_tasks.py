"""Tests for custom lm-eval task YAML definitions (PubMedQA, BIGPATENT).

Per Plan 04-02 Task 1: custom YAML task definitions for the two benchmarks
not natively supported by lm-eval-harness must load via TaskManager with
correct output_type, metric_list, and dataset_path.

Tests avoid network downloads by inspecting ``task_index`` (the parsed YAML
config dict) rather than calling ``load_task_or_group`` (which downloads).
For Test 5 (invalid dataset_path fail-fast), ``load_task_or_group`` is invoked
directly — that is the API that surfaces ``DatasetNotFoundError``.
"""

import textwrap
from pathlib import Path

import pytest

from eval.benchmark_tasks import (
    BENCHMARKS_CONFIG_DIR,
    create_task_manager,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _task_cfg(tm, name: str) -> dict:
    """Return the parsed YAML config dict for a registered task.

    TaskManager.task_index maps task name -> Entry with a ``.cfg`` dict
    containing the YAML fields. This avoids any network download.
    """
    assert name in tm.task_index, (
        f"task '{name}' not registered. Available: {sorted(tm.task_index)[:20]}..."
    )
    entry = tm.task_index[name]
    # Entry may be a dataclass-like object with .cfg, or a dict depending on
    # lm-eval version. Handle both.
    if hasattr(entry, "cfg"):
        return entry.cfg
    if isinstance(entry, dict) and "cfg" in entry:
        return entry["cfg"]
    return entry


def _write_minimal_dataset_stub_yaml(path: Path) -> None:
    """Write a YAML that references a guaranteed-nonexistent dataset."""
    path.write_text(textwrap.dedent("""\
        task: broken_dataset_ref
        dataset_path: this/does-not-exist-xyz-12345-fake
        output_type: multiple_choice
        doc_to_text: "q"
        doc_to_target: "a"
        metric_list:
          - metric: acc
            aggregation: mean
            higher_is_better: true
        metadata:
          version: 0
        """))


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestPubMedQATask:
    """PubMedQA custom YAML task (Plan 04-02 Task 1, behavior 1-2)."""

    def test_pubmedqa_yaml_loads_via_task_manager(self):
        """Test 1: PubMedQA YAML loads; dataset_path=qiaojin/PubMedQA,
        output_type=multiple_choice with 3 choices (yes/no/maybe)."""
        tm = create_task_manager()
        cfg = _task_cfg(tm, "pubmedqa")

        assert cfg["dataset_path"] == "qiaojin/PubMedQA"
        assert cfg["output_type"] == "multiple_choice"
        choices = cfg["doc_to_choice"]
        assert choices == ["yes", "no", "maybe"], (
            f"expected 3-option yes/no/maybe, got {choices}"
        )

    def test_pubmedqa_metric_list_has_acc_mean(self):
        """Test 2: metric_list includes acc with mean aggregation."""
        tm = create_task_manager()
        cfg = _task_cfg(tm, "pubmedqa")

        metrics = cfg["metric_list"]
        acc_entries = [m for m in metrics if m.get("metric") == "acc"]
        assert len(acc_entries) == 1, f"expected one acc metric, got {metrics}"
        assert acc_entries[0].get("aggregation") == "mean"
        assert acc_entries[0].get("higher_is_better") is True

    def test_pubmedqa_targets_yes_no_maybe(self):
        """Per RESEARCH.md OQ4: PubMedQA is 3-way (yes/no/maybe)."""
        tm = create_task_manager()
        cfg = _task_cfg(tm, "pubmedqa")
        assert "{{final_decision}}" in cfg["doc_to_target"]


class TestBigpatentTask:
    """BIGPATENT custom YAML task (Plan 04-02 Task 1, behavior 3-4)."""

    def test_bigpatent_yaml_loads_via_task_manager(self):
        """Test 3: BIGPATENT YAML loads; dataset_path=big_patent,
        output_type=generate_until (summarization)."""
        tm = create_task_manager()
        cfg = _task_cfg(tm, "bigpatent")

        assert cfg["dataset_path"] == "big_patent"
        assert cfg["output_type"] == "generate_until", (
            "summarization must use generate_until, not multiple_choice"
        )

    def test_bigpatent_metric_list_has_rouge(self):
        """Test 4: metric_list includes rouge1 and rougeL metrics."""
        tm = create_task_manager()
        cfg = _task_cfg(tm, "bigpatent")

        metric_names = {m.get("metric") for m in cfg["metric_list"]}
        assert "rouge1" in metric_names, (
            f"missing rouge1; metrics={metric_names}"
        )
        assert "rougeL" in metric_names, (
            f"missing rougeL; metrics={metric_names}"
        )

    def test_bigpatent_has_frozen_generation_kwargs(self):
        """Per D-03: canonical generation params frozen (temp=0.0, do_sample=false)."""
        tm = create_task_manager()
        cfg = _task_cfg(tm, "bigpatent")
        gk = cfg.get("generation_kwargs", {})
        assert gk.get("temperature") == 0.0
        assert gk.get("do_sample") is False


class TestCustomTaskFailFast:
    """Failure-mode tests (Plan 04-02 Task 1, behavior 5-6)."""

    def test_invalid_dataset_path_raises_descriptive_error(self, tmp_path):
        """Test 5: Custom task YAML fails fast on invalid dataset_path with a
        descriptive error when the task is actually loaded (not just registered).

        TaskManager registration is lazy — invalid dataset_path surfaces only
        at load time via ``load_task_or_group``. This test verifies the
        fail-fast contract: a broken dataset_path does not silently succeed.
        """
        _write_minimal_dataset_stub_yaml(tmp_path / "broken.yaml")
        from lm_eval.tasks import TaskManager
        tm = TaskManager(include_path=str(tmp_path))

        # Registration is lazy (no error yet)
        assert "broken_dataset_ref" in tm.task_index

        # Loading the task must raise — proves fail-fast contract.
        with pytest.raises(Exception) as excinfo:
            tm.load_task_or_group("broken_dataset_ref")

        # Error must mention the broken dataset path
        message = str(excinfo.value).lower()
        assert "does-not-exist-xyz-12345-fake" in message or "doesn't exist" in message, (
            f"error not descriptive: {excinfo.value}"
        )

    def test_custom_yaml_has_metadata_version(self):
        """Test 6a: both custom YAMLs have metadata.version field (v0.4 compat)."""
        tm = create_task_manager()
        for name in ("pubmedqa", "bigpatent"):
            cfg = _task_cfg(tm, name)
            assert "metadata" in cfg, f"{name} missing metadata block"
            assert "version" in cfg["metadata"], (
                f"{name} missing metadata.version (required for lm-eval v0.4)"
            )

    def test_task_name_matches_yaml_key(self):
        """Test 6b: registered task name matches expected key."""
        tm = create_task_manager()
        # task_index keys ARE the registered task names
        assert "pubmedqa" in tm.task_index
        assert "bigpatent" in tm.task_index


class TestCreateTaskManager:
    """Smoke test for the create_task_manager() factory."""

    def test_create_task_manager_returns_task_manager(self):
        """create_task_manager() returns a TaskManager with custom tasks registered."""
        from lm_eval.tasks import TaskManager

        tm = create_task_manager()
        assert isinstance(tm, TaskManager)

    def test_create_task_manager_uses_config_benchmarks_dir(self):
        """create_task_manager() points include_path at config/benchmarks/."""
        # The directory must exist for TaskManager to register custom tasks.
        assert BENCHMARKS_CONFIG_DIR.is_dir(), (
            f"config dir missing: {BENCHMARKS_CONFIG_DIR}"
        )
        tm = create_task_manager()
        # Both custom tasks must be registered after construction
        assert "pubmedqa" in tm.task_index
        assert "bigpatent" in tm.task_index
