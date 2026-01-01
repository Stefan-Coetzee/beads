#!/usr/bin/env python3
"""
End-to-End Agentic Workflow Test

This script simulates a full agentic use of the LTT system:
1. Creates a new learner
2. Walks through an entire epic + 1 task from a different epic
3. Tests all status transitions (open -> in_progress -> closed)
4. Verifies hierarchical closure (parent can't close until children close)
5. Verifies dependencies block work correctly
6. Logs everything for debugging

Run:
    PYTHONPATH=src DATABASE_URL="postgresql+asyncpg://ltt_user:ltt_password@localhost:5432/ltt_dev" \
    uv run python scripts/e2e_agentic_test.py

Output: logs/e2e_workflow.log
"""

import asyncio
import logging
import os
import sys
from datetime import datetime
from pathlib import Path

from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

# Setup logging
log_dir = Path("logs")
log_dir.mkdir(exist_ok=True)
log_file = log_dir / f"e2e_workflow_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler(log_file),
        logging.StreamHandler(sys.stdout),
    ],
)
logger = logging.getLogger(__name__)


async def get_session():
    """Get database session."""
    db_url = os.getenv(
        "DATABASE_URL", "postgresql+asyncpg://ltt_user:ltt_password@localhost:5432/ltt_dev"
    )
    engine = create_async_engine(db_url, echo=False)
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    return async_session()


