# Agent Tools Module

> Stateless function interface for LLM agents (runtime CLI).
>
> **Architecture Note**: This module implements the two-layer architecture described in [ADR-001](./adr/001-learner-scoped-task-progress.md). All status reads/writes go through `learner_task_progress`, not the `tasks` table. Comments are scoped by `learner_id` (NULL=shared, set=private).

## Overview

This module provides the **runtime interface** for LLM agents:
- Stateless function calls with structured input/output
- All operations scoped to learner (session management handled by LangGraph)
- Error handling with informative messages
- Designed for MCP, function calling, or CLI patterns

### Design Principles

1. **Stateless**: Each call is independent; context loaded from DB
2. **Typed**: Pydantic models for all inputs and outputs
3. **Scoped**: Operations limited to current learner's data
4. **Informative Errors**: Errors explain what went wrong and how to fix

**Note**: Session and conversation management is handled by LangGraph's thread_id mechanism. These tools only interact with task/learner data.

---

## 1. Tool Categories

| Category | Tools | Purpose |
|----------|-------|---------|
| **Navigation** | get_ready, show_task, get_context | Find and view tasks |
| **Progress** | start_task, submit | Move through tasks |
| **Feedback** | add_comment, get_comments | Communication |
| **Control** | go_back, request_help | Special actions |

---

## 2. Tool Definitions

### Navigation Tools

