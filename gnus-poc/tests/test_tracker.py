"""Tests for ExperimentTracker."""

from training.config import TrainingConfig
from training.tracker import ExperimentTracker


class TestExperimentTracker:
    def test_start_and_end_run(self):
        tracker = ExperimentTracker()
        tracker.start_run("code", "rank16")
        tracker.log_metrics({"perplexity": 5.2, "bleu": 0.45})
        run_id = tracker.end_run()
        assert "code" in run_id
        assert tracker._active is False

    def test_list_runs(self):
        tracker = ExperimentTracker()
        tracker.start_run("medical", "default")
        tracker.log_metrics({"perplexity": 4.1})
        tracker.end_run()

        runs = tracker.list_runs()
        assert len(runs) >= 1
        assert any("medical" in r["run_id"] for r in runs)

    def test_config_hash(self):
        tracker = ExperimentTracker()
        cfg = TrainingConfig(batch_size=4, lora_rank=16)
        h1 = tracker.config_hash(cfg)
        assert len(h1) == 12
        assert isinstance(h1, str)

    def test_config_hash_different(self):
        tracker = ExperimentTracker()
        cfg_a = TrainingConfig(batch_size=4)
        cfg_b = TrainingConfig(batch_size=8)
        assert tracker.config_hash(cfg_a) != tracker.config_hash(cfg_b)

    def test_config_hash_same(self):
        tracker = ExperimentTracker()
        cfg_a = TrainingConfig(batch_size=4, lora_rank=16)
        cfg_b = TrainingConfig(batch_size=4, lora_rank=16)
        assert tracker.config_hash(cfg_a) == tracker.config_hash(cfg_b)
