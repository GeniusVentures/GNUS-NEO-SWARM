"""Tests for TrainingConfig dataclass."""

import yaml
from pathlib import Path

from training.config import TrainingConfig


class TestTrainingConfig:
    def test_defaults(self):
        cfg = TrainingConfig()
        assert cfg.batch_size == 4
        assert cfg.iters == 1000
        assert cfg.lora_rank == 16
        assert cfg.use_qlora is True

    def test_to_lora_params(self):
        cfg = TrainingConfig(lora_rank=8, lora_dropout=0.1, lora_scale=10.0)
        params = cfg.to_lora_params()
        assert params == {"rank": 8, "dropout": 0.1, "scale": 10.0}

    def test_to_args_dict(self):
        cfg = TrainingConfig()
        args = cfg.to_args_dict()
        assert args["batch_size"] == 4
        assert args["iters"] == 1000
        assert args["lora_parameters"]["rank"] == 16

    def test_from_yaml(self, tmp_path):
        pipeline = tmp_path / "pipeline.yaml"
        pipeline.write_text(yaml.dump({
            "training": {
                "batch_size": 2,
                "iterations": 500,
                "lora_rank": 8,
                "use_qlora": False,
            }
        }))
        cfg = TrainingConfig.from_yaml(pipeline)
        assert cfg.batch_size == 2
        assert cfg.iters == 500
        assert cfg.lora_rank == 8
        assert cfg.use_qlora is False

    def test_from_yaml_with_specialist_override(self, tmp_path):
        pipeline = tmp_path / "pipeline.yaml"
        pipeline.write_text(yaml.dump({
            "training": {"batch_size": 4, "lora_rank": 16}
        }))

        spec_dir = tmp_path / "specialists"
        spec_dir.mkdir()
        spec_file = spec_dir / "code.yaml"
        spec_file.write_text(yaml.dump({
            "training": {"lora_rank": 32, "iterations": 2000}
        }))

        cfg = TrainingConfig.from_yaml(pipeline, specialist="code")
        assert cfg.batch_size == 4
        assert cfg.lora_rank == 32
        assert cfg.iters == 2000
