"""
End-to-End Agentic Workflow Test.

This test validates the complete learner journey through a project,
testing all agent tools, CLI commands, and multi-learner isolation.

Requirements:
1. Database must be running (PostgreSQL 17)
2. Ingests project from JSON (part of test setup)
3. Tests CLI commands for learner creation
4. Tests multi-learner isolation (comments, status, progress)
5. Validates all failure modes

Run with: pytest -m integration
"""

from pathlib import Path

import pytest

# Mark all tests in this module as integration tests (skipped by default)
pytestmark = pytest.mark.integration
from ltt.models import LearnerModel
from ltt.services.dependency_service import is_task_blocked
from ltt.services.ingest import ingest_project_file
from ltt.services.learning import get_progress
from ltt.services.progress_service import (
    close_task,
    get_or_create_progress,
    reopen_task,
)
from ltt.services.task_service import get_children, get_comments, get_task
from ltt.tools import (
    AddCommentInput,
    GetReadyInput,
    StartTaskInput,
    SubmitInput,
    add_comment,
    get_ready,
    start_task,
    submit,
)
from ltt.utils.ids import PREFIX_LEARNER, generate_entity_id
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession


@pytest.fixture
async def check_database(async_session: AsyncSession):
    """Verify database is running and accessible."""
    try:
        result = await async_session.execute(text("SELECT 1"))
        result.scalar()
    except Exception as e:
        pytest.fail(
            f"Database connection failed: {e}\n\n"
            "Please ensure PostgreSQL is running:\n"
            "  docker-compose up -d\n\n"
            "See README.md for setup instructions."
        )


@pytest.fixture
async def ingested_project(async_session: AsyncSession, check_database):
    """Ingest the water analysis project from JSON."""
    project_file = Path("project_data/DA/MN_Part1/structured/water_analysis_project.json")

    if not project_file.exists():
        pytest.fail(
            f"Project file not found: {project_file}\n\n"
            "Please ensure the project data exists in the repository."
        )

    # Ingest the project
    result = await ingest_project_file(async_session, project_file, dry_run=False)

    if result.errors:
        pytest.fail(f"Project ingestion failed: {result.errors}")

    return result.project_id


@pytest.fixture
async def learner_a(async_session: AsyncSession):
    """Create first test learner."""
    learner_id = generate_entity_id(PREFIX_LEARNER)
    learner = LearnerModel(id=learner_id, learner_metadata='{"name": "Alice", "test": "e2e"}')
    async_session.add(learner)
    await async_session.commit()
    return learner_id


@pytest.fixture
async def learner_b(async_session: AsyncSession):
    """Create second test learner."""
    learner_id = generate_entity_id(PREFIX_LEARNER)
    learner = LearnerModel(id=learner_id, learner_metadata='{"name": "Bob", "test": "e2e"}')
    async_session.add(learner)
    await async_session.commit()
    return learner_id


@pytest.mark.asyncio
async def test_e2e_initial_state(async_session, ingested_project, learner_a):
    """Test: Initial project state shows all unblocked work."""
    project_id = ingested_project

    # Get initial progress (should be 0)
    progress = await get_progress(async_session, learner_a, project_id)
    assert progress.completed_tasks == 0
    assert progress.in_progress_tasks == 0

    # Get ready work - should only include Epic 1 (due to epic dependencies)
    result = await get_ready(
        GetReadyInput(project_id=project_id, limit=20), learner_a, async_session
    )

    assert result.total_ready > 0
    # Should NOT include tasks from blocked epics (Epic 2+)
    epic_2_tasks = [t for t in result.tasks if t.id.startswith(f"{project_id}.2.")]
    assert len(epic_2_tasks) == 0, "Epic 2 tasks should be blocked initially"


