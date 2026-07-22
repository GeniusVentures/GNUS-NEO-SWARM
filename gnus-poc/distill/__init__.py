"""GNUS-POC distillation — teacher API client, knowledge distillation, convergence, and sweep analysis."""

from distill.teacher import TeacherClient
from distill.synthetic import SyntheticDataGenerator
from distill.convergence import ConvergenceConfig, ConvergenceState, ConvergenceTracker
from distill.distillation import Distiller
from distill.sweep_analyzer import SweepAnalyzer
from distill.teacher_errors import (
    BudgetExceededError,
    CircuitBreakerOpenError,
    SyntheticDataError,
    TeacherConfigError,
)

__all__ = [
    "TeacherClient",
    "SyntheticDataGenerator",
    "Distiller",
    "ConvergenceConfig",
    "ConvergenceState",
    "ConvergenceTracker",
    "SweepAnalyzer",
    "BudgetExceededError",
    "CircuitBreakerOpenError",
    "SyntheticDataError",
    "TeacherConfigError",
]
