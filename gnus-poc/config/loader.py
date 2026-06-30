"""ConfigLoader — centralized YAML config loading, validation, and per-specialist override resolution.

Loads the two-layer pipeline configuration (endpoints + models) from config/pipeline.yaml,
validates the schema, and deep-merges per-specialist overrides from config/specialists/<niche>.yaml.

Usage:
    loader = ConfigLoader(Path("."))
    code_config = loader.get_effective_config("code")
"""

from __future__ import annotations

import copy
from pathlib import Path
from typing import Any, Dict, List, Optional

import yaml


class ConfigValidationError(Exception):
    """Raised when pipeline or specialist config fails schema validation.

    The error message includes the YAML key path (e.g., "endpoints.litellm.url")
    to help diagnose the exact location of the invalid field.
    """

    def __init__(self, key_path: str, message: str) -> None:
        self.key_path = key_path
        self.message = message
        super().__init__(f"{key_path}: {message}")


# Allowed values for endpoints.<name>.apiType
_VALID_API_TYPES = frozenset({"openai", "anthropic"})


class ConfigLoader:
    """Loads, validates, and resolves the two-layer pipeline configuration.

    On construction, loads config/pipeline.yaml and all config/specialists/*.yaml
    files. Validation runs immediately — a ConfigValidationError is raised for
    any schema violation.
    """

    def __init__(self, project_root: Path) -> None:
        self._project_root = project_root
        self._global_config: Dict[str, Any] = self._load_global_config()
        self._specialist_configs: Dict[str, Dict[str, Any]] = self._load_specialist_configs()
        self._validate()

    # -- public API ----------------------------------------------------------------

    def get_effective_config(self, niche: str) -> Dict[str, Any]:
        """Return the effective config for *niche*, with per-specialist overrides applied.

        The effective config starts as a deep copy of the global config. If a
        specialist config exists for ``niche``, its values are deep-merged:
        dict values merge recursively, lists and scalars replace the global
        default.

        Raises ConfigValidationError if *niche* is not in ``pipeline.specialists``.
        """
        specialists_list = self._global_config.get("pipeline", {}).get("specialists", [])
        if niche not in specialists_list:
            raise ConfigValidationError(
                f"pipeline.specialists",
                f"unknown niche '{niche}'; valid options: {', '.join(specialists_list)}",
            )

        effective = copy.deepcopy(self._global_config)

        spec_path = self._specialist_configs.get(niche)
        if spec_path is not None:
            specialist_data = self._load_yaml(spec_path)
            self._apply_specialist_overrides(effective, specialist_data)

        return effective

    # -- private: loading -----------------------------------------------------------

    def _load_global_config(self) -> Dict[str, Any]:
        pipeline_path = self._project_root / "config" / "pipeline.yaml"
        if not pipeline_path.exists():
            raise ConfigValidationError(
                "pipeline.yaml",
                f"configuration file not found at {pipeline_path}",
            )
        return self._load_yaml(pipeline_path)

    def _load_specialist_configs(self) -> Dict[str, Path]:
        specialists_dir = self._project_root / "config" / "specialists"
        if not specialists_dir.is_dir():
            return {}

        configs: Dict[str, Path] = {}
        for yaml_file in sorted(specialists_dir.glob("*.yaml")):
            data = self._load_yaml(yaml_file)
            name = data.get("specialist", {}).get("name")
            if name is None:
                continue
            configs[name] = yaml_file
        return configs

    @staticmethod
    def _load_yaml(path: Path) -> Dict[str, Any]:
        with open(path, "r") as fh:
            return yaml.safe_load(fh) or {}

    # -- private: validation --------------------------------------------------------

    def _validate(self) -> None:
        self._validate_endpoints()
        self._validate_models()
        self._validate_teacher()
        self._validate_teacher_benchmark()
        self._validate_pipeline_specialists()
        self._validate_fp4_export()

    def _validate_endpoints(self) -> None:
        endpoints = self._global_config.get("endpoints")
        if not isinstance(endpoints, dict) or len(endpoints) == 0:
            raise ConfigValidationError("endpoints", "must be a non-empty dictionary")

        for ep_name, ep_data in endpoints.items():
            prefix = f"endpoints.{ep_name}"
            if not isinstance(ep_data, dict):
                raise ConfigValidationError(prefix, "must be a dictionary")
            if "url" not in ep_data or not isinstance(ep_data["url"], str):
                raise ConfigValidationError(f"{prefix}.url", "missing required field 'url' (string)")
            if "apiType" not in ep_data:
                raise ConfigValidationError(f"{prefix}.apiType", "missing required field 'apiType'")
            if ep_data["apiType"] not in _VALID_API_TYPES:
                raise ConfigValidationError(
                    f"{prefix}.apiType",
                    f"must be one of {sorted(_VALID_API_TYPES)}, got '{ep_data['apiType']}'",
                )

    def _validate_models(self) -> None:
        models = self._global_config.get("models")
        if not isinstance(models, dict) or len(models) == 0:
            raise ConfigValidationError("models", "must be a non-empty dictionary")

        endpoints = set(self._global_config.get("endpoints", {}).keys())

        for model_name, model_data in models.items():
            prefix = f"models.{model_name}"
            if not isinstance(model_data, dict):
                raise ConfigValidationError(prefix, "must be a dictionary")
            if "endpoint" not in model_data:
                raise ConfigValidationError(f"{prefix}.endpoint", "missing required field 'endpoint'")
            endpoint_ref = model_data["endpoint"]
            if endpoint_ref not in endpoints:
                raise ConfigValidationError(
                    f"{prefix}.endpoint",
                    f"references unknown endpoint '{endpoint_ref}'; "
                    f"available endpoints: {', '.join(sorted(endpoints))}",
                )

    def _validate_teacher(self) -> None:
        teacher = self._global_config.get("teacher")
        if not isinstance(teacher, dict):
            raise ConfigValidationError("teacher", "must be a dictionary")

        if "level1" not in teacher:
            raise ConfigValidationError("teacher.level1", "missing required field 'level1'")

        level1_model = teacher["level1"]
        models = self._global_config.get("models", {})
        if level1_model not in models:
            raise ConfigValidationError(
                "teacher.level1",
                f"references unknown model '{level1_model}'; "
                f"available models: {', '.join(sorted(models.keys()))}",
            )

    def _validate_teacher_benchmark(self) -> None:
        benchmark = self._global_config.get("teacher_benchmark")
        if not isinstance(benchmark, dict):
            raise ConfigValidationError("teacher_benchmark", "must be a dictionary")

        models = set(self._global_config.get("models", {}).keys())

        for domain, domain_scores in benchmark.items():
            prefix = f"teacher_benchmark.{domain}"
            if not isinstance(domain_scores, dict):
                raise ConfigValidationError(prefix, "must be a dictionary of model_name -> score")
            for model_name, score in domain_scores.items():
                if model_name not in models:
                    raise ConfigValidationError(
                        f"{prefix}.{model_name}",
                        f"references unknown model '{model_name}'; "
                        f"available models: {', '.join(sorted(models))}",
                    )
                if not isinstance(score, (int, float)):
                    raise ConfigValidationError(
                        f"{prefix}.{model_name}",
                        f"score must be a number, got {type(score).__name__}",
                    )

    def _validate_pipeline_specialists(self) -> None:
        pipeline = self._global_config.get("pipeline")
        if not isinstance(pipeline, dict):
            raise ConfigValidationError("pipeline", "must be a dictionary")

        specialists = pipeline.get("specialists")
        if not isinstance(specialists, list) or len(specialists) == 0:
            raise ConfigValidationError(
                "pipeline.specialists",
                "must be a non-empty list of strings",
            )
        for i, spec in enumerate(specialists):
            if not isinstance(spec, str):
                raise ConfigValidationError(
                    f"pipeline.specialists[{i}]",
                    "must be a string",
                )

    def _validate_fp4_export(self) -> None:
        """Validate the fp4_export configuration block.

        Per D-08: fp4_export is optional (Phase 1/2 may run without quantization).
        When present, validates error_thresholds per block size, ternary_delta range,
        min_block_size power-of-2, laplacian_levels, and log_mode_enabled type.
        """
        fp4_export = self._global_config.get("fp4_export")

        # fp4_export block is optional — absent means quantization not configured
        if fp4_export is None:
            import logging
            logging.getLogger(__name__).warning(
                "fp4_export block not found in pipeline.yaml; "
                "quantization configuration not validated"
            )
            return

        if not isinstance(fp4_export, dict):
            raise ConfigValidationError("fp4_export", "must be a dictionary")

        # --- error_thresholds -------------------------------------------------
        error_thresholds = fp4_export.get("error_thresholds")
        prefix_et = "fp4_export.error_thresholds"

        if error_thresholds is not None:
            if not isinstance(error_thresholds, dict):
                raise ConfigValidationError(prefix_et, "must be a dictionary")

            required_block_sizes = [64, 32, 16, 8, 4]
            for size in required_block_sizes:
                # Allow both integer and string keys (YAML parses keys as int or str)
                if size not in error_thresholds and str(size) not in error_thresholds:
                    raise ConfigValidationError(
                        prefix_et,
                        f"missing required block size: {size}",
                    )

                entry = error_thresholds.get(size, error_thresholds.get(str(size)))
                if not isinstance(entry, dict):
                    raise ConfigValidationError(
                        f"{prefix_et}.{size}",
                        f"must be a dictionary with max_mse and max_relative",
                    )

                for field_name in ("max_mse", "max_relative"):
                    field_path = f"{prefix_et}.{size}.{field_name}"
                    value = entry.get(field_name)
                    if value is None:
                        raise ConfigValidationError(field_path, f"missing required field '{field_name}'")
                    if not isinstance(value, (int, float)):
                        raise ConfigValidationError(
                            field_path,
                            f"must be a number, got {type(value).__name__}",
                        )
                    if value <= 0.0:
                        raise ConfigValidationError(
                            field_path,
                            f"must be positive (> 0), got {value}",
                        )

        # --- ternary_delta ----------------------------------------------------
        ternary_delta = fp4_export.get("ternary_delta")
        if ternary_delta is not None:
            if not isinstance(ternary_delta, (int, float)):
                raise ConfigValidationError(
                    "fp4_export.ternary_delta",
                    f"must be a number, got {type(ternary_delta).__name__}",
                )
            if ternary_delta < 0.0 or ternary_delta > 1.0:
                raise ConfigValidationError(
                    "fp4_export.ternary_delta",
                    f"must be in range [0.0, 1.0], got {ternary_delta}",
                )

        # --- min_block_size ---------------------------------------------------
        min_block_size = fp4_export.get("min_block_size")
        if min_block_size is not None:
            if not isinstance(min_block_size, int):
                raise ConfigValidationError(
                    "fp4_export.min_block_size",
                    f"must be an integer, got {type(min_block_size).__name__}",
                )
            if min_block_size not in (4, 8, 16, 32, 64):
                raise ConfigValidationError(
                    "fp4_export.min_block_size",
                    f"must be a power of 2 in {{4, 8, 16, 32, 64}}, got {min_block_size}",
                )

        # --- laplacian_levels -------------------------------------------------
        laplacian_levels = fp4_export.get("laplacian_levels")
        if laplacian_levels is not None:
            if not isinstance(laplacian_levels, int):
                raise ConfigValidationError(
                    "fp4_export.laplacian_levels",
                    f"must be an integer, got {type(laplacian_levels).__name__}",
                )
            if laplacian_levels < 1:
                raise ConfigValidationError(
                    "fp4_export.laplacian_levels",
                    f"must be >= 1, got {laplacian_levels}",
                )

        # --- log_mode_enabled -------------------------------------------------
        log_mode_enabled = fp4_export.get("log_mode_enabled")
        if log_mode_enabled is not None and not isinstance(log_mode_enabled, bool):
            raise ConfigValidationError(
                "fp4_export.log_mode_enabled",
                f"must be a boolean, got {type(log_mode_enabled).__name__}",
            )

    # -- private: override resolution ------------------------------------------------

    def _apply_specialist_overrides(
        self,
        effective: Dict[str, Any],
        specialist_data: Dict[str, Any],
    ) -> None:
        """Deep-merge specialist overrides into *effective* config in-place."""
        spec_block = specialist_data.get("specialist", {})
        if not isinstance(spec_block, dict):
            return

        # base_model override: specialist.base_model -> training.base_model
        if "base_model" in spec_block:
            effective.setdefault("training", {})["base_model"] = spec_block["base_model"]

        # training.* overrides
        spec_training = spec_block.get("training", {})
        if isinstance(spec_training, dict):
            for key, value in spec_training.items():
                effective.setdefault("training", {})[key] = value

        # system_prompt and synthetic_prompts — surfaced as top-level specialist keys
        if "system_prompt" in spec_block:
            effective.setdefault("specialist", {})["system_prompt"] = spec_block["system_prompt"]

        if "synthetic_prompts" in spec_block:
            effective.setdefault("specialist", {})["synthetic_prompts"] = spec_block["synthetic_prompts"]

        if "niche_sources" in spec_block:
            effective.setdefault("specialist", {})["niche_sources"] = spec_block["niche_sources"]


