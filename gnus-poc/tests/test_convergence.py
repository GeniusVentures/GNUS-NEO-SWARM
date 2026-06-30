"""Tests for ConvergenceTracker — two-tier stopping and patience-based plateau detection."""

from distill.convergence import ConvergenceTracker


class TestConvergenceTracker:
    def test_initial_state(self):
        tracker = ConvergenceTracker(target=2.5, warning=3.0, hard_stop=5.0)

        assert tracker.converged is False
        assert tracker.converged_at_step is None
        assert tracker.aborted is False
        assert tracker.best_loss == float("inf")
        assert tracker.no_improvement_steps == 0
        assert tracker.warnings == []
        assert tracker.losses == []

    def test_converges_below_target(self):
        # target=2.5, patience=10, window_size=5. Drop below target and stay there.
        tracker = ConvergenceTracker(
            target=2.5, warning=3.0, hard_stop=5.0,
            patience=10, window_size=5,
        )

        status = None
        # First 5 steps above target to fill the rolling window, then drop below.
        for step in range(5):
            status = tracker.step(3.0, step)
            assert status in ("continue", "warning")

        # Now drop below target and stay below for enough steps so that the rolling
        # average stays below 2.5 for 10 consecutive steps.
        converged_seen = False
        for step in range(5, 25):
            status = tracker.step(2.0, step)
            if status == "converged":
                converged_seen = True
                break

        assert converged_seen is True
        assert tracker.converged is True
        assert tracker.converged_at_step is not None

    def test_warning_threshold(self):
        tracker = ConvergenceTracker(
            target=2.5, warning=3.0, hard_stop=5.0,
            patience=100, window_size=5,
        )

        status = tracker.step(3.5, 0)
        assert status == "warning"
        assert 0 in tracker.warnings
        # A warning alone does not converge or abort.
        assert tracker.converged is False
        assert tracker.aborted is False

    def test_hard_stop(self):
        tracker = ConvergenceTracker(
            target=2.5, warning=3.0, hard_stop=5.0,
        )

        status = tracker.step(6.0, 0)
        assert status == "hard_stop"
        assert tracker.aborted is True

    def test_patience_early_stop(self):
        # patience=5, min_delta=0.01, target unreachable (1.0). Loss oscillates
        # around 3.0 with no real improvement -> early stop after patience steps.
        tracker = ConvergenceTracker(
            target=1.0, warning=3.0, hard_stop=5.0,
            patience=5, min_delta=0.01,
        )

        statuses = []
        for step in range(11):
            loss = 3.005 if step % 2 == 0 else 3.0
            statuses.append(tracker.step(loss, step))

        assert "early_stop" in statuses
        # Convergence was never reached because the rolling average never went
        # below the target.
        assert tracker.converged is False

    def test_improvement_resets_patience(self):
        tracker = ConvergenceTracker(
            target=1.0, warning=3.0, hard_stop=5.0,
            patience=5, min_delta=0.01,
        )

        # Four flat steps at 3.0 (no improvement).
        tracker.step(3.0, 0)
        tracker.step(3.0, 1)
        tracker.step(3.0, 2)
        tracker.step(3.0, 3)

        # Big improvement resets the counter.
        tracker.step(2.5, 4)

        # Three more flat steps — counter should be 3, not 5, so no early stop yet.
        for step in range(5, 8):
            status = tracker.step(2.5, step)
            assert status != "early_stop"

    def test_rolling_window_average(self):
        tracker = ConvergenceTracker(
            target=2.5, warning=3.0, hard_stop=5.0,
            patience=100, window_size=5,
        )

        # After 5 steps the rolling window is exactly the last 5 losses.
        for loss in [5.0, 4.0, 3.0, 2.0, 1.0]:
            tracker.step(loss, 0)

        # Last 5 losses: [5,4,3,2,1] -> mean = 3.0
        assert abs(tracker._rolling_average() - 3.0) < 1e-9

        # Push one more loss; window slides to [4,3,2,1,1] -> mean = 2.2
        tracker.step(1.0, 0)
        assert abs(tracker._rolling_average() - 2.2) < 1e-9
