"""
Progress tracking service.

Calculates learner progress metrics including task counts and objective achievement.
"""

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from ltt.models import BloomLevel, LearnerProgress, TaskModel

# ============================================================================
# Progress Calculation
# ============================================================================


async def get_progress(
    session: AsyncSession,
    learner_id: str,
    project_id: str,
) -> LearnerProgress:
    """
    Get comprehensive progress for a learner in a project.

    Per ADR-001: Task status is per-learner, so we query learner_task_progress,
    not tasks.status. Uses COALESCE to default to 'open' for tasks without
    a progress record yet (lazy initialization).

    Args:
        session: Database session
        learner_id: Learner ID
        project_id: Project ID

    Returns:
        Comprehensive progress metrics
    """
    # Verify project exists
    project_result = await session.execute(select(TaskModel).where(TaskModel.id == project_id))
    project = project_result.scalar_one_or_none()

    if not project:
        raise ValueError(f"Project {project_id} does not exist")

    # Task counts - join with learner_task_progress for per-learner status
    task_stats = await session.execute(
        text("""
        SELECT
            COUNT(*) as total,
            SUM(CASE WHEN COALESCE(ltp.status, 'open') = 'closed' THEN 1 ELSE 0 END) as completed,
            SUM(CASE WHEN COALESCE(ltp.status, 'open') = 'in_progress' THEN 1 ELSE 0 END) as in_progress,
            SUM(CASE WHEN COALESCE(ltp.status, 'open') = 'blocked' THEN 1 ELSE 0 END) as blocked
        FROM tasks t
        LEFT JOIN learner_task_progress ltp
            ON ltp.task_id = t.id AND ltp.learner_id = :learner_id
        WHERE t.project_id = :project_id
          AND t.task_type IN ('task', 'subtask')
    """),
        {"project_id": project_id, "learner_id": learner_id},
    )
    stats = task_stats.fetchone()

    # Objective counts
    # Achievement is based on passing validations
    obj_stats = await session.execute(
        text("""
        SELECT
            COUNT(DISTINCT lo.id) as total,
            COUNT(DISTINCT CASE WHEN v.passed = true THEN lo.id END) as achieved
        FROM learning_objectives lo
        JOIN tasks t ON lo.task_id = t.id
        LEFT JOIN submissions s
            ON s.task_id = t.id AND s.learner_id = :learner_id
        LEFT JOIN validations v
            ON v.submission_id = s.id AND v.passed = true
        WHERE t.project_id = :project_id
    """),
        {"project_id": project_id, "learner_id": learner_id},
    )
    obj_result = obj_stats.fetchone()

    total_tasks = stats.total or 0
    completed_tasks = stats.completed or 0

    # Calculate completion percentage
    completion_percentage = (completed_tasks / total_tasks * 100) if total_tasks > 0 else 0.0

    return LearnerProgress(
        learner_id=learner_id,
        project_id=project_id,
        total_tasks=total_tasks,
        completed_tasks=completed_tasks,
        in_progress_tasks=stats.in_progress or 0,
        blocked_tasks=stats.blocked or 0,
        completion_percentage=completion_percentage,
        total_objectives=obj_result.total or 0,
        objectives_achieved=obj_result.achieved or 0,
        total_time_spent_minutes=None,  # Future: calculate from timestamps
    )


async def get_bloom_distribution(
    session: AsyncSession,
    learner_id: str,
    project_id: str,
) -> dict[BloomLevel, dict[str, int]]:
    """
    Get objective distribution by Bloom level.

    Args:
        session: Database session
        learner_id: Learner ID
        project_id: Project ID

    Returns:
        Distribution by level, e.g.:
        {
            BloomLevel.REMEMBER: {"total": 5, "achieved": 5},
            BloomLevel.UNDERSTAND: {"total": 8, "achieved": 6},
            ...
        }
    """
    result = await session.execute(
        text("""
        SELECT
            lo.level,
            COUNT(DISTINCT lo.id) as total,
            COUNT(DISTINCT CASE WHEN v.passed = true THEN lo.id END) as achieved
        FROM learning_objectives lo
        JOIN tasks t ON lo.task_id = t.id
        LEFT JOIN submissions s
            ON s.task_id = t.id AND s.learner_id = :learner_id
        LEFT JOIN validations v
            ON v.submission_id = s.id AND v.passed = true
        WHERE t.project_id = :project_id
        GROUP BY lo.level
    """),
        {"project_id": project_id, "learner_id": learner_id},
    )

    distribution = {}
    for row in result.fetchall():
        if row.level:
            level = BloomLevel(row.level)
            distribution[level] = {"total": row.total or 0, "achieved": row.achieved or 0}

    return distribution
