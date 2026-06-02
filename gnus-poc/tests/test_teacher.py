"""Tests for TeacherClient — DeepSeek v4 pro API client."""

import json
import os
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
import yaml

from distill.teacher import TeacherClient
from distill.teacher_errors import BudgetExceededError, CircuitBreakerOpenError, TeacherConfigError


def make_mock_completion(content, prompt_tokens=10, completion_tokens=5):
    resp = MagicMock()
    resp.choices = [MagicMock()]
    resp.choices[0].message.content = content
    resp.usage = MagicMock()
    resp.usage.prompt_tokens = prompt_tokens
    resp.usage.completion_tokens = completion_tokens
    return resp


@pytest.fixture
def config_path(tmp_path):
    config = tmp_path / "pipeline.yaml"
    config.write_text(yaml.dump({
        "teacher": {
            "model": "deepseek-v4-pro",
            "api_key_env": "DEEPSEEK_API_KEY",
            "base_url": "https://api.deepseek.com",
            "max_tokens": 4096,
            "temperature": 0.7,
            "max_retries": 1,
            "backoff_base_seconds": 1.0,
            "budget_cap_usd": 5.0,
        }
    }))
    return config


@pytest.fixture
def mock_openai():
    with patch("distill.teacher.OpenAI") as mock:
        client = MagicMock()
        mock.return_value = client
        yield client


@pytest.fixture
def client(config_path, mock_openai, tmp_path, monkeypatch):
    monkeypatch.setenv("DEEPSEEK_API_KEY", "sk-test")
    artifacts = tmp_path / "artifacts"
    client = TeacherClient(config_path=config_path, project_root=tmp_path)
    client._cost_log_path = artifacts / "api_cost.jsonl"
    client._error_log_path = artifacts / "api_errors.jsonl"
    return client


class TestTeacherClientInit:
    def test_loads_config(self, client):
        assert client._model == "deepseek-v4-pro"
        assert client._budget_cap == 5.0

    def test_raises_without_api_key(self, config_path, tmp_path, monkeypatch):
        monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)
        with pytest.raises(TeacherConfigError):
            TeacherClient(config_path=config_path, project_root=tmp_path)

    def test_budget_cap_default(self, tmp_path, monkeypatch, mock_openai):
        monkeypatch.setenv("DEEPSEEK_API_KEY", "sk-test")
        config = tmp_path / "pipeline.yaml"
        config.write_text(yaml.dump({"teacher": {}}))
        client = TeacherClient(config_path=config, project_root=tmp_path)
        assert client._budget_cap == 5.0


class TestTeacherClientGenerate:
    def test_successful_generation(self, client, mock_openai):
        mock_openai.chat.completions.create.return_value = make_mock_completion("Hello world")

        response = client.generate([{"role": "user", "content": "Hi"}])
        assert response.choices[0].message.content == "Hello world"
        assert client.call_count == 1
        assert client.total_cost > 0

    def test_circuit_breaker_opens_after_failures(self, client, mock_openai):
        client._max_consecutive_failures = 2
        mock_openai.chat.completions.create.side_effect = Exception("Server error")

        for _ in range(2):
            try:
                client.generate([{"role": "user", "content": "Hi"}])
            except Exception:
                pass

        assert client.circuit_open

    def test_budget_exceeded_raises(self, client, mock_openai):
        client._total_cost = 5.0
        client._budget_cap = 5.0
        mock_openai.chat.completions.create.return_value = make_mock_completion("OK")

        with pytest.raises(BudgetExceededError):
            client.generate([{"role": "user", "content": "Hi"}])

    def test_budget_not_exceeded_below_cap(self, client, mock_openai):
        client._total_cost = 4.99
        client._budget_cap = 5.0
        mock_openai.chat.completions.create.return_value = make_mock_completion("OK", 1, 1)

        response = client.generate([{"role": "user", "content": "Hi"}])
        assert response.choices[0].message.content == "OK"

    def test_logs_cost(self, client, mock_openai, tmp_path):
        log_file = tmp_path / "artifacts" / "api_cost.jsonl"
        client._cost_log_path = log_file
        mock_openai.chat.completions.create.return_value = make_mock_completion("OK", 100, 50)

        client.generate([{"role": "user", "content": "Hi"}])
        assert log_file.exists()
        records = [json.loads(line) for line in log_file.read_text().strip().split("\n")]
        assert len(records) == 1
        assert "cost_usd" in records[0]

    def test_logs_error_on_failure(self, client, mock_openai, tmp_path):
        error_log = tmp_path / "artifacts" / "api_errors.jsonl"
        client._error_log_path = error_log
        mock_openai.chat.completions.create.side_effect = Exception("Boom")

        try:
            client.generate([{"role": "user", "content": "Hi"}])
        except Exception:
            pass

        assert client.call_count == 0
        assert client._consecutive_failures >= 1

    def test_non_retryable_400_error_raises_immediately(self, client, mock_openai):
        err = Exception("Bad request")
        err.status_code = 400
        mock_openai.chat.completions.create.side_effect = err

        with pytest.raises(Exception):
            client.generate([{"role": "user", "content": "Hi"}])

        assert client._consecutive_failures == 0
