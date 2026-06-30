"""Tests for TeacherClient — multi-backend teacher API client."""

import json
import os
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
import yaml

from distill.teacher import TeacherClient
from distill.teacher_errors import BudgetExceededError, CircuitBreakerOpenError, TeacherConfigError


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def make_mock_completion(content, prompt_tokens=10, completion_tokens=5):
    """Return a uniform backend dict (not an OpenAI mock)."""
    return {
        "content": content,
        "prompt_tokens": prompt_tokens,
        "completion_tokens": completion_tokens,
        "raw_response": MagicMock(),
    }


def make_mock_backend():
    """Return a MagicMock that looks like a TeacherBackend."""
    backend = MagicMock()
    backend.generate.return_value = make_mock_completion("Hello world")
    return backend


def new_config_dict(**overrides):
    """Build a minimal valid two-layer config dict."""
    cfg = {
        "endpoints": {
            "litellm": {
                "url": "http://127.0.0.1:4000",
                "apiType": "openai",
            }
        },
        "models": {
            "deepseek-v4-fast": {
                "endpoint": "litellm",
                "model_id": "deepseek-v4-fast",
            }
        },
        "teacher": {
            "level1": "deepseek-v4-fast",
            "max_tokens": 4096,
            "temperature": 0.7,
            "max_retries": 1,
            "backoff_base_seconds": 1.0,
            "budget_cap_usd": 5.0,
            "circuit_breaker_failure_threshold": 5,
        },
    }
    cfg.update(overrides)
    return cfg


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def config_path(tmp_path):
    """Write a two-layer (endpoints + models) pipeline.yaml to a temp dir."""
    config = tmp_path / "pipeline.yaml"
    config.write_text(yaml.dump(new_config_dict()))
    return config


@pytest.fixture
def mock_backend_cls():
    """Patch both backend classes so no real SDK clients are created."""
    with patch("distill.teacher.OpenAIBackend") as mock_openai, \
         patch("distill.teacher.AnthropicBackend") as mock_anthropic:
        # Return mock instances
        openai_instance = MagicMock()
        openai_instance.generate.return_value = make_mock_completion("Mocked")
        mock_openai.return_value = openai_instance

        anthropic_instance = MagicMock()
        anthropic_instance.generate.return_value = make_mock_completion("Mocked")
        mock_anthropic.return_value = anthropic_instance

        yield mock_openai, mock_anthropic


@pytest.fixture
def client(config_path, mock_backend_cls, tmp_path, monkeypatch):
    """Construct a TeacherClient with mocked backends."""
    monkeypatch.setenv("LITELLM_API_KEY", "sk-test")
    artifacts = tmp_path / "artifacts"
    client = TeacherClient(config_path=config_path, project_root=tmp_path)
    client._cost_log_path = artifacts / "api_cost.jsonl"
    client._error_log_path = artifacts / "api_errors.jsonl"
    return client


# ---------------------------------------------------------------------------
# Init tests
# ---------------------------------------------------------------------------

class TestTeacherClientInit:
    def test_loads_config(self, client):
        """Model registry and defaults are populated from config."""
        assert "deepseek-v4-fast" in client._models
        assert client._budget_cap == 5.0
        assert client._default_max_tokens == 4096

    def test_raises_without_api_key(self, config_path, tmp_path, monkeypatch):
        """Missing API key should raise TeacherConfigError."""
        monkeypatch.delenv("LITELLM_API_KEY", raising=False)
        # Also remove any other possible API key env vars
        for v in ["ANTHROPIC_API_KEY", "OPENAI_API_KEY", "LITELLM_API_KEY"]:
            monkeypatch.delenv(v, raising=False)
        with patch("distill.teacher.OpenAIBackend") as mock_oa, \
             patch("distill.teacher.AnthropicBackend") as mock_ant:
            mock_oa.return_value = MagicMock()
            mock_ant.return_value = MagicMock()
            with pytest.raises(TeacherConfigError):
                TeacherClient(config_path=config_path, project_root=tmp_path)

    def test_raises_missing_endpoints(self, tmp_path, monkeypatch):
        """Config without 'endpoints' block raises TeacherConfigError."""
        monkeypatch.setenv("LITELLM_API_KEY", "sk-test")
        config = tmp_path / "pipeline.yaml"
        config.write_text(yaml.dump({"models": {}, "teacher": {"level1": "x"}}))
        with patch("distill.teacher.OpenAIBackend"), patch("distill.teacher.AnthropicBackend"):
            with pytest.raises(TeacherConfigError, match="endpoints"):
                TeacherClient(config_path=config, project_root=tmp_path)

    def test_raises_unknown_api_type(self, tmp_path, monkeypatch):
        """Unknown apiType in endpoint config raises TeacherConfigError."""
        monkeypatch.setenv("LITELLM_API_KEY", "sk-test")
        config = tmp_path / "pipeline.yaml"
        config.write_text(yaml.dump({
            "endpoints": {"bad": {"url": "http://x", "apiType": "garbage"}},
            "models": {"m": {"endpoint": "bad"}},
            "teacher": {"level1": "m"},
        }))
        with patch("distill.teacher.OpenAIBackend"), patch("distill.teacher.AnthropicBackend"):
            with pytest.raises(TeacherConfigError, match="apiType"):
                TeacherClient(config_path=config, project_root=tmp_path)


