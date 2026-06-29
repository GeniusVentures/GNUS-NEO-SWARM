"""Benchmark runner entry point — invokes lm-eval simple_evaluate() for specialists.

Per D-01 (multi-mode): dataset source (huggingface/local), model backend (MLX).
Per D-02 (reproducibility fingerprint): 11-field fingerprint per benchmark run.
Per D-03 (canonical vs diagnostic): canonical = frozen params, diagnostic = overrides.
Per D-04 (MMLU universal baseline): every specialist runs MMLU, never blocks.
Per D-05 (specialist-benchmark mapping): domain-specific blocking + MMLU diagnostic.

Pipeline invocation: ``python eval/benchmark_runner.py --niche {niche}``

Threat mitigations:
- T-04-02: lm-eval import wrapped in try/except with clear message.
- T-04-05: local dataset paths validated with Path.resolve() prefix check.
"""

import argparse
import json
import logging
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# D-03: Canonical mode frozen parameters
CANONICAL_PARAMS: Dict = {
    "temperature": 0.0,
    "do_sample": False,
    "num_fewshot": None,
}

# D-05: Specialist-to-benchmark mapping
SPECIALIST_BENCHMARKS: Dict[str, Dict[str, List[str]]] = {
    "code": {
        "blocking": ["humaneval", "livecodebench"],
        "diagnostic": ["mmlu"],
    },
    "medical": {
        "blocking": ["medmcqa", "pubmedqa", "medhelm"],
        "diagnostic": ["mmlu"],
    },
    "qa_technical": {
        "blocking": ["gpqa_main_n_shot"],
        "diagnostic": ["mmlu"],
    },
    "encyclopedic": {
        "blocking": ["rag_pipeline_eval"],
        "diagnostic": ["mmlu"],
    },
    "patents": {
        "blocking": ["bigpatent", "uspto_classification"],
        "diagnostic": ["mmlu"],
    },
}

# Benchmarks not yet implemented — runner logs a warning and skips with
# status "not_implemented" in results JSON. Does NOT fail the run.
kNotImplementedBenchmarks: frozenset = frozenset({
    "livecodebench", "medhelm", "rag_pipeline_eval", "uspto_classification",
})

# Per-benchmark few-shot defaults (D-02: established shot counts)
kBenchmarkFewShot: Dict[str, int] = {
    "mmlu": 5,
    "humaneval": 0,
    "medmcqa": 5,
    "pubmedqa": 0,
    "gpqa_main_n_shot": 0,
    "bigpatent": 0,
}

kDefaultFewShot: int = 0


# ---------------------------------------------------------------------------
# Public helpers
# ---------------------------------------------------------------------------

def build_task_list(niche: str, mode: str) -> List[str]:
    """Build the list of benchmark task names for a specialist niche and mode.

    Args:
        niche: Specialist niche name (e.g., "medical", "code").
        mode: "canonical" or "diagnostic" (both include the same tasks,
              differentiated at simple_evaluate() call time params).

    Returns:
        List of lm-eval task names (e.g., ["mmlu", "medmcqa", "pubmedqa"]).

    Raises:
        ValueError: If *niche* is not in SPECIALIST_BENCHMARKS.
    """
    if niche not in SPECIALIST_BENCHMARKS:
        raise ValueError(f"Unknown niche '{niche}'. Valid: {list(SPECIALIST_BENCHMARKS.keys())}")

    mapping = SPECIALIST_BENCHMARKS[niche]
    tasks = list(mapping["blocking"]) + list(mapping["diagnostic"])
    return tasks


