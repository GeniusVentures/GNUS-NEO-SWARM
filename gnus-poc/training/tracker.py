"""MLflow experiment tracking wrapper for training runs."""

import hashlib
import json
from pathlib import Path
from typing import Optional


class ExperimentTracker:
    def __init__(self, project_root: Optional[Path] = None):
        if project_root is None:
            project_root = Path(__file__).resolve().parent.parent
        self._project_root = project_root
        self._tracking_dir = project_root / "artifacts" / "experiments"
        self._tracking_dir.mkdir(parents=True, exist_ok=True)
        self._active = False

    def config_hash(self, config) -> str:
        if hasattr(config, "to_args_dict"):
            data = config.to_args_dict()
        elif isinstance(config, dict):
            data = config
        else:
            data = str(config)
        raw = json.dumps(data, sort_keys=True, default=str)
        return hashlib.sha256(raw.encode()).hexdigest()[:12]

    def start_run(self, niche_name: str, variant: str = "default"):
        self._niche = niche_name
        self._variant = variant
        self._run_id = f"{niche_name}_{variant}_{self.config_hash({})}"
        self._metrics = {}
        self._active = True

    def log_params(self, params: dict):
        if not self._active:
            return
        self._params = dict(params)

    def log_metrics(self, metrics: dict):
        if not self._active:
            return
        self._metrics.update(metrics)

    def end_run(self):
        if not self._active:
            return
        run_dir = self._tracking_dir / self._run_id
        run_dir.mkdir(parents=True, exist_ok=True)

        run_data = {}
        if hasattr(self, '_params'):
            run_data["params"] = self._params
        run_data["metrics"] = self._metrics

        with (run_dir / "run.json").open("w") as f:
            json.dump(run_data, f, indent=2, default=str)

        self._active = False
        return self._run_id

    def list_runs(self) -> list:
        runs = []
        if not self._tracking_dir.exists():
            return runs
        for d in sorted(self._tracking_dir.iterdir()):
            if d.is_dir() and (d / "run.json").exists():
                with (d / "run.json").open() as f:
                    data = json.load(f)
                runs.append({"run_id": d.name, **data})
        return runs

    def compare_runs(self) -> list:
        runs = self.list_runs()
        comparison = []
        for r in runs:
            entry = {"run_id": r["run_id"]}
            entry.update(r.get("metrics", {}))
            comparison.append(entry)
        return comparison
