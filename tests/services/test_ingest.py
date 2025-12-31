"""
Tests for ingestion service.
"""

import json

import pytest

from ltt.models import TaskType
from ltt.services.ingest import (
    count_objectives,
    count_tasks,
    ingest_project_file,
    validate_project_structure,
)
from ltt.services.learning import get_objectives
from ltt.services.task_service import get_children, get_task


@pytest.mark.asyncio
async def test_ingest_simple_project(async_session, tmp_path):
    """Test ingesting a simple project."""
    # Create test file
    project_data = {
        "title": "Test Project",
        "description": "A test project",
        "learning_objectives": [{"level": "apply", "description": "Test objective"}],
        "epics": [],
    }

    file_path = tmp_path / "project.json"
    file_path.write_text(json.dumps(project_data))

    # Ingest
    result = await ingest_project_file(async_session, file_path)

    assert result.project_id is not None
    assert result.task_count == 1  # Just the project
    assert result.objective_count == 1
    assert result.errors == []

    # Verify in database
    project = await get_task(async_session, result.project_id)
    assert project.title == "Test Project"
    assert project.task_type == TaskType.PROJECT

    objectives = await get_objectives(async_session, result.project_id)
    assert len(objectives) == 1
    assert objectives[0].description == "Test objective"


@pytest.mark.asyncio
async def test_ingest_project_with_hierarchy(async_session, tmp_path):
    """Test ingesting a project with epics and tasks."""
    project_data = {
        "title": "Full Project",
        "description": "Complete hierarchy",
        "epics": [
            {
                "title": "Epic 1",
                "description": "First epic",
                "tasks": [
                    {"title": "Task 1-1", "description": "First task", "subtasks": [{"title": "Subtask 1-1-1"}]}
                ],
            }
        ],
    }

    file_path = tmp_path / "project.json"
    file_path.write_text(json.dumps(project_data))

    # Ingest
    result = await ingest_project_file(async_session, file_path)

    assert result.task_count == 4  # project + epic + task + subtask

    # Verify hierarchy
    project = await get_task(async_session, result.project_id)
    epics = await get_children(async_session, project.id)
    assert len(epics) == 1
    assert epics[0].title == "Epic 1"

    tasks = await get_children(async_session, epics[0].id)
    assert len(tasks) == 1
    assert tasks[0].title == "Task 1-1"

    subtasks = await get_children(async_session, tasks[0].id)
    assert len(subtasks) == 1
    assert subtasks[0].title == "Subtask 1-1-1"


@pytest.mark.asyncio
async def test_ingest_with_learning_objectives(async_session, tmp_path):
    """Test ingesting learning objectives at all levels."""
    project_data = {
        "title": "Project",
        "learning_objectives": [{"level": "create", "description": "Build project"}],
        "epics": [
            {
                "title": "Epic",
                "learning_objectives": [{"level": "apply", "description": "Apply concepts"}],
                "tasks": [
                    {
                        "title": "Task",
                        "learning_objectives": [{"level": "understand", "description": "Understand basics"}],
                        "subtasks": [
                            {
                                "title": "Subtask",
                                "learning_objectives": [{"level": "remember", "description": "Remember syntax"}],
                            }
                        ],
                    }
                ],
            }
        ],
    }

    file_path = tmp_path / "project.json"
    file_path.write_text(json.dumps(project_data))

    # Ingest
    result = await ingest_project_file(async_session, file_path)

    assert result.objective_count == 4  # One at each level

    # Verify objectives
    project = await get_task(async_session, result.project_id)
    proj_objectives = await get_objectives(async_session, project.id)
    assert len(proj_objectives) == 1
    assert proj_objectives[0].level == "create"


@pytest.mark.asyncio
async def test_ingest_with_dependencies(async_session, tmp_path):
    """Test dependency resolution by title."""
    project_data = {
        "title": "Project",
        "epics": [
            {
                "title": "Epic",
                "tasks": [
                    {"title": "Task 1", "description": "First task"},
                    {"title": "Task 2", "description": "Second task", "dependencies": ["Task 1"]},
                ],
            }
        ],
    }

    file_path = tmp_path / "project.json"
    file_path.write_text(json.dumps(project_data))

    # Ingest
    result = await ingest_project_file(async_session, file_path)

    # Verify dependency
    project = await get_task(async_session, result.project_id)
    epics = await get_children(async_session, project.id)
    tasks = await get_children(async_session, epics[0].id)

    task2 = next(t for t in tasks if t.title == "Task 2")

    from ltt.services.dependency_service import get_dependencies

    deps = await get_dependencies(async_session, task2.id)
    assert len(deps) == 1
    assert deps[0].depends_on_id in [t.id for t in tasks if t.title == "Task 1"]


@pytest.mark.asyncio
async def test_ingest_dry_run(async_session, tmp_path):
    """Test dry run doesn't create anything."""
    project_data = {"title": "Test Project", "epics": [{"title": "Epic", "tasks": [{"title": "Task"}]}]}

    file_path = tmp_path / "project.json"
    file_path.write_text(json.dumps(project_data))

    # Dry run
    result = await ingest_project_file(async_session, file_path, dry_run=True)

    assert result.project_id == "(dry-run)"
    assert result.task_count == 3  # project + epic + task
    assert result.errors == []

    # Verify nothing created
    from sqlalchemy import select

    from ltt.models import TaskModel

    db_result = await async_session.execute(select(TaskModel))
    tasks = db_result.scalars().all()
    assert len(tasks) == 0  # Nothing created