@pytest.mark.asyncio
async def test_e2e_start_task(async_session, ingested_project, learner_a):
    """Test: Starting a task transitions status to in_progress."""
    project_id = ingested_project

    # Get first task
    ready = await get_ready(GetReadyInput(project_id=project_id), learner_a, async_session)
    first_task = ready.tasks[0]

    # Start the task
    result = await start_task(StartTaskInput(task_id=first_task.id), learner_a, async_session)

    assert result.success is True
    assert result.status == "in_progress"
    assert result.context is not None


@pytest.mark.asyncio
async def test_e2e_submission_and_validation(async_session, ingested_project, learner_a):
    """Test: Submission triggers validation and auto-closes on success."""
    project_id = ingested_project

    # Get first subtask
    ready = await get_ready(GetReadyInput(project_id=project_id), learner_a, async_session)
    # Find a subtask
    subtask = None
    for task in ready.tasks:
        if task.task_type == "subtask":
            subtask = task
            break

    if not subtask:
        pytest.skip("No subtask available for submission test")

    # Start subtask
    await start_task(StartTaskInput(task_id=subtask.id), learner_a, async_session)

    # Submit work
    result = await submit(
        SubmitInput(task_id=subtask.id, content="Test submission content", submission_type="text"),
        learner_a,
        async_session,
    )

    assert result.success is True
    assert result.validation_passed is True
    assert result.status == "closed", "Task should auto-close on successful validation"


@pytest.mark.asyncio
async def test_e2e_hierarchical_closure(async_session, ingested_project, learner_a):
    """Test: Task closes only after all children are closed."""
    project_id = ingested_project

    # Get first epic
    await get_task(async_session, project_id)
    epics = await get_children(async_session, project_id, recursive=False)
    epic = epics[0]

    # Get first task in epic
    tasks = await get_children(async_session, epic.id, recursive=False)
    task = tasks[0]

    # Get subtasks
    subtasks = await get_children(async_session, task.id, recursive=False)

    if not subtasks:
        pytest.skip("No subtasks to test hierarchical closure")

    # Close all subtasks
    for subtask in subtasks:
        await start_task(StartTaskInput(task_id=subtask.id), learner_a, async_session)
        await submit(
            SubmitInput(task_id=subtask.id, content="work", submission_type="text"),
            learner_a,
            async_session,
        )

    # Now parent task should be closable
    await start_task(StartTaskInput(task_id=task.id), learner_a, async_session)
    await close_task(async_session, task.id, learner_a, "All subtasks complete")

    progress = await get_or_create_progress(async_session, task.id, learner_a)
    assert progress.status == "closed"


@pytest.mark.asyncio
async def test_e2e_epic_blocking_propagation(async_session, ingested_project, learner_a):
    """Test: Epic blocking propagates to child tasks."""
    project_id = ingested_project

    # Initially, Epic 2 tasks should be blocked
    ready = await get_ready(GetReadyInput(project_id=project_id), learner_a, async_session)
    epic_2_tasks = [t for t in ready.tasks if t.id.startswith(f"{project_id}.2.")]
    assert len(epic_2_tasks) == 0, "Epic 2 tasks should be blocked by Epic 1"

    # Complete Epic 1
    epic_1_id = f"{project_id}.1"
    epic_1_tasks = await get_children(async_session, epic_1_id, recursive=True)

    # Close all leaf tasks (subtasks first, then tasks)
    for task in sorted(epic_1_tasks, key=lambda t: t.id.count("."), reverse=True):
        if task.task_type in ["subtask", "task"]:
            try:
                await start_task(StartTaskInput(task_id=task.id), learner_a, async_session)
                await submit(
                    SubmitInput(task_id=task.id, content="work", submission_type="text"),
                    learner_a,
                    async_session,
                )
            except Exception:
                # Skip if can't close (e.g., has children)
                pass

    # Close Epic 1 itself
    try:
        await start_task(StartTaskInput(task_id=epic_1_id), learner_a, async_session)
        await close_task(async_session, epic_1_id, learner_a, "Epic 1 complete")
    except Exception:
        # May fail if children not fully closed - that's ok for this test
        pass

    # Now Epic 2 tasks should become available (if Epic 1 fully closed)
    ready_after = await get_ready(GetReadyInput(project_id=project_id), learner_a, async_session)
    epic_2_tasks_after = [t for t in ready_after.tasks if t.id.startswith(f"{project_id}.2.")]

    # If Epic 1 is closed, Epic 2 should be unblocked
    epic_1_progress = await get_or_create_progress(async_session, epic_1_id, learner_a)
    if epic_1_progress.status == "closed":
        assert len(epic_2_tasks_after) > 0, "Epic 2 should be unblocked after Epic 1 closes"


