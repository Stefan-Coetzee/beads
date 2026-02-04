"""
Feedback tools for agent interface.

Tools for communication: add_comment, get_comments.

Implementation Note (ADR-001):
- Comments can be shared (learner_id=NULL) or private (learner_id set)
- get_comments returns shared + this learner's private comments
- Other learners' private comments are not visible
"""

from sqlalchemy.ext.asyncio import AsyncSession

from ltt.models import CommentCreate
from ltt.services.task_service import add_comment as service_add_comment
from ltt.services.task_service import get_comments as service_get_comments
from ltt.tools.schemas import (
    AddCommentInput,
    CommentOutput,
    GetCommentsInput,
    GetCommentsOutput,
)


async def add_comment(
    input: AddCommentInput, learner_id: str, session: AsyncSession
) -> CommentOutput:
    """
    Add a comment to a task.

    Use for questions, feedback, or notes.

    Implementation Note (ADR-001):
    - Sets learner_id on the comment (private to this learner)
    - Only this learner will see their private comments
    - Shared comments (instructor notes) have learner_id=NULL
    """
    comment_data = CommentCreate(
        task_id=input.task_id, learner_id=learner_id, author=learner_id, text=input.comment
    )

    comment = await service_add_comment(session, input.task_id, comment_data)

    return CommentOutput(
        id=comment.id,
        author=comment.author,
        text=comment.text,
        created_at=comment.created_at.isoformat(),
    )


async def get_comments(
    input: GetCommentsInput, learner_id: str, session: AsyncSession
) -> GetCommentsOutput:
    """
    Get comments on a task.

    Implementation Note (ADR-001):
    - Returns shared comments (learner_id=NULL) + this learner's private comments
    - Query: WHERE task_id = ? AND (learner_id IS NULL OR learner_id = ?)
    - Other learners' private comments are not visible
    """
    comments = await service_get_comments(session, input.task_id, learner_id)

    # Apply limit
    limited_comments = comments[: input.limit]

    return GetCommentsOutput(
        comments=[
            CommentOutput(
                id=c.id, author=c.author, text=c.text, created_at=c.created_at.isoformat()
            )
            for c in limited_comments
        ],
        total=len(limited_comments),
    )
