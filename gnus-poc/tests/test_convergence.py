"""Tests for ConvergenceTracker — plateau detection and two-tier thresholds."""

import pytest

from distill.convergence import ConvergenceConfig, ConvergenceTracker


class TestConvergenceTracker:
    """Behavior tests for ConvergenceTracker — covers hard-stop, convergence, warning, and plateau detection."""

    def test_hard_stop_when_loss_exceeds_limit(self):
        """Loss above hard_stop threshold immediately returns 'hard_stop'."""
        config = ConvergenceConfig(
            distill_loss_hard_stop=5.0,
            distill_loss_warning=3.0,
            distill_loss_target=2.5,
            patience=10,
            min_delta=0.01,
        )
        tracker = ConvergenceTracker(config)
        result = tracker.step(6.0)
        assert result == "hard_stop"
        assert tracker.state.hard_stopped is True

    def test_converged_when_loss_sustained_below_target(self):
        """Loss below target for patience steps AFTER no improvement declares convergence."""
        config = ConvergenceConfig(
            distill_loss_target=2.5,
            distill_loss_warning=3.0,
            distill_loss_hard_stop=5.0,
            patience=5,
            min_delta=0.01,
        )
        tracker = ConvergenceTracker(config)

        # Feed steadily decreasing but above-target losses to build steps_since_improvement
        for i in range(5):
            loss = 2.6 - (i * 0.02)  # 2.6, 2.58, 2.56, 2.54, 2.52 — all above target
            result = tracker.step(loss)
            assert result in ("continue", "warning"), f"Unexpected status at step {i}: {result}"

        # Now feed losses below target — the first one is an improvement (resets counter),
        # then patience steps of flat loss are needed before convergence triggers.
        results = []
        for _step in range(6):
            result = tracker.step(2.45)
            results.append(result)

        # The last one should be 'converged' — loss is below target AND steps_since_improvement >= patience
        assert "converged" in results, f"Expected converged in: {results}"
        assert tracker.state.converged is True

    def test_warning_when_loss_exceeds_warning_threshold(self):
        """Loss above warning threshold but below hard-stop issues 'warning' once."""
        config = ConvergenceConfig(
            distill_loss_warning=3.0,
            distill_loss_hard_stop=5.0,
            distill_loss_target=2.5,
            patience=10,
            min_delta=0.01,
        )
        tracker = ConvergenceTracker(config)

        # First step: 3.5 — should trigger warning
        result1 = tracker.step(3.5)
        assert result1 == "warning"
        assert tracker.state.warning_issued is True

        # Second step: another above-warning loss — should NOT reissue warning
        result2 = tracker.step(3.5)
        assert result2 == "continue"  # warning already issued, just continue

    def test_improvement_resets_steps_since_improvement(self):
        """A loss improvement by at least min_delta resets the plateau counter."""
        config = ConvergenceConfig(
            distill_loss_target=0.5,
            distill_loss_warning=10.0,
            distill_loss_hard_stop=20.0,
            patience=100,
            min_delta=0.05,
        )
        tracker = ConvergenceTracker(config)

        # Feed flat losses to build counter
        for _ in range(10):
            tracker.step(3.0)

        assert tracker.state.steps_since_improvement == 9  # first step registers improvement (loss < inf)
        assert tracker.state.best_loss == 3.0

        # Significant improvement should reset counter
        tracker.step(2.5)  # improvement = 0.5 > min_delta
        assert tracker.state.steps_since_improvement == 0
        assert tracker.state.best_loss == 2.5

    def test_continue_when_loss_below_warning_above_target(self):
        """Normal operating zone: loss between target and warning returns 'continue'."""
        config = ConvergenceConfig(
            distill_loss_target=1.0,
            distill_loss_warning=5.0,
            distill_loss_hard_stop=10.0,
            patience=50,
            min_delta=0.01,
        )
        tracker = ConvergenceTracker(config)
        result = tracker.step(3.0)
        assert result == "continue"
        assert tracker.state.hard_stopped is False
        assert tracker.state.converged is False
        assert tracker.state.warning_issued is False

    def test_hard_stop_takes_priority_over_all(self):
        """Hard stop is checked first and returned regardless of other conditions."""
        config = ConvergenceConfig(
            distill_loss_hard_stop=5.0,
            distill_loss_warning=3.0,
            distill_loss_target=2.5,
            patience=5,
            min_delta=0.01,
        )
        tracker = ConvergenceTracker(config)

        # Build improvement counter
        for _ in range(3):
            tracker.step(2.8)

        # Now a hard-stop loss — must return 'hard_stop' even though loss improved
        result = tracker.step(6.0)
        assert result == "hard_stop"
        assert tracker.state.hard_stopped is True
