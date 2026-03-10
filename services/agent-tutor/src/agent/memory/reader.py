"""Format learner memory for system prompt injection."""

from agent.memory.schemas import LearnerProfile, MemoryEntry


def format_memories_for_prompt(
    profile: LearnerProfile,
    global_memories: list[MemoryEntry],
    project_memories: list[MemoryEntry],
    project_slug: str | None = None,
) -> str:
    """Format profile + memories into a text block for the system prompt.

    Returns empty string if there's nothing to include (no profile data,
    no memories).  This avoids polluting the prompt with empty tags.
    """
    sections: list[str] = []

    # ── Profile ──────────────────────────────────────────────────────
    profile_lines = _format_profile(profile)
    if profile_lines:
        sections.append("[Learner Profile]\n" + "\n".join(profile_lines))

    # ── Global memories ──────────────────────────────────────────────
    if global_memories:
        lines = [f"  - {m.text}" for m in global_memories]
        sections.append("[Observations]\n" + "\n".join(lines))

    # ── Project memories ─────────────────────────────────────────────
    if project_memories and project_slug:
        lines = [f"  - {m.text}" for m in project_memories]
        sections.append(f"[Project: {project_slug}]\n" + "\n".join(lines))

    if not sections:
        return ""

    body = "\n\n".join(sections)
    return f"<learner_memory>\n{body}\n</learner_memory>"


def _format_profile(profile: LearnerProfile) -> list[str]:
    """Convert non-empty profile fields to display lines."""
    lines: list[str] = []
    for field_name, value in profile.model_dump().items():
        if value is None or value == [] or value == "":
            continue
        label = field_name.replace("_", " ").title()
        if isinstance(value, list):
            lines.append(f"  {label}: {', '.join(value)}")
        else:
            lines.append(f"  {label}: {value}")
    return lines