```python
from pydantic import BaseModel, Field
from typing import List, Optional


class GetReadyInput(BaseModel):
    """Input for get_ready tool."""
    project_id: str = Field(..., description="Project to get ready work from")
    task_type: Optional[str] = Field(None, description="Filter by type: task, subtask")
    limit: int = Field(5, description="Maximum tasks to return", ge=1, le=20)


class TaskSummaryOutput(BaseModel):
    """Summary of a task for lists."""
    id: str
    title: str
    status: str
    task_type: str
    priority: int
    has_children: bool


class GetReadyOutput(BaseModel):
    """Output from get_ready tool."""
    tasks: List[TaskSummaryOutput]
    total_ready: int
    message: str  # Human-readable summary


async def get_ready(
    input: GetReadyInput,
    learner_id: str,
    db
) -> GetReadyOutput:
    """
    Get tasks that are unblocked and ready to work on.

    Returns tasks ordered by:
    1. Status (in_progress first, then open)
    2. Priority (P0 first)
    3. Age (oldest first)

    Implementation Note (ADR-001):
    - Queries `learner_task_progress` to get per-learner status
    - Falls back to 'open' for tasks without progress records (lazy initialization)
    - Checks dependencies against learner's progress, not global task status
    """
    ready_tasks = await get_ready_work(
        db,
        project_id=input.project_id,
        learner_id=learner_id,
        task_type=input.task_type,
        limit=input.limit
    )

    in_progress_count = sum(1 for t in ready_tasks if t.status == "in_progress")

    return GetReadyOutput(
        tasks=[TaskSummaryOutput(
            id=t.id,
            title=t.title,
            status=t.status,  # From learner_task_progress join
            task_type=t.task_type,
            priority=t.priority,
            has_children=await has_children(db, t.id)
        ) for t in ready_tasks],
        total_ready=len(ready_tasks),
        message=f"Found {len(ready_tasks)} tasks ready ({in_progress_count} in progress)."
    )


class ShowTaskInput(BaseModel):
    """Input for show_task tool."""
    task_id: str = Field(..., description="Task ID to show details for")


class AcceptanceCriterionOutput(BaseModel):
    """Acceptance criterion for a task."""
    id: str
    criterion_type: str  # code_test, sql_result, text_match, manual
    description: str


class TaskDetailOutput(BaseModel):
    """Detailed task information."""
    id: str
    title: str
    description: str
    acceptance_criteria: List[AcceptanceCriterionOutput]
    notes: str
    status: str
    task_type: str
    priority: int

    # Hierarchy
    parent_id: Optional[str]
    children: List[TaskSummaryOutput]

    # Learning
    learning_objectives: List[dict]
    content: Optional[str]

    # Dependencies
    blocked_by: List[TaskSummaryOutput]
    blocks: List[TaskSummaryOutput]

    # History (for current learner)
    submission_count: int
    latest_validation_passed: Optional[bool]
    status_summaries: List[dict]


async def show_task(
    input: ShowTaskInput,
    learner_id: str,
    db
) -> TaskDetailOutput:
    """
    Show detailed information about a task.

    Includes learning objectives, structured acceptance criteria, and submission history.

    Implementation Note (ADR-001):
    - Task template (title, description, objectives) from `tasks` table
    - Status comes from `learner_task_progress` join (per-learner)
    - Submissions, validations, summaries are learner-scoped
    """
    task = await get_task_detail(db, input.task_id, learner_id)

    # Get learner-specific data
    submissions = await get_submissions(db, input.task_id, learner_id)
    latest_val = await get_latest_validation(db, input.task_id, learner_id)
    summaries = await get_status_summaries(db, input.task_id, learner_id)

    return TaskDetailOutput(
        id=task.id,
        title=task.title,
        description=task.description,
        acceptance_criteria=[
            AcceptanceCriterionOutput(
                id=c.id,
                criterion_type=c.criterion_type,
                description=c.description
            )
            for c in task.acceptance_criteria
        ],
        notes=task.notes,
        status=task.learner_status,  # From learner_task_progress join
        task_type=task.task_type,
        priority=task.priority,
        parent_id=task.parent_id,
        children=[TaskSummaryOutput(...) for c in task.children],
        learning_objectives=[
            {"level": o.level, "description": o.description}
            for o in task.learning_objectives
        ],
        content=task.content,
        blocked_by=[TaskSummaryOutput(...) for t in task.blocked_by],
        blocks=[TaskSummaryOutput(...) for t in task.blocks],
        submission_count=len(submissions),
        latest_validation_passed=latest_val.passed if latest_val else None,
        status_summaries=[
            {"version": s.version, "summary": s.summary, "created_at": s.created_at.isoformat()}
            for s in summaries
        ]
    )


class GetContextInput(BaseModel):
    """Input for get_context tool."""
    task_id: str = Field(..., description="Task to get context for")


class GetContextOutput(BaseModel):
    """Full task context for agent."""
    learner_id: str

    current_task: TaskSummaryOutput
    project_id: str

    hierarchy: List[dict]  # [{id, title, type}, ...] ancestors up to project
    ready_tasks: List[TaskSummaryOutput]  # in_progress first, then open
    progress: Optional[dict]

    # Task-specific context
    acceptance_criteria: List[AcceptanceCriterionOutput]
    learning_objectives: List[dict]
    status_summaries: List[dict]


async def get_context(
    input: GetContextInput,
    learner_id: str,
    db
) -> GetContextOutput:
    """
    Get full context for a task.

    Use this to understand the current state of a task and what needs to be done.
    Note: Session/conversation context is managed by LangGraph.

    Implementation Note (ADR-001):
    - Status comes from learner's progress record
    - Dependencies checked against learner's progress
    """
    ctx = await load_task_context(db, input.task_id, learner_id)

    return GetContextOutput(
        learner_id=learner_id,
        current_task=TaskSummaryOutput(
            id=ctx.current_task.id,
            title=ctx.current_task.title,
            status=ctx.learner_status,  # From learner_task_progress
            task_type=ctx.current_task.task_type,
            priority=ctx.current_task.priority,
            has_children=len(ctx.children) > 0
        ),
        project_id=ctx.current_task.project_id,
        hierarchy=[
            {"id": t.id, "title": t.title, "type": t.task_type}
            for t in ctx.task_ancestors
        ],
        ready_tasks=[TaskSummaryOutput(...) for t in ctx.ready_tasks],
        progress={
            "completed": ctx.project_progress.completed_tasks,
            "total": ctx.project_progress.total_tasks,
            "percentage": ctx.project_progress.completion_percentage
        } if ctx.project_progress else None,
        acceptance_criteria=[
            AcceptanceCriterionOutput(
                id=c.id,
                criterion_type=c.criterion_type,
                description=c.description
            )
            for c in ctx.acceptance_criteria
        ],
        learning_objectives=[
            {"level": o.level, "description": o.description}
            for o in ctx.learning_objectives
        ],
        status_summaries=[
            {"version": s.version, "summary": s.summary, "created_at": s.created_at.isoformat()}
            for s in ctx.status_summaries
        ]
    )
```

### Progress Tools

