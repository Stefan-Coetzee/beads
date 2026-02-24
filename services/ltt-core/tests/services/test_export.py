"""
Tests for export service.
"""

import json

import pytest
from ltt.models import BloomLevel, DependencyType, TaskCreate, TaskType
from ltt.services.dependency_service import add_dependency
from ltt.services.export import export_project
from ltt.services.ingest import ingest_project_file, validate_project_structure
from ltt.services.learning import attach_objective
from ltt.services.task_service import create_task, get_children, get_task


@pytest.mark.asyncio
async def test_export_simple_project(async_session):
    """Test exporting a simple project."""
    # Create project
    project = await create_task(
        async_session,
        TaskCreate(
            title="Test Project", description="Test description", task_type=TaskType.PROJECT
        ),
    )

    # Export
    exported = await export_project(async_session, project.id, format="json")

    # Parse and verify
    data = json.loads(exported)
    assert data["title"] == "Test Project"
    assert data["description"] == "Test description"
    assert data["epics"] == []


@pytest.mark.asyncio
async def test_export_with_hierarchy(async_session):
    """Test exporting project with full hierarchy."""
    # Create hierarchy
    project = await create_task(
        async_session, TaskCreate(title="Project", task_type=TaskType.PROJECT)
    )
    epic = await create_task(
        async_session,
        TaskCreate(
            title="Epic 1", task_type=TaskType.EPIC, parent_id=project.id, project_id=project.id
        ),
    )
    task = await create_task(
        async_session,
        TaskCreate(
            title="Task 1", task_type=TaskType.TASK, parent_id=epic.id, project_id=project.id
        ),
    )
    await create_task(
        async_session,
        TaskCreate(
            title="Subtask 1", task_type=TaskType.SUBTASK, parent_id=task.id, project_id=project.id
        ),
    )

    # Export
    exported = await export_project(async_session, project.id)
    data = json.loads(exported)

    # Verify structure
    assert len(data["epics"]) == 1
    assert data["epics"][0]["title"] == "Epic 1"
    assert len(data["epics"][0]["tasks"]) == 1
    assert data["epics"][0]["tasks"][0]["title"] == "Task 1"
    assert len(data["epics"][0]["tasks"][0]["subtasks"]) == 1
    assert data["epics"][0]["tasks"][0]["subtasks"][0]["title"] == "Subtask 1"


@pytest.mark.asyncio
async def test_export_with_objectives(async_session):
    """Test exporting learning objectives."""
    # Create project with objectives
    project = await create_task(
        async_session, TaskCreate(title="Project", task_type=TaskType.PROJECT)
    )
    await attach_objective(async_session, project.id, "Build application", BloomLevel.CREATE)

    epic = await create_task(
        async_session,
        TaskCreate(
            title="Epic", task_type=TaskType.EPIC, parent_id=project.id, project_id=project.id
        ),
    )
    await attach_objective(async_session, epic.id, "Apply patterns", BloomLevel.APPLY)

    # Export
    exported = await export_project(async_session, project.id)
    data = json.loads(exported)

    # Verify objectives
    assert len(data["learning_objectives"]) == 1
    assert data["learning_objectives"][0]["level"] == "create"
    assert data["learning_objectives"][0]["description"] == "Build application"

    assert len(data["epics"][0]["learning_objectives"]) == 1
    assert data["epics"][0]["learning_objectives"][0]["level"] == "apply"


@pytest.mark.asyncio
async def test_export_with_dependencies(async_session):
    """Test exporting dependencies."""
    # Create project with dependencies
    project = await create_task(
        async_session, TaskCreate(title="Project", task_type=TaskType.PROJECT)
    )
    epic = await create_task(
        async_session,
        TaskCreate(
            title="Epic", task_type=TaskType.EPIC, parent_id=project.id, project_id=project.id
        ),
    )
    task1 = await create_task(
        async_session,
        TaskCreate(
            title="Task 1", task_type=TaskType.TASK, parent_id=epic.id, project_id=project.id
        ),
    )
    task2 = await create_task(
        async_session,
        TaskCreate(
            title="Task 2", task_type=TaskType.TASK, parent_id=epic.id, project_id=project.id
        ),
    )

    # Add dependency: task2 depends on task1
    await add_dependency(async_session, task2.id, task1.id, DependencyType.BLOCKS)

    # Export
    exported = await export_project(async_session, project.id)
    data = json.loads(exported)

    # Verify dependency exported as title
    task2_data = data["epics"][0]["tasks"][1]
    assert "dependencies" in task2_data
    assert "Task 1" in task2_data["dependencies"]


