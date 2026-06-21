"""Convergence tracker with plateau-based early stopping and two-tier thresholds.

Provides ConvergenceConfig (per-specialist parameters), ConvergenceState (mutable
per-run tracking), and ConvergenceTracker (plateau detection with patience-based
early stopping).

From 02-RESEARCH.md Pattern 1: standard plateau-based early stopping adapted for
the two-tier stopping model specified in D-04.
"""

from dataclasses import dataclass, field
from typing import List


@dataclass
class ConvergenceConfig:
    """Per-specialist convergence thresholds and plateau detection parameters.

    Attributes:
        distill_loss_target: Loss must drop to this value for convergence.
        distill_loss_warning: Loss above this logs a warning and continues.
        distill_loss_hard_stop: Loss at or above this halts training immediately.
        patience: Consecutive steps without improvement before early stopping.
        min_delta: Minimum loss improvement required to reset the patience counter.
    """

    distill_loss_target: float = 2.5
    distill_loss_warning: float = 3.0
    distill_loss_hard_stop: float = 5.0
    patience: int = 100
    min_delta: float = 0.01


@dataclass
class ConvergenceState:
    """Mutable tracking state for a single training run.

    Attributes:
        losses: Full loss history for the current run.
        best_loss: Best (lowest) loss observed so far.
        steps_since_improvement: Consecutive steps without a min_delta improvement.
        converged: True when loss is below target and patience is exhausted.
        hard_stopped: True when loss exceeded the hard-stop threshold.
        warning_issued: True when the warning threshold has been breached at least once.
    """

    losses: List[float] = field(default_factory=list)
    best_loss: float = float("inf")
    steps_since_improvement: int = 0
    converged: bool = False
    hard_stopped: bool = False
    warning_issued: bool = False


class ConvergenceTracker:
    """Tracks training loss, detects plateaus, and enforces two-tier stopping.

    Call ``step(loss)`` after each training iteration. The return value is one of:

    * ``"continue"`` — normal operation, keep training.
    * ``"warning"`` — loss exceeded the warning threshold (issued once per run).
    * ``"hard_stop"`` — loss exceeded the hard-stop threshold; halt immediately.
    * ``"converged"`` — loss sustained below target for patience steps with no
      min_delta improvement; training is complete.
    """

    def __init__(self, config: ConvergenceConfig):
        """Initialise the tracker with per-specialist convergence parameters.

        Args:
            config: Convergence thresholds and plateau detection settings.
        """
        self._config = config
        self._state = ConvergenceState()

    @property
    def state(self) -> ConvergenceState:
        """Return the mutable tracking state (read-only for callers)."""
        return self._state

    def step(self, loss: float) -> str:
        """Record a loss value and return the training status.

        Args:
            loss: The current distillation loss value.

        Returns:
            One of ``"continue"``, ``"warning"``, ``"hard_stop"``, or ``"converged"``.
        """
        self._state.losses.append(loss)

        # Hard stop check — takes priority over everything (Rule 2: fail-safe for runaway loss)
        if loss >= self._config.distill_loss_hard_stop:
            self._state.hard_stopped = True
            return "hard_stop"

        # Improvement tracking
        if loss < self._state.best_loss - self._config.min_delta:
            self._state.best_loss = loss
            self._state.steps_since_improvement = 0
        else:
            self._state.steps_since_improvement += 1

        # Convergence check — loss below target AND patience exhausted since last improvement
        if (
            loss <= self._config.distill_loss_target
            and self._state.steps_since_improvement >= self._config.patience
        ):
            self._state.converged = True
            return "converged"

        # Warning threshold check — issued once per run
        if loss > self._config.distill_loss_warning and not self._state.warning_issued:
            self._state.warning_issued = True
            return "warning"

        return "continue"