```python
class StartTaskInput(BaseModel):
    """Input for start_task tool."""
    task_id: str = Field(..., description="Task to start working on")


class StartTaskOutput(BaseModel):
    """Result of starting a task - includes full context."""
    success: bool
    task_id: str
    old_status: str
    new_status: str
    message: str

    # Full context for the task (same as get_context)
    context: Optional[GetContextOutput]

    # Side effects
    newly_unblocked: List[str]  # Tasks that became unblocked


async def start_task(
    input: StartTaskInput,
    learner_id: str,
    db
) -> StartTaskOutput:
    """
    Start working on a task.

    Sets status to in_progress and returns full context for the task.
    This is the primary way to begin work on a task.

    Implementation Note (ADR-001):
    - Status is written to `learner_task_progress`, not `tasks` table
    - Creates progress record if it doesn't exist (lazy initialization)
    - Checks blocking against learner's own progress
    """
    # Get or create learner's progress record
    progress = await get_or_create_progress(db, input.task_id, learner_id)
    old_status = progress.status

    # Check if task can be started
    if progress.status == TaskStatus.CLOSED.value:
        return StartTaskOutput(
            success=False,
            task_id=input.task_id,
            old_status=old_status,
            new_status=old_status,
            message="Cannot start a closed task. Use go_back to reopen it first.",
            context=None,
            newly_unblocked=[]
        )

    if progress.status == TaskStatus.BLOCKED.value:
        blockers = await get_blocking_tasks(db, input.task_id, learner_id)
        return StartTaskOutput(
            success=False,
            task_id=input.task_id,
            old_status=old_status,
            new_status=old_status,
            message=f"Task is blocked by {len(blockers)} other task(s).",
            context=None,
            newly_unblocked=[]
        )

    # Set to in_progress if not already
    if progress.status != TaskStatus.IN_PROGRESS.value:
        await update_learner_task_status(
            db, input.task_id, learner_id, TaskStatus.IN_PROGRESS
        )

    # Load full context
    ctx = await load_task_context(db, input.task_id, learner_id)

    context_output = GetContextOutput(
        learner_id=learner_id,
        current_task=TaskSummaryOutput(
            id=ctx.current_task.id,
            title=ctx.current_task.title,
            status="in_progress",  # We just set it
            task_type=ctx.current_task.task_type,
            priority=ctx.current_task.priority,
            has_children=len(ctx.children) > 0
        ),
        project_id=ctx.current_task.project_id,
        hierarchy=[{"id": t.id, "title": t.title, "type": t.task_type} for t in ctx.task_ancestors],
        ready_tasks=[TaskSummaryOutput(...) for t in ctx.ready_tasks],
        progress={
            "completed": ctx.project_progress.completed_tasks,
            "total": ctx.project_progress.total_tasks,
            "percentage": ctx.project_progress.completion_percentage
        } if ctx.project_progress else None,
        acceptance_criteria=[
            AcceptanceCriterionOutput(id=c.id, criterion_type=c.criterion_type, description=c.description)
            for c in ctx.acceptance_criteria
        ],
        learning_objectives=[{"level": o.level, "description": o.description} for o in ctx.learning_objectives],
        status_summaries=[
            {"version": s.version, "summary": s.summary, "created_at": s.created_at.isoformat()}
            for s in ctx.status_summaries
        ]
    )

    return StartTaskOutput(
        success=True,
        task_id=input.task_id,
        old_status=old_status,
        new_status="in_progress",
        message=f"Started working on '{task.title}'",
        context=context_output,
        newly_unblocked=[]
    )


class SubmitInput(BaseModel):
    """Input for submit tool."""
    task_id: str = Field(..., description="Task to submit for")
    content: str = Field(..., description="Submission content (code, text, etc.)")
    submission_type: str = Field(
        "code",
        description="Type: code, sql, jupyter_cell, text, result_set"
    )


class SubmitOutput(BaseModel):
    """Result of submission."""
    success: bool
    submission_id: str
    attempt_number: int

    # Validation result
    validation_passed: Optional[bool]
    validation_message: Optional[str]

    # Status
    can_close_task: bool
    message: str


async def submit(
    input: SubmitInput,
    learner_id: str,
    db
) -> SubmitOutput:
    """
    Submit work for a task and trigger validation.

    Returns validation result and whether task can be closed.
    """
    submission, validation = await create_submission(
        db,
        task_id=input.task_id,
        learner_id=learner_id,
        content=input.content,
        submission_type=SubmissionType(input.submission_type),
        auto_validate=True
    )

    can_close, _ = await can_close_task(db, input.task_id, learner_id)

    if validation and validation.passed:
        message = f"Submission passed validation! (Attempt #{submission.attempt_number})"
    elif validation:
        message = f"Submission failed: {validation.error_message}"
    else:
        message = f"Submission recorded (Attempt #{submission.attempt_number})"

    return SubmitOutput(
        success=True,
        submission_id=submission.id,
        attempt_number=submission.attempt_number,
        validation_passed=validation.passed if validation else None,
        validation_message=validation.error_message if validation else None,
        can_close_task=can_close,
        message=message
    )
```

### Feedback Tools

