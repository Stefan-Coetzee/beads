# Learning & Progress Module

> Learning objectives, progress tracking, and hierarchical summarization.
>
> **Architecture**: This module implements the Two-Layer Architecture defined in [ADR-001](./adr/001-learner-scoped-task-progress.md). Task status and progress are per-learner, tracked in the `learner_task_progress` table, not in the `tasks` table.

## Overview

This module manages the pedagogical layer:
- Attaching learning objectives to tasks (Bloom's taxonomy)
- Tracking learner progress through objectives (derived from validation results)
- Generating hierarchical summaries of completed work (stored as StatusSummary)
- Managing content references

**Note**: Objective achievement is derived from successful validation of task submissions, not tracked separately. When a learner passes validation for a task, the associated objectives are considered achieved.

---

## 1. Learning Objectives

### Bloom's Taxonomy Levels

```python
class BloomLevel(str, Enum):
    """
    Bloom's Taxonomy cognitive levels (revised).

    From lowest to highest:
    1. REMEMBER - Recall facts and basic concepts
    2. UNDERSTAND - Explain ideas or concepts
    3. APPLY - Use information in new situations
    4. ANALYZE - Draw connections among ideas
    5. EVALUATE - Justify a decision or course of action
    6. CREATE - Produce new or original work
    """
    REMEMBER = "remember"
    UNDERSTAND = "understand"
    APPLY = "apply"
    ANALYZE = "analyze"
    EVALUATE = "evaluate"
    CREATE = "create"


# Ordered for progression
BLOOM_ORDER = [
    BloomLevel.REMEMBER,
    BloomLevel.UNDERSTAND,
    BloomLevel.APPLY,
    BloomLevel.ANALYZE,
    BloomLevel.EVALUATE,
    BloomLevel.CREATE,
]
```

### Service Interface

```python
class LearningObjectiveService:
    """
    Service for managing learning objectives.
    """

    def __init__(self, db_session, event_service: "EventService"):
        self.db = db_session
        self.events = event_service

    async def attach_objective(
        self,
        task_id: str,
        description: str,
        level: BloomLevel,
        taxonomy: str = "bloom"
    ) -> LearningObjective:
        """
        Attach a learning objective to a task.

        Args:
            task_id: Task to attach to
            description: What the learner should achieve
            level: Bloom's taxonomy level
            taxonomy: Which taxonomy (default: bloom)
        """
        ...

    async def get_objectives(
        self,
        task_id: str
    ) -> List[LearningObjective]:
        """Get all objectives for a task."""
        ...

    async def get_objectives_for_hierarchy(
        self,
        task_id: str,
        include_ancestors: bool = True,
        include_descendants: bool = False
    ) -> List[LearningObjective]:
        """
        Get objectives for a task and its hierarchy.

        Useful for loading full context:
        - Ancestor objectives: higher-level goals
        - Descendant objectives: breakdown of this task
        """
        ...

    async def remove_objective(
        self,
        objective_id: str,
        actor: str
    ) -> None:
        """Remove a learning objective."""
        ...
```

---

## 2. Progress Tracking

### Learner Progress Model

```python
@dataclass
class LearnerProgress:
    """
    Progress summary for a learner in a project.
    """
    learner_id: str
    project_id: str

    # Task counts
    total_tasks: int
    completed_tasks: int
    in_progress_tasks: int
    blocked_tasks: int

    # Computed
    @property
    def completion_percentage(self) -> float:
        if self.total_tasks == 0:
            return 0.0
        return (self.completed_tasks / self.total_tasks) * 100

    # Objective tracking
    total_objectives: int
    objectives_achieved: int

    # By Bloom level
    objectives_by_level: Dict[BloomLevel, int]
    achieved_by_level: Dict[BloomLevel, int]

    # Time tracking (optional)
    total_time_spent_minutes: Optional[int] = None
    average_attempts_per_task: Optional[float] = None


class ProgressService:
    """
    Service for tracking learner progress.
    """

    async def get_progress(
        self,
        learner_id: str,
        project_id: str
    ) -> LearnerProgress:
        """
        Get comprehensive progress for a learner in a project.
        """
        ...

    async def get_achieved_objectives(
        self,
        learner_id: str,
        project_id: str
    ) -> List[LearningObjective]:
        """Get all objectives achieved by learner."""
        ...

    async def get_bloom_distribution(
        self,
        learner_id: str,
        project_id: str
    ) -> Dict[BloomLevel, Dict[str, int]]:
        """
        Get objective distribution by Bloom level.

        Returns:
            {
                "remember": {"total": 5, "achieved": 5},
                "understand": {"total": 8, "achieved": 6},
                ...
            }
        """
        ...
```

### Progress Calculation

```python
async def get_progress(
    db,
    learner_id: str,
    project_id: str
) -> LearnerProgress:
    """
    Calculate comprehensive progress for a learner.

    Per ADR-001: Task status is per-learner, so we query learner_task_progress,
    not tasks.status. Uses COALESCE to default to 'open' for tasks without
    a progress record yet (lazy initialization).
    """

    # Task counts - join with learner_task_progress for per-learner status
    task_stats = await db.execute(text("""
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
    """), {"project_id": project_id, "learner_id": learner_id})
    stats = task_stats.fetchone()

    # Objective counts
    # Achievement is based on passing validations (see get_achieved_objectives_for_learner)
    obj_stats = await db.execute(text("""
        SELECT
            lo.level,
            COUNT(*) as total,
            SUM(CASE WHEN v.id IS NOT NULL THEN 1 ELSE 0 END) as achieved
        FROM learning_objectives lo
        JOIN tasks t ON lo.task_id = t.id
        LEFT JOIN submissions s
            ON s.task_id = t.id AND s.learner_id = :learner_id
        LEFT JOIN validations v
            ON v.submission_id = s.id AND v.passed = true
        WHERE t.project_id = :project_id
        GROUP BY lo.level
    """), {"project_id": project_id, "learner_id": learner_id})

    objectives_by_level = {}
    achieved_by_level = {}
    total_objectives = 0
    objectives_achieved = 0

    for row in obj_stats.fetchall():
        level = BloomLevel(row.level) if row.level else None
        if level:
            objectives_by_level[level] = row.total
            achieved_by_level[level] = row.achieved
            total_objectives += row.total
            objectives_achieved += row.achieved

    return LearnerProgress(
        learner_id=learner_id,
        project_id=project_id,
        total_tasks=stats.total or 0,
        completed_tasks=stats.completed or 0,
        in_progress_tasks=stats.in_progress or 0,
        blocked_tasks=stats.blocked or 0,
        total_objectives=total_objectives,
        objectives_achieved=objectives_achieved,
        objectives_by_level=objectives_by_level,
        achieved_by_level=achieved_by_level,
    )
```

---

## 3. Hierarchical Summarization

When modules/epics complete, generate summaries to reduce cognitive load.

### Summarization Service

```python
class SummarizationService:
    """
    Service for generating hierarchical summaries.

    Inspired by beads compaction but adapted for learning context.
    Summaries are stored as versioned StatusSummary records.
    """

    async def summarize_completed(
        self,
        task_id: str,
        learner_id: str
    ) -> StatusSummary:
        """
        Generate a summary for any completed task (subtask, task, epic, or project).

        Works for any task_type:
        - subtask: Summary of the specific work done
        - task: Aggregates subtask summaries + task-level details
        - epic: Aggregates task summaries + epic-level objectives
        - project: Full project summary for portfolio/review

        The summary is stored as a StatusSummary with incremented version.

        Returns:
            StatusSummary with the generated summary text
        """
        ...

    async def get_summaries(
        self,
        task_id: str,
        learner_id: str
    ) -> List[StatusSummary]:
        """
        Get all status summaries for a task/learner, ordered by version.

        Returns the version history of summaries for this task.
        """
        ...

    async def get_latest_summary(
        self,
        task_id: str,
        learner_id: str
    ) -> Optional[StatusSummary]:
        """
        Get the most recent summary for a task/learner.
        """
        ...
```

### Summary Generation

```python
async def summarize_completed(
    db,
    task_id: str,
    learner_id: str
) -> StatusSummary:
    """
    Generate a summary for any completed task (works for all task_types).

    The behavior adapts based on task_type:
    - subtask: Direct summary of the work
    - task/epic/project: Aggregates child summaries

    Per ADR-001: Task completion is per-learner, so we check
    learner_task_progress.status, not task.status.
    """
    # 1. Get the task and learner's progress
    task = await db.get(TaskModel, task_id)
    if not task:
        raise NotFoundError(f"Task '{task_id}' not found")

    # Check learner's progress status (not task.status)
    progress_result = await db.execute(
        select(LearnerTaskProgressModel)
        .where(
            LearnerTaskProgressModel.task_id == task_id,
            LearnerTaskProgressModel.learner_id == learner_id
        )
    )
    progress = progress_result.scalar_one_or_none()

    # Task must be closed for THIS learner
    if not progress or progress.status != TaskStatus.CLOSED.value:
        raise InvalidStateError(
            f"Task '{task_id}' is not closed for learner '{learner_id}'"
        )

    # 2. Get descendants (if any)
    descendants = await get_descendants(db, task_id)

    # 3. Get objectives
    objectives = await get_objectives_for_hierarchy(db, task_id, include_descendants=True)

    # 4. Get submission history for this learner
    submissions = []
    all_task_ids = [task_id] + [d.id for d in descendants]
    for tid in all_task_ids:
        task_subs = await get_submissions(db, tid, learner_id)
        submissions.extend(task_subs)

    # 5. Get child summaries if this is a parent task
    child_summaries = []
    if descendants:
        for child in get_direct_children(descendants, task_id):
            child_summary = await get_latest_summary(db, child.id, learner_id)
            if child_summary:
                child_summaries.append(child_summary)

    # 6. Build summary data
    summary_data = {
        "task_title": task.title,
        "task_type": task.task_type,
        "task_description": task.description,
        "total_subtasks": len(descendants),
        "total_objectives": len(objectives),
        "total_attempts": sum(s.attempt_number for s in submissions),
        "tasks_with_retries": len([s for s in submissions if s.attempt_number > 1]),
        "objectives_by_level": group_by_bloom_level(objectives),
        "child_summaries": child_summaries,
    }

    # 7. Generate summary text
    # This would use AI in production; for now, template-based
    summary_text = generate_summary_text(summary_data)

    # 8. Store as StatusSummary with incremented version
    latest = await get_latest_summary(db, task_id, learner_id)
    new_version = (latest.version + 1) if latest else 1

    status_summary = StatusSummaryModel(
        id=generate_entity_id("sum"),
        task_id=task_id,
        learner_id=learner_id,
        summary=summary_text,
        version=new_version,
    )
    db.add(status_summary)
    await db.commit()

    return StatusSummary.model_validate(status_summary)


def generate_summary_text(data: dict) -> str:
    """
    Generate summary text from structured data.

    In production, this would use an LLM.
    For now, template-based.
    """
    task_type = data.get('task_type', 'task')

    parts = [
        f"## {data['task_title']}",
        "",
    ]

    if data['total_subtasks'] > 0:
        parts.append(
            f"Completed {data['total_subtasks']} subtasks with "
            f"{data['total_objectives']} objectives."
        )
    else:
        parts.append(f"Completed with {data['total_objectives']} objectives.")

    parts.append("")

    # Add objective breakdown
    if data.get('objectives_by_level'):
        parts.append("### Skills Demonstrated")
        for level, objs in data['objectives_by_level'].items():
            parts.append(f"- **{level.value.title()}**: {len(objs)} objectives")

    # Note struggles if any
    if data.get('tasks_with_retries', 0) > 0:
        parts.append("")
        parts.append(f"*Note: {data['tasks_with_retries']} tasks required multiple attempts.*")

    return "\n".join(parts)
```

---

## 4. Content Management

```python
class ContentService:
    """
    Service for managing learning content.
    """

    async def create_content(
        self,
        content_type: ContentType,
        body: str,
        metadata: Optional[dict] = None
    ) -> Content:
        """Create a content item."""
        ...

    async def get_content(
        self,
        content_id: str
    ) -> Content:
        """Get content by ID."""
        ...

    async def attach_content_to_task(
        self,
        content_id: str,
        task_id: str
    ) -> None:
        """
        Attach content to a task.

        Adds content_id to task's content_refs array.
        """
        ...

    async def get_task_content(
        self,
        task_id: str
    ) -> List[Content]:
        """
        Get all content for a task.

        Returns both inline content and referenced content.
        """
        ...

    async def get_relevant_content(
        self,
        task_id: str,
        learner_id: str
    ) -> List[Content]:
        """
        Get content relevant for a learner on a task.

        Future: personalize based on learner's skill gaps.
        """
        ...
```

---

## 5. Objective Achievement Tracking

**Note**: Objective achievement is derived from validation results, not stored separately.

A learner is considered to have achieved an objective when:
1. The objective is attached to a task
2. The learner has a passing validation for that task

This is computed at query time rather than stored, ensuring consistency with the actual validation state.

```python
async def get_achieved_objectives_for_learner(
    db,
    learner_id: str,
    project_id: str
) -> List[LearningObjective]:
    """
    Get all objectives achieved by a learner in a project.

    Achievement is derived from passing validations.
    """
    result = await db.execute(text("""
        SELECT DISTINCT lo.*
        FROM learning_objectives lo
        JOIN tasks t ON lo.task_id = t.id
        JOIN submissions s ON s.task_id = t.id AND s.learner_id = :learner_id
        JOIN validations v ON v.submission_id = s.id AND v.passed = true
        WHERE t.project_id = :project_id
    """), {"learner_id": learner_id, "project_id": project_id})

    return [LearningObjective.model_validate(row) for row in result.fetchall()]
```

---

## 6. Status Summary Storage

Summaries are stored using the `status_summaries` table (defined in 01-data-models.md):

```sql
CREATE TABLE status_summaries (
    id VARCHAR PRIMARY KEY,
    task_id VARCHAR REFERENCES tasks(id),
    learner_id VARCHAR REFERENCES learners(id),
    summary TEXT NOT NULL,
    version INTEGER DEFAULT 1,
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_status_summaries_task_learner ON status_summaries(task_id, learner_id);
```

Each time `summarize_completed()` is called, a new version is created, preserving history.

---

## 7. File Structure

```
src/ltt/services/
├── learning/
│   ├── __init__.py
│   ├── objectives.py      # LearningObjectiveService
│   ├── progress.py        # ProgressService
│   ├── summarization.py   # SummarizationService
│   └── content.py         # ContentService
```

---

## 8. Testing Requirements

```python
class TestLearningObjectiveService:
    async def test_attach_objective_to_task(self):
        ...

    async def test_get_objectives_includes_ancestors(self):
        ...


class TestProgressService:
    async def test_progress_calculation(self):
        """Progress correctly counts tasks and objectives."""
        ...

    async def test_bloom_distribution(self):
        """Objectives correctly grouped by Bloom level."""
        ...


class TestSummarizationService:
    async def test_epic_summary_aggregates_children(self):
        ...

    async def test_summary_notes_retries(self):
        """Summary mentions tasks that needed multiple attempts."""
        ...
```
