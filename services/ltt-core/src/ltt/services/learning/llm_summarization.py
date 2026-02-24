"""
LLM-based hierarchical summarization for tasks and epics.

Uses LangGraph to generate summaries by:
1. Summarizing tasks from their subtasks (bottom-up)
2. Summarizing epics from their task summaries
3. Running in parallel where possible

Requires ANTHROPIC_API_KEY in environment.
"""

import asyncio
import os
from dataclasses import dataclass
from typing import Any

from dotenv import load_dotenv
from langchain_anthropic import ChatAnthropic
from langchain_core.messages import HumanMessage, SystemMessage
from langgraph.graph import END, StateGraph

load_dotenv()


@dataclass
class HierarchyContext:
    """Full hierarchy context for summarization."""

    project_title: str
    project_description: str
    project_narrative: str | None
    epic_title: str | None = None
    epic_description: str | None = None
    task_title: str | None = None
    task_description: str | None = None
    task_acceptance_criteria: str | None = None


@dataclass
class SummarizationRequest:
    """Request to summarize a task or epic."""

    item_id: str
    item_type: str  # "task" or "epic"
    item_title: str
    item_description: str
    children: list[dict[str, Any]]  # Child items with title, description, etc.
    hierarchy: HierarchyContext


@dataclass
class SummarizationResult:
    """Result of summarization."""

    item_id: str
    summary: str


# State type for LangGraph
class SummarizationState(dict):
    """State for the summarization graph."""

    request: SummarizationRequest
    summary: str | None


def _get_llm() -> ChatAnthropic:
    """Get the Anthropic LLM instance."""
    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        raise ValueError("ANTHROPIC_API_KEY not set in environment")

    return ChatAnthropic(
        model="claude-sonnet-4-20250514",
        api_key=api_key,
        max_tokens=500,
    )


TASK_SUMMARY_PROMPT = """You are summarizing a learning task for a Socratic tutoring system.

## Project Context
**Project**: {project_title}
{project_description}

{narrative_section}

## Epic Context
**Epic**: {epic_title}
{epic_description}

## Task to Summarize
**Task**: {task_title}
{task_description}

**Acceptance Criteria**:
{acceptance_criteria}

## Subtasks in this Task
{children_section}

## Your Task
Write a 2-3 sentence summary of what the learner will accomplish in this task, based on its subtasks.
Focus on the learning outcomes and skills developed. Write in present tense, as if describing what happens during the task.
Be concise but informative - this summary helps tutors understand the task at a glance."""

EPIC_SUMMARY_PROMPT = """You are summarizing a learning epic for a Socratic tutoring system.

## Project Context
**Project**: {project_title}
{project_description}

{narrative_section}

## Epic to Summarize
**Epic**: {epic_title}
{epic_description}

## Tasks in this Epic
{children_section}

## Your Task
Write a 2-4 sentence summary of what the learner will accomplish in this epic, based on its tasks.
Focus on the major themes, skills, and learning journey. Write in present tense.
This summary helps tutors understand the epic's scope and purpose."""


async def _generate_summary(state: SummarizationState) -> SummarizationState:
    """Generate summary using Claude."""
    request = state["request"]
    llm = _get_llm()

    # Build narrative section if available
    narrative_section = ""
    if request.hierarchy.project_narrative:
        narrative_section = f"**Narrative Context**: {request.hierarchy.project_narrative}"

    # Build children section
    children_lines = []
    for child in request.children:
        title = child.get("title", "Untitled")
        desc = child.get("description", "")
        # Include child's summary if available (for epics summarizing tasks)
        summary = child.get("summary", "")
        if summary:
            children_lines.append(f"- **{title}**: {desc}\n  *Summary*: {summary}")
        else:
            children_lines.append(f"- **{title}**: {desc}")

    children_section = "\n".join(children_lines) if children_lines else "No children defined."

    # Select prompt based on item type
    if request.item_type == "task":
        prompt = TASK_SUMMARY_PROMPT.format(
            project_title=request.hierarchy.project_title,
            project_description=request.hierarchy.project_description,
            narrative_section=narrative_section,
            epic_title=request.hierarchy.epic_title or "Unknown Epic",
            epic_description=request.hierarchy.epic_description or "",
            task_title=request.item_title,
            task_description=request.item_description,
            acceptance_criteria=request.hierarchy.task_acceptance_criteria or "Not specified",
            children_section=children_section,
        )
    else:  # epic
        prompt = EPIC_SUMMARY_PROMPT.format(
            project_title=request.hierarchy.project_title,
            project_description=request.hierarchy.project_description,
            narrative_section=narrative_section,
            epic_title=request.item_title,
            epic_description=request.item_description,
            children_section=children_section,
        )

    # Call LLM
    messages = [
        SystemMessage(
            content="You are a helpful assistant that writes concise, informative summaries for educational content."
        ),
        HumanMessage(content=prompt),
    ]

    response = await llm.ainvoke(messages)
    summary = (
        response.content.strip() if isinstance(response.content, str) else str(response.content)
    )

    state["summary"] = summary
    return state