# ---------------------------------------------------------------------------
# Backend dispatch tests
# ---------------------------------------------------------------------------

class TestBackendDispatch:
    def test_dispatches_to_correct_backend_by_api_type(self, tmp_path, monkeypatch):
        """Verify OpenAIBackend is called for 'openai' apiType."""
        monkeypatch.setenv("LITELLM_API_KEY", "sk-test")
        config = tmp_path / "pipeline.yaml"
        config.write_text(yaml.dump({
            "endpoints": {
                "litellm": {"url": "http://127.0.0.1:4000", "apiType": "openai"},
            },
            "models": {
                "deepseek-v4-fast": {"endpoint": "litellm", "model_id": "deepseek-v4-fast"},
            },
            "teacher": {"level1": "deepseek-v4-fast", "budget_cap_usd": 9999},
        }))
        with patch("distill.teacher.OpenAIBackend") as mock_oa, \
             patch("distill.teacher.AnthropicBackend") as mock_ant:
            oa_instance = MagicMock()
            oa_instance.generate.return_value = make_mock_completion("OK")
            mock_oa.return_value = oa_instance
            mock_ant.return_value = MagicMock()

            client = TeacherClient(config_path=config, project_root=tmp_path)
            response = client.generate("deepseek-v4-fast", [{"role": "user", "content": "Hi"}])

            # OpenAIBackend.generate was called
            oa_instance.generate.assert_called_once()
            mock_ant.return_value.generate.assert_not_called()
            assert response.choices[0].message.content == "OK"

    def test_dispatches_to_anthropic_backend(self, tmp_path, monkeypatch):
        """Verify AnthropicBackend is called for 'anthropic' apiType."""
        monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-test")
        config = tmp_path / "pipeline.yaml"
        config.write_text(yaml.dump({
            "endpoints": {
                "anthropic_direct": {"url": "https://api.anthropic.com", "apiType": "anthropic"},
            },
            "models": {
                "claude-sonnet": {"endpoint": "anthropic_direct", "model_id": "claude-sonnet-4"},
            },
            "teacher": {"level1": "claude-sonnet", "budget_cap_usd": 9999},
        }))
        with patch("distill.teacher.OpenAIBackend") as mock_oa, \
             patch("distill.teacher.AnthropicBackend") as mock_ant:
            ant_instance = MagicMock()
            ant_instance.generate.return_value = make_mock_completion("Anthropic says hi")
            mock_ant.return_value = ant_instance
            mock_oa.return_value = MagicMock()

            client = TeacherClient(config_path=config, project_root=tmp_path)
            response = client.generate("claude-sonnet", [{"role": "user", "content": "Hi"}])

            ant_instance.generate.assert_called_once()
            mock_oa.return_value.generate.assert_not_called()
            assert response.choices[0].message.content == "Anthropic says hi"

    def test_resolve_backend_for_unknown_model_raises(self, client):
        """Calling generate with an unknown model raises TeacherConfigError."""
        with pytest.raises(TeacherConfigError, match="nonexistent-model"):
            client.generate("nonexistent-model", [{"role": "user", "content": "Hi"}])


# ---------------------------------------------------------------------------
# Generate tests
# ---------------------------------------------------------------------------