# -- self-test (run: python config/loader.py) -------------------------------------

if __name__ == "__main__":
    import sys

    project_root = Path(__file__).resolve().parent.parent
    passed = 0
    failed = 0

    def check(name: str, condition: bool, detail: str = "") -> None:
        global passed, failed
        if condition:
            passed += 1
            print(f"  PASS  {name}")
        else:
            failed += 1
            print(f"  FAIL  {name}{' — ' + detail if detail else ''}")

    # Test 1: Basic loading
    try:
        loader = ConfigLoader(project_root)
        check("ConfigLoader(project_root) loads without error", True)
    except Exception as exc:
        check("ConfigLoader(project_root) loads without error", False, str(exc))
        sys.exit(1)

    # Test 2: endpoints and models present
    check("endpoints in global config", "endpoints" in loader._global_config)
    check("models in global config", "models" in loader._global_config)
    check("teacher_benchmark in global config", "teacher_benchmark" in loader._global_config)

    # Test 3: code specialist override (base_model differs from global)
    eff_code = loader.get_effective_config("code")
    check(
        "code specialist uses Qwen3-Coder base_model",
        eff_code["training"]["base_model"] == "mlx-community/Qwen3-Coder-30B-A3B-Instruct-bf16",
        eff_code["training"]["base_model"],
    )

    # Test 4: medical uses global default (no override)
    eff_med = loader.get_effective_config("medical")
    check(
        "medical uses global default base_model",
        eff_med["training"]["base_model"] == "mlx-community/Qwen3-30B-A3B-Instruct-2507-bf16",
        eff_med["training"]["base_model"],
    )

    # Test 5: unknown niche raises ConfigValidationError
    try:
        loader.get_effective_config("nonexistent")
        check("unknown niche raises ConfigValidationError", False, "no exception raised")
    except ConfigValidationError as exc:
        check("unknown niche raises ConfigValidationError", "nonexistent" in str(exc), str(exc))

    # Test 6: system_prompt surfaced
    check(
        "code specialist system_prompt surfaced",
        "You are a programming" in eff_code.get("specialist", {}).get("system_prompt", ""),
    )

    # Test 7: synthetic_prompts surfaced
    check(
        "code specialist synthetic_prompts surfaced",
        isinstance(eff_code.get("specialist", {}).get("synthetic_prompts"), list),
    )

    # Test 8: global keys preserved in effective config
    check("effective config preserves endpoints", "endpoints" in eff_code)
    check("effective config preserves paths", "paths" in eff_code)
    check("effective config preserves evaluation", "evaluation" in eff_code)

    # Test 9: fp4_export validation — no error on valid config
    try:
        fp4_export = loader._global_config.get("fp4_export", {})
        loader._validate_fp4_export()
        check("fp4_export validation passes on valid config", True)
    except ConfigValidationError as exc:
        check("fp4_export validation passes on valid config", False, str(exc))

    # Test 10: fp4_export with missing block size raises error
    saved_fp4 = loader._global_config.get("fp4_export")
    if saved_fp4 and "error_thresholds" in saved_fp4:
        saved_et = dict(saved_fp4["error_thresholds"])
        # Simulate: remove block size 4
        bad_et = {k: v for k, v in saved_et.items() if k != 4 and k != "4"}
        loader._global_config["fp4_export"]["error_thresholds"] = bad_et
        try:
            loader._validate_fp4_export()
            check("missing block size 4 raises ConfigValidationError", False, "no exception raised")
        except ConfigValidationError as exc:
            check("missing block size 4 raises ConfigValidationError", "missing required block size: 4" in str(exc), str(exc))
        # Restore
        loader._global_config["fp4_export"]["error_thresholds"] = saved_et

    # Test 11: negative max_mse raises ConfigValidationError
    if saved_fp4 and "error_thresholds" in saved_fp4:
        saved_et = dict(saved_fp4["error_thresholds"])
        bad_et = dict(saved_et)
        saved_64 = dict(saved_et.get(64, saved_et.get("64", {})))
        bad_et[64] = dict(saved_64)
        bad_et[64]["max_mse"] = -1.0
        loader._global_config["fp4_export"]["error_thresholds"] = bad_et
        try:
            loader._validate_fp4_export()
            check("negative max_mse raises ConfigValidationError", False, "no exception raised")
        except ConfigValidationError as exc:
            check("negative max_mse raises ConfigValidationError",
                  "positive" in str(exc) and "-1" in str(exc), str(exc))
        # Restore
        loader._global_config["fp4_export"]["error_thresholds"] = saved_et

    # Test 12: ternary_delta out of range raises ConfigValidationError
    if saved_fp4:
        saved_delta = saved_fp4.get("ternary_delta")
        loader._global_config["fp4_export"]["ternary_delta"] = 1.5
        try:
            loader._validate_fp4_export()
            check("ternary_delta=1.5 raises ConfigValidationError", False, "no exception raised")
        except ConfigValidationError as exc:
            check("ternary_delta=1.5 raises ConfigValidationError",
                  "1.5" in str(exc), str(exc))
        loader._global_config["fp4_export"]["ternary_delta"] = saved_delta

    # Test 13: min_block_size=3 raises ConfigValidationError
    if saved_fp4:
        saved_mbs = saved_fp4.get("min_block_size")
        loader._global_config["fp4_export"]["min_block_size"] = 3
        try:
            loader._validate_fp4_export()
            check("min_block_size=3 raises ConfigValidationError", False, "no exception raised")
        except ConfigValidationError as exc:
            check("min_block_size=3 raises ConfigValidationError",
                  "power of 2" in str(exc) and "3" in str(exc), str(exc))
        loader._global_config["fp4_export"]["min_block_size"] = saved_mbs

    # Test 14: absent fp4_export block does not raise error
    saved_fp4_block = loader._global_config.pop("fp4_export", None)
    try:
        loader._validate_fp4_export()
        check("absent fp4_export block succeeds (warning only)", True)
    except ConfigValidationError as exc:
        check("absent fp4_export block succeeds (warning only)", False, str(exc))
    if saved_fp4_block is not None:
        loader._global_config["fp4_export"] = saved_fp4_block

    print(f"\n  {passed} passed, {failed} failed")
    sys.exit(0 if failed == 0 else 1)
