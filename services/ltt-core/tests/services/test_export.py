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


# ============================================================================
# Export Round-Trip Tests (Phase 07)
# ============================================================================


@pytest.mark.asyncio
async def test_export_includes_project_slug(async_session):
    """Test that project_slug is exported as 'project_id'."""
    project = await create_task(
        async_session,
        TaskCreate(
            title="Slug Test",
            task_type=TaskType.PROJECT,
            project_slug="my-slug",
        ),
    )

    exported = await export_project(async_session, project.id)
    data = json.loads(exported)

    assert data["project_id"] == "my-slug"


@pytest.mark.asyncio
async def test_export_includes_version(async_session):
    """Test that version and version_tag are exported."""
    project = await create_task(
        async_session,
        TaskCreate(
            title="Versioned Project",
            task_type=TaskType.PROJECT,
            version=3,
            version_tag="v3-beta",
        ),
    )

    exported = await export_project(async_session, project.id)
    data = json.loads(exported)

    assert data["version"] == 3
    assert data["version_tag"] == "v3-beta"


@pytest.mark.asyncio
async def test_export_includes_workspace_type(async_session):
    """Test that workspace_type is exported."""
    from ltt.models import WorkspaceType

    project = await create_task(
        async_session,
        TaskCreate(
            title="SQL Project",
            task_type=TaskType.PROJECT,
            workspace_type=WorkspaceType.SQL,
        ),
    )

    exported = await export_project(async_session, project.id)
    data = json.loads(exported)

    assert data["workspace_type"] == "sql"


@pytest.mark.asyncio
async def test_export_includes_estimated_minutes(async_session):
    """Test that estimated_minutes is exported at all levels."""
    project = await create_task(
        async_session,
        TaskCreate(
            title="Project",
            task_type=TaskType.PROJECT,
            estimated_minutes=120,
        ),
    )
    epic = await create_task(
        async_session,
        TaskCreate(
            title="Epic",
            task_type=TaskType.EPIC,
            parent_id=project.id,
            project_id=project.id,
            estimated_minutes=60,
        ),
    )
    await create_task(
        async_session,
        TaskCreate(
            title="Task",
            task_type=TaskType.TASK,
            parent_id=epic.id,
            project_id=project.id,
            estimated_minutes=30,
        ),
    )

    exported = await export_project(async_session, project.id)
    data = json.loads(exported)

    assert data["estimated_minutes"] == 120
    assert data["epics"][0]["estimated_minutes"] == 60
    assert data["epics"][0]["tasks"][0]["estimated_minutes"] == 30


@pytest.mark.asyncio
async def test_export_includes_max_grade(async_session):
    """Test that max_grade is exported on tasks."""
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
            title="Graded Task",
            task_type=TaskType.TASK,
            parent_id=epic.id,
            project_id=project.id,
            max_grade=10.0,
        ),
    )

    exported = await export_project(async_session, project.id)
    data = json.loads(exported)

    assert data["epics"][0]["tasks"][0]["max_grade"] == 10.0


@pytest.mark.asyncio
async def test_export_includes_subtask_type(async_session):
    """Test that non-default subtask_type is exported on subtasks."""
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
            title="Chat Subtask",
            task_type=TaskType.SUBTASK,
            parent_id=epic.id,
            project_id=project.id,
            subtask_type="conversational",
        ),
    )

    exported = await export_project(async_session, project.id)
    data = json.loads(exported)

    assert data["epics"][0]["tasks"][0]["subtask_type"] == "conversational"


@pytest.mark.asyncio
async def test_export_includes_tutor_config(async_session):
    """Test that tutor_config is exported at project level."""
    project = await create_task(
        async_session,
        TaskCreate(
            title="Project",
            task_type=TaskType.PROJECT,
            tutor_config={"temperature": 0.7, "model": "claude"},
        ),
    )

    exported = await export_project(async_session, project.id)
    data = json.loads(exported)

    assert data["tutor_config"] == {"temperature": 0.7, "model": "claude"}


@pytest.mark.asyncio
async def test_export_omits_none_values(async_session):
    """Test that None-valued fields are omitted from export."""
    project = await create_task(
        async_session,
        TaskCreate(title="Minimal Project", task_type=TaskType.PROJECT),
    )

    exported = await export_project(async_session, project.id)
    data = json.loads(exported)

    # These should be absent (not present as null)
    assert "project_id" not in data  # project_slug is None
    assert "version_tag" not in data
    assert "workspace_type" not in data
    assert "tutor_persona" not in data
    assert "tutor_config" not in data
    assert "estimated_minutes" not in data
    assert "requires_submission" not in data


@pytest.mark.asyncio
async def test_roundtrip_all_fields(async_session, tmp_path):
    """Test that export → ingest preserves all new fields."""
    from ltt.models import WorkspaceType

    # Create project with all fields
    project = await create_task(
        async_session,
        TaskCreate(
            title="Full Project",
            description="All fields set",
            task_type=TaskType.PROJECT,
            project_slug="full-roundtrip",
            version=1,
            version_tag="v1-test",
            workspace_type=WorkspaceType.SQL,
            narrative_context="A story about data",
            tutor_persona="Friendly guide",
            tutor_config={"style": "socratic"},
            estimated_minutes=180,
            narrative=True,
        ),
    )
    epic = await create_task(
        async_session,
        TaskCreate(
            title="Epic 1",
            task_type=TaskType.EPIC,
            parent_id=project.id,
            project_id=project.id,
            estimated_minutes=90,
        ),
    )
    await create_task(
        async_session,
        TaskCreate(
            title="Graded Task",
            task_type=TaskType.TASK,
            parent_id=epic.id,
            project_id=project.id,
            max_grade=10.0,
            estimated_minutes=45,
        ),
    )

    # Export
    exported = await export_project(async_session, project.id)
    data = json.loads(exported)

    # Verify all fields present
    assert data["project_id"] == "full-roundtrip"
    assert data["version"] == 1
    assert data["version_tag"] == "v1-test"
    assert data["workspace_type"] == "sql"
    assert data["narrative_context"] == "A story about data"
    assert data["tutor_persona"] == "Friendly guide"
    assert data["tutor_config"] == {"style": "socratic"}
    assert data["estimated_minutes"] == 180
    assert data["narrative"] is True

    # Re-ingest as v2
    data["version"] = 2
    export_file = tmp_path / "roundtrip.json"
    export_file.write_text(json.dumps(data))

    result = await ingest_project_file(async_session, export_file)
    reimported = await get_task(async_session, result.project_id)

    assert reimported.title == "Full Project"
    assert reimported.project_slug == "full-roundtrip"
    assert reimported.version == 2
    assert reimported.workspace_type == "sql"
    assert reimported.narrative_context == "A story about data"
    assert reimported.tutor_persona == "Friendly guide"
    assert reimported.tutor_config == {"style": "socratic"}
    assert reimported.estimated_minutes == 180
    assert reimported.narrative is True