def _create_summarization_graph() -> StateGraph:
    """Create the LangGraph workflow for summarization."""
    workflow = StateGraph(SummarizationState)

    # Add the summary generation node
    workflow.add_node("generate_summary", _generate_summary)

    # Set entry point and edge to end
    workflow.set_entry_point("generate_summary")
    workflow.add_edge("generate_summary", END)

    return workflow.compile()


# Compiled graph (singleton)
_summarization_graph = None


def _get_graph():
    """Get or create the summarization graph."""
    global _summarization_graph
    if _summarization_graph is None:
        _summarization_graph = _create_summarization_graph()
    return _summarization_graph


async def summarize_item(request: SummarizationRequest) -> SummarizationResult:
    """
    Summarize a single task or epic using LLM.

    Args:
        request: Summarization request with hierarchy context

    Returns:
        SummarizationResult with the generated summary
    """
    graph = _get_graph()

    initial_state: SummarizationState = {
        "request": request,
        "summary": None,
    }

    result = await graph.ainvoke(initial_state)
    summary = result.get("summary", "")

    return SummarizationResult(item_id=request.item_id, summary=summary)


async def summarize_items_parallel(
    requests: list[SummarizationRequest],
) -> list[SummarizationResult]:
    """
    Summarize multiple items in parallel.

    Args:
        requests: List of summarization requests

    Returns:
        List of SummarizationResults (in same order as requests)
    """
    if not requests:
        return []

    tasks = [summarize_item(req) for req in requests]
    results = await asyncio.gather(*tasks)
    return list(results)


async def generate_task_summary(
    task_id: str,
    task_title: str,
    task_description: str,
    acceptance_criteria: str,
    subtasks: list[dict[str, Any]],
    project_title: str,
    project_description: str,
    project_narrative: str | None,
    epic_title: str,
    epic_description: str,
) -> str:
    """
    Generate a summary for a task based on its subtasks.

    Convenience function for ingestion.
    """
    hierarchy = HierarchyContext(
        project_title=project_title,
        project_description=project_description,
        project_narrative=project_narrative,
        epic_title=epic_title,
        epic_description=epic_description,
        task_title=task_title,
        task_description=task_description,
        task_acceptance_criteria=acceptance_criteria,
    )

    request = SummarizationRequest(
        item_id=task_id,
        item_type="task",
        item_title=task_title,
        item_description=task_description,
        children=subtasks,
        hierarchy=hierarchy,
    )

    result = await summarize_item(request)
    return result.summary


async def generate_epic_summary(
    epic_id: str,
    epic_title: str,
    epic_description: str,
    tasks_with_summaries: list[dict[str, Any]],
    project_title: str,
    project_description: str,
    project_narrative: str | None,
) -> str:
    """
    Generate a summary for an epic based on its tasks (with their summaries).

    Convenience function for ingestion.
    """
    hierarchy = HierarchyContext(
        project_title=project_title,
        project_description=project_description,
        project_narrative=project_narrative,
        epic_title=epic_title,
        epic_description=epic_description,
    )

    request = SummarizationRequest(
        item_id=epic_id,
        item_type="epic",
        item_title=epic_title,
        item_description=epic_description,
        children=tasks_with_summaries,
        hierarchy=hierarchy,
    )

    result = await summarize_item(request)
    return result.summary
