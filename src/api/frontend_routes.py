"""
Frontend API routes for the Learning Task Tracker.

Provides endpoints for:
- Project tree with learner progress
- Task details
- Start/submit task actions
- Ready work queries
- Database schema for SQL.js
"""

from typing import Any

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from api.database import get_session_factory
from ltt.models import SubmissionType, TaskStatus
from ltt.services.task_service import get_task, get_children, TaskNotFoundError
from ltt.services.progress_service import get_or_create_progress, update_status
from ltt.services.dependency_service import get_ready_work, is_task_blocked
from ltt.services.submission_service import create_submission
from ltt.services.validation_service import validate_submission

router = APIRouter(prefix="/api/v1", tags=["frontend"])


# =============================================================================
# Response Models
# =============================================================================


class TaskNode(BaseModel):
    """Task node for tree display."""

    id: str
    title: str
    task_type: str
    status: str
    priority: int
    description: str | None = None
    acceptance_criteria: str | None = None
    children: list["TaskNode"] = []
    progress: dict[str, int] | None = None


class ProjectInfo(BaseModel):
    """Basic project information."""

    id: str
    title: str
    description: str | None = None
    narrative_context: str | None = None


class ProjectProgress(BaseModel):
    """Project progress summary."""

    total_tasks: int
    completed_tasks: int
    in_progress: int
    blocked: int
    percentage: float


class ProjectTreeResponse(BaseModel):
    """Project tree with learner progress."""

    project: ProjectInfo
    hierarchy: list[TaskNode]
    progress: ProjectProgress


class TaskDetailResponse(BaseModel):
    """Detailed task information."""

    id: str
    title: str
    description: str | None
    acceptance_criteria: str | None
    task_type: str
    status: str
    priority: int
    content: str | None
    tutor_guidance: dict[str, Any] | None
    is_blocked: bool
    blocking_tasks: list[str]
    parent_id: str | None
    project_id: str


class TaskSummaryResponse(BaseModel):
    """Summary of a task for listing."""

    id: str
    title: str
    task_type: str
    status: str
    priority: int


class ReadyTasksResponse(BaseModel):
    """Ready tasks response."""

    tasks: list[TaskSummaryResponse]
    total_ready: int
    message: str


class StartTaskRequest(BaseModel):
    """Request to start a task."""

    learner_id: str = Field(..., description="The learner's ID")


class StartTaskResponse(BaseModel):
    """Response from starting a task."""

    success: bool
    status: str
    message: str


class SubmitWorkRequest(BaseModel):
    """Request to submit work."""

    learner_id: str = Field(..., description="The learner's ID")
    content: str = Field(..., description="The submission content")
    submission_type: str = Field(default="sql", description="Type of submission")


class SubmitWorkResponse(BaseModel):
    """Response from submitting work."""

    success: bool
    passed: bool
    message: str
    status: str
    submission_id: str | None = None


class DatabaseSchemaResponse(BaseModel):
    """Database schema for SQL.js initialization."""

    schema_sql: str = Field(..., alias="schema")
    sample_data: str

    model_config = {"populate_by_name": True}


# =============================================================================
# Endpoints
# =============================================================================