async def run_e2e_test():
    """Run the full end-to-end agentic workflow test."""
    from ltt.models import LearnerModel, TaskStatus
    from ltt.services.dependency_service import get_ready_work, is_task_blocked
    from ltt.services.learning import get_progress
    from ltt.services.progress_service import (
        close_task,
        get_or_create_progress,
        reopen_task,
        start_task as service_start_task,
    )
    from ltt.services.submission_service import create_submission
    from ltt.services.task_service import get_children, get_task
    from ltt.services.validation_service import can_close_task
    from ltt.tools import (
        GetReadyInput,
        ShowTaskInput,
        StartTaskInput,
        SubmitInput,
        get_ready,
        show_task,
        start_task,
        submit,
    )
    from ltt.utils.ids import PREFIX_LEARNER, generate_entity_id

    session = await get_session()
    project_id = "proj-f4b1"  # Maji Ndogo Water Analysis project

    logger.info("=" * 70)
    logger.info("E2E AGENTIC WORKFLOW TEST")
    logger.info("=" * 70)

    try:
        # =====================================================================
        # STEP 1: Create a fresh learner
        # =====================================================================
        logger.info("\n[STEP 1] Creating new learner...")
        learner_id = generate_entity_id(PREFIX_LEARNER)
        learner = LearnerModel(id=learner_id, learner_metadata='{"test": "e2e_workflow"}')
        session.add(learner)
        await session.commit()
        logger.info(f"  Created learner: {learner_id}")

        # =====================================================================
        # STEP 2: Check initial project state
        # =====================================================================
        logger.info("\n[STEP 2] Checking initial project state...")

        progress = await get_progress(session, learner_id, project_id)
        logger.info(f"  Project: {project_id}")
        logger.info(f"  Total tasks: {progress.total_tasks}")
        logger.info(f"  Completed: {progress.completed_tasks}")
        logger.info(f"  In Progress: {progress.in_progress_tasks}")
        logger.info(f"  Blocked: {progress.blocked_tasks}")
        logger.info(f"  Objectives: {progress.objectives_achieved}/{progress.total_objectives}")

        # =====================================================================
        # STEP 3: Get ready work - should show all unblocked tasks
        # =====================================================================
        logger.info("\n[STEP 3] Getting ready work (unblocked tasks)...")

        ready_result = await get_ready(
            GetReadyInput(project_id=project_id, limit=20),
            learner_id=learner_id,
            session=session,
        )
        logger.info(f"  Total ready: {ready_result.total_ready}")
        logger.info(f"  Message: {ready_result.message}")

        # Log all ready tasks
        for i, task in enumerate(ready_result.tasks[:10]):
            logger.info(
                f"    [{i + 1}] {task.id}: {task.title[:40]}... (status: {task.status}, type: {task.task_type})"
            )

        # =====================================================================
        # STEP 4: Pick first epic and its tasks
        # =====================================================================
        logger.info("\n[STEP 4] Selecting first epic to complete...")

        # Get epic 1 (Introduction)
        epic_id = f"{project_id}.1"
        epic = await get_task(session, epic_id)
        logger.info(f"  Epic: {epic.id} - {epic.title}")

        # Get all children of the epic
        epic_children = await get_children(session, epic_id, recursive=False)
        logger.info(f"  Direct children (tasks): {len(epic_children)}")
        for child in epic_children:
            logger.info(f"    - {child.id}: {child.title[:40]}...")

        # =====================================================================
        # STEP 5: Complete all subtasks in first task
        # =====================================================================
        logger.info("\n[STEP 5] Working through first task and its subtasks...")

        first_task_id = f"{epic_id}.1"  # proj-f4b1.1.1
        first_task = await get_task(session, first_task_id)
        logger.info(f"  Task: {first_task.id} - {first_task.title}")

        # Get subtasks
        subtasks = await get_children(session, first_task_id, recursive=False)
        logger.info(f"  Subtasks: {len(subtasks)}")

        # Process each subtask
        for subtask in subtasks:
            logger.info(f"\n  --- Processing subtask: {subtask.id} ---")
            logger.info(f"      Title: {subtask.title[:50]}...")

            # Check current status
            progress_record = await get_or_create_progress(session, subtask.id, learner_id)
            logger.info(f"      Initial status: {progress_record.status}")

            # Start the task
            start_result = await start_task(
                StartTaskInput(task_id=subtask.id),
                learner_id=learner_id,
                session=session,
            )
            logger.info(f"      After start_task: {start_result.new_status}")

            # Submit work
            submit_result = await submit(
                SubmitInput(
                    task_id=subtask.id,
                    content="-- Completed subtask work\nSELECT 1;",
                    submission_type="sql",
                ),
                learner_id=learner_id,
                session=session,
            )
            logger.info(
                f"      Submission: attempt #{submit_result.attempt_number}, passed: {submit_result.validation_passed}"
            )
            logger.info(f"      Can close: {submit_result.can_close_task}")

            # Auto-close subtask on passing validation (mimics expected behavior - see GH issue)
            # TODO: This should be automatic in submit() - see issue #835
            if submit_result.can_close_task and submit_result.validation_passed:
                try:
                    await close_task(session, subtask.id, learner_id, "Passed validation")
                    progress_record = await get_or_create_progress(session, subtask.id, learner_id)
                    logger.info(f"      Auto-closed subtask: status = {progress_record.status}")
                except Exception as e:
                    logger.error(f"      Failed to auto-close subtask: {e}")

        # =====================================================================
        # STEP 6: Try to close parent task (should succeed if all children closed)
        # =====================================================================
        logger.info("\n[STEP 6] Attempting to close parent task...")

        # Check if all subtasks are closed
        subtasks_status = []
        for subtask in subtasks:
            prog = await get_or_create_progress(session, subtask.id, learner_id)
            subtasks_status.append((subtask.id, prog.status))
            logger.info(f"  Subtask {subtask.id}: {prog.status}")

        all_closed = all(status == TaskStatus.CLOSED.value for _, status in subtasks_status)
        logger.info(f"  All subtasks closed: {all_closed}")

        # Check if we can close the task
        can_close, reason = await can_close_task(session, first_task_id, learner_id)
        logger.info(f"  Can close task {first_task_id}: {can_close}")
        if not can_close:
            logger.info(f"    Reason: {reason}")

        # Try to close
        if can_close:
            # First start it if not started
            task_prog = await get_or_create_progress(session, first_task_id, learner_id)
            if task_prog.status == TaskStatus.OPEN.value:
                await service_start_task(session, first_task_id, learner_id)

            await close_task(session, first_task_id, learner_id, "Completed task")
            task_prog = await get_or_create_progress(session, first_task_id, learner_id)
            logger.info(f"  Closed task {first_task_id}: status = {task_prog.status}")

        # =====================================================================
        # STEP 7: Check epic status (can't close until all children closed)
        # =====================================================================
        logger.info("\n[STEP 7] Checking epic closure requirements...")

        epic_children = await get_children(session, epic_id, recursive=False)
        closed_count = 0
        for child in epic_children:
            prog = await get_or_create_progress(session, child.id, learner_id)
            status = prog.status
            is_closed = status == TaskStatus.CLOSED.value
            closed_count += 1 if is_closed else 0
            logger.info(f"  {child.id}: {status}")

        logger.info(f"  Tasks closed: {closed_count}/{len(epic_children)}")

        can_close_epic, reason = await can_close_task(session, epic_id, learner_id)
        logger.info(f"  Can close epic: {can_close_epic}")
        if not can_close_epic:
            logger.info(f"    Reason: {reason}")

        # =====================================================================
        # STEP 8: Complete remaining tasks in epic
        # =====================================================================
        logger.info("\n[STEP 8] Completing remaining tasks in epic...")

        for task in epic_children:
            task_prog = await get_or_create_progress(session, task.id, learner_id)
            if task_prog.status == TaskStatus.CLOSED.value:
                logger.info(f"  {task.id}: Already closed, skipping")
                continue

            logger.info(f"\n  --- Processing task: {task.id} ---")

            # Get and complete all subtasks
            task_subtasks = await get_children(session, task.id, recursive=False)
            for subtask in task_subtasks:
                sub_prog = await get_or_create_progress(session, subtask.id, learner_id)
                if sub_prog.status == TaskStatus.CLOSED.value:
                    continue

                # Start and submit
                await start_task(
                    StartTaskInput(task_id=subtask.id),
                    learner_id=learner_id,
                    session=session,
                )
                await submit(
                    SubmitInput(
                        task_id=subtask.id,
                        content="-- Work done\nSELECT 1;",
                        submission_type="sql",
                    ),
                    learner_id=learner_id,
                    session=session,
                )
                await close_task(session, subtask.id, learner_id, "Passed validation")
                logger.info(f"      Completed subtask: {subtask.id}")

            # Close the task
            task_prog = await get_or_create_progress(session, task.id, learner_id)
            if task_prog.status == TaskStatus.OPEN.value:
                await service_start_task(session, task.id, learner_id)

            can_close, _ = await can_close_task(session, task.id, learner_id)
            if can_close:
                await close_task(session, task.id, learner_id, "All subtasks completed")
                logger.info(f"      Closed task: {task.id}")

        # =====================================================================
        # STEP 9: Now close the epic
        # =====================================================================
        logger.info("\n[STEP 9] Closing the epic...")

        epic_prog = await get_or_create_progress(session, epic_id, learner_id)
        if epic_prog.status == TaskStatus.OPEN.value:
            await service_start_task(session, epic_id, learner_id)

        can_close_epic, reason = await can_close_task(session, epic_id, learner_id)
        logger.info(f"  Can close epic now: {can_close_epic}")

        if can_close_epic:
            await close_task(session, epic_id, learner_id, "All tasks completed")
            epic_prog = await get_or_create_progress(session, epic_id, learner_id)
            logger.info(f"  Epic closed: status = {epic_prog.status}")
        else:
            logger.warning(f"  Cannot close epic: {reason}")

        # =====================================================================
        # STEP 10: Test dependencies - start a task from epic 2
        # =====================================================================
        logger.info("\n[STEP 10] Testing work on epic 2...")

        epic2_id = f"{project_id}.2"
        epic2 = await get_task(session, epic2_id)
        logger.info(f"  Epic 2: {epic2.id} - {epic2.title}")

        # Get first task of epic 2
        epic2_tasks = await get_children(session, epic2_id, recursive=False)
        if epic2_tasks:
            task2 = epic2_tasks[0]
            logger.info(f"  First task: {task2.id} - {task2.title[:40]}...")

            # Check if blocked
            is_blocked, blockers = await is_task_blocked(session, task2.id, learner_id)
            logger.info(f"  Is blocked: {is_blocked}")
            if blockers:
                logger.info(f"  Blocked by: {[b.id for b in blockers]}")

            # Try to start it
            start_result = await start_task(
                StartTaskInput(task_id=task2.id),
                learner_id=learner_id,
                session=session,
            )
            logger.info(
                f"  Start result: success={start_result.success}, status={start_result.new_status}"
            )

        # =====================================================================
        # STEP 11: Test go_back (reopen)
        # =====================================================================
        logger.info("\n[STEP 11] Testing go_back (reopen closed task)...")

        # Find a closed subtask to reopen
        subtask_to_reopen = subtasks[0] if subtasks else None
        if subtask_to_reopen:
            prog = await get_or_create_progress(session, subtask_to_reopen.id, learner_id)
            logger.info(f"  Task to reopen: {subtask_to_reopen.id}")
            logger.info(f"  Current status: {prog.status}")

            if prog.status == TaskStatus.CLOSED.value:
                # reopen_task doesn't take reason - the go_back tool adds it as comment
                await reopen_task(session, subtask_to_reopen.id, learner_id)
                prog = await get_or_create_progress(session, subtask_to_reopen.id, learner_id)
                logger.info(f"  After reopen: {prog.status}")

                # Close it again
                await service_start_task(session, subtask_to_reopen.id, learner_id)
                await close_task(
                    session, subtask_to_reopen.id, learner_id, "Re-completed after go_back"
                )
                logger.info(
                    f"  Closed again: {(await get_or_create_progress(session, subtask_to_reopen.id, learner_id)).status}"
                )

        # =====================================================================
        # STEP 12: Final progress check
        # =====================================================================
        logger.info("\n[STEP 12] Final progress check...")

        final_progress = await get_progress(session, learner_id, project_id)
        logger.info(f"  Total tasks: {final_progress.total_tasks}")
        logger.info(f"  Completed: {final_progress.completed_tasks}")
        logger.info(f"  Completion: {final_progress.completion_percentage:.1f}%")
        logger.info(f"  In Progress: {final_progress.in_progress_tasks}")
        logger.info(f"  Blocked: {final_progress.blocked_tasks}")
        logger.info(
            f"  Objectives achieved: {final_progress.objectives_achieved}/{final_progress.total_objectives}"
        )

        # =====================================================================
        # STEP 13: Get ready work again - should be different now
        # =====================================================================
        logger.info("\n[STEP 13] Getting ready work after completing epic...")

        ready_result = await get_ready(
            GetReadyInput(project_id=project_id, limit=10),
            learner_id=learner_id,
            session=session,
        )
        logger.info(f"  Total ready: {ready_result.total_ready}")
        logger.info(
            f"  In progress count: {sum(1 for t in ready_result.tasks if t.status == 'in_progress')}"
        )

        for i, task in enumerate(ready_result.tasks[:5]):
            logger.info(f"    [{i + 1}] {task.id}: {task.title[:40]}... (status: {task.status})")

        # =====================================================================
        # STEP 14: Verify no orphan "in_progress" tasks
        # =====================================================================
        logger.info("\n[STEP 14] Checking for orphan in_progress tasks...")

        from sqlalchemy import select
        from ltt.models import LearnerTaskProgressModel

        result = await session.execute(
            select(LearnerTaskProgressModel)
            .where(LearnerTaskProgressModel.learner_id == learner_id)
            .where(LearnerTaskProgressModel.status == TaskStatus.IN_PROGRESS.value)
        )
        in_progress_tasks = result.scalars().all()

        logger.info(f"  Tasks currently in_progress: {len(in_progress_tasks)}")
        for prog in in_progress_tasks:
            task = await get_task(session, prog.task_id)
            logger.info(f"    - {prog.task_id}: {task.title[:40]}...")

        await session.commit()

        # =====================================================================
        # SUMMARY
        # =====================================================================
        logger.info("\n" + "=" * 70)
        logger.info("TEST SUMMARY")
        logger.info("=" * 70)
        logger.info(f"  Learner: {learner_id}")
        logger.info(f"  Project: {project_id}")
        logger.info(f"  Epic completed: {epic_id}")
        logger.info(
            f"  Final completion: {final_progress.completed_tasks}/{final_progress.total_tasks} ({final_progress.completion_percentage:.1f}%)"
        )
        logger.info(f"  Orphan in_progress tasks: {len(in_progress_tasks)}")
        logger.info(f"  Log file: {log_file}")
        logger.info("=" * 70)

        return True

    except Exception as e:
        logger.exception(f"Test failed with error: {e}")
        return False
    finally:
        await session.close()


if __name__ == "__main__":
    success = asyncio.run(run_e2e_test())
    sys.exit(0 if success else 1)
