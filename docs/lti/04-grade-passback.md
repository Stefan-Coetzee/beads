# AGS Grade Passback

> How LTT sends grades to Open edX when learners complete tasks.

---

## Overview

LTI Advantage includes the **Assignments and Grades Service (AGS)**. This lets our tool send scores back to the Open edX gradebook automatically when learners progress through tasks.

```
Learner submits work → Validation passes → Task closes
                                              ↓
                            Calculate project progress (15/42 = 35.7%)
                                              ↓
                            AGS: PUT score to Open edX gradebook
                                              ↓
                            Open edX shows 35.7% in gradebook
```

---

## Grade Passback Modes

Open edX supports two AGS modes:

### Declarative (Simple)

- **One grade per LTI component** in the course
- Tool sends a single score that maps to one gradebook entry
- Configure in Studio: "Allow tools to submit grades only"

### Programmatic (Advanced)

- **Multiple line items per LTI component**
- Tool can create, manage, and delete gradebook columns
- Configure in Studio: "Allow tools to manage and submit grades"

**Recommendation**: Start with **declarative** mode. One LTI component = one project = one grade in the gradebook (project completion percentage).

---

## When to Send Grades

### Option A: On Every Task Completion (Recommended)

Send an updated score every time any task closes. This gives learners continuous feedback in the gradebook.

```python
# In the submit tool (ltt/tools/progress.py), after successful validation:
async def submit(input: SubmitInput, learner_id: str, session) -> SubmitResult:
    # ... existing submission and validation logic ...

    if validation.passed:
        # Calculate overall project progress
        progress = await get_progress(session, learner_id, project_id)

        # Send grade to LMS if this is an LTI session
        await maybe_send_grade(
            learner_id=learner_id,
            project_id=project_id,
            completed=progress.completed_tasks,
            total=progress.total_tasks,
        )
```

### Option B: On Project Completion Only

Send a single 100% grade when the entire project closes. Simpler but less useful for intermediate feedback.

### Option C: Milestone-Based

Send grades at specific points (e.g., when epics complete). Good for courses where each epic maps to a graded assignment.

---

## Implementation

### `grades.py`

```python
"""
AGS grade passback service.

Sends learner progress scores to the LMS via LTI AGS.
"""

from __future__ import annotations

import datetime
import logging
from typing import Optional

from pylti1p3.grade import Grade
from pylti1p3.lineitem import LineItem

from .adapter import FastAPIMessageLaunch, FastAPIRequest
from .config import get_tool_config
from .storage import RedisLaunchDataStorage

logger = logging.getLogger(__name__)


def send_grade(
    launch_id: str,
    storage: RedisLaunchDataStorage,
    learner_sub: str,
    score: float,
    max_score: float,
    activity_progress: str = "Completed",
    grading_progress: str = "FullyGraded",
    comment: Optional[str] = None,
) -> bool:
    """
    Send a grade to the LMS via AGS.

    Args:
        launch_id: The LTI launch ID (from Redis cache)
        storage: Redis launch data storage
        learner_sub: The LTI sub claim (platform user ID)
        score: Points earned (e.g., 15)
        max_score: Points possible (e.g., 42)
        activity_progress: One of: Initialized, Started, InProgress, Submitted, Completed
        grading_progress: One of: FullyGraded, Pending, PendingManual, Failed, NotReady
        comment: Optional comment visible to learner in gradebook

    Returns:
        True if grade was sent successfully, False otherwise.
    """
    tool_conf = get_tool_config()

    # Reconstruct message launch from cache
    dummy_request = FastAPIRequest(
        cookies={}, session={}, request_data={}, request_is_secure=True
    )

    try:
        message_launch = FastAPIMessageLaunch.from_cache(
            launch_id, dummy_request, tool_conf,
            launch_data_storage=storage,
        )
    except Exception as e:
        logger.warning(f"Failed to restore LTI launch {launch_id}: {e}")
        return False

    if not message_launch.has_ags():
        logger.info(f"AGS not available for launch {launch_id}")
        return False

    ags = message_launch.get_ags()

    # Get resource_link_id from cached launch data
    launch_data = message_launch.get_launch_data()
    resource_link = launch_data.get(
        "https://purl.imsglobal.org/spec/lti/claim/resource_link", {}
    )

    # Build grade
    grade = Grade()
    grade.set_score_given(score)
    grade.set_score_maximum(max_score)
    grade.set_timestamp(datetime.datetime.utcnow().isoformat() + "Z")
    grade.set_activity_progress(activity_progress)
    grade.set_grading_progress(grading_progress)
    grade.set_user_id(learner_sub)

    if comment:
        grade.set_comment(comment)

    # Build line item (describes the gradebook column)
    line_item = LineItem()
    line_item.set_tag("ltt-progress")
    line_item.set_score_maximum(max_score)
    line_item.set_label("Project Progress")
    if resource_link.get("id"):
        line_item.set_resource_id(resource_link["id"])

    try:
        ags.put_grade(grade, line_item)
        logger.info(
            f"Grade sent: {score}/{max_score} for sub={learner_sub} "
            f"launch={launch_id}"
        )
        return True
    except Exception as e:
        logger.error(f"AGS grade passback failed: {e}")
        return False


async def maybe_send_grade(
    learner_id: str,
    project_id: str,
    completed: int,
    total: int,
    launch_id: Optional[str] = None,
) -> bool:
    """
    Send grade if this learner has an active LTI session.

    Called after task completion. Looks up the learner's active
    launch_id and sends the grade. No-op for standalone sessions.

    Args:
        learner_id: Internal LTT learner ID
        project_id: LTT project ID
        completed: Number of completed tasks
        total: Total number of tasks
        launch_id: Optional explicit launch_id (if known)

    Returns:
        True if grade was sent, False if skipped or failed.
    """
    if not launch_id:
        # Look up active launch_id for this learner
        # (stored in Redis during launch)
        launch_id = _get_active_launch(learner_id, project_id)

    if not launch_id:
        return False  # Not an LTI session

    from .routes import get_launch_data_storage
    storage = get_launch_data_storage()

    # Get the LTI sub for this learner
    learner_sub = _get_learner_sub(learner_id)
    if not learner_sub:
        return False

    return send_grade(
        launch_id=launch_id,
        storage=storage,
        learner_sub=learner_sub,
        score=float(completed),
        max_score=float(total),
        activity_progress="Completed" if completed == total else "InProgress",
        grading_progress="FullyGraded" if completed == total else "Pending",
        comment=f"Completed {completed}/{total} tasks ({completed/total*100:.0f}%)" if total > 0 else None,
    )


def _get_active_launch(learner_id: str, project_id: str) -> Optional[str]:
    """
    Look up the most recent active launch_id for a learner+project.

    We store this mapping in Redis during LTI launch:
      key: lti1p3:active:{learner_id}:{project_id}
      value: launch_id
      TTL: 2 hours (same as launch data)
    """
    from .routes import get_launch_data_storage
    storage = get_launch_data_storage()

    key = f"active:{learner_id}:{project_id}"
    result = storage.get_value(key)
    if result and isinstance(result, dict):
        return result.get("launch_id")
    return None


def _get_learner_sub(learner_id: str) -> Optional[str]:
    """
    Get the LTI sub claim for a learner.

    Reads from the lti_user_mappings table (sync, since PyLTI1p3 is sync).
    """
    # For MVP: parse from learner_metadata JSON
    # For production: query lti_user_mappings table
    import json
    from ltt.db.connection import get_session_sync

    with get_session_sync() as session:
        from sqlalchemy import select, text
        result = session.execute(
            text("SELECT lti_sub FROM lti_user_mappings WHERE learner_id = :lid"),
            {"lid": learner_id},
        )
        row = result.fetchone()
        return row[0] if row else None
```

