"""
Base validator interface for submission validation.
"""

from abc import ABC, abstractmethod


class Validator(ABC):
    """
    Base class for validators.

    Validators check submission content against acceptance criteria
    and return pass/fail results with optional error messages.
    """

    @abstractmethod
    async def validate(
        self,
        content: str,
        acceptance_criteria: str,
        submission_type: str,
    ) -> tuple[bool, str | None]:
        """
        Validate submission content against acceptance criteria.

        Args:
            content: The submission content to validate
            acceptance_criteria: Task's acceptance criteria
            submission_type: Type of submission (code, sql, text, etc.)

        Returns:
            (passed, error_message)
            - passed: True if validation passed
            - error_message: Error details if failed, None if passed
        """