```python
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


async def add_comment(
    input: AddCommentInput,
    learner_id: str,
    db
) -> CommentOutput:
    """
    Add a comment to a task.

    Use for questions, feedback, or notes.

    Implementation Note (ADR-001):
    - Sets `learner_id` on the comment (private to this learner)
    - Only this learner will see their private comments
    - Shared comments (instructor notes) have learner_id=NULL
    """
    comment = await create_comment(
        db,
        task_id=input.task_id,
        author=learner_id,
        text=input.comment,
        learner_id=learner_id  # Private to this learner
    )

    return CommentOutput(
        id=comment.id,
        author=comment.author,
        text=comment.text,
        created_at=comment.created_at.isoformat()
    )


class GetCommentsInput(BaseModel):
    """Input for get_comments tool."""
    task_id: str = Field(..., description="Task to get comments for")
    limit: int = Field(10, description="Maximum comments", ge=1, le=50)


class GetCommentsOutput(BaseModel):
    """Comments on a task."""
    comments: List[CommentOutput]
    total: int


async def get_comments(
    input: GetCommentsInput,
    learner_id: str,
    db
) -> GetCommentsOutput:
    """
    Get comments on a task.

    Implementation Note (ADR-001):
    - Returns shared comments (learner_id=NULL) + this learner's private comments
    - Query: WHERE task_id = ? AND (learner_id IS NULL OR learner_id = ?)
    - Other learners' private comments are not visible
    """
    comments = await get_task_comments(
        db,
        task_id=input.task_id,
        learner_id=learner_id,  # Filter for shared + learner's private
        limit=input.limit
    )

    return GetCommentsOutput(
        comments=[CommentOutput(
            id=c.id,
            author=c.author,
            text=c.text,
            created_at=c.created_at.isoformat()
        ) for c in comments],
        total=len(comments)
    )
```

### Control Tools

```python
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


async def go_back(
    input: GoBackInput,
    learner_id: str,
    db
) -> GoBackOutput:
    """
    Reopen a closed task.

    Use when learner wants to redo or the task was closed prematurely.
    Requires a reason for the audit trail.

    Implementation Note (ADR-001):
    - Reopening updates `learner_task_progress.status`, not `task.status`
    - Only affects this learner's progress record
    - Other learners' progress is unchanged
    """
    # Get learner's progress record
    progress = await get_or_create_progress(db, input.task_id, learner_id)

    if progress.status != TaskStatus.CLOSED.value:
        return GoBackOutput(
            success=False,
            task_id=input.task_id,
            new_status=progress.status,
            message=f"Task is not closed (status: {progress.status})",
            reason=input.reason
        )

    # Reopen the task for this learner
    reopened = await reopen_learner_task(
        db, input.task_id, learner_id, input.reason
    )

    return GoBackOutput(
        success=True,
        task_id=input.task_id,
        new_status=reopened.status,
        message=f"Task reopened: {input.reason}",
        reason=input.reason
    )


class RequestHelpInput(BaseModel):
    """Input for request_help tool."""
    task_id: str = Field(..., description="Task needing help")
    message: str = Field(..., description="Description of the issue")


class RequestHelpOutput(BaseModel):
    """Result of help request."""
    request_id: str
    message: str


async def request_help(
    input: RequestHelpInput,
    learner_id: str,
    db
) -> RequestHelpOutput:
    """
    Request human help for a task.

    Creates a help request that can be reviewed by instructors.
    """
    # Create a comment tagged as help request
    comment = await create_comment(
        db,
        task_id=input.task_id,
        author=learner_id,
        text=f"[HELP REQUEST] {input.message}"
    )

    # Future: could create a separate help_requests table
    # and notify instructors

    return RequestHelpOutput(
        request_id=comment.id,
        message="Help request submitted. An instructor will review it."
    )
```

---

## 3. Tool Registry

