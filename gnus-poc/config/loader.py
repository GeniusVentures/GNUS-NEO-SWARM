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

    print(f"\n  {passed} passed, {failed} failed")
    sys.exit(0 if failed == 0 else 1)