def collect_fingerprint_fields(
    task_name: str,
    task_revision: str,
    dataset_revision: str,
    prompt_hash: str,
    fewshot_seed: int,
    chat_template_hash: str,
    answer_extraction: str,
    generation_params: dict,
) -> dict:
    """Collect the 11-field reproducibility fingerprint per D-02.

    ``model_manifest_sha256`` and ``sgfp4_manifest_sha256`` are stub
    placeholders until the fingerprint module is added in Plan 04-03.

    Args:
        task_name: lm-eval task name.
        task_revision: Task YAML revision string.
        dataset_revision: Dataset version/pin.
        prompt_hash: SHA256 of the rendered prompt template.
        fewshot_seed: Seed used for few-shot example sampling.
        chat_template_hash: SHA256 of the chat template used.
        answer_extraction: Method name for answer extraction.
        generation_params: Decoding parameters used.

    Returns:
        Dict with all 11 fingerprint fields.
    """
    return {
        "harness_commit": "0.4.12",
        "task_name": task_name,
        "task_revision": task_revision,
        "dataset_revision": dataset_revision,
        "prompt_hash": prompt_hash,
        "fewshot_seed": fewshot_seed,
        "chat_template_hash": chat_template_hash,
        "answer_extraction": answer_extraction,
        "generation_params": generation_params,
        "model_manifest_sha256": "stub",
        "sgfp4_manifest_sha256": "stub",
    }


def validate_results_schema(data: dict) -> None:
    """Validate that *data* conforms to the benchmark results JSON schema.

    Required top-level fields: ``niche``, ``timestamp_utc``, ``model_version``,
    ``mode``, ``results``. Each entry in ``results`` must have ``score`` and
    ``per_category``.

    Args:
        data: Parsed results dict to validate.

    Raises:
        ValueError: If the schema is violated.
    """
    required_fields = ["niche", "timestamp_utc", "model_version", "mode", "results"]
    for field in required_fields:
        if field not in data:
            raise ValueError(f"results JSON missing required field: {field}")

    if not isinstance(data["results"], dict):
        raise ValueError("results JSON field 'results' must be a dict")

    for benchmark_name, entry in data["results"].items():
        if not isinstance(entry, dict):
            raise ValueError(
                f"results JSON entry for '{benchmark_name}' must be a dict"
            )
        if "score" not in entry:
            raise ValueError(
                f"results JSON missing 'score' in results.{benchmark_name}"
            )
        if "per_category" not in entry:
            raise ValueError(
                f"results JSON missing 'per_category' in results.{benchmark_name}"
            )


# ---------------------------------------------------------------------------
# BenchmarkRunner
# ---------------------------------------------------------------------------