@router.get("/project/{project_id}/tree", response_model=ProjectTreeResponse)
async def get_project_tree(
    project_id: str,
    learner_id: str = Query(..., description="The learner's ID"),
) -> ProjectTreeResponse:
    """
    Get the full project tree with learner progress.

    Returns hierarchical task structure with completion status.
    """
    session_factory = get_session_factory()

    async with session_factory() as session:
        try:
            # Get project (root task)
            project = await get_task(session, project_id)

            # Recursively build tree with progress
            async def build_tree(task_id: str) -> tuple[TaskNode, dict]:
                task = await get_task(session, task_id)
                progress = await get_or_create_progress(session, task_id, learner_id)

                # Get children
                children = await get_children(session, task_id, recursive=False)

                child_nodes = []
                stats = {"total": 0, "completed": 0, "in_progress": 0, "blocked": 0}

                for child in children:
                    child_node, child_stats = await build_tree(child.id)
                    child_nodes.append(child_node)

                    # Aggregate stats
                    stats["total"] += child_stats["total"]
                    stats["completed"] += child_stats["completed"]
                    stats["in_progress"] += child_stats["in_progress"]
                    stats["blocked"] += child_stats["blocked"]

                # Count this task (if it's a leaf or task type)
                if task.task_type.value in ("task", "subtask") or not children:
                    stats["total"] += 1
                    if progress.status == TaskStatus.CLOSED.value:
                        stats["completed"] += 1
                    elif progress.status == TaskStatus.IN_PROGRESS.value:
                        stats["in_progress"] += 1
                    elif progress.status == TaskStatus.BLOCKED.value:
                        stats["blocked"] += 1

                # Add progress info to task nodes
                task_progress = None
                if stats["total"] > 0:
                    task_progress = {"completed": stats["completed"], "total": stats["total"]}

                node = TaskNode(
                    id=task.id,
                    title=task.title,
                    task_type=task.task_type.value,
                    status=progress.status,
                    priority=task.priority,
                    description=task.description,
                    acceptance_criteria=task.acceptance_criteria,
                    children=child_nodes,
                    progress=task_progress,
                )

                return node, stats

            root_node, stats = await build_tree(project_id)

            # Calculate percentage
            percentage = (stats["completed"] / stats["total"] * 100) if stats["total"] > 0 else 0

            return ProjectTreeResponse(
                project=ProjectInfo(
                    id=project.id,
                    title=project.title,
                    description=project.description,
                    narrative_context=project.narrative_context,
                ),
                hierarchy=root_node.children,
                progress=ProjectProgress(
                    total_tasks=stats["total"],
                    completed_tasks=stats["completed"],
                    in_progress=stats["in_progress"],
                    blocked=stats["blocked"],
                    percentage=percentage,
                ),
            )

        except TaskNotFoundError:
            raise HTTPException(status_code=404, detail=f"Project {project_id} not found")
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))


@router.get("/task/{task_id}", response_model=TaskDetailResponse)
async def get_task_details(
    task_id: str,
    learner_id: str = Query(..., description="The learner's ID"),
) -> TaskDetailResponse:
    """
    Get detailed information about a specific task.

    Includes progress status, blocking info, and content.
    """
    session_factory = get_session_factory()

    async with session_factory() as session:
        try:
            task = await get_task(session, task_id)
            progress = await get_or_create_progress(session, task_id, learner_id)
            is_blocked, blockers = await is_task_blocked(session, task_id, learner_id)

            return TaskDetailResponse(
                id=task.id,
                title=task.title,
                description=task.description,
                acceptance_criteria=task.acceptance_criteria,
                task_type=task.task_type.value,
                status=progress.status,
                priority=task.priority,
                content=task.content,
                tutor_guidance=task.tutor_guidance,
                is_blocked=is_blocked,
                blocking_tasks=[b.id for b in blockers],
                parent_id=task.parent_id,
                project_id=task.project_id,
            )

        except TaskNotFoundError:
            raise HTTPException(status_code=404, detail=f"Task {task_id} not found")
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))


@router.get("/project/{project_id}/ready", response_model=ReadyTasksResponse)
async def get_ready_tasks(
    project_id: str,
    learner_id: str = Query(..., description="The learner's ID"),
    limit: int = Query(default=5, ge=1, le=20),
) -> ReadyTasksResponse:
    """
    Get tasks that are ready to work on.

    Returns unblocked tasks ordered by priority.
    """
    session_factory = get_session_factory()

    async with session_factory() as session:
        try:
            ready_tasks = await get_ready_work(
                session,
                project_id=project_id,
                learner_id=learner_id,
                limit=limit,
            )

            tasks = []
            for task in ready_tasks:
                progress = await get_or_create_progress(session, task.id, learner_id)
                tasks.append(
                    TaskSummaryResponse(
                        id=task.id,
                        title=task.title,
                        task_type=task.task_type.value,
                        status=progress.status,
                        priority=task.priority,
                    )
                )

            message = (
                f"Found {len(tasks)} task(s) ready to work on"
                if tasks
                else "No tasks ready - complete blocking tasks first"
            )

            return ReadyTasksResponse(
                tasks=tasks,
                total_ready=len(tasks),
                message=message,
            )

        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))


