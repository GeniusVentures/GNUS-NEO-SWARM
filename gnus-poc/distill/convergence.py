"""Convergence tracking for knowledge distillation.

Implements the two-tier early-stopping and patience-based plateau detection
algorithm defined in 02-RESEARCH.md (Pattern 1). The tracker is a pure state
machine: callers feed one loss per training step and act on the returned status
string. No exceptions are raised in the hot path — the caller (Distiller)
decides what to do with each status.

Decisions implemented:
    D-02 — convergence is defined as the rolling-window average of the loss
           dropping below the configured ``target`` threshold.
    D-03 — patience and min_delta are configurable per specialist.
    D-04 — two-tier stopping: a soft ``warning`` threshold surfaces drift to the
           operator (training continues) while a ``hard_stop`` threshold aborts.
"""

import logging
from collections import deque
from typing import Optional

logger = logging.getLogger(__name__)


class ConvergenceTracker:
    """Two-tier convergence tracker with patience-based plateau detection.

    The tracker maintains a rolling window of recent loss values and returns a
    status string after every step. Status values:

        ``"continue"``   — loss is in the normal range; keep training.
        ``"warning"``    — loss exceeded the warning threshold; keep training.
        ``"converged"``  — rolling average dropped below target; stop.
        ``"early_stop"`` — loss plateaued for ``patience`` steps; stop.
        ``"hard_stop"``  — loss exceeded the hard-stop threshold; abort.
    """

    def __init__(
        self,
        target: float,
        warning: float,
        hard_stop: float,
        patience: int = 100,
        min_delta: float = 0.01,
        window_size: int = 20,
    ) -> None:
        self._target = target
        self._warning = warning
        self._hard_stop = hard_stop
        self._patience = patience
        self._min_delta = min_delta
        self._window_size = window_size

        self._losses: list[float] = []
        self._window: deque[float] = deque(maxlen=window_size)

        self._converged: bool = False
        self._converged_at_step: Optional[int] = None
        self._aborted: bool = False
        self._best_loss: float = float("inf")
        self._no_improvement_steps: int = 0
        self._warnings: list[int] = []

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def step(self, loss: float, step_number: int) -> str:
        """Record one training step and return the resulting status.

        Args:
            loss: Scalar loss value for this step.
            step_number: Monotonic step index (used for the warnings log).

        Returns:
            One of ``continue``, ``warning``, ``converged``, ``early_stop``,
            ``hard_stop``.
        """
        self._losses.append(loss)
        self._window.append(loss)

        status = "continue"

        # D-04: hard stop takes precedence over everything else.
        if loss > self._hard_stop:
            self._aborted = True
            return "hard_stop"

        # D-04: warning is surfaced but does not stop training.
        if loss > self._warning:
            self._warnings.append(step_number)
            status = "warning"

        # Patience tracking (D-03). A step counts as an improvement only if it
        # beats the best loss by more than min_delta.
        if loss < self._best_loss - self._min_delta:
            self._best_loss = loss
            self._no_improvement_steps = 0
        else:
            self._no_improvement_steps += 1

        # D-02: convergence uses the rolling-window average, not the point
        # value, to smooth out step-to-step noise. Convergence is terminal —
        # once set it does not un-set.
        if not self._converged and self._rolling_average() < self._target:
            self._converged = True
            self._converged_at_step = step_number
            return "converged"

        # D-03: plateau early stop. Checked after convergence so a converging
        # run reports "converged" rather than "early_stop".
        if self._no_improvement_steps >= self._patience:
            return "early_stop"

        return status

    @property
    def converged(self) -> bool:
        return self._converged

    @property
    def converged_at_step(self) -> Optional[int]:
        return self._converged_at_step

    @property
    def aborted(self) -> bool:
        return self._aborted

    @property
    def best_loss(self) -> float:
        return self._best_loss

    @property
    def losses(self) -> list:
        return list(self._losses)

    @property
    def no_improvement_steps(self) -> int:
        return self._no_improvement_steps

    @property
    def warnings(self) -> list:
        return list(self._warnings)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _rolling_average(self) -> float:
        """Return the mean of the last ``window_size`` losses, or inf if empty."""
        if not self._window:
            return float("inf")
        return sum(self._window) / len(self._window)
