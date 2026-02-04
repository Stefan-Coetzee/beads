"""
Verify that epic-level blocking propagates to child tasks in the real project.

This script tests the fix for the issue where tasks under a blocked epic
(Epic 2) were showing as ready work even though Epic 2 was blocked by Epic 1.
"""

import asyncio
import os

from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

from ltt.services.dependency_service import get_ready_work


async def verify_epic_blocking():
    """Verify epic blocking in the real water analysis project."""
    # Connect to database
    db_url = os.getenv(
        "DATABASE_URL", "postgresql+asyncpg://ltt_user:ltt_password@localhost:5432/ltt_dev"
    )
    engine = create_async_engine(db_url, echo=False)
    async_session_maker = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with async_session_maker() as session:
        # Known project and learner from e2e test
        project_id = "proj-096c"  # Water Analysis project
        learner_id = "learner-test-user"

        # Get ready work
        ready = await get_ready_work(session, project_id, learner_id, limit=50)

        print(f"\n{'=' * 80}")
        print("Verifying Epic Blocking Propagation")
        print(f"{'=' * 80}")
        print(f"Project: {project_id}")
        print(f"Learner: {learner_id}")
        print(f"\nReady tasks ({len(ready)} total):\n")

        # Group by epic
        epic_groups = {}
        for task in ready:
            # Extract epic from hierarchical ID (e.g., proj-096c.1.1 → Epic 1)
            parts = task.id.split(".")
            if len(parts) == 1:
                epic = "Project"
            elif len(parts) >= 2:
                epic_num = parts[1]
                epic = f"Epic {epic_num}"
            else:
                epic = "Unknown"

            if epic not in epic_groups:
                epic_groups[epic] = []
            epic_groups[epic].append(task)

        for epic, tasks in sorted(epic_groups.items()):
            print(f"\n{epic}:")
            for task in tasks:
                print(f"  - {task.id}: {task.title} ({task.task_type})")

        # Validate expectations
        print(f"\n{'=' * 80}")
        print("Validation:")
        print(f"{'=' * 80}")

        epic_1_tasks = [t for t in ready if t.id.startswith("proj-096c.1.")]
        epic_2_tasks = [t for t in ready if t.id.startswith("proj-096c.2.")]

        print(f"\nEpic 1 tasks in ready work: {len(epic_1_tasks)}")
        print(f"Epic 2 tasks in ready work: {len(epic_2_tasks)}")

        if epic_2_tasks:
            print("\n❌ FAIL: Epic 2 tasks should NOT be in ready work!")
            print("Epic 2 is blocked by Epic 1, so all its children should be blocked.")
            print("\nEpic 2 tasks found:")
            for task in epic_2_tasks:
                print(f"  - {task.id}: {task.title}")
            return False
        else:
            print("\n✅ PASS: Epic 2 tasks correctly excluded from ready work!")
            print("Epic blocking is propagating to child tasks as expected.")
            return True


if __name__ == "__main__":
    success = asyncio.run(verify_epic_blocking())
    exit(0 if success else 1)