```python
from typing import Callable, Dict, Type
from pydantic import BaseModel


@dataclass
class ToolDefinition:
    """Definition of a tool for registration."""
    name: str
    description: str
    input_model: Type[BaseModel]
    output_model: Type[BaseModel]
    handler: Callable
    requires_learner: bool = True  # Most tools need learner_id


TOOLS: Dict[str, ToolDefinition] = {
    "get_ready": ToolDefinition(
        name="get_ready",
        description="Get tasks that are unblocked and ready to work on (in_progress first)",
        input_model=GetReadyInput,
        output_model=GetReadyOutput,
        handler=get_ready
    ),
    "show_task": ToolDefinition(
        name="show_task",
        description="Show detailed information about a specific task",
        input_model=ShowTaskInput,
        output_model=TaskDetailOutput,
        handler=show_task
    ),
    "get_context": ToolDefinition(
        name="get_context",
        description="Get full context for a task (objectives, criteria, summaries)",
        input_model=GetContextInput,
        output_model=GetContextOutput,
        handler=get_context
    ),
    "start_task": ToolDefinition(
        name="start_task",
        description="Start working on a task (sets to in_progress and returns full context)",
        input_model=StartTaskInput,
        output_model=StartTaskOutput,
        handler=start_task
    ),
    "submit": ToolDefinition(
        name="submit",
        description="Submit work for a task and trigger validation",
        input_model=SubmitInput,
        output_model=SubmitOutput,
        handler=submit
    ),
    "add_comment": ToolDefinition(
        name="add_comment",
        description="Add a comment to a task",
        input_model=AddCommentInput,
        output_model=CommentOutput,
        handler=add_comment
    ),
    "get_comments": ToolDefinition(
        name="get_comments",
        description="Get comments on a task",
        input_model=GetCommentsInput,
        output_model=GetCommentsOutput,
        handler=get_comments
    ),
    "go_back": ToolDefinition(
        name="go_back",
        description="Reopen a closed task (reason required)",
        input_model=GoBackInput,
        output_model=GoBackOutput,
        handler=go_back
    ),
    "request_help": ToolDefinition(
        name="request_help",
        description="Request human help for a task",
        input_model=RequestHelpInput,
        output_model=RequestHelpOutput,
        handler=request_help
    ),
}


def get_tool_schemas() -> List[dict]:
    """Get OpenAI-compatible tool schemas for function calling."""
    schemas = []
    for tool in TOOLS.values():
        schema = {
            "type": "function",
            "function": {
                "name": tool.name,
                "description": tool.description,
                "parameters": tool.input_model.model_json_schema() if tool.input_model else {}
            }
        }
        schemas.append(schema)
    return schemas
```

---

## 4. Error Handling

```python
class ToolError(BaseModel):
    """Standard error response from tools."""
    success: bool = False
    error_code: str
    message: str
    details: Optional[dict] = None


ERROR_CODES = {
    "NOT_FOUND": "Resource not found",
    "INVALID_STATE": "Operation not allowed in current state",
    "VALIDATION_FAILED": "Input validation failed",
    "PERMISSION_DENIED": "Not authorized for this operation",
    "BLOCKED": "Task is blocked by dependencies",
}


async def execute_tool(
    tool_name: str,
    input_data: dict,
    learner_id: str,
    db
) -> BaseModel:
    """
    Execute a tool with error handling.

    Note: Session management is handled by LangGraph. Tools only need learner_id.
    """
    if tool_name not in TOOLS:
        return ToolError(
            error_code="UNKNOWN_TOOL",
            message=f"Unknown tool: {tool_name}"
        )

    tool = TOOLS[tool_name]

    try:
        # Parse input
        if tool.input_model:
            input_obj = tool.input_model(**input_data)
        else:
            input_obj = None

        # Execute
        result = await tool.handler(
            input=input_obj,
            learner_id=learner_id,
            db=db
        )
        return result

    except NotFoundError as e:
        return ToolError(
            error_code="NOT_FOUND",
            message=str(e)
        )
    except InvalidStateError as e:
        return ToolError(
            error_code="INVALID_STATE",
            message=str(e)
        )
    except ValidationError as e:
        return ToolError(
            error_code="VALIDATION_FAILED",
            message=str(e),
            details=e.errors() if hasattr(e, 'errors') else None
        )
    except Exception as e:
        return ToolError(
            error_code="INTERNAL_ERROR",
            message=f"An unexpected error occurred: {str(e)}"
        )
```

---

## 5. File Structure

```
src/ltt/
├── tools/
│   ├── __init__.py       # Tool registry, execute_tool
│   ├── navigation.py     # get_ready, show_task, get_context
│   ├── progress.py       # update_status, submit
│   ├── feedback.py       # add_comment, get_comments
│   ├── control.py        # go_back, request_help
│   └── schemas.py        # All input/output Pydantic models
```

---

## 6. Testing Requirements

```python
class TestNavigationTools:
    async def test_get_ready_returns_unblocked(self):
        ...

    async def test_show_task_includes_objectives(self):
        ...


class TestProgressTools:
    async def test_submit_triggers_validation(self):
        ...

    async def test_update_status_checks_validation(self):
        ...


class TestControlTools:
    async def test_go_back_reopens_closed_task(self):
        ...
```
