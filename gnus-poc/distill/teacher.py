"""DeepSeek v4 pro API client with cost controls, retry, and circuit breaker."""

import json
import os
import time
from datetime import datetime
from pathlib import Path
from typing import Optional

import yaml
from openai import OpenAI

from distill.teacher_errors import (
    BudgetExceededError,
    CircuitBreakerOpenError,
    TeacherConfigError,
)

HTTP_NON_RETRYABLE = {400, 401, 402, 403, 404, 405, 422}
HTTP_RATE_LIMIT = 429


class TeacherClient:
    def __init__(self, config_path: Optional[Path] = None, project_root: Optional[Path] = None):
        if project_root is None:
            project_root = Path(__file__).resolve().parent.parent
        self._project_root = project_root

        if config_path is None:
            config_path = project_root / "config" / "pipeline.yaml"
        self._config = self._load_config(config_path)

        teacher_cfg = self._config["teacher"]
        api_key = os.getenv(teacher_cfg.get("api_key_env", "DEEPSEEK_API_KEY"))
        if not api_key:
            raise TeacherConfigError(
                f"API key not found. Set {teacher_cfg.get('api_key_env', 'DEEPSEEK_API_KEY')} "
                f"in gnus-poc/.env or environment."
            )

        self._client = OpenAI(
            api_key=api_key,
            base_url=teacher_cfg.get("base_url", "https://api.deepseek.com"),
        )
        self._model = teacher_cfg.get("model", "deepseek-v4-pro")
        self._max_tokens = teacher_cfg.get("max_tokens", 4096)
        self._temperature = teacher_cfg.get("temperature", 0.7)
        self._max_retries = int(teacher_cfg.get("max_retries", 3))
        self._backoff_base = float(teacher_cfg.get("backoff_base_seconds", 2.0))
        self._budget_cap = float(teacher_cfg.get("budget_cap_usd", 5.0))

        self._total_cost = 0.0
        self._call_count = 0
        self._consecutive_failures = 0
        self._max_consecutive_failures = 5
        self._circuit_open = False

        self._cost_log_path = project_root / "artifacts" / "api_cost.jsonl"
        self._error_log_path = project_root / "artifacts" / "api_errors.jsonl"
        self._cost_log_path.parent.mkdir(parents=True, exist_ok=True)

    def _load_config(self, config_path):
        with config_path.open() as f:
            return yaml.safe_load(f)

    def _estimate_cost(self, prompt_tokens: int, completion_tokens: int) -> float:
        return (prompt_tokens * 0.27 + completion_tokens * 1.10) / 1_000_000

    def _log_cost(self, prompt_tokens: int, completion_tokens: int, cost: float):
        record = {
            "timestamp": datetime.now().isoformat(),
            "model": self._model,
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

    def _check_circuit(self):
        if self._circuit_open:
            raise CircuitBreakerOpenError("Circuit breaker is open. Too many consecutive failures.")

    def _check_budget(self):
        if self._total_cost >= self._budget_cap:
            raise BudgetExceededError(
                f"Budget cap exceeded: ${self._total_cost:.4f} >= ${self._budget_cap:.2f}"
            )

    def _is_retryable(self, exception: Exception) -> bool:
        status_code = getattr(exception, "status_code", None)
        if status_code is not None:
            if status_code in HTTP_NON_RETRYABLE:
                return False
            if status_code == HTTP_RATE_LIMIT:
                return True
        return True

    def _call_api(self, messages, **kwargs):
        self._check_circuit()
        self._check_budget()

        last_exception = None
        for attempt in range(self._max_retries):
            try:
                response = self._client.chat.completions.create(
                    model=self._model,
                    messages=messages,
                    max_tokens=kwargs.get("max_tokens", self._max_tokens),
                    temperature=kwargs.get("temperature", self._temperature),
                )
                return response
            except NON_RETRYABLE_EXCEPTIONS:
                raise
            except Exception as e:
                last_exception = e
                if not self._is_retryable(e):
                    raise
                self._consecutive_failures += 1
                self._log_error(type(e).__name__, getattr(e, "status_code", None), str(e))
                if self._consecutive_failures >= self._max_consecutive_failures:
                    self._circuit_open = True
                    raise CircuitBreakerOpenError(
                        f"Circuit breaker opened after {self._consecutive_failures} consecutive failures."
                    ) from e
                if attempt < self._max_retries - 1:
                    delay = self._backoff_base * (2 ** attempt)
                    time.sleep(delay)

        raise last_exception

    def generate(self, messages, **kwargs):
        response = self._call_api(messages, **kwargs)
        self._consecutive_failures = 0
        self._call_count += 1
        usage = response.usage
        cost = self._estimate_cost(usage.prompt_tokens, usage.completion_tokens)
        self._total_cost += cost
        self._log_cost(usage.prompt_tokens, usage.completion_tokens, cost)
        return response

    def generate_with_logprobs(self, messages, **kwargs):
        kwargs["logprobs"] = True
        kwargs["top_logprobs"] = kwargs.get("top_logprobs", 20)
        return self.generate(messages, **kwargs)

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


NON_RETRYABLE_EXCEPTIONS = (
    BudgetExceededError,
    CircuitBreakerOpenError,
    TeacherConfigError,
)