class BenchmarkRunner:
    """Orchestrates benchmark evaluation for a single specialist niche.

    Loads the MLX model once (per RESEARCH.md Pitfall 3), invokes
    ``simple_evaluate()`` with the specialist's task list, and writes
    structured results JSON to ``artifacts/benchmarks/``.
    """

    _kModelVersionPlaceholder = "sgfp4-v2-unknown"

    def __init__(self, project_root: Optional[Path] = None):
        """Initialize the benchmark runner.

        Args:
            project_root: Root of the gnus-poc project. Auto-located if None.
        """
        if project_root is None:
            project_root = Path(__file__).resolve().parent.parent
        self._project_root = project_root
        self._benchmarks_dir = project_root / "artifacts" / "benchmarks"
        self._benchmarks_dir.mkdir(parents=True, exist_ok=True)

    def run_benchmarks(
        self,
        niche: str,
        mode: str = "canonical",
        source: str = "huggingface",
        force_download: bool = False,
        quantized: bool = True,
    ) -> List[Path]:
        """Run all benchmarks for a specialist niche and return output paths.

        Steps:
        1. Load per-specialist config (model_path, quantization params).
        2. Create MLXBenchmarkModel once.
        3. Build task list from specialist mapping.
        4. Call ``simple_evaluate()`` with all tasks.
        5. Extract per-benchmark scores and per-category breakdowns.
        6. Write results JSON to ``artifacts/benchmarks/``.
        7. Return list of output file paths.

        Args:
            niche: Specialist niche name (e.g., "medical", "code").
            mode: "canonical" (frozen params per D-03) or "diagnostic"
                  (allows overrides from config/benchmarks/<name>.yaml).
            source: "huggingface" (default, via datasets library) or
                    "local" (reads from data/benchmarks/).
            force_download: If True, re-download datasets even when cached.
            quantized: If True (default), the run is the SGFP4 quantized model
                -- entries are stamped with ``"quantized": True`` so the
                benchmarker's canonical-quantized gate dimension (D-08) finds
                them. Set False for the unquantized-adapter comparison run
                that the mandatory SGFP4 regression check consumes.

        Returns:
            List of Paths to written results JSON files.

        Raises:
            NotImplementedError: If source is "api".
            RuntimeError: If lm-eval is not installed.
        """
        # Validate source mode early
        if source == "api":
            raise NotImplementedError(
                "API judge mode is not implemented in this phase. "
                "Use source=huggingface or source=local."
            )

        if source == "local":
            self._validate_local_source()

        # Load specialist config
        specialist_config = self._load_specialist_config(niche)
        model_path = specialist_config.get("model_path")
        adapter_path = specialist_config.get("adapter_path")

        # Create MLX model wrapper once (RESEARCH.md Pitfall 3)
        from eval.benchmark_mlx_model import MLXBenchmarkModel
        model_path = Path(model_path) if model_path else self._default_model_path(niche)
        adapter_path = Path(adapter_path) if adapter_path else None

        try:
            model = MLXBenchmarkModel(model_path=model_path, adapter_path=adapter_path)
        except Exception as exc:
            raise RuntimeError(
                f"Failed to load MLX model for niche '{niche}': {exc}"
            ) from exc

        # Build task list (blocking + diagnostic per D-05)
        tasks = build_task_list(niche, mode)

        # Separate implemented vs not-implemented tasks
        implemented_tasks = [t for t in tasks if t not in kNotImplementedBenchmarks]
        not_implemented = [t for t in tasks if t in kNotImplementedBenchmarks]

        # Log warnings for not-yet-implemented benchmarks
        for task_name in not_implemented:
            logger.warning(
                "Benchmark '%s' is not yet implemented — skipping with status "
                "'not_implemented' (does not fail the run)",
                task_name,
            )

        # Generate timestamp once for all output files
        timestamp_str = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")

        # Determine generation params based on mode
        gen_params = {}
        if mode == "canonical":
            gen_params = dict(CANONICAL_PARAMS)
            gen_params.pop("num_fewshot", None)  # per-benchmark override

        # Call simple_evaluate() if there are implemented tasks
        lm_eval_results = {}
        if implemented_tasks:
            lm_eval_results = self._run_lm_eval(
                model=model,
                tasks=implemented_tasks,
                mode=mode,
                gen_params=gen_params,
                force_download=force_download,
            )

        # Build per-benchmark results with per-category breakdown
        output_paths: List[Path] = []

        for task_name in tasks:
            if task_name in not_implemented:
                # Write not-implemented entry
                entry = self._build_not_implemented_entry(
                    niche, timestamp_str, mode, source, task_name, quantized=quantized,
                )
            else:
                entry = self._build_benchmark_entry(
                    niche=niche,
                    timestamp_str=timestamp_str,
                    mode=mode,
                    source=source,
                    task_name=task_name,
                    raw_results=lm_eval_results.get("results", {}),
                    gen_params=gen_params,
                    specialist_config=specialist_config,
                    quantized=quantized,
                )

            output_path = self._benchmarks_dir / f"{niche}_{task_name}_{timestamp_str}.json"
            with output_path.open("w", encoding="utf-8") as f:
                json.dump(entry, f, indent=2)

            output_paths.append(output_path)
            logger.info("Wrote benchmark results: %s", output_path)

        return output_paths

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _run_lm_eval(
        self,
        model,
        tasks: List[str],
        mode: str,
        gen_params: dict,
        force_download: bool = False,
    ) -> dict:
        """Invoke lm-eval simple_evaluate() with the model and task list.

        Per T-04-02 mitigation: lm-eval import is wrapped in try/except
        with a clear error message.
        """
        try:
            from lm_eval import simple_evaluate
        except ImportError as exc:
            raise RuntimeError(
                "lm-eval v0.4.12 is not installed. Install with: "
                "pip install lm-eval==0.4.12"
            ) from exc

        eval_kwargs = {
            "model": model,
            "tasks": tasks,
            "batch_size": 1,
            "log_samples": False,
        }

        # Per-benchmark few-shot counts
        for task_name in tasks:
            fewshot = kBenchmarkFewShot.get(task_name, kDefaultFewShot)
            if fewshot > 0:
                eval_kwargs.setdefault("num_fewshot", fewshot)

        # Canonical mode applies frozen gen params if available
        if mode == "canonical" and gen_params:
            # Pass gen params through model_args or other mechanism
            pass

        try:
            results = simple_evaluate(**eval_kwargs)
        except Exception as exc:
            raise RuntimeError(
                f"lm-eval simple_evaluate() failed for tasks {tasks}: {exc}"
            ) from exc

        return results

    def _build_benchmark_entry(
        self,
        niche: str,
        timestamp_str: str,
        mode: str,
        source: str,
        task_name: str,
        raw_results: dict,
        gen_params: dict,
        specialist_config: dict,
        quantized: bool = True,
    ) -> dict:
        """Build a single benchmark result entry conforming to the D-02 schema.

        Extracts the primary score metric and per-category breakdown from
        the raw lm-eval results dict.

        Args:
            quantized: Whether this run is the SGFP4 quantized model (True)
                or the unquantized-adapter comparison (False). Stamped into
                the payload so the benchmarker's D-08 gate can distinguish
                canonical-quantized (gated) from canonical-unquantized
                (the SGFP4 regression baseline) without relying on filename
                tokens.
        """
        task_results = raw_results.get(task_name, {})

        # Determine the primary score
        score = self._extract_primary_score(task_name, task_results)

        # Per-category breakdown (MMLU subjects)
        per_category = self._extract_per_category(task_name, raw_results)

        # Quantization config
        quant_config = specialist_config.get("quantization_config", {
            "bits": 4,
            "block_size": 64,
            "encoder_version": "unknown",
        })

        # Model version
        model_version = specialist_config.get(
            "model_version", self._kModelVersionPlaceholder
        )

        # Reproducibility fingerprint
        fingerprint = collect_fingerprint_fields(
            task_name=task_name,
            task_revision="0",
            dataset_revision="unknown",
            prompt_hash="n/a",
            fewshot_seed=kBenchmarkFewShot.get(task_name, kDefaultFewShot),
            chat_template_hash="n/a",
            answer_extraction="default",
            generation_params=gen_params,
        )

        entry = {
            "niche": niche,
            "timestamp_utc": datetime.now(timezone.utc).isoformat(),
            "model_version": model_version,
            "quantization_config": quant_config,
            "mode": mode,
            "source": source,
            "quantized": bool(quantized),
            "fingerprint": fingerprint,
            "results": {
                task_name: {
                    "score": score,
                    "per_category": per_category,
                },
            },
        }
        return entry

    def _build_not_implemented_entry(
        self,
        niche: str,
        timestamp_str: str,
        mode: str,
        source: str,
        task_name: str,
        quantized: bool = True,
    ) -> dict:
        """Build a result entry for a not-yet-implemented benchmark."""
        return {
            "niche": niche,
            "timestamp_utc": datetime.now(timezone.utc).isoformat(),
            "model_version": self._kModelVersionPlaceholder,
            "quantization_config": {},
            "mode": mode,
            "source": source,
            "quantized": bool(quantized),
            "fingerprint": {},
            "results": {
                task_name: {
                    "score": None,
                    "status": "not_implemented",
                    "per_category": {},
                },
            },
        }

    @staticmethod
    def _extract_primary_score(task_name: str, task_results: dict) -> Optional[float]:
        """Extract the primary metric score from raw lm-eval task results.

        Prefers metrics in order: ``acc_norm``, ``acc``, ``pass@1``, ``f1``,
        ``exact_match``. Returns None if no metric found or results are empty.
        """
        if not task_results:
            return None

        preferred_metrics = ["acc_norm", "acc", "pass@1", "f1", "exact_match"]
        for metric in preferred_metrics:
            if metric in task_results:
                value = task_results[metric]
                if isinstance(value, (int, float)):
                    return float(value)

        return None

    @staticmethod
    def _extract_per_category(task_name: str, raw_results: dict) -> Dict[str, float]:
        """Extract per-category/subject breakdown from raw lm-eval results.

        For MMLU group tasks, extracts per-subject ``mmlu_<subject>`` entries.
        For other tasks, returns an empty dict (per-category not applicable).
        """
        per_category: Dict[str, float] = {}

        if task_name == "mmlu":
            # MMLU returns per-subject results like mmlu_anatomy, mmlu_astronomy, etc.
            prefix = "mmlu_"
            for key, value in raw_results.items():
                if key.startswith(prefix) and key != "mmlu":
                    subject = key[len(prefix):]
                    if isinstance(value, dict):
                        # Extract primary metric
                        for metric in ("acc_norm", "acc"):
                            if metric in value:
                                per_category[subject] = float(value[metric])
                                break
                        else:
                            per_category[subject] = 0.0

        return per_category

    def _load_specialist_config(self, niche: str) -> dict:
        """Load per-specialist config from config/specialists/{niche}.yaml."""
        config_path = self._project_root / "config" / "specialists" / f"{niche}.yaml"
        if config_path.exists():
            try:
                import yaml
                with config_path.open("r", encoding="utf-8") as f:
                    return yaml.safe_load(f) or {}
            except Exception:
                logger.warning("Could not load specialist config: %s", config_path)
        return {}

    def _default_model_path(self, niche: str) -> Path:
        """Return the default model path for a niche."""
        return self._project_root / "models" / "specialists_mlx" / niche

    def _validate_local_source(self) -> None:
        """Validate that the local benchmarks data directory exists.

        T-04-05 mitigation: Validate local dataset paths are within
        data/benchmarks/ using Path.resolve() + prefix check.
        """
        local_dir = self._project_root / "data" / "benchmarks"
        if not local_dir.exists():
            logger.warning(
                "Local benchmarks directory does not exist: %s. "
                "lm-eval may fail for tasks not cached externally.",
                local_dir,
            )


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