class TestTeacherClientGenerate:
    def test_successful_generation(self, client, mock_backend_cls):
        """A successful call returns response content and increments counters."""
        _, _ = mock_backend_cls
        mock_backend = make_mock_backend()
        # Replace the litellm backend with our mock
        client._backends["litellm"] = mock_backend

        response = client.generate("deepseek-v4-fast", [{"role": "user", "content": "Hi"}])
        assert response.choices[0].message.content == "Hello world"
        assert client.call_count == 1
        assert client.total_cost > 0

    def test_successful_generation_default_model(self, client, mock_backend_cls):
        """When model_name is None, the Level 1 default is used."""
        _, _ = mock_backend_cls
        mock_backend = make_mock_backend()
        client._backends["litellm"] = mock_backend

        response = client.generate(messages=[{"role": "user", "content": "Hi"}])
        assert response.choices[0].message.content == "Hello world"
        assert client.call_count == 1

    def test_circuit_breaker_opens_after_failures(self, client, mock_backend_cls):
        """After max consecutive failures, the circuit breaker opens."""
        _, _ = mock_backend_cls
        client._max_consecutive_failures = 2
        mock_backend = MagicMock()
        mock_backend.generate.side_effect = Exception("Server error")
        client._backends["litellm"] = mock_backend

        for _ in range(2):
            try:
                client.generate("deepseek-v4-fast", [{"role": "user", "content": "Hi"}])
            except Exception:
                pass

        assert client.circuit_open

    def test_budget_exceeded_raises(self, client, mock_backend_cls):
        """When cost is at cap, BudgetExceededError is raised."""
        _, _ = mock_backend_cls
        client._total_cost = 5.0
        client._budget_cap = 5.0

        with pytest.raises(BudgetExceededError):
            client.generate("deepseek-v4-fast", [{"role": "user", "content": "Hi"}])

    def test_budget_not_exceeded_below_cap(self, client, mock_backend_cls):
        """When cost is below cap, generation proceeds."""
        _, _ = mock_backend_cls
        client._total_cost = 4.99
        client._budget_cap = 5.0
        mock_backend = MagicMock()
        mock_backend.generate.return_value = make_mock_completion("OK", prompt_tokens=1, completion_tokens=1)
        client._backends["litellm"] = mock_backend

        response = client.generate("deepseek-v4-fast", [{"role": "user", "content": "Hi"}])
        assert response.choices[0].message.content == "OK"

    def test_logs_cost(self, client, mock_backend_cls, tmp_path):
        """Cost is logged to the JSONL cost log."""
        _, _ = mock_backend_cls
        log_file = tmp_path / "artifacts" / "api_cost.jsonl"
        client._cost_log_path = log_file
        mock_backend = MagicMock()
        mock_backend.generate.return_value = make_mock_completion("OK", prompt_tokens=100, completion_tokens=50)
        client._backends["litellm"] = mock_backend

        client.generate("deepseek-v4-fast", [{"role": "user", "content": "Hi"}])
        assert log_file.exists()
        records = [json.loads(line) for line in log_file.read_text().strip().split("\n")]
        assert len(records) == 1
        assert "cost_usd" in records[0]

    def test_logs_error_on_failure(self, client, mock_backend_cls, tmp_path):
        """Errors are logged to the JSONL error log."""
        _, _ = mock_backend_cls
        error_log = tmp_path / "artifacts" / "api_errors.jsonl"
        client._error_log_path = error_log
        mock_backend = MagicMock()
        mock_backend.generate.side_effect = Exception("Boom")
        client._backends["litellm"] = mock_backend

        try:
            client.generate("deepseek-v4-fast", [{"role": "user", "content": "Hi"}])
        except Exception:
            pass

        assert client.call_count == 0
        assert client._consecutive_failures >= 1

    def test_non_retryable_400_error_raises_immediately(self, client, mock_backend_cls):
        """A 400 error should not trigger retries."""
        _, _ = mock_backend_cls
        err = Exception("Bad request")
        err.status_code = 400
        mock_backend = MagicMock()
        mock_backend.generate.side_effect = err
        client._backends["litellm"] = mock_backend

        with pytest.raises(Exception):
            client.generate("deepseek-v4-fast", [{"role": "user", "content": "Hi"}])

        assert client._consecutive_failures == 0


# ---------------------------------------------------------------------------
# Properties tests
# ---------------------------------------------------------------------------

class TestTeacherClientProperties:
    def test_properties_work(self, client, mock_backend_cls):
        """All public properties return expected values."""
        _, _ = mock_backend_cls
        mock_backend = make_mock_backend()
        client._backends["litellm"] = mock_backend

        client.generate("deepseek-v4-fast", [{"role": "user", "content": "Hi"}])

        assert client.total_cost > 0
        assert client.budget_cap == 5.0
        assert not client.circuit_open
        assert client.call_count == 1

    def test_generate_with_logprobs(self, client, mock_backend_cls):
        """generate_with_logprobs passes logprobs=True and top_logprobs."""
        _, _ = mock_backend_cls
        mock_backend = MagicMock()
        mock_backend.generate.return_value = make_mock_completion("Logprob result")
        client._backends["litellm"] = mock_backend

        response = client.generate_with_logprobs(
            "deepseek-v4-fast", [{"role": "user", "content": "Hi"}]
        )

        # Verify logprobs was passed through
        call_kwargs = mock_backend.generate.call_args[1]
        assert call_kwargs.get("logprobs") is True
        assert call_kwargs.get("top_logprobs") == 20
        assert response.choices[0].message.content == "Logprob result"
