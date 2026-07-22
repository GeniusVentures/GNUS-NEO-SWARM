"""Manifest catalog for deployed specialists — consumed by C++ engine."""

import hashlib
import json
from datetime import datetime
from pathlib import Path
from typing import Optional


class ManifestBuilder:
    def __init__(self, project_root: Optional[Path] = None):
        if project_root is None:
            project_root = Path(__file__).resolve().parent.parent
        self._root = project_root
        self._artifacts_dir = project_root / "artifacts"

    def build(
        self,
        niche_name: str,
        base_model: str,
        training_metadata: dict,
        fp4_bin_path: Path,
        fp4_stats: dict,
        eval_results: Optional[dict] = None,
    ) -> dict:
        checksum = self._file_sha256(fp4_bin_path)

        manifest = {
            "manifest_version": "1.0",
            "niche": niche_name,
            "base_model": base_model,
            "created": datetime.now().isoformat(),
            "fp4_binary": {
                "path": str(fp4_bin_path.relative_to(self._root)),
                "sha256": checksum,
                "format": "fp4_ultra_v0.2",
                "container": {
                    "macroblock_size": 64,
                    "payload_bytes_per_block": 2048,
                    "alignment": 16,
                },
                "stats": fp4_stats,
            },
            "training": {
                "iterations": training_metadata.get("iters"),
                "batch_size": training_metadata.get("batch_size"),
                "lora_rank": training_metadata.get("lora_parameters", {}).get("rank"),
                "duration_minutes": training_metadata.get("training_duration_minutes"),
                "trained_at": training_metadata.get("trained_at"),
                "base_model": base_model,
            },
        }

        if eval_results:
            manifest["evaluation"] = {
                "perplexity": eval_results.get("perplexity"),
                "bleu_score": eval_results.get("bleu_score"),
                "rouge_l": eval_results.get("rouge_l"),
                "latency_ms_per_token": eval_results.get("latency_ms_per_token"),
            }

        return manifest

    def save(self, manifest: dict, niche_name: str):
        out_dir = self._artifacts_dir / "manifests"
        out_dir.mkdir(parents=True, exist_ok=True)
        out_path = out_dir / f"{niche_name}_manifest.json"
        with out_path.open("w") as f:
            json.dump(manifest, f, indent=2)
        return out_path

    def save_catalog(self, manifests: list):
        catalog = {
            "catalog_version": "1.0",
            "generated": datetime.now().isoformat(),
            "num_specialists": len(manifests),
            "specialists": [m["niche"] for m in manifests],
            "default_router": "keyword",
        }
        out = self._artifacts_dir / "manifests" / "catalog.json"
        out.parent.mkdir(parents=True, exist_ok=True)
        with out.open("w") as f:
            json.dump(catalog, f, indent=2)
        return out

    def _file_sha256(self, path: Path) -> str:
        h = hashlib.sha256()
        with path.open("rb") as f:
            for chunk in iter(lambda: f.read(65536), b""):
                h.update(chunk)
        return h.hexdigest()