@pytest.mark.asyncio
async def test_export_jsonl_format(async_session):
    """Test exporting to JSONL format."""
    # Create simple project
    project = await create_task(
        async_session, TaskCreate(title="Project", description="Test", task_type=TaskType.PROJECT)
    )
    await create_task(
        async_session,
        TaskCreate(
            title="Epic", task_type=TaskType.EPIC, parent_id=project.id, project_id=project.id
        ),
    )

    # Export as JSONL
    exported = await export_project(async_session, project.id, format="jsonl")

    # Verify JSONL format (one JSON object per line)
    lines = exported.strip().split("\n")
    assert len(lines) == 2  # project + epic

    # Parse each line
    line1 = json.loads(lines[0])
    line2 = json.loads(lines[1])

    assert line1["type"] == "project"
    assert line1["title"] == "Project"
    assert line2["type"] == "epic"
    assert line2["title"] == "Epic"


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

    # Invalid epic (missing title)
    invalid_epic = {"title": "Project", "epics": [{"description": "No title"}]}
    errors = validate_project_structure(invalid_epic)
    assert len(errors) > 0


@pytest.mark.asyncio
async def test_ingest_invalid_file(async_session, tmp_path):
    """Test ingesting invalid JSON fails."""
    # Create invalid JSON file
    file_path = tmp_path / "invalid.json"
    file_path.write_text("{invalid json")

    with pytest.raises(json.JSONDecodeError):
        await ingest_project_file(async_session, file_path)


@pytest.mark.asyncio
async def test_ingest_missing_title(async_session, tmp_path):
    """Test ingesting project without title fails."""
    project_data = {"description": "No title"}

    file_path = tmp_path / "project.json"
    file_path.write_text(json.dumps(project_data))

    with pytest.raises(ValueError, match="Invalid project structure"):
        await ingest_project_file(async_session, file_path)


@pytest.mark.asyncio
async def test_roundtrip_export_import(async_session, tmp_path):
    """Test export then import produces same structure."""
    # Create project
    project = await create_task(
        async_session,
        TaskCreate(title="Original Project", description="Test", task_type=TaskType.PROJECT),
    )
    await attach_objective(async_session, project.id, "Main objective", BloomLevel.CREATE)

    epic = await create_task(
        async_session,
        TaskCreate(
            title="Epic 1", task_type=TaskType.EPIC, parent_id=project.id, project_id=project.id
        ),
    )
    await create_task(
        async_session,
        TaskCreate(
            title="Task 1", task_type=TaskType.TASK, parent_id=epic.id, project_id=project.id
        ),
    )

    # Export
    exported = await export_project(async_session, project.id)

    # Write to file
    export_file = tmp_path / "exported.json"
    export_file.write_text(exported)

    # Reimport
    result = await ingest_project_file(async_session, export_file)

    # Verify structure matches
    new_project = await get_task(async_session, result.project_id)
    assert new_project.title == "Original Project"
    assert new_project.description == "Test"

    new_epics = await get_children(async_session, result.project_id)
    assert len(new_epics) == 1
    assert new_epics[0].title == "Epic 1"

    new_tasks = await get_children(async_session, new_epics[0].id)
    assert len(new_tasks) == 1
    assert new_tasks[0].title == "Task 1"


@pytest.mark.asyncio
async def test_export_with_narrative_context(async_session):
    """Test exporting project with narrative_context."""
    # Create project with narrative_context
    project = await create_task(
        async_session,
        TaskCreate(
            title="Water Analysis",
            description="Analyze water quality",
            task_type=TaskType.PROJECT,
            narrative_context="This data comes from President Naledi's water quality initiative. Real communities will benefit.",
        ),
    )

    # Export
    exported = await export_project(async_session, project.id)
    data = json.loads(exported)

    # Verify narrative_context exported
    assert "narrative_context" in data
    assert "President Naledi" in data["narrative_context"]


@pytest.mark.asyncio
async def test_export_with_tutor_guidance(async_session):
    """Test exporting tutor_guidance."""
    # Create project with task that has tutor_guidance
    project = await create_task(
        async_session, TaskCreate(title="Project", task_type=TaskType.PROJECT)
    )
    epic = await create_task(
        async_session,
        TaskCreate(
            title="Epic", task_type=TaskType.EPIC, parent_id=project.id, project_id=project.id
        ),
    )
    await create_task(
        async_session,
        TaskCreate(
            title="Task with guidance",
            task_type=TaskType.TASK,
            parent_id=epic.id,
            project_id=project.id,
            tutor_guidance={
                "teaching_approach": "Start with real-world examples",
                "discussion_prompts": ["What does this mean in practice?"],
                "common_mistakes": ["Off-by-one errors"],
                "hints_to_give": ["Check the loop bounds"],
            },
        ),
    )

    # Export
    exported = await export_project(async_session, project.id)
    data = json.loads(exported)

    # Verify tutor_guidance exported
    task_data = data["epics"][0]["tasks"][0]
    assert "tutor_guidance" in task_data
    assert task_data["tutor_guidance"]["teaching_approach"] == "Start with real-world examples"
    assert "What does this mean in practice?" in task_data["tutor_guidance"]["discussion_prompts"]