@router.post("/task/{task_id}/start", response_model=StartTaskResponse)
async def start_task(
    task_id: str,
    request: StartTaskRequest,
) -> StartTaskResponse:
    """
    Start working on a task.

    Sets the learner's status to 'in_progress'.
    """
    session_factory = get_session_factory()

    async with session_factory() as session:
        try:
            # Check task exists
            await get_task(session, task_id)

            # Check not blocked
            is_blocked, blockers = await is_task_blocked(session, task_id, request.learner_id)
            if is_blocked:
                blocker_ids = ", ".join(b.id for b in blockers)
                return StartTaskResponse(
                    success=False,
                    status="blocked",
                    message=f"Task is blocked by: {blocker_ids}",
                )

            # Update status
            progress = await get_or_create_progress(session, task_id, request.learner_id)

            if progress.status == TaskStatus.CLOSED.value:
                return StartTaskResponse(
                    success=False,
                    status="closed",
                    message="Task is already completed",
                )

            await update_status(session, task_id, request.learner_id, TaskStatus.IN_PROGRESS)
            await session.commit()

            return StartTaskResponse(
                success=True,
                status="in_progress",
                message="Task started successfully",
            )

        except TaskNotFoundError:
            raise HTTPException(status_code=404, detail=f"Task {task_id} not found")
        except Exception as e:
            await session.rollback()
            raise HTTPException(status_code=500, detail=str(e))


@router.post("/task/{task_id}/submit", response_model=SubmitWorkResponse)
async def submit_work(
    task_id: str,
    request: SubmitWorkRequest,
) -> SubmitWorkResponse:
    """
    Submit work for a task.

    Creates a submission and runs validation.
    """
    session_factory = get_session_factory()

    async with session_factory() as session:
        try:
            # Map string to enum
            try:
                sub_type = SubmissionType(request.submission_type)
            except ValueError:
                sub_type = SubmissionType.SQL

            # Create submission
            submission = await create_submission(
                session,
                task_id=task_id,
                learner_id=request.learner_id,
                content=request.content,
                submission_type=sub_type,
            )

            await session.commit()

            # Validate submission
            validation = await validate_submission(session, submission.id)
            await session.commit()

            # Update task status if passed
            if validation.passed:
                await update_status(session, task_id, request.learner_id, TaskStatus.CLOSED)
                await session.commit()

            progress = await get_or_create_progress(session, task_id, request.learner_id)

            return SubmitWorkResponse(
                success=True,
                passed=validation.passed,
                message=validation.feedback or ("Correct!" if validation.passed else "Try again"),
                status=progress.status,
                submission_id=submission.id,
            )

        except TaskNotFoundError:
            raise HTTPException(status_code=404, detail=f"Task {task_id} not found")
        except Exception as e:
            await session.rollback()
            raise HTTPException(status_code=500, detail=str(e))


