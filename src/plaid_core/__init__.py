"""
PLAID_Core: Constraint-Based Microplate Layout Engine

Main package for designing microplate layouts using MiniZinc constraint programming.
"""

from .config import PlateConfig, Compound, Control
from .designer import PlateDesigner
from .output import Layout
from .exceptions import (
    PLAIDError,
    ConfigurationError,
    SolverError,
    NoSolutionFoundError,
    TimeoutError as PLAIDTimeoutError,
    LayoutError,
    ValidationError,
)

__version__ = "1.0.0"
__author__ = "PLAID Team (pharmbio.uu.se)"
__license__ = "Apache License 2.0"

__all__ = [
    'PlateDesigner',
    'PlateConfig',
    'Compound',
    'Control',
    'Layout',
    'PLAIDError',
    'ConfigurationError',
    'SolverError',
    'NoSolutionFoundError',
    'PLAIDTimeoutError',
    'LayoutError',
    'ValidationError',
]