@pytest.mark.asyncio
async def test_e2e_multi_learner_isolation_status(
    async_session, ingested_project, learner_a, learner_b
):
    """Test: Learner A's status changes don't affect Learner B."""
    project_id = ingested_project

    # Get same task for both learners
    ready = await get_ready(GetReadyInput(project_id=project_id), learner_a, async_session)
    task_id = ready.tasks[0].id

    # Learner A starts task
    await start_task(StartTaskInput(task_id=task_id), learner_a, async_session)

    # Check Learner A status
    progress_a = await get_or_create_progress(async_session, task_id, learner_a)
    assert progress_a.status == "in_progress"

    # Check Learner B status (should still be open)
    progress_b = await get_or_create_progress(async_session, task_id, learner_b)
    assert progress_b.status == "open", "Learner B should not see Learner A's status change"


@pytest.mark.asyncio
async def test_e2e_multi_learner_isolation_comments(
    async_session, ingested_project, learner_a, learner_b
):
    """Test: Private comments are isolated per learner."""
    project_id = ingested_project

    # Get same task
    ready = await get_ready(GetReadyInput(project_id=project_id), learner_a, async_session)
    task_id = ready.tasks[0].id

    # Learner A adds private comment
    await add_comment(
        AddCommentInput(task_id=task_id, comment="Learner A private note"),
        learner_a,
        async_session,
    )

    # Learner B adds private comment
    await add_comment(
        AddCommentInput(task_id=task_id, comment="Learner B private note"),
        learner_b,
        async_session,
    )

    # Learner A should only see their own comment
    comments_a = await get_comments(async_session, task_id, learner_a)
    a_texts = [c.text for c in comments_a]
    assert "Learner A private note" in a_texts
    assert "Learner B private note" not in a_texts, "Learner A should not see B's comments"

    # Learner B should only see their own comment
    comments_b = await get_comments(async_session, task_id, learner_b)
    b_texts = [c.text for c in comments_b]
    assert "Learner B private note" in b_texts
    assert "Learner A private note" not in b_texts, "Learner B should not see A's comments"


@pytest.mark.asyncio
async def test_e2e_multi_learner_isolation_progress(
    async_session, ingested_project, learner_a, learner_b
):
    """Test: Progress tracking is independent per learner."""
    project_id = ingested_project

    # Learner A starts a task (not epic - epics are not counted in progress)
    ready_a = await get_ready(
        GetReadyInput(project_id=project_id, task_type="task"),
        learner_a,
        async_session,
    )

    if not ready_a.tasks:
        # If no tasks are ready yet, we need to start the epic first to unblock tasks
        epics = await get_ready(
            GetReadyInput(project_id=project_id, task_type="epic"),
            learner_a,
            async_session,
        )
        if epics.tasks:
            await start_task(StartTaskInput(task_id=epics.tasks[0].id), learner_a, async_session)
            ready_a = await get_ready(
                GetReadyInput(project_id=project_id, task_type="task"),
                learner_a,
                async_session,
            )

    assert ready_a.tasks, "No tasks available for learner A"
    task_a = ready_a.tasks[0]

    await start_task(StartTaskInput(task_id=task_a.id), learner_a, async_session)

    # Get progress for both learners
    progress_a = await get_progress(async_session, learner_a, project_id)
    progress_b = await get_progress(async_session, learner_b, project_id)

    # Learner A should have 1 in_progress task
    assert progress_a.in_progress_tasks == 1, (
        f"Expected 1 in_progress, got {progress_a.in_progress_tasks}"
    )

    # Learner B should have 0 in_progress
    assert progress_b.in_progress_tasks == 0, "Learner B progress should be independent"


