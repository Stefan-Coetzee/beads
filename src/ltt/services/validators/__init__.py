"""
Validators for submission content.

Pluggable validation strategies for different submission types.
"""

from .base import Validator
from .simple import SimpleValidator

__all__ = ["Validator", "SimpleValidator"]