---

## Storing Active Launch Mapping

During the LTI launch (in `routes.py`), after creating/resolving the learner, store the launch_id mapping:

```python
# In lti_launch(), after mapping the user:
storage = get_launch_data_storage()
storage.set_value(
    f"active:{learner_id}:{project_id}",
    {"launch_id": launch_id, "sub": sub},
    exp=7200,  # 2 hours, same as launch data TTL
)
```

---

## AGS Under the Hood

When `ags.put_grade()` is called, PyLTI1p3:

1. **Requests an OAuth2 access token** from the platform's `auth_token_url`:
   - Creates a JWT signed with the tool's private key
   - Sends `grant_type=client_credentials` with the signed JWT as `client_assertion`
   - Platform returns a Bearer token

2. **Finds or creates a line item** at the platform's `lineitems` endpoint:
   - Searches for existing line item matching tag + resource_id
   - Creates one if it doesn't exist

3. **POSTs the score** to the line item's score endpoint:
   - `POST {lineitem_url}/scores` with the grade payload
   - Uses the Bearer token from step 1

All of this is handled by the library -- we just call `ags.put_grade(grade, line_item)`.

---

## Activity Progress Values

| Value | When to Use |
|---|---|
| `Initialized` | Learner has been provisioned but hasn't started |
| `Started` | Learner has opened the tool |
| `InProgress` | Learner has started but not completed all tasks |
| `Submitted` | Learner has submitted (but grading pending) |
| `Completed` | All tasks in the project are closed |

---

## Grading Progress Values

| Value | When to Use |
|---|---|
| `NotReady` | Grading hasn't started |
| `Pending` | Partial grade (some tasks done, more to go) |
| `PendingManual` | Waiting for instructor review |
| `FullyGraded` | Final grade calculated |
| `Failed` | Grading system error |

---

## Grade Mapping Strategy

### Simple: Task Count Ratio

```
score = completed_tasks / total_tasks * 100
```

**Example**: 15/42 tasks completed = 35.7 points out of 100.

### Weighted: By Task Type

```
subtask = 1 point
task = 3 points (completing all children)
epic = 10 points (completing all tasks)
project = 0 points (just a container)
```

### Bloom's Taxonomy Weighted

Weight by cognitive level:
```
remember = 1, understand = 2, apply = 3, analyze = 4, evaluate = 5, create = 6
```

**Recommendation**: Start with simple task count ratio. It maps naturally to the existing `get_progress()` service and is easy to explain to learners.

---

## Open edX Gradebook Integration

When AGS grades are received, Open edX:

1. Creates a "subsection grade" for the LTI component
2. The grade contributes to the overall course grade based on weight
3. Course staff can see grades in the gradebook
4. Learners see their grade on the progress page

The LTI component weight is configured in Studio (e.g., "this LTT project is worth 30% of the final grade").

---

## Error Handling

| Scenario | Behavior |
|---|---|
| AGS not configured in Open edX | `has_ags()` returns False, grade silently skipped |
| Launch data expired in Redis | `from_cache()` fails, grade silently skipped |
| Network error to Open edX | Exception logged, task completion still succeeds |
| Invalid score values | Exception logged, grade not sent |

**Key principle**: Grade passback failures should never block the learner experience. Task completion always succeeds; grade sync is best-effort.