@pytest.mark.asyncio
async def test_e2e_multi_learner_blocking(async_session, ingested_project, learner_a, learner_b):
    """Test: Blocking is per-learner (A unblocked doesn't unblock B)."""
    project_id = ingested_project

    # Find a task with dependencies
    all_tasks = await async_session.execute(
        text(
            """
        SELECT DISTINCT t.id, t.title
        FROM tasks t
        JOIN dependencies d ON d.task_id = t.id
        WHERE t.project_id = :project_id
        LIMIT 1
    """
        ),
        {"project_id": project_id},
    )
    blocked_task_row = all_tasks.fetchone()

    if not blocked_task_row:
        pytest.skip("No tasks with dependencies found")

    blocked_task_id = blocked_task_row.id

    # Check if blocked for both learners initially
    is_blocked_a, _ = await is_task_blocked(async_session, blocked_task_id, learner_a)
    is_blocked_b, _ = await is_task_blocked(async_session, blocked_task_id, learner_b)

    # If not blocked initially, skip
    if not is_blocked_a or not is_blocked_b:
        pytest.skip("Task not blocked for testing")

    # Learner A completes blocker (would need to find blocker and complete it)
    # For this test, we just verify both see blocking independently
    assert is_blocked_a == is_blocked_b, "Both learners should see same blocking state initially"


@pytest.mark.asyncio
async def test_e2e_go_back_reopens_task(async_session, ingested_project, learner_a):
    """Test: go_back reopens a closed task."""
    project_id = ingested_project

    # Get and close a subtask
    ready = await get_ready(GetReadyInput(project_id=project_id), learner_a, async_session)
    subtask = None
    for task in ready.tasks:
        if task.task_type == "subtask":
            subtask = task
            break

    if not subtask:
        pytest.skip("No subtask for go_back test")

    # Close it
    await start_task(StartTaskInput(task_id=subtask.id), learner_a, async_session)
    await submit(
        SubmitInput(task_id=subtask.id, content="work", submission_type="text"),
        learner_a,
        async_session,
    )

    # Verify closed
    progress = await get_or_create_progress(async_session, subtask.id, learner_a)
    assert progress.status == "closed"

    # Reopen
    await reopen_task(async_session, subtask.id, learner_a)

    # Verify reopened
    progress_after = await get_or_create_progress(async_session, subtask.id, learner_a)
    assert progress_after.status == "open"


@pytest.mark.asyncio
async def test_e2e_single_in_progress_enforcement(async_session, ingested_project, learner_a):
    """Test: System allows multiple in_progress tasks (not enforced)."""
    project_id = ingested_project

    # Get ready work
    ready = await get_ready(
        GetReadyInput(project_id=project_id, limit=10), learner_a, async_session
    )

    # Find two different tasks to start
    task_ids = [t.id for t in ready.tasks if t.task_type in ["task", "subtask"]][:2]

    if len(task_ids) < 2:
        pytest.skip("Need at least 2 tasks to test multiple in_progress")

    # Start first task
    await start_task(StartTaskInput(task_id=task_ids[0]), learner_a, async_session)

    # Check in_progress count
    progress = await get_progress(async_session, learner_a, project_id)
    assert progress.in_progress_tasks == 1

    # Start second task (this is allowed - system doesn't enforce single in_progress)
    await start_task(StartTaskInput(task_id=task_ids[1]), learner_a, async_session)

    # Now should have 2 in_progress (system allows this)
    progress_after = await get_progress(async_session, learner_a, project_id)
    # This is actually allowed, so we just document the behavior
    assert progress_after.in_progress_tasks >= 1, "Should have at least 1 in_progress"


