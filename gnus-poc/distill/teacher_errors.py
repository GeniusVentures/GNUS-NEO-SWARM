"""Error types for the teacher API client."""


class TeacherConfigError(Exception):
    pass


class BudgetExceededError(Exception):
    pass


class CircuitBreakerOpenError(Exception):
    pass


class SyntheticDataError(Exception):
    pass


class BackendNotFoundError(TeacherConfigError):
    """Raised when no backend can be resolved for a given model name."""
    pass
