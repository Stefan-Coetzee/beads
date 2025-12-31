"""
Simple validator for MVP.

Just checks that submission content is non-empty.
In production, this would be replaced with actual validation logic.
"""

from .base import Validator


class SimpleValidator(Validator):
    """
    Basic validator that checks if submission is non-empty.

    This is a placeholder for MVP. Real validation would:
    - Parse structured acceptance criteria
    - Execute code/SQL
    - Check outputs against expected results
    """

    async def validate(
        self,
        content: str,
        acceptance_criteria: str,
        submission_type: str,
    ) -> tuple[bool, str | None]:
        """
        Validate that submission content is non-empty.

        Args:
            content: The submission content
            acceptance_criteria: Task's acceptance criteria (ignored for now)
            submission_type: Type of submission (ignored for now)

        Returns:
            (passed, error_message)
        """
        # Check for empty content
        if not content or not content.strip():
            return False, "Submission is empty"

        # For MVP, all non-empty submissions pass
        # TODO: Real validation logic based on acceptance_criteria
        return True, None
