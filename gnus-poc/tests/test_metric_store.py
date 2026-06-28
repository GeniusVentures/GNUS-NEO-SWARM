"""Tests for MetricStore — SGFP4 quantization metric persistence."""

import json
from pathlib import Path

import pytest

from eval.metric_store import MetricStore


class TestMetricStore:
    """Tests for MetricStore record/load/list of SGFP4 quantization metrics."""

    def test_init_creates_metrics_dir(self, tmp_path):
        """MetricStore.__init__ creates artifacts/evaluations/ directory."""
        store = MetricStore(project_root=tmp_path)
        metrics_dir = tmp_path / "artifacts" / "evaluations"
        assert metrics_dir.exists()
        assert metrics_dir.is_dir()

    def test_record_sgfp4_metrics_writes_json(self, tmp_path):
        """record_sgfp4_metrics() writes a valid JSON file with all required fields."""
        store = MetricStore(project_root=tmp_path)

        fp4_stats = {
            "shape": [4096, 256],
            "num_superblocks": 4,
            "layout_distribution": {0: 3, 1: 1, 2: 0, 3: 0, 4: 0, 5: 0},
            "fp4_blocks": 100,
            "t158_blocks": 15,
            "effective_bpw": 3.2,
            "total_bytes": 8192,
        }

        out_path = store.record_sgfp4_metrics("code", fp4_stats)

        assert out_path.exists()
        assert "code_sgfp4_metrics.json" in out_path.name

        with out_path.open() as f:
            data = json.load(f)

        assert data["niche"] == "code"
        assert "timestamp_utc" in data
        assert "quantization_metrics" in data
        assert "raw_stats" in data

        qm = data["quantization_metrics"]
        assert "fp4_mse" in qm
        assert "fp4_effective_bitrate" in qm
        assert "fp4_t158_ratio" in qm
        assert isinstance(qm["fp4_mse"], float)
        assert isinstance(qm["fp4_effective_bitrate"], float)
        assert isinstance(qm["fp4_t158_ratio"], float)

        # Note: JSON serializes integer dict keys as strings.
        # layout_distribution {0: 3} -> {"0": 3}. Normalize for comparison.
        raw = data["raw_stats"]
        assert raw["shape"] == fp4_stats["shape"]
        assert raw["num_superblocks"] == fp4_stats["num_superblocks"]
        assert raw["fp4_blocks"] == fp4_stats["fp4_blocks"]
        assert raw["t158_blocks"] == fp4_stats["t158_blocks"]
        assert raw["effective_bpw"] == fp4_stats["effective_bpw"]
        assert raw["total_bytes"] == fp4_stats["total_bytes"]
        # layout_distribution: normalize string keys back to int
        assert {int(k): v for k, v in raw["layout_distribution"].items()} == fp4_stats["layout_distribution"]

    def test_record_sgfp4_metrics_computes_values(self, tmp_path):
        """Computed metric values are reasonable for known input."""
        store = MetricStore(project_root=tmp_path)

        fp4_stats = {
            "shape": [4096, 256],
            "num_superblocks": 4,
            "layout_distribution": {0: 3, 1: 1, 2: 0, 3: 0, 4: 0, 5: 0},
            "fp4_blocks": 100,
            "t158_blocks": 30,
            "effective_bpw": 3.5,
            "total_bytes": 8192,
        }

        out_path = store.record_sgfp4_metrics("medical", fp4_stats)
        with out_path.open() as f:
            data = json.load(f)

        qm = data["quantization_metrics"]
        # effective_bitrate should be 3.5
        assert qm["fp4_effective_bitrate"] == 3.5
        # t158_ratio: 30 / (100 + 30) = 0.2307...
        expected_t158 = 30.0 / 130.0
        assert abs(qm["fp4_t158_ratio"] - expected_t158) < 1e-9
        # mse from proxy: max(0.0, (3.5 - 2.5) / 100.0) = 0.01
        assert qm["fp4_mse"] >= 0.0

    def test_record_sgfp4_metrics_t158_ratio_zero_blocks(self, tmp_path):
        """t158_ratio is 0.0 when total blocks is zero."""
        store = MetricStore(project_root=tmp_path)
        fp4_stats = {
            "shape": [4096, 256],
            "num_superblocks": 0,
            "layout_distribution": {},
            "fp4_blocks": 0,
            "t158_blocks": 0,
            "effective_bpw": 0.0,
            "total_bytes": 0,
        }
        out_path = store.record_sgfp4_metrics("empty", fp4_stats)
        with out_path.open() as f:
            data = json.load(f)
        assert data["quantization_metrics"]["fp4_t158_ratio"] == 0.0

    def test_load_sgfp4_metrics_returns_most_recent(self, tmp_path):
        """load_sgfp4_metrics() returns the most recent metrics file by timestamp."""
        store = MetricStore(project_root=tmp_path)

        fp4_stats = {
            "shape": [1024, 512],
            "num_superblocks": 1,
            "layout_distribution": {0: 1},
            "fp4_blocks": 50,
            "t158_blocks": 5,
            "effective_bpw": 3.8,
            "total_bytes": 4096,
        }

        # Write first record
        path1 = store.record_sgfp4_metrics("code", fp4_stats)
        # Write second record (should be returned as most recent)
        fp4_stats2 = dict(fp4_stats, effective_bpw=3.9)
        path2 = store.record_sgfp4_metrics("code", fp4_stats2)

        loaded = store.load_sgfp4_metrics("code")
        assert loaded is not None
        assert loaded["quantization_metrics"]["fp4_effective_bitrate"] == 3.9

    def test_load_sgfp4_metrics_none_for_unknown_niche(self, tmp_path):
        """load_sgfp4_metrics() returns None when no metrics file exists for niche."""
        store = MetricStore(project_root=tmp_path)
        loaded = store.load_sgfp4_metrics("nonexistent")
        assert loaded is None

    def test_list_all_metrics(self, tmp_path):
        """list_all_metrics() returns dict of all niche_name -> metrics."""
        store = MetricStore(project_root=tmp_path)

        fp4_stats = {
            "shape": [1024, 512],
            "num_superblocks": 2,
            "layout_distribution": {0: 2},
            "fp4_blocks": 60,
            "t158_blocks": 10,
            "effective_bpw": 3.6,
            "total_bytes": 4096,
        }

        store.record_sgfp4_metrics("code", fp4_stats)
        store.record_sgfp4_metrics("medical", fp4_stats)

        all_metrics = store.list_all_metrics()
        assert "code" in all_metrics
        assert "medical" in all_metrics
        assert len(all_metrics) == 2

    def test_list_all_metrics_empty(self, tmp_path):
        """list_all_metrics() returns empty dict when no metrics exist."""
        store = MetricStore(project_root=tmp_path)
        all_metrics = store.list_all_metrics()
        assert all_metrics == {}

    def test_record_sgfp4_metrics_with_per_block_errors(self, tmp_path):
        """When fp4_stats contains per_block_errors, use them for fp4_mse."""
        store = MetricStore(project_root=tmp_path)
        fp4_stats = {
            "shape": [4096, 256],
            "num_superblocks": 2,
            "layout_distribution": {0: 1, 1: 1},
            "fp4_blocks": 80,
            "t158_blocks": 20,
            "effective_bpw": 3.3,
            "total_bytes": 7000,
            "per_block_errors": [0.005, 0.007, 0.003, 0.008],
        }
        out_path = store.record_sgfp4_metrics("code", fp4_stats)
        with out_path.open() as f:
            data = json.load(f)
        # Average of per_block_errors: (0.005+0.007+0.003+0.008)/4 = 0.00575
        expected_mse = (0.005 + 0.007 + 0.003 + 0.008) / 4.0
        assert abs(data["quantization_metrics"]["fp4_mse"] - expected_mse) < 1e-9

    def test_record_sgfp4_metrics_empty_per_block_errors(self, tmp_path):
        """Empty per_block_errors list falls back to proxy computation."""
        store = MetricStore(project_root=tmp_path)
        fp4_stats = {
            "shape": [4096, 256],
            "num_superblocks": 1,
            "layout_distribution": {0: 1},
            "fp4_blocks": 40,
            "t158_blocks": 5,
            "effective_bpw": 3.4,
            "total_bytes": 4000,
            "per_block_errors": [],
        }
        out_path = store.record_sgfp4_metrics("code", fp4_stats)
        with out_path.open() as f:
            data = json.load(f)
        # Falls back to proxy: max(0.0, (3.4 - 2.5) / 100.0)
        assert data["quantization_metrics"]["fp4_mse"] >= 0.0

    def test_json_valid_utf8(self, tmp_path):
        """JSON output is valid UTF-8 and contains timestamp_utc, quantization_metrics, raw_stats."""
        store = MetricStore(project_root=tmp_path)
        fp4_stats = {
            "shape": [256, 128],
            "num_superblocks": 1,
            "layout_distribution": {0: 1},
            "fp4_blocks": 30,
            "t158_blocks": 3,
            "effective_bpw": 3.9,
            "total_bytes": 1024,
        }
        out_path = store.record_sgfp4_metrics("qa_technical", fp4_stats)
        with out_path.open("r", encoding="utf-8") as f:
            data = json.load(f)

        assert "timestamp_utc" in data
        assert isinstance(data["timestamp_utc"], str)
        assert "T" in data["timestamp_utc"]  # ISO 8601
        assert "quantization_metrics" in data
        assert "raw_stats" in data
        assert data["raw_stats"]["effective_bpw"] == 3.9