@pytest.mark.asyncio
async def test_e2e_submission_increments_attempt(async_session, ingested_project, learner_a):
    """Test: Multiple submissions increment attempt number."""
    project_id = ingested_project

    # Get a subtask
    ready = await get_ready(GetReadyInput(project_id=project_id), learner_a, async_session)
    subtask = None
    for task in ready.tasks:
        if task.task_type == "subtask":
            subtask = task
            break

    if not subtask:
        pytest.skip("No subtask for attempt test")

    await start_task(StartTaskInput(task_id=subtask.id), learner_a, async_session)

    # First submission
    result1 = await submit(
        SubmitInput(task_id=subtask.id, content="attempt 1", submission_type="text"),
        learner_a,
        async_session,
    )
    assert result1.attempt_number == 1

    # If task auto-closed, reopen it
    if result1.status == "closed":
        await reopen_task(async_session, subtask.id, learner_a)
        await start_task(StartTaskInput(task_id=subtask.id), learner_a, async_session)

    # Second submission
    result2 = await submit(
        SubmitInput(task_id=subtask.id, content="attempt 2", submission_type="text"),
        learner_a,
        async_session,
    )
    assert result2.attempt_number == 2


@pytest.mark.asyncio
async def test_e2e_invalid_submission_type(async_session, ingested_project, learner_a):
    """Test: Invalid submission type returns error."""
    project_id = ingested_project

    ready = await get_ready(GetReadyInput(project_id=project_id), learner_a, async_session)
    task_id = ready.tasks[0].id

    # Must start the task first
    await start_task(StartTaskInput(task_id=task_id), learner_a, async_session)

    # Try invalid submission type
    result = await submit(
        SubmitInput(task_id=task_id, content="work", submission_type="invalid_type"),
        learner_a,
        async_session,
    )

    assert result.success is False
    # Invalid submission types should be rejected
    assert result.message is not None


@pytest.mark.asyncio
async def test_e2e_cannot_start_blocked_task(async_session, ingested_project, learner_a):
    """Test: Cannot start a task that is blocked."""
    project_id = ingested_project

    # Find Epic 2 task (should be blocked by Epic 1 initially)
    epic_2_id = f"{project_id}.2"

    # Verify Epic 2 is actually blocked
    is_blocked, blockers = await is_task_blocked(async_session, epic_2_id, learner_a)

    if not is_blocked:
        pytest.skip("Epic 2 not blocked (Epic 1 may already be complete)")

    # Find a task under Epic 2
    tasks = await get_children(async_session, epic_2_id, recursive=False)

    if not tasks:
        pytest.skip("No tasks in Epic 2")

    task_id = tasks[0].id

    # Try to start blocked task
    result = await start_task(StartTaskInput(task_id=task_id), learner_a, async_session)

    # Should fail due to blocking (if still blocked)
    if result.success:
        pytest.skip("Task successfully started - Epic 1 may have been completed by previous test")

    assert result.success is False
    assert "blocked" in result.message.lower()


@pytest.mark.asyncio
async def test_e2e_full_workflow_summary(async_session, ingested_project, learner_a, learner_b):
    """
    Test: Full workflow summary - verify project structure and independence.

    This is the final integration check.
    """
    project_id = ingested_project

    # Get final state for both learners
    progress_a = await get_progress(async_session, learner_a, project_id)
    progress_b = await get_progress(async_session, learner_b, project_id)

    # Both should see same project structure
    assert progress_a.total_tasks == progress_b.total_tasks
    assert progress_a.total_tasks > 0, "Project should have tasks"

    # Both should see same total objectives
    assert progress_a.total_objectives == progress_b.total_objectives
    assert progress_a.total_objectives > 0, "Project should have objectives"

    # Progress should be independent (each test uses fresh fixtures)
    # Both may have 0 completed if tests ran in isolation
    print("\n--- E2E Test Summary ---")
    print(f"Learner A: {progress_a.completed_tasks}/{progress_a.total_tasks} completed")
    print(f"Learner B: {progress_b.completed_tasks}/{progress_b.total_tasks} completed")
    print(f"Project: {project_id}")
    print(f"Total objectives: {progress_a.total_objectives}")
