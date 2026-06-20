"""Multi-backend teacher API client with cost controls, retry, and circuit breaker.

Dispatches teacher calls to the correct backend (OpenAI or Anthropic) based on the
model's configured endpoint ``apiType``.  All backends produce a uniform response
wrapper so callers receive the same interface regardless of backend.
"""

import json
import os
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import yaml

from distill.backends.openai_backend import OpenAIBackend
from distill.backends.anthropic_backend import AnthropicBackend
from distill.cascade import TeacherCascade
from distill.teacher_errors import (
    BackendNotFoundError,
    BudgetExceededError,
    CircuitBreakerOpenError,
    TeacherConfigError,
)

HTTP_NON_RETRYABLE = {400, 401, 402, 403, 404, 405, 422}
HTTP_RATE_LIMIT = 429

NON_RETRYABLE_EXCEPTIONS = (
    BudgetExceededError,
    CircuitBreakerOpenError,
    TeacherConfigError,
    BackendNotFoundError,
)

_SUPPORTED_API_TYPES = ("openai", "anthropic")


def _backend_class_for(api_type: str):
    """Resolve apiType string to backend class."""
    if api_type == "openai":
        return OpenAIBackend
    if api_type == "anthropic":
        return AnthropicBackend
    return None


class _ResponseWrapper:
    """Lightweight adapter that makes a uniform backend dict look like an
    OpenAI ``chat.completions.create`` response for backward compatibility."""

    def __init__(self, uniform: dict):
        class _Choice:
            def __init__(self, msg_content):
                self.message = _Choice._Message(msg_content)

            class _Message:
                def __init__(self, content):  # noqa: N805
                    self.content = content

        class _Usage:
            def __init__(self, prompt_tokens, completion_tokens):
                self.prompt_tokens = prompt_tokens
                self.completion_tokens = completion_tokens

        self.choices = [_Choice(uniform["content"])]
        self.usage = _Usage(uniform["prompt_tokens"], uniform["completion_tokens"])
        self._raw_response = uniform["raw_response"]