@router.get("/project/{project_id}/database", response_model=DatabaseSchemaResponse)
async def get_database_schema(project_id: str) -> DatabaseSchemaResponse:
    """
    Get the database schema for SQL.js initialization.

    Returns SQL statements to create and populate the learning database.
    """
    # For now, return the Maji Ndogo water survey schema
    # In a full implementation, this would be stored per-project
    schema = """
-- Maji Ndogo Water Access Survey Database
CREATE TABLE IF NOT EXISTS md_water_services (
    location_id INTEGER PRIMARY KEY,
    region TEXT NOT NULL,
    province TEXT NOT NULL,
    town TEXT NOT NULL,
    location_type TEXT NOT NULL,
    source_id INTEGER,
    type_of_water_source TEXT,
    number_of_people_served INTEGER,
    time_in_queue INTEGER,
    visit_count INTEGER,
    assigned_employee_id INTEGER
);

CREATE TABLE IF NOT EXISTS well_pollution (
    source_id INTEGER PRIMARY KEY,
    date DATE,
    status TEXT,
    description TEXT,
    pollutant_ppm REAL,
    biological REAL,
    results TEXT
);

CREATE TABLE IF NOT EXISTS employee (
    assigned_employee_id INTEGER PRIMARY KEY,
    employee_name TEXT NOT NULL,
    phone_number TEXT,
    email TEXT,
    address TEXT,
    town TEXT,
    province TEXT
);

CREATE TABLE IF NOT EXISTS visits (
    record_id INTEGER PRIMARY KEY AUTOINCREMENT,
    location_id INTEGER,
    source_id INTEGER,
    visit_count INTEGER,
    time_in_queue INTEGER,
    assigned_employee_id INTEGER,
    FOREIGN KEY (location_id) REFERENCES md_water_services(location_id),
    FOREIGN KEY (assigned_employee_id) REFERENCES employee(assigned_employee_id)
);

CREATE TABLE IF NOT EXISTS infrastructure_cost (
    improvement TEXT PRIMARY KEY,
    unit_cost REAL
);
"""

    sample_data = """
-- Sample data for Maji Ndogo
INSERT INTO md_water_services VALUES
    (1, 'Amanzi', 'Central', 'Harare', 'Urban', 101, 'tap_in_home', 150, 0, 1, 1),
    (2, 'Amanzi', 'Central', 'Harare', 'Urban', 102, 'shared_tap', 500, 30, 2, 1),
    (3, 'Amanzi', 'Central', 'Bulawayo', 'Peri-urban', 103, 'well', 200, 120, 3, 2),
    (4, 'Sokoto', 'North', 'Katsina', 'Rural', 104, 'river', 100, 180, 1, 3),
    (5, 'Sokoto', 'North', 'Kaduna', 'Rural', 105, 'well', 300, 90, 2, 3),
    (6, 'Hawassa', 'South', 'Awasa', 'Urban', 106, 'tap_in_home_broken', 250, 0, 1, 4),
    (7, 'Hawassa', 'South', 'Dilla', 'Peri-urban', 107, 'shared_tap', 400, 60, 2, 4),
    (8, 'Kilimani', 'East', 'Moshi', 'Rural', 108, 'river', 150, 200, 1, 5),
    (9, 'Kilimani', 'East', 'Arusha', 'Urban', 109, 'tap_in_home', 180, 0, 3, 5),
    (10, 'Amanzi', 'Central', 'Gweru', 'Peri-urban', 110, 'well', 220, 45, 2, 2);

INSERT INTO well_pollution VALUES
    (103, '2023-01-15', 'Contaminated', 'Biological contamination detected', 0.5, 0.8, 'Failed'),
    (105, '2023-01-20', 'Clean', 'No contamination', 0.1, 0.0, 'Passed'),
    (110, '2023-02-01', 'Contaminated', 'Chemical pollutants', 1.2, 0.0, 'Failed');

INSERT INTO employee VALUES
    (1, 'Amara Osei', '+234-555-0101', 'amara@water.gov', '123 Main St', 'Harare', 'Central'),
    (2, 'Kofi Mensah', '+234-555-0102', 'kofi@water.gov', '456 Oak Ave', 'Bulawayo', 'Central'),
    (3, 'Fatima Ibrahim', '+234-555-0103', 'fatima@water.gov', '789 Elm Rd', 'Katsina', 'North'),
    (4, 'Yohannes Tadesse', '+251-555-0104', 'yohannes@water.gov', '321 Pine Ln', 'Awasa', 'South'),
    (5, 'Grace Kimani', '+255-555-0105', 'grace@water.gov', '654 Cedar Dr', 'Moshi', 'East');

INSERT INTO infrastructure_cost VALUES
    ('tap_in_home', 500.00),
    ('shared_tap', 250.00),
    ('well_repair', 150.00),
    ('well_new', 800.00),
    ('river_filter', 200.00),
    ('pipe_extension', 75.00);

INSERT INTO visits VALUES
    (1, 1, 101, 1, 0, 1),
    (2, 2, 102, 2, 30, 1),
    (3, 3, 103, 3, 120, 2),
    (4, 4, 104, 1, 180, 3),
    (5, 5, 105, 2, 90, 3);
"""

    return DatabaseSchemaResponse(schema_sql=schema, sample_data=sample_data)