@pytest.mark.asyncio
async def test_validate_project_structure():
    """Test project structure validation."""
    # Valid structure
    valid = {"title": "Project", "epics": [{"title": "Epic"}]}
    errors = validate_project_structure(valid)
    assert errors == []

    # Missing title
    invalid = {"description": "No title"}
    errors = validate_project_structure(invalid)
    assert len(errors) > 0
    assert any("title" in e.lower() for e in errors)

    # Invalid epic
    invalid_epic = {"title": "Project", "epics": [{"description": "No title"}]}
    errors = validate_project_structure(invalid_epic)
    assert len(errors) > 0


@pytest.mark.asyncio
async def test_count_tasks():
    """Test task counting."""
    data = {
        "title": "Project",
        "epics": [{"title": "Epic", "tasks": [{"title": "Task", "subtasks": [{"title": "Subtask"}]}]}],
    }

    count = count_tasks(data)
    assert count == 4  # project + epic + task + subtask


@pytest.mark.asyncio
async def test_count_objectives():
    """Test objective counting."""
    data = {
        "title": "Project",
        "learning_objectives": [{"level": "create", "description": "Obj 1"}],
        "epics": [
            {
                "title": "Epic",
                "learning_objectives": [{"level": "apply", "description": "Obj 2"}],
                "tasks": [{"title": "Task", "learning_objectives": [{"level": "remember", "description": "Obj 3"}]}],
            }
        ],
    }

    count = count_objectives(data)
    assert count == 3


@pytest.mark.asyncio
async def test_ingest_task_type_detection(async_session, tmp_path):
    """Test automatic task_type detection based on children."""
    project_data = {
        "title": "Project",
        "epics": [
            {
                "title": "Epic",
                "tasks": [
                    {"title": "Task with subtasks", "subtasks": [{"title": "Subtask"}]},  # Should be TASK
                    {"title": "Task without children"},  # Should be SUBTASK
                ],
            }
        ],
    }

    file_path = tmp_path / "project.json"
    file_path.write_text(json.dumps(project_data))

    # Ingest
    result = await ingest_project_file(async_session, file_path)

    # Verify types
    project = await get_task(async_session, result.project_id)
    epics = await get_children(async_session, project.id)
    tasks = await get_children(async_session, epics[0].id)

    task_with_children = next(t for t in tasks if t.title == "Task with subtasks")
    task_without_children = next(t for t in tasks if t.title == "Task without children")

    assert task_with_children.task_type == TaskType.TASK
    assert task_without_children.task_type == TaskType.SUBTASK


@pytest.mark.asyncio
async def test_ingest_with_narrative_context(async_session, tmp_path):
    """Test ingesting project with narrative_context."""
    project_data = {
        "title": "Water Quality Analysis",
        "description": "Analyze water quality data",
        "narrative_context": "This data comes from President Naledi's water quality initiative. You are helping analyze survey data that will impact real communities.",
        "epics": [],
    }

    file_path = tmp_path / "project.json"
    file_path.write_text(json.dumps(project_data))

    # Ingest
    result = await ingest_project_file(async_session, file_path)

    # Verify narrative_context
    project = await get_task(async_session, result.project_id)
    assert project.narrative_context == "This data comes from President Naledi's water quality initiative. You are helping analyze survey data that will impact real communities."


@pytest.mark.asyncio
async def test_ingest_with_tutor_guidance(async_session, tmp_path):
    """Test ingesting tasks with tutor_guidance."""
    project_data = {
        "title": "SQL Basics",
        "epics": [
            {
                "title": "Query Fundamentals",
                "tasks": [
                    {
                        "title": "Filter with WHERE",
                        "tutor_guidance": {
                            "teaching_approach": "Start with real-world context before SQL syntax",
                            "discussion_prompts": ["What does 500 minutes mean in real life?"],
                            "common_mistakes": ["Using = for pattern matching instead of LIKE"],
                            "hints_to_give": ["Try SHOW TABLES first to see what's available"],
                        },
                        "subtasks": [
                            {
                                "title": "Use LIKE for pattern matching",
                                "tutor_guidance": {
                                    "common_mistakes": ["Forgetting the % wildcards"],
                                    "hints_to_give": ["Remember LIKE uses % as a wildcard"],
                                },
                            }
                        ],
                    }
                ],
            }
        ],
    }

    file_path = tmp_path / "project.json"
    file_path.write_text(json.dumps(project_data))

    # Ingest
    result = await ingest_project_file(async_session, file_path)

    # Verify tutor_guidance at task level
    project = await get_task(async_session, result.project_id)
    epics = await get_children(async_session, project.id)
    tasks = await get_children(async_session, epics[0].id)
    task = tasks[0]

    assert task.tutor_guidance is not None
    assert task.tutor_guidance["teaching_approach"] == "Start with real-world context before SQL syntax"
    assert "What does 500 minutes mean in real life?" in task.tutor_guidance["discussion_prompts"]

    # Verify tutor_guidance at subtask level
    subtasks = await get_children(async_session, task.id)
    subtask = subtasks[0]

    assert subtask.tutor_guidance is not None
    assert "Forgetting the % wildcards" in subtask.tutor_guidance["common_mistakes"]