class TeacherClient:
    """Multi-backend teacher API client.

    Builds a backend registry from ``config/pipeline.yaml`` endpoints and
    dispatches each ``generate()`` call to the correct backend based on the
    model's endpoint ``apiType``.

    Backends are constructed lazily on first use so that test code can inject
    mock backends via ``client._backends`` without triggering real SDK imports.
    """

    def __init__(self, config_path: Optional[Path] = None, project_root: Optional[Path] = None):
        if project_root is None:
            project_root = Path(__file__).resolve().parent.parent
        self._project_root = project_root

        if config_path is None:
            config_path = project_root / "config" / "pipeline.yaml"
        self._config = self._load_config(config_path)

        # --- Endpoints & models (new two-layer config) ---
        endpoints_cfg = self._config.get("endpoints", {})
        models_cfg = self._config.get("models", {})
        teacher_cfg = self._config.get("teacher", {})

        if not endpoints_cfg:
            raise TeacherConfigError("No 'endpoints' block found in pipeline.yaml")
        if not models_cfg:
            raise TeacherConfigError("No 'models' block found in pipeline.yaml")

        self._models = models_cfg

        # --- Teacher settings ---
        self._default_max_tokens = int(teacher_cfg.get("max_tokens", 4096))
        self._default_temperature = float(teacher_cfg.get("temperature", 0.7))
        self._max_retries = int(teacher_cfg.get("max_retries", 3))
        self._backoff_base = float(teacher_cfg.get("backoff_base_seconds", 2.0))
        self._budget_cap = float(teacher_cfg.get("budget_cap_usd", 5.0))
        self._max_consecutive_failures = int(
            teacher_cfg.get("circuit_breaker_failure_threshold", 5)
        )
        self._circuit_recovery_timeout = float(
            teacher_cfg.get("circuit_breaker_recovery_timeout", 60)
        )

        # --- Backend registry (lazy) ---
        # Store endpoint configs so backends can be constructed on first use.
        # Keys: endpoint name.  Values: (endpoint_config, api_key).
        self._endpoint_registry = {}
        for endpoint_name, ep_cfg in endpoints_cfg.items():
            api_type = ep_cfg.get("apiType", "").lower()
            if api_type not in _SUPPORTED_API_TYPES:
                raise TeacherConfigError(
                    f"Unknown apiType '{ep_cfg.get('apiType')}' for endpoint "
                    f"'{endpoint_name}'. Supported: {list(_SUPPORTED_API_TYPES)}"
                )
            api_key = self._resolve_api_key(endpoint_name, api_type)
            self._endpoint_registry[endpoint_name] = (ep_cfg, api_key)

        # Lazily-created backend instances.  Tests may replace entries with mocks.
        self._backends = {}

        # --- Teacher cascade orchestrator ---
        teacher_benchmark = self._config.get("teacher_benchmark", {})
        level1_model = teacher_cfg.get("level1", list(self._models.keys())[0] if self._models else "deepseek-v4-fast")
        confidence_threshold = float(teacher_cfg.get("confidence_threshold", 0.7))
        self._cascade = TeacherCascade(
            teacher_client=self,
            benchmark_table=teacher_benchmark,
            level1_model=level1_model,
            confidence_threshold=confidence_threshold,
        )

        # --- Runtime state ---
        self._total_cost = 0.0
        self._budget_version = 1
        self._call_count = 0
        self._consecutive_failures = 0
        self._circuit_open = False
        self._circuit_opened_at = None
        self._circuit_half_open = False

        self._cost_log_path = project_root / "artifacts" / "api_cost.jsonl"
        self._error_log_path = project_root / "artifacts" / "api_errors.jsonl"
        self._cost_log_path.parent.mkdir(parents=True, exist_ok=True)

        self._budget_state_path = project_root / "artifacts" / ".budget_state.json"
        self._load_budget_state()

    # ------------------------------------------------------------------
    # API key resolution
    # ------------------------------------------------------------------

    @staticmethod
    def _resolve_api_key(endpoint_name: str, api_type: str) -> str:
        """Resolve the API key for an endpoint.

        Priority:
        1. ``LITELLM_API_KEY`` env var (for LiteLLM proxy endpoints)
        2. ``{ENDPOINT_NAME_UPPER}_API_KEY`` env var
        3. ``{API_TYPE_UPPER}_API_KEY`` env var (e.g. ``ANTHROPIC_API_KEY``)

        Raises:
            TeacherConfigError: If no API key is found.
        """
        candidates = [
            "LITELLM_API_KEY",
            f"{endpoint_name.upper()}_API_KEY",
            f"{api_type.upper()}_API_KEY",
        ]
        for var_name in candidates:
            key = os.getenv(var_name)
            if key:
                return key
        raise TeacherConfigError(
            f"No API key found for endpoint '{endpoint_name}' ({api_type}). "
            f"Set one of: {', '.join(candidates)} in gnus-poc/.env or environment."
        )

    # ------------------------------------------------------------------
    # Config loading
    # ------------------------------------------------------------------

    def _load_config(self, config_path):
        with config_path.open() as f:
            return yaml.safe_load(f)

    # ------------------------------------------------------------------
    # Backend dispatch
    # ------------------------------------------------------------------

    def _get_or_create_backend(self, endpoint_name: str):
        """Return (possibly creating) the backend instance for an endpoint.

        Backends are created lazily so that tests may inject mocks into
        ``self._backends`` before any real SDK client is constructed.
        """
        if endpoint_name not in self._backends:
            ep_cfg, api_key = self._endpoint_registry[endpoint_name]
            api_type = ep_cfg.get("apiType", "").lower()
            backend_cls = _backend_class_for(api_type)
            # api_type is already validated in __init__, so backend_cls is not None
            self._backends[endpoint_name] = backend_cls(
                endpoint_config=ep_cfg,
                model_id="",  # placeholder — real model_id is set per-call
                api_key=api_key,
            )
        return self._backends[endpoint_name]

    def _resolve_backend(self, model_name: str):
        """Look up the backend instance for a model name.

        Args:
            model_name: Key in the ``models`` config block (e.g. ``"deepseek-v4-fast"``).

        Returns:
            A ``TeacherBackend`` instance.

        Raises:
            TeacherConfigError: If the model or its endpoint is unknown.
        """
        model_cfg = self._models.get(model_name)
        if model_cfg is None:
            raise TeacherConfigError(
                f"Unknown model '{model_name}'. "
                f"Available: {list(self._models.keys())}"
            )
        endpoint_name = model_cfg.get("endpoint")
        if endpoint_name is None:
            raise TeacherConfigError(
                f"Model '{model_name}' has no 'endpoint' configured."
            )
        if endpoint_name not in self._endpoint_registry:
            raise TeacherConfigError(
                f"Endpoint '{endpoint_name}' not found for model '{model_name}'."
            )
        return self._get_or_create_backend(endpoint_name)

    # ------------------------------------------------------------------
    # Cost estimation (delegates to backends)
    # ------------------------------------------------------------------

    def _estimate_cost(self, prompt_tokens: int, completion_tokens: int) -> float:
        # Use the default formula from TeacherBackend
        from distill.backends.base import TeacherBackend
        return TeacherBackend.estimate_cost(prompt_tokens, completion_tokens)

    # ------------------------------------------------------------------
    # Logging
    # ------------------------------------------------------------------

    def _log_cost(self, model_name: str, prompt_tokens: int, completion_tokens: int, cost: float):
        record = {
            "timestamp": datetime.now().isoformat(),
            "model": model_name,
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
            "cost_usd": round(cost, 6),
            "cumulative_cost_usd": round(self._total_cost, 6),
            "call_number": self._call_count,
        }
        with self._cost_log_path.open("a") as f:
            f.write(json.dumps(record) + "\n")

    def _log_error(self, error_type: str, status_code: Optional[int], detail: str):
        record = {
            "timestamp": datetime.now().isoformat(),
            "error_type": error_type,
            "status_code": status_code,
            "detail": detail,
        }
        with self._error_log_path.open("a") as f:
            f.write(json.dumps(record) + "\n")

    # ------------------------------------------------------------------
    # Budget state persistence (disk)
    # ------------------------------------------------------------------

    def _load_budget_state(self):
        """Load cumulative spend from ``artifacts/.budget_state.json``.

        Budget state file format::

            {
                "cumulative_cost_usd": 1.234,
                "budget_cap_usd": 5.0,
                "last_updated": "2026-06-19T12:00:00+00:00",
                "version": 1
            }

        If the file does not exist the budget starts at ``0.0``.
        The budget state file can be edited manually — it is a soft
        cost-control limit, not a security boundary (see T-04-01).
        """
        if self._budget_state_path.exists():
            try:
                data = json.loads(self._budget_state_path.read_text())
                self._total_cost = float(data.get("cumulative_cost_usd", 0.0))
                self._budget_version = int(data.get("version", 1))
                print(
                    f"Budget state loaded: ${self._total_cost:.4f} "
                    f"of ${self._budget_cap:.2f}"
                )
            except (json.JSONDecodeError, ValueError, KeyError):
                self._total_cost = 0.0
                self._budget_version = 1
        else:
            self._total_cost = 0.0
            self._budget_version = 1

    def _save_budget_state(self):
        """Persist current cumulative spend to ``artifacts/.budget_state.json``.

        Called after every successful API call that adds cost.  Creates
        parent directories if they do not exist.
        """
        self._budget_state_path.parent.mkdir(parents=True, exist_ok=True)
        data = {
            "cumulative_cost_usd": round(self._total_cost, 6),
            "budget_cap_usd": self._budget_cap,
            "last_updated": datetime.now(timezone.utc).isoformat(),
            "version": self._budget_version,
        }
        self._budget_state_path.write_text(json.dumps(data, indent=2) + "\n")

    def reset_budget(self):
        """Reset cumulative spend to zero and persist the change.

        Used by the pipeline runner when the ``--reset-budget`` CLI flag
        is passed.
        """
        self._total_cost = 0.0
        self._save_budget_state()
        print("Budget reset — cumulative spend set to $0.00")

    # ------------------------------------------------------------------
    # Circuit breaker & budget (runtime gates)
    # ------------------------------------------------------------------

    def _check_circuit(self):
        """Gate API calls through a half-open circuit breaker.

        **Closed:**  calls proceed normally.
        **Open:**    calls are blocked for ``recovery_timeout`` seconds.
                     After the timeout elapses the circuit transitions to
                     *half-open* — the next call is allowed as a probe.
        **Half-open:** a single probe call is permitted.  If it succeeds
                     the circuit closes.  If it fails the circuit re-opens
                     with a fresh recovery timer.

        Raises:
            CircuitBreakerOpenError: When the circuit is open and the
                recovery timeout has not elapsed.
        """
        if not self._circuit_open:
            return  # circuit closed — allow calls

        if self._circuit_opened_at is None:
            return  # safety: should not happen

        elapsed = (datetime.now(timezone.utc) - self._circuit_opened_at).total_seconds()
        if elapsed >= self._circuit_recovery_timeout:
            self._circuit_half_open = True
            return  # allow one probe request

        remaining = self._circuit_recovery_timeout - elapsed
        raise CircuitBreakerOpenError(
            f"Circuit breaker open. {remaining:.0f}s remaining "
            f"until half-open probe."
        )

    def _check_budget(self):
        """Raise ``BudgetExceededError`` when cumulative spend hits the cap.

        Budget enforcement reads the persisted total from disk on startup
        (see ``_load_budget_state``), so the cap applies across runs.
        """
        if self._total_cost >= self._budget_cap:
            raise BudgetExceededError(
                f"Budget cap exceeded: ${self._total_cost:.4f} >= ${self._budget_cap:.2f}"
            )

    # ------------------------------------------------------------------
    # Retry classification
    # ------------------------------------------------------------------

    def _is_retryable(self, exception: Exception) -> bool:
        status_code = getattr(exception, "status_code", None)
        if status_code is not None:
            if status_code in HTTP_NON_RETRYABLE:
                return False
            if status_code == HTTP_RATE_LIMIT:
                return True
        return True

    # ------------------------------------------------------------------
    # Core API call
    # ------------------------------------------------------------------

    def _call_api(self, model_name: str, messages, **kwargs):
        """Execute an API call through the correct backend with retry + circuit breaker.

        Circuit breaker state machine:

        * **Closed** → calls proceed; after ``failure_threshold`` consecutive
          failures the circuit **opens** with a timestamp.
        * **Open** → calls are blocked for ``recovery_timeout`` seconds.
        * **Half-open** → one probe call is allowed.  Success **closes** the
          circuit.  Failure **re-opens** it with a fresh recovery timer.

        Args:
            model_name: Key from the ``models`` config block.
            messages: List of message dicts (OpenAI format).
            **kwargs: Passed to ``backend.generate()`` (max_tokens, temperature, etc.).

        Returns:
            ``_ResponseWrapper`` with ``.choices[0].message.content`` and ``.usage``.
        """
        self._check_circuit()
        self._check_budget()

        backend = self._resolve_backend(model_name)

        # Apply defaults for max_tokens and temperature if not explicitly passed
        max_tokens = kwargs.pop("max_tokens", self._default_max_tokens)
        temperature = kwargs.pop("temperature", self._default_temperature)

        last_exception = None
        for attempt in range(self._max_retries):
            try:
                uniform = backend.generate(
                    messages=messages,
                    max_tokens=max_tokens,
                    temperature=temperature,
                    **kwargs,
                )
                # Success — close the circuit if it was half-open
                if self._circuit_half_open:
                    self._circuit_open = False
                    self._circuit_half_open = False
                    self._circuit_opened_at = None
                    print("Circuit breaker closed — half-open probe succeeded")
                return _ResponseWrapper(uniform)
            except NON_RETRYABLE_EXCEPTIONS:
                raise
            except Exception as e:
                last_exception = e
                if not self._is_retryable(e):
                    raise
                self._consecutive_failures += 1
                self._log_error(type(e).__name__, getattr(e, "status_code", None), str(e))

                if self._consecutive_failures >= self._max_consecutive_failures:
                    if self._circuit_half_open:
                        # Half-open probe failed — re-open with fresh timer
                        self._circuit_half_open = False
                        self._circuit_opened_at = datetime.now(timezone.utc)
                        raise CircuitBreakerOpenError(
                            "Half-open probe failed. Circuit re-opened."
                        ) from e
                    if not self._circuit_open:
                        # Open the circuit for the first time
                        self._circuit_open = True
                        self._circuit_opened_at = datetime.now(timezone.utc)
                        self._circuit_half_open = False
                        raise CircuitBreakerOpenError(
                            f"Circuit breaker opened after "
                            f"{self._consecutive_failures} consecutive failures."
                        ) from e

                if attempt < self._max_retries - 1:
                    delay = self._backoff_base * (2 ** attempt)
                    time.sleep(delay)

        raise last_exception

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def generate(self, model_name: Optional[str] = None, messages=None, **kwargs):
        """Generate a completion through the appropriate backend.

        Args:
            model_name: Model key from the ``models`` config block.  If ``None``,
                defaults to ``teacher.level1`` from pipeline.yaml.
            messages: List of message dicts (OpenAI format).
            **kwargs: Extra parameters forwarded to the backend.

        Returns:
            ``_ResponseWrapper`` with ``.choices[0].message.content`` and ``.usage``.
        """
        if model_name is None:
            model_name = self._config["teacher"].get(
                "level1", list(self._models.keys())[0]
            )
        if messages is None:
            raise TeacherConfigError("messages parameter is required")

        response = self._call_api(model_name, messages, **kwargs)
        self._consecutive_failures = 0
        self._call_count += 1
        usage = response.usage
        cost = self._estimate_cost(usage.prompt_tokens, usage.completion_tokens)
        self._total_cost += cost
        self._log_cost(model_name, usage.prompt_tokens, usage.completion_tokens, cost)
        self._save_budget_state()
        return response

    def generate_with_logprobs(self, model_name: Optional[str] = None, messages=None, **kwargs):
        """Generate with log-probabilities (OpenAI-compatible endpoints only).

        Args:
            model_name: Model key (defaults to ``teacher.level1``).
            messages: List of message dicts.
            **kwargs: Extra parameters.

        Returns:
            ``_ResponseWrapper`` with logprobs data.
        """
        kwargs["logprobs"] = True
        kwargs["top_logprobs"] = kwargs.get("top_logprobs", 20)
        return self.generate(model_name, messages, **kwargs)

    def generate_with_cascade(self, messages, domain="encyclopedic", **kwargs):
        """Generate a completion using the multi-teacher cascade.

        Routes through ``TeacherCascade.execute()``: Level 1 always runs;
        Level 2 is invoked only when Level 1 confidence is below threshold
        and the best Level 2 teacher is selected from the benchmark table.

        Args:
            messages: List of message dicts (OpenAI format).
            domain: Specialist niche name (e.g. ``"code"``, ``"medical"``).
                Defaults to ``"encyclopedic"``.
            **kwargs: Extra parameters forwarded to each teacher call.

        Returns:
            ``_ResponseWrapper`` with ``.choices[0].message.content`` set to
            the cascade's final content.  The raw response payload is the
            cascade result dict (for logging / inspection).
        """
        result = self._cascade.execute(messages, domain, **kwargs)
        uniform = {
            "content": result.final_content,
            "prompt_tokens": 0,
            "completion_tokens": 0,
            "raw_response": result.to_dict(),
        }
        return _ResponseWrapper(uniform)

    # ------------------------------------------------------------------
    # Properties
    # ------------------------------------------------------------------

    @property
    def total_cost(self):
        return self._total_cost

    @property
    def budget_cap(self):
        return self._budget_cap

    @property
    def circuit_open(self):
        return self._circuit_open

    @property
    def call_count(self):
        return self._call_count
