"""GNUS-POC distillation — teacher API client and knowledge distillation."""

from distill.teacher import TeacherClient
from distill.synthetic import SyntheticDataGenerator
from distill.teacher_errors import (
    BudgetExceededError,
    CircuitBreakerOpenError,
    SyntheticDataError,
    TeacherConfigError,
)

__all__ = [
    "TeacherClient",
    "SyntheticDataGenerator",
    "BudgetExceededError",
    "CircuitBreakerOpenError",
    "SyntheticDataError",
    "TeacherConfigError",
]
