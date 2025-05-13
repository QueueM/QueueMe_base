"""
Availability calculation algorithms.

This package contains sophisticated algorithms for calculating availability, generating
time slots, resolving scheduling conflicts, and optimizing resource allocation.

Key components:
- SlotGenerator: Generates available time slots based on multiple constraints
- ConstraintSolver: Solves complex scheduling problems with multiple constraints
- ConflictDetector: Detects scheduling conflicts across multiple dimensions
"""

from .conflict_detector import ConflictDetector
from .constraint_solver import ConstraintSolver
from .slot_generator import SlotGenerator

__all__ = ["SlotGenerator", "ConstraintSolver", "ConflictDetector"]
