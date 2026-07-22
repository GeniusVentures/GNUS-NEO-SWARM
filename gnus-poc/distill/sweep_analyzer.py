"""Structured temperature sweep analysis and persistence.

SweepAnalyzer saves per-specialist sweep results to ``artifacts/sweeps/<niche>_sweep.json``
and can load them back for trend analysis.  The output format includes per-temperature loss
curves, convergence status, and identified best temperature — enabling data-driven temperature
selection per specialist (D-05).
"""

import json
from pathlib import Path
from typing import Any, Dict, Optional


class SweepAnalyzer:
    """Persist and load structured temperature sweep analysis results.

    Args:
        project_root: Root of the gnus-poc project. The ``artifacts/sweeps``
            directory is created beneath this path.
    """

    def __init__(self, project_root: Optional[Path] = None):
        if project_root is None:
            project_root = Path(__file__).resolve().parent.parent
        self._project_root = project_root
        self._sweep_dir = project_root / "artifacts" / "sweeps"

    def save(self, niche: str, analysis: Dict[str, Any]) -> Path:
        """Write a sweep analysis to ``artifacts/sweeps/<niche>_sweep.json``.

        Args:
            niche: Specialist niche name (e.g. ``"medical"``).
            analysis: Dictionary with keys ``niche``, ``sweep_date``,
                ``best_temperature``, ``best_loss``, ``temperatures``,
                and ``convergence``.

        Returns:
            Path to the written file.
        """
        self._sweep_dir.mkdir(parents=True, exist_ok=True)
        out_path = self._sweep_dir / f"{niche}_sweep.json"
        out_path.write_text(json.dumps(analysis, indent=2), encoding="utf-8")
        return out_path

    def load(self, niche: str) -> Optional[Dict[str, Any]]:
        """Load a previously saved sweep analysis for *niche*.

        Args:
            niche: Specialist niche name.

        Returns:
            The analysis dictionary, or ``None`` if no sweep file exists.
        """
        file_path = self._sweep_dir / f"{niche}_sweep.json"
        if not file_path.exists():
            return None
        return json.loads(file_path.read_text(encoding="utf-8"))
