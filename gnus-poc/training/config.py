"""TrainingConfig — single source of truth for all LoRA hyperparameters."""

from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Optional

import yaml


@dataclass
class TrainingConfig:
    fine_tune_type: str = "lora"
    optimizer: str = "adamw"
    batch_size: int = 4
    iters: int = 1000
    val_batches: int = 25
    learning_rate: float = 1e-5
    steps_per_report: int = 50
    steps_per_eval: int = 200
    save_every: int = 200
    num_layers: int = 16
    grad_checkpoint: bool = True
    grad_accumulation_steps: int = 1
    mask_prompt: bool = False
    report_to: Optional[str] = None
    project_name: Optional[str] = None
    seed: int = 42
    lora_rank: int = 16
    lora_dropout: float = 0.05
    lora_scale: float = 20.0
    use_qlora: bool = True

    def to_lora_params(self) -> dict:
        return {
            "rank": self.lora_rank,
            "dropout": self.lora_dropout,
            "scale": self.lora_scale,
        }

    def to_args_dict(self) -> dict:
        return {
            "fine_tune_type": self.fine_tune_type,
            "optimizer": self.optimizer,
            "batch_size": self.batch_size,
            "iters": self.iters,
            "val_batches": self.val_batches,
            "learning_rate": self.learning_rate,
            "steps_per_report": self.steps_per_report,
            "steps_per_eval": self.steps_per_eval,
            "save_every": self.save_every,
            "num_layers": self.num_layers,
            "grad_checkpoint": self.grad_checkpoint,
            "grad_accumulation_steps": self.grad_accumulation_steps,
            "mask_prompt": self.mask_prompt,
            "report_to": self.report_to,
            "project_name": self.project_name,
            "seed": self.seed,
            "lora_parameters": self.to_lora_params(),
        }

    @classmethod
    def from_yaml(cls, yaml_path: Path, specialist: Optional[str] = None) -> "TrainingConfig":
        with yaml_path.open() as f:
            cfg_data = yaml.safe_load(f)

        defaults = cfg_data.get("pipeline", cfg_data).get("training",
                   cfg_data.get("training", {}))

        if specialist:
            spec_cfg = yaml_path.parent / "specialists" / f"{specialist}.yaml"
            if spec_cfg.exists():
                with spec_cfg.open() as f:
                    spec_data = yaml.safe_load(f)
                spec_training = spec_data.get("training", {})
                defaults = {**defaults, **spec_training}

        return cls(
            batch_size=defaults.get("batch_size", 4),
            iters=defaults.get("iterations", defaults.get("iters", 1000)),
            val_batches=defaults.get("val_batches", 25),
            learning_rate=defaults.get("learning_rate", 1e-5),
            steps_per_report=defaults.get("steps_per_report", 50),
            steps_per_eval=defaults.get("steps_per_eval", 200),
            save_every=defaults.get("save_every", 200),
            num_layers=defaults.get("num_layers", 16),
            grad_checkpoint=defaults.get("grad_checkpoint", True),
            grad_accumulation_steps=defaults.get("grad_accumulation_steps", 1),
            mask_prompt=defaults.get("mask_prompt", False),
            seed=defaults.get("seed", 42),
            lora_rank=defaults.get("lora_rank", 16),
            lora_dropout=defaults.get("lora_dropout", 0.05),
            lora_scale=defaults.get("lora_scale", 20.0),
            use_qlora=defaults.get("use_qlora", True),
            fine_tune_type=defaults.get("fine_tune_type", "lora"),
            optimizer=defaults.get("optimizer", "adamw"),
        )


def validate_hyperparameters(config: TrainingConfig) -> None:
    """Validate hyperparameter combinations before training starts (TRAIN-02).

    Raises ValueError with a message naming the offending field when any
    hyperparameter is out of its valid range. Called at config load time so
    invalid combinations are blocked before ``mlx_lora.train_model()`` is
    invoked (T-02-14 mitigation / WARNING 2 resolution).

    Args:
        config: The TrainingConfig to validate.

    Raises:
        ValueError: If any hyperparameter is invalid. The message names the
            offending field and its current value.
    """
    if config.batch_size <= 0:
        raise ValueError(
            f"Invalid hyperparameter batch_size={config.batch_size}: must be > 0"
        )
    if config.learning_rate <= 0:
        raise ValueError(
            f"Invalid hyperparameter learning_rate={config.learning_rate}: must be > 0"
        )
    if config.lora_rank < 1:
        raise ValueError(
            f"Invalid hyperparameter lora_rank={config.lora_rank}: must be >= 1"
        )
    if config.iters <= 0:
        raise ValueError(
            f"Invalid hyperparameter iterations={config.iters}: must be > 0"
        )
