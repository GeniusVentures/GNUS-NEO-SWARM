"""Tests for hyperparameter validation from specialist config (TRAIN-02).

Covers the validation gate that runs at config load time, before
mlx_lora.train_model() is invoked with invalid parameters. Invalid combos
(batch_size <= 0, learning_rate <= 0, lora_rank < 1, iterations <= 0) raise
a clear ValueError naming the offending field (T-02-14 mitigation / WARNING 2
resolution).
"""

import pytest
import yaml

from training.config import TrainingConfig, validate_hyperparameters


class TestTrainingConfig:
    """Hyperparameter override and validation per TRAIN-02."""

    def test_hyperparameter_override_from_config(self, tmp_path):
        """Specialist YAML values (lora_rank, iterations, batch_size) are
        read and applied at runtime via TrainingConfig.from_yaml."""
        pipeline = tmp_path / "pipeline.yaml"
        pipeline.write_text(yaml.dump({
            "training": {"batch_size": 4, "lora_rank": 16}
        }))

        spec_dir = tmp_path / "specialists"
        spec_dir.mkdir()
        spec_file = spec_dir / "code.yaml"
        spec_file.write_text(yaml.dump({
            "training": {"lora_rank": 32, "iterations": 2000, "batch_size": 8}
        }))

        cfg = TrainingConfig.from_yaml(pipeline, specialist="code")
        assert cfg.lora_rank == 32
        assert cfg.iters == 2000
        assert cfg.batch_size == 8

    def test_invalid_batch_size_rejected(self):
        """batch_size <= 0 raises ValueError with a clear field-named message."""
        cfg = TrainingConfig(batch_size=0)
        with pytest.raises(ValueError, match="batch_size"):
            validate_hyperparameters(cfg)

    def test_invalid_learning_rate_rejected(self):
        """learning_rate <= 0 raises ValueError."""
        cfg = TrainingConfig(learning_rate=0.0)
        with pytest.raises(ValueError, match="learning_rate"):
            validate_hyperparameters(cfg)

    def test_invalid_lora_rank_rejected(self):
        """lora_rank < 1 raises ValueError."""
        cfg = TrainingConfig(lora_rank=0)
        with pytest.raises(ValueError, match="lora_rank"):
            validate_hyperparameters(cfg)

    def test_invalid_iterations_rejected(self):
        """iterations <= 0 raises ValueError."""
        cfg = TrainingConfig(iters=0)
        with pytest.raises(ValueError, match="iterations"):
            validate_hyperparameters(cfg)

    def test_valid_config_accepted(self):
        """All valid values pass validation without error."""
        cfg = TrainingConfig(
            batch_size=4, learning_rate=1e-5, lora_rank=16, iters=1000
        )
        # Should not raise.
        validate_hyperparameters(cfg)