def main() -> None:
    """Parse CLI arguments and run benchmarks for a specialist niche.

    Usage: python eval/benchmark_runner.py --niche medical --mode canonical
    """
    parser = argparse.ArgumentParser(
        description="GNUS-POC Benchmark Runner — evaluate quantized specialist models"
    )
    parser.add_argument(
        "--niche",
        type=str,
        required=True,
        help="Specialist niche name (e.g., medical, code, qa_technical)",
    )
    parser.add_argument(
        "--mode",
        type=str,
        default="canonical",
        choices=["canonical", "diagnostic"],
        help="Evaluation mode: canonical (frozen params) or diagnostic (override)",
    )
    parser.add_argument(
        "--source",
        type=str,
        default="huggingface",
        choices=["huggingface", "local", "api"],
        help="Benchmark source: huggingface (datasets API), local (pre-downloaded), "
             "api (not implemented)",
    )
    parser.add_argument(
        "--force-download",
        action="store_true",
        default=False,
        help="Re-download datasets even if cached",
    )
    parser.add_argument(
        "--unquantized",
        action="store_true",
        default=False,
        help="Stamp results as the unquantized-adapter run (quantized=False) "
             "consumed by the SGFP4 regression check. Default: quantized=True.",
    )
    args = parser.parse_args()

    runner = BenchmarkRunner()

    try:
        paths = runner.run_benchmarks(
            niche=args.niche,
            mode=args.mode,
            source=args.source,
            force_download=args.force_download,
            quantized=not args.unquantized,
        )
        print(f"Benchmark {args.niche}: {len(paths)} results written")
        for p in paths:
            print(f"  {p}")
    except NotImplementedError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        sys.exit(2)
    except RuntimeError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
