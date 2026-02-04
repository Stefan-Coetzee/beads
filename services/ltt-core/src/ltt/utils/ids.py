"""
ID generation utilities for the Learning Task Tracker.

Following beads pattern for hierarchical, collision-free IDs.
Reference: beads/internal/storage/sqlite/ids.go
"""

import hashlib
from collections.abc import Callable
from uuid import uuid4


def generate_task_id(
    parent_id: str | None,
    project_prefix: str,
    get_next_child_number: Callable[[str], int],
) -> str:
    """
    Generate a hierarchical task ID.

    Args:
        parent_id: ID of parent task, or None for root
        project_prefix: Prefix for project (e.g., "proj")
        get_next_child_number: Function to get next child counter for parent

    Returns:
        Hierarchical ID like "proj-a1b2" or "proj-a1b2.1.1"

    Examples:
        >>> # Root task (project)
        >>> generate_task_id(None, "proj", lambda _: 0)  # doctest: +SKIP
        'proj-a1b2'

        >>> # Child task
        >>> generate_task_id("proj-a1b2", "proj", lambda _: 1)
        'proj-a1b2.1'

        >>> # Grandchild task
        >>> generate_task_id("proj-a1b2.1", "proj", lambda _: 2)
        'proj-a1b2.1.2'
    """
    if parent_id is None:
        # Root task: generate hash-based ID
        unique_bytes = uuid4().bytes
        hash_digest = hashlib.sha256(unique_bytes).hexdigest()[:4]
        return f"{project_prefix}-{hash_digest}"
    else:
        # Child task: increment counter
        next_number = get_next_child_number(parent_id)
        return f"{parent_id}.{next_number}"


def generate_entity_id(prefix: str) -> str:
    """
    Generate a unique ID for any entity.

    Args:
        prefix: Entity type prefix (e.g., "sub", "val", "ltp")

    Returns:
        ID like "sub-a1b2c3d4"

    Examples:
        >>> id = generate_entity_id("sub")
        >>> id.startswith("sub-")
        True
        >>> len(id)
        12
    """
    unique_bytes = uuid4().bytes
    hash_digest = hashlib.sha256(unique_bytes).hexdigest()[:8]
    return f"{prefix}-{hash_digest}"


# Common entity prefixes
PREFIX_LEARNER = "learner"
PREFIX_LEARNER_TASK_PROGRESS = "ltp"
PREFIX_SUBMISSION = "sub"
PREFIX_VALIDATION = "val"
PREFIX_OBJECTIVE = "obj"
PREFIX_CRITERION = "crit"
PREFIX_SUMMARY = "sum"
PREFIX_CONTENT = "cnt"
PREFIX_COMMENT = "cmt"
PREFIX_DEPENDENCY = "dep"
