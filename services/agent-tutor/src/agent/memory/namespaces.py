"""Namespace helpers for the LangGraph store.

Namespaces are tuples of strings that scope data in the store:
- Profile:          (learner_id, "profile")    / key="main"
- Global memories:  (learner_id, "memories")   / key=<uuid>
- Project memories: (learner_id, slug, "memories") / key=<uuid>
"""

PROFILE_KEY = "main"


def profile_ns(learner_id: str) -> tuple[str, ...]:
    """Namespace for a learner's structured profile."""
    return (learner_id, "profile")


def global_memories_ns(learner_id: str) -> tuple[str, ...]:
    """Namespace for a learner's cross-project observations."""
    return (learner_id, "memories")


def project_memories_ns(learner_id: str, project_slug: str) -> tuple[str, ...]:
    """Namespace for a learner's observations within a specific project."""
    return (learner_id, project_slug, "memories")
