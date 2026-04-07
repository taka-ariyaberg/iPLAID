"""
Custom exceptions for PLAID_Core.
"""


class PLAIDError(Exception):
    """Base exception for PLAID_Core."""
    pass


class ConfigurationError(PLAIDError):
    """Invalid configuration parameters."""
    pass


class SolverError(PLAIDError):
    """Error running MiniZinc solver."""
    pass


class MiniZincNotFoundError(SolverError):
    """MiniZinc executable not found in PATH."""
    pass


class NoSolutionFoundError(SolverError):
    """Solver could not find a valid layout."""
    pass


class TimeoutError(SolverError):
    """Solver exceeded timeout."""
    pass


class LayoutError(PLAIDError):
    """Error with layout result."""
    pass


class ValidationError(PLAIDError):
    """Configuration or input validation failed."""
    pass
