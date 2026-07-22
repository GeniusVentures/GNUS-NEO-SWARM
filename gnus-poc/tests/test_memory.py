"""Tests for memory estimator."""

from unittest.mock import patch

from training.memory import (
    check_memory,
    estimate_model_memory_gb,
    get_available_ram_gb,
    _MIN_HEADROOM_GB,
    _WARN_HEADROOM_GB,
)


class TestMemoryEstimator:
    def test_model_memory_estimate_qlora(self):
        est = estimate_model_memory_gb(30.0, batch_size=4, use_qlora=True)
        assert est < 25.0

    def test_model_memory_estimate_full_precision(self):
        est = estimate_model_memory_gb(30.0, batch_size=4, use_qlora=False)
        assert est > 60.0

    @patch("training.memory.get_available_ram_gb")
    def test_check_memory_warning(self, mock_ram):
        mock_ram.return_value = 28.0
        result = check_memory(30.0, batch_size=4, use_qlora=True)
        assert result is not None
        assert "WARNING" in result

    @patch("training.memory.get_available_ram_gb")
    def test_check_memory_error(self, mock_ram):
        mock_ram.return_value = 5.0
        result = check_memory(30.0, batch_size=4, use_qlora=True)
        assert result is not None
        assert "ERROR" in result

    @patch("training.memory.get_available_ram_gb")
    def test_check_memory_ok(self, mock_ram):
        mock_ram.return_value = 100.0
        result = check_memory(30.0, batch_size=4, use_qlora=True)
        assert result is None

    @patch("training.memory.get_available_ram_gb")
    def test_check_memory_unavailable(self, mock_ram):
        mock_ram.return_value = -1.0
        result = check_memory(30.0)
        assert result is None
