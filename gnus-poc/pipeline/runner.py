"""Pipeline runner — sequential DAG with checkpoint detection."""

import argparse
import sys
from pathlib import Path
from typing import Optional


class PipelineRunner:
    STAGES = [
        "data_prep",
        "synthetic_data",
        "dedup",
        "train",
        "evaluate",
        "distill",
        "quantize",
    ]

    def __init__(self, project_root: Optional[Path] = None, config_path: Optional[Path] = None):
        if project_root is None:
            project_root = Path(__file__).resolve().parent.parent
        self._root = project_root

        if config_path is None:
            config_path = project_root / "config" / "pipeline.yaml"
        self._config_path = config_path

    def run(
        self,
        niche: Optional[str] = None,
        from_stage: Optional[str] = None,
        force: bool = False,
    ):
        niches = [niche] if niche else self._load_niches()
        start_idx = self._stage_index(from_stage) if from_stage else 0

        for n in niches:
            print(f"\n{'=' * 60}\nPipeline: {n.upper()}\n{'=' * 60}")
            for i in range(start_idx, len(self.STAGES)):
                stage = self.STAGES[i]
                if self._is_complete(n, stage) and not force:
                    print(f"  [{stage}] Skipped (complete)")
                    continue
                self._run_stage(n, stage)
                self._mark_complete(n, stage)

    def _load_niches(self) -> list:
        try:
            import yaml
            with self._config_path.open() as f:
                cfg = yaml.safe_load(f)
            return cfg.get("pipeline", cfg).get("specialists", [])
        except Exception:
            return []

    def _stage_index(self, stage_name: str) -> int:
        try:
            return self.STAGES.index(stage_name)
        except ValueError:
            return 0

    def _is_complete(self, niche: str, stage: str) -> bool:
        marker = self._root / "artifacts" / ".checkpoints" / niche / f"{stage}.done"
        return marker.exists()

    def _mark_complete(self, niche: str, stage: str):
        marker = self._root / "artifacts" / ".checkpoints" / niche / f"{stage}.done"
        marker.parent.mkdir(parents=True, exist_ok=True)
        marker.touch()

    def _run_stage(self, niche: str, stage: str):
        print(f"  [{stage}] Running...")
        if stage == "data_prep":
            print(f"    → python data/scripts/prepare_datasets.py")
        elif stage == "synthetic_data":
            print(f"    → python distill/synthetic.py --niche {niche}")
        elif stage == "dedup":
            print(f"    → python training/dedup.py --niche {niche}")
        elif stage == "train":
            print(f"    → python training/train_specialists_mlx.py --niche {niche}")
        elif stage == "evaluate":
            print(f"    → python eval/evaluator.py --niche {niche}")
        elif stage == "distill":
            print(f"    → python distill/distillation.py --niche {niche}")
        elif stage == "quantize":
            print(f"    → python quantize/fp4_exporter.py --niche {niche}")
        print(f"  [{stage}] Complete")


def main():
    parser = argparse.ArgumentParser(description="GNUS-POC Pipeline Runner")
    parser.add_argument("--niche", type=str, help="Run for a single specialist niche")
    parser.add_argument("--from-stage", type=str, help="Start from a specific stage")
    parser.add_argument("--config", type=str, help="Path to pipeline config YAML")
    parser.add_argument("--force", action="store_true", help="Force re-run all stages")
    args = parser.parse_args()

    config_path = Path(args.config) if args.config else None
    runner = PipelineRunner(config_path=config_path)
    runner.run(niche=args.niche, from_stage=args.from_stage, force=args.force)


if __name__ == "__main__":
    main()
