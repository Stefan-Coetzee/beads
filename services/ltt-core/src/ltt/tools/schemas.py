"""
Pydantic schemas for agent tool inputs and outputs.

All tools use typed inputs/outputs for validation and serialization.
"""

from pydantic import BaseModel, Field

# =============================================================================
# Navigation Tool Schemas
# =============================================================================


class GetReadyInput(BaseModel):
    """Input for get_ready tool."""

    project_id: str = Field(..., description="Project to get ready work from")
    task_type: str | None = Field(None, description="Filter by type: task, subtask")
    limit: int = Field(5, description="Maximum tasks to return", ge=1, le=20)


class TaskSummaryOutput(BaseModel):
    """Summary of a task for lists."""

    id: str
    title: str
    status: str
    task_type: str
    priority: int
    has_children: bool
    parent_id: str | None = None  # For hierarchy context

    # Content and summary (for epics and tasks with children)
    description: str | None = None
    content: str | None = None
    summary: str | None = None  # LLM-generated hierarchical summary


class GetReadyOutput(BaseModel):
    """Output from get_ready tool."""

    tasks: list[TaskSummaryOutput]
    total_ready: int
    message: str


class ShowTaskInput(BaseModel):
    """Input for show_task tool."""

    task_id: str = Field(..., description="Task ID to show details for")


class AcceptanceCriterionOutput(BaseModel):
    """Acceptance criterion for a task."""

    id: str
    criterion_type: str
    description: str


class TaskDetailOutput(BaseModel):
    """Detailed task information."""

    id: str
    title: str
    description: str
    acceptance_criteria: str
    notes: str
    status: str
    task_type: str
    priority: int

    # Hierarchy
    parent_id: str | None
    children: list[TaskSummaryOutput]

    # Learning
    learning_objectives: list[dict]
    content: str | None

    # Pedagogical guidance
    tutor_guidance: dict | None
    narrative_context: str | None

    # Dependencies
    blocked_by: list[TaskSummaryOutput]
    blocks: list[TaskSummaryOutput]

    # History (for current learner)
    submission_count: int
    latest_validation_passed: bool | None
    status_summaries: list[dict]


class GetContextInput(BaseModel):
    """Input for get_context tool."""

    task_id: str = Field(..., description="Task to get context for")


class GetContextOutput(BaseModel):
    """Full task context for agent."""

    learner_id: str

    current_task: TaskSummaryOutput
    project_id: str

    hierarchy: list[dict]
    ready_tasks: list[TaskSummaryOutput]
    progress: dict | None

    # Task-specific context
    acceptance_criteria: str
    learning_objectives: list[dict]
    status_summaries: list[dict]


# =============================================================================
# Progress Tool Schemas
# =============================================================================


class StartTaskInput(BaseModel):
    """Input for start_task tool."""

    task_id: str = Field(..., description="Task to start working on")


class StartTaskContextOutput(BaseModel):
    """Focused context for a started task - just what's needed to teach."""

    task_id: str
    title: str
    task_type: str
    status: str

    # Content for teaching
    description: str
    acceptance_criteria: str
    content: str | None = None
    narrative_context: str | None = None

    # Pedagogical
    learning_objectives: list[dict]  # Include Bloom levels: {"level": "apply", "description": "..."}
    tutor_guidance: dict | None = None


class StartTaskOutput(BaseModel):
    """Result of starting a task."""

    success: bool
    task_id: str
    status: str  # Just current status, no old/new confusion
    message: str

    # Focused context (only when task is newly started)
    context: StartTaskContextOutput | None = None


class SubmitInput(BaseModel):
    """Input for submit tool."""

    task_id: str = Field(..., description="Task to submit for")
    content: str = Field(..., description="Submission content (code, text, etc.)")
    submission_type: str = Field(
        "code", description="Type: code, sql, jupyter_cell, text, result_set"
    )


class AutoClosedTask(BaseModel):
    """A task that was auto-closed due to all children completing."""

    id: str
    title: str
    task_type: str


class SubmitOutput(BaseModel):
    """Result of submission."""

    success: bool
    submission_id: str
    attempt_number: int

    # Validation result
    validation_passed: bool | None
    validation_message: str | None

    # Current status after submission
    status: str
    message: str

    # Ready tasks after successful submission (to avoid extra get_ready call)
    ready_tasks: list[TaskSummaryOutput] | None = None

    # Tasks auto-closed due to all children completing (hierarchical auto-close)
    auto_closed: list[AutoClosedTask] | None = None


# =============================================================================
# Feedback Tool Schemas
# =============================================================================


class AddCommentInput(BaseModel):
    """Input for add_comment tool."""

    task_id: str = Field(..., description="Task to comment on")
    comment: str = Field(..., description="Comment text")


class CommentOutput(BaseModel):
    """A comment on a task."""

    id: str
    author: str
    text: str
    created_at: str


class GetCommentsInput(BaseModel):
    """Input for get_comments tool."""

    task_id: str = Field(..., description="Task to get comments for")
    limit: int = Field(10, description="Maximum comments", ge=1, le=50)


class GetCommentsOutput(BaseModel):
    """Comments on a task."""

    comments: list[CommentOutput]
    total: int


# =============================================================================
# Control Tool Schemas
# =============================================================================


class GoBackInput(BaseModel):
    """Input for go_back tool."""

    task_id: str = Field(..., description="Closed task to reopen")
    reason: str = Field(..., description="Why reopening (required)")


class GoBackOutput(BaseModel):
    """Result of go_back action."""

    success: bool
    task_id: str
    new_status: str
    message: str
    reason: str


class RequestHelpInput(BaseModel):
    """Input for request_help tool."""

    task_id: str = Field(..., description="Task needing help")
    message: str = Field(..., description="Description of the issue")


class RequestHelpOutput(BaseModel):
    """Result of help request."""

    request_id: str
    message: str


# =============================================================================
# Error Handling
# =============================================================================


class ToolError(BaseModel):
    """Standard error response from tools."""

    success: bool = False
    error_code: str
    message: str
    details: dict | list | None = None
