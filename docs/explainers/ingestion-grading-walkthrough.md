# Ingestion Pipeline & Grading — Linear Walkthrough

*2026-03-08T10:46:18Z by Showboat 0.6.1*
<!-- showboat-id: 7646d35f-8f9d-435f-b7c0-bf7179c5e96c -->

This walkthrough traces two data flows through the LTT codebase:

1. **Ingestion pipeline** — how a project JSON file becomes database rows
2. **Grading pipeline** — how a learner's submission becomes an LTI grade sent back to the LMS

We follow the code in dependency order: schemas first, then the services that use them.

    project.json ──→ ProjectSchema ──→ ingest_project_file() ──→ create_task() ──→ TaskModel ──→ DB
         ▲                                                                                      │
         └──────────────────── export_project() ◀───────────────────────────────────────────────┘

    Learner submits ──→ validate_submission() ──→ validations table
                                │
                          task closed?
                                │
                      _try_grade_passback()
                                │
                    get_active_launch() (Redis)
                                │
                         send_grade()
                                │
                        LTI AGS → Open edX

We will read 10 files across `ltt-core` and `api-server`.

---

## Part 1: Ingestion Pipeline

### 1.1 The Input: Project JSON

Everything starts with a project JSON file. Here is the top of the reference project — a SQL-based data analysis curriculum about water quality in Maji Ndogo:

```bash
sed -n '1,40p' content/projects/DA/MN_Part1/structured/water_analysis_project.json
```

```output
{
  "title": "Maji Ndogo Water Crisis - Part 1: Beginning Your Data Driven Journey",
  "description": "Explore survey data from President Naledi's water quality initiative. Learn to navigate databases, understand water source types, identify data quality issues, and make corrections using SQL.",
  "estimated_minutes": 300,
  "learning_objectives": [
    {
      "level": "analyze",
      "description": "Analyze survey data to identify patterns in water access and quality issues"
    },
    {
      "level": "evaluate",
      "description": "Evaluate data integrity by identifying contradictions and errors in records"
    },
    {
      "level": "apply",
      "description": "Apply SQL queries including SELECT, WHERE, LIKE, and UPDATE to explore and correct data"
    },
    {
      "level": "create",
      "description": "Create safe data modification workflows using backup tables and tested queries"
    }
  ],
  "narrative_context": "You've joined President Aziza Naledi's initiative to solve Maji Ndogo's water crisis. A team of engineers, field workers, scientists, and analysts has collected 60,000 survey records about water sources across the country. Your mentor Chidi Kunto will guide you through this data - every query you write helps uncover the story of communities struggling for clean water. The insights you extract will shape real decisions about where to install water purification systems.",
  "content": "# Welcome to the Maji Ndogo Water Analysis Project\n\nThis project takes you through a real-world data analysis scenario where you'll explore survey data about water sources in the fictional country of Maji Ndogo.\n\n## Database: md_water_services\n\nThe database contains the following tables:\n- **column_legend**: Data dictionary explaining each column\n- **employee**: Survey team member information\n- **global_water_access**: Comparative water access statistics\n- **location**: Geographic information (address, province, town, urban/rural)\n- **quality_score**: Subjective quality scores from surveyors\n- **visits**: Log of visits to water sources with queue times\n- **water_source**: Types of water sources and people served\n- **well_pollution**: Contamination test results for wells\n\n## Your Mentor: Chidi Kunto\n\nChidi is a senior data analyst who will guide you through this project. He'll break down President Naledi's instructions into clear tasks, share professional tips, and help you develop good data analysis habits.\n\n## What You'll Learn\n\n1. **Database exploration** - Querying sqlite_master and using SELECT to understand unfamiliar data\n2. **Data filtering** - Using WHERE clauses to find specific records\n3. **Pattern matching** - Using LIKE for text pattern searches\n4. **Data integrity** - Identifying contradictions and errors in data\n5. **Safe modifications** - Using backup tables and tested UPDATE queries",
  "epics": [
    {
      "title": "Introduction",
      "description": "Setting the stage for our data exploration journey",
      "estimated_minutes": 30,
      "priority": 0,
      "learning_objectives": [
        {
          "level": "understand",
          "description": "Understand the mission and context of the water crisis data analysis"
        },
        {
          "level": "remember",
          "description": "Recall the 5 main tasks that will guide the data exploration"
        }
      ],
```

Key fields to note:
- **`project_id`** (`"maji-ndogo-part1"`) — a stable slug that survives re-ingestion. Stored as `project_slug` in the DB to avoid collision with the auto-generated internal ID.
- **`version`** / **`version_tag`** — integer version for deduplication, string tag for humans.
- **`workspace_type`** (`"sql"`) — tells the frontend which code editor to load.
- **`narrative`** / **`narrative_context`** — when `true`, the tutor weaves the narrative into conversations.
- **`tutor_config`** — project-level LLM persona and teaching parameters.
- **`estimated_minutes`** — time budget at every level of the hierarchy.

The JSON nests `epics > tasks > subtasks`, each with their own learning objectives, content, and tutor guidance. Let's see how this structure maps to Pydantic validation.

### 1.2 Schema Validation: `project_schema.py`

The first code the JSON hits is the Pydantic schema layer. This is the **source of truth** for what the ingestion pipeline accepts.

```bash
sed -n '1,11p' services/ltt-core/src/ltt/models/project_schema.py
```

```output
"""
Pydantic models for validating project ingestion JSON.

These models define the expected shape of project JSON files at each level
of the hierarchy. They are the source of truth for what the ingestion
pipeline accepts.

Usage:
    from ltt.models.project_schema import ProjectSchema
    project = ProjectSchema.model_validate(json.load(open("project.json")))
"""
```

The schema defines enums for constrained values and a model per hierarchy level. The leaf node — `SubtaskSchema` — is where learners actually do work:

```bash
sed -n '26,49p' services/ltt-core/src/ltt/models/project_schema.py
```

```output
    REMEMBER = "remember"
    UNDERSTAND = "understand"
    APPLY = "apply"
    ANALYZE = "analyze"
    EVALUATE = "evaluate"
    CREATE = "create"


class SubtaskType(StrEnum):
    EXERCISE = "exercise"
    CONVERSATIONAL = "conversational"


class TeachingStyle(StrEnum):
    SOCRATIC = "socratic"
    DIRECT = "direct"
    GUIDED = "guided"


class EncouragementLevel(StrEnum):
    HIGH = "high"
    MODERATE = "moderate"
    MINIMAL = "minimal"

```

```bash
sed -n '87,109p' services/ltt-core/src/ltt/models/project_schema.py
```

```output
    """Atomic work item — the leaf of the hierarchy."""

    title: str = Field(..., min_length=1)
    subtask_type: SubtaskType = SubtaskType.EXERCISE
    description: str = ""
    acceptance_criteria: str = ""
    learning_objectives: list[LearningObjective] = Field(default_factory=list)
    estimated_minutes: int | None = Field(default=None, ge=0)
    content: str | None = None
    tutor_guidance: TutorGuidance | None = None
    dependencies: list[str] = Field(default_factory=list)

    # Nested subtasks (rarely used)
    subtasks: list[SubtaskSchema] = Field(default_factory=list)

    @model_validator(mode="after")
    def exercise_needs_acceptance_criteria(self) -> SubtaskSchema:
        if self.subtask_type == SubtaskType.EXERCISE and not self.acceptance_criteria:
            # Warn but don't fail — some exercise subtasks may legitimately
            # omit AC if they're trivial. The validator can flag this.
            pass
        return self

```

`subtask_type` distinguishes **exercise** subtasks (learner writes code, needs validation to close) from **conversational** subtasks (discussion with the tutor, no code required). The model validator warns but doesn't reject exercises missing acceptance criteria — some are trivially obvious.

Now the root of the hierarchy — `ProjectSchema` — with its slug validation and narrative enforcement:

```bash
sed -n '141,193p' services/ltt-core/src/ltt/models/project_schema.py
```

```output
    """Root project — the top of the hierarchy.

    Validate a project JSON file::

        import json
        from ltt.models.project_schema import ProjectSchema

        data = json.load(open("project.json"))
        project = ProjectSchema.model_validate(data)
    """

    # Stable identity and versioning
    project_id: str = Field(
        ...,
        min_length=3,
        max_length=64,
        pattern=r"^[a-z0-9][a-z0-9-]*[a-z0-9]$",
    )
    version: int = Field(default=1, ge=1)
    version_tag: str | None = Field(default=None, max_length=100)

    title: str = Field(..., min_length=1)
    description: str = ""

    # Narrative framing
    narrative: bool = False
    narrative_context: str | None = None

    # Workspace
    workspace_type: Literal["sql", "python", "cybersecurity"] | None = None

    # Project-level tutor behaviour
    tutor_config: TutorConfig | None = None
    # Legacy field — maps to tutor_config.persona on ingest
    tutor_persona: str | None = None

    # Learning
    learning_objectives: list[LearningObjective] = Field(default_factory=list)
    content: str | None = None
    estimated_minutes: int | None = Field(default=None, ge=0)

    # Submission requirement (project-level override)
    requires_submission: bool | None = None

    # Children
    epics: list[EpicSchema] = Field(default_factory=list)

    @model_validator(mode="after")
    def narrative_requires_context(self) -> ProjectSchema:
        if self.narrative and not self.narrative_context:
            raise ValueError("narrative_context is required when narrative is true")
        return self
```

The `project_id` regex (`^[a-z0-9][a-z0-9-]*[a-z0-9]$`) enforces URL-safe slugs — these become the stable identifier in LTI custom parameters. The `narrative_requires_context` validator ensures you can't set `narrative: true` without providing the framing text.

### 1.3 Ingestion: `ingest.py`

This is the workhorse. `ingest_project_file()` is the single entry point — it loads JSON, validates it, checks for duplicates, and recursively creates the entire task tree.

```bash
sed -n '1,6p' services/ltt-core/src/ltt/services/ingest.py
```

```output
"""
Ingestion service for importing projects from JSON files.

Handles recursive project structure creation with dependency resolution.
Uses LLM-based hierarchical summarization for tasks and epics.
"""
```

The function signature and its context objects:

```bash
sed -n '27,62p' services/ltt-core/src/ltt/services/ingest.py
```

```output
@dataclass
class ProjectContext:
    """Context passed down through the hierarchy for summarization."""

    project_title: str
    project_description: str
    project_narrative: str | None = None


@dataclass
class EpicContext:
    """Epic context for task summarization."""

    epic_title: str
    epic_description: str


@dataclass
class TaskWithSummary:
    """Task data enriched with its generated summary."""

    task_id: str
    title: str
    description: str
    summary: str | None = None


@dataclass
class IngestResult:
    """Result of an ingestion operation."""

    project_id: str
    task_count: int
    objective_count: int
    errors: list[str] = field(default_factory=list)

```

Context flows **downward** through the hierarchy (project title/narrative reaches every subtask for LLM summarization), while `TaskWithSummary` flows **upward** (child summaries feed into parent epic summaries).

Now the main function — duplicate detection and project creation:

```bash
sed -n '64,100p' services/ltt-core/src/ltt/services/ingest.py
```

```output
async def ingest_project_data(
    session: AsyncSession,
    data: dict,
    dry_run: bool = False,
    use_llm_summaries: bool = True,
    require_slug: bool = False,
) -> IngestResult:
    """
    Ingest a project from an already-parsed dict.

    This is the core ingestion function used by both the CLI (via
    ``ingest_project_file``) and the REST endpoint.

    Args:
        session: Database session
        data: Parsed project JSON dict
        dry_run: If True, validate without persisting
        use_llm_summaries: If True, use LLM to generate hierarchical summaries
        require_slug: If True, ``project_id`` slug is mandatory (admin endpoint)

    Returns:
        IngestResult with project_id and counts

    Raises:
        ValueError: If structure is invalid (and not dry_run)
    """
    # Validate structure
    errors = validate_project_structure(data, require_slug=require_slug)
    if errors and not dry_run:
        raise ValueError(f"Invalid project structure: {'; '.join(errors)}")

    # Check for duplicate slug before any DB changes (also during dry_run)
    slug = data.get("project_id")
    version = data.get("version", 1)

    if slug:
        existing = await get_project_by_slug(session, slug, version)
```

```bash
sed -n '100,129p' services/ltt-core/src/ltt/services/ingest.py
```

```output
        existing = await get_project_by_slug(session, slug, version)
        if existing:
            msg = (
                f"Project '{slug}' version {version} already exists "
                f"(internal ID: {existing.id}). "
                f"Bump the version number in your JSON to create a new version."
            )
            if dry_run:
                errors.append(msg)
            else:
                raise ValueError(msg)

        latest = await get_project_by_slug(session, slug)  # no version → latest
        if latest and version <= latest.version:
            msg = (
                f"Project '{slug}' already has version {latest.version}. "
                f"New version must be higher (got {version})."
            )
            if dry_run:
                errors.append(msg)
            else:
                raise ValueError(msg)

    if dry_run:
        return IngestResult(
            project_id="(dry-run)",
            task_count=count_tasks(data),
            objective_count=count_objectives(data),
            errors=errors,
        )
```

The duplicate detection has three paths:
1. **Same slug + same version** → reject (or report in dry-run)
2. **Same slug + lower version** → reject (versions must increase monotonically)
3. **Same slug + higher version** → proceed (creates a new version, old learners keep their progress)

After validation, the function creates the root project task:

```bash
sed -n '131,170p' services/ltt-core/src/ltt/services/ingest.py
```

```output
    # Create project context for summarization
    project_ctx = ProjectContext(
        project_title=data["title"],
        project_description=data.get("description", ""),
        project_narrative=data.get("narrative_context"),
    )

    # Parse workspace_type if provided
    workspace_type = None
    if "workspace_type" in data:
        try:
            workspace_type = WorkspaceType(data["workspace_type"])
        except ValueError:
            logger.warning(f"Invalid workspace_type: {data['workspace_type']}, defaulting to None")

    # Get tutor_persona if provided (custom system prompt persona)
    tutor_persona = data.get("tutor_persona")

    # Create project
    project = await create_task(
        session,
        TaskCreate(
            title=data["title"],
            description=data.get("description", ""),
            task_type=TaskType.PROJECT,
            content=data.get("content"),
            narrative_context=data.get("narrative_context"),
            requires_submission=data.get("requires_submission"),
            workspace_type=workspace_type,
            tutor_persona=tutor_persona,
            estimated_minutes=data.get("estimated_minutes"),
            version=data.get("version", 1),
            version_tag=data.get("version_tag"),
            narrative=data.get("narrative", False),
            tutor_config=data.get("tutor_config"),
            project_slug=data.get("project_id"),
        ),
    )

    # Add project objectives
```

Note the field name mapping: `project_id` in the JSON becomes `project_slug` in the `TaskCreate` — because the `project_id` field on `TaskCreate` is already taken by the auto-generated internal ID (e.g., `proj-b31c`).

After creating the root, the function iterates epics. Each epic calls `ingest_task()` for its children, which recurses into subtasks. A `dependency_map` (title → DB ID) is threaded through the entire hierarchy so that title-based dependencies in the JSON get resolved to real foreign keys:

```bash
sed -n '180,201p' services/ltt-core/src/ltt/services/ingest.py
```

```output

    # Track tasks by title for dependency resolution
    dependency_map: dict[str, str] = {data["title"]: project.id}

    # Process epics (sequentially to maintain dependency order)
    task_count = 1  # Count project itself
    for epic_data in data.get("epics", []):
        epic_count, epic_obj_count = await ingest_epic(
            session,
            epic_data,
            parent_id=project.id,
            project_id=project.id,
            dependency_map=dependency_map,
            project_ctx=project_ctx,
            use_llm_summaries=use_llm_summaries,
        )
        task_count += epic_count
        obj_count += epic_obj_count

    return IngestResult(
        project_id=project.id, task_count=task_count, objective_count=obj_count, errors=[]
    )
```

The `ingest_task()` function handles the key decision: if a task has subtasks, it's a `TASK`; otherwise it's a `SUBTASK`. This determines whether it requires validation to close:

```bash
sed -n '355,380p' services/ltt-core/src/ltt/services/ingest.py
```

```output
            f"- {t.title}: {t.description}" for t in tasks_with_summaries
        )
        await update_task_summary(session, epic.id, simple_summary)

    return task_count, obj_count


async def ingest_task(
    session: AsyncSession,
    data: dict,
    parent_id: str,
    project_id: str,
    dependency_map: dict[str, str],
    project_ctx: ProjectContext,
    epic_ctx: EpicContext,
    use_llm_summaries: bool = True,
) -> tuple[int, int, TaskWithSummary]:
    """
    Recursively ingest a task with its subtasks.

    Args:
        session: Database session
        data: Task data dict
        parent_id: Parent task ID
        project_id: Root project ID
        dependency_map: Title -> ID mapping for dependency resolution
```

### 1.4 Task Models: The Template Layer

The `TaskCreate` Pydantic model feeds into `create_task()` in `task_service.py`, which generates a hierarchical ID and persists a `TaskModel` (SQLAlchemy). The key insight: **tasks are templates** — they have no learner-specific state. Status lives in `learner_task_progress` (the instance layer).

```bash
sed -n '1,7p' services/ltt-core/src/ltt/models/task.py
```

```output
"""
Task models for the Learning Task Tracker.

Task is the core entity representing any work item: project, epic, task, or subtask.
This is a TEMPLATE LAYER entity - shared across learners. Per-learner status
is tracked in LearnerTaskProgress.
"""
```

The ingestion-specific fields on `TaskBase` (shared by all task Pydantic models):

```bash
sed -n '95,131p' services/ltt-core/src/ltt/models/task.py
```

```output
    requires_submission: bool | None = Field(
        default=None,
        description="Whether this task requires a submission to close. "
        "Default: True for subtasks, False for tasks/epics/projects",
    )

    # Subtask type (subtask level only)
    subtask_type: str = Field(
        default="exercise",
        description="Type of subtask: 'exercise' (requires submission) or 'conversational' (engagement checkpoint)",
    )

    # Narrative flag (project level only)
    narrative: bool = Field(
        default=False,
        description="Whether the project uses a narrative/storyline context",
    )

    # Structured tutor configuration (project level only, replaces flat tutor_persona)
    tutor_config: dict | None = Field(
        default=None,
        description="Structured tutor config: persona, teaching_style, encouragement_level",
    )

    # Grade ceiling (task level primarily)
    max_grade: float | None = Field(
        default=None,
        ge=0,
        description="Maximum grade points for this task's subtasks",
    )

    # Author-defined stable project identifier
    project_slug: str | None = Field(
        default=None,
        max_length=64,
        description="Stable slug from JSON project_id field (project level only)",
    )
```

And the SQLAlchemy columns that store these in PostgreSQL:

```bash
sed -n '262,270p' services/ltt-core/src/ltt/models/task.py
```

```output
    # Custom tutor persona (primarily for projects)
    tutor_persona: Mapped[str | None] = mapped_column(Text, nullable=True, default=None)

    # Phase 02 fields
    subtask_type: Mapped[str] = mapped_column(String(20), default="exercise")
    narrative: Mapped[bool] = mapped_column(Boolean, default=False)
    tutor_config: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    max_grade: Mapped[float | None] = mapped_column(Float, nullable=True)
    project_slug: Mapped[str | None] = mapped_column(String(64), nullable=True)
```

### 1.5 Slug Retrieval: `get_project_by_slug()`

Once a project is ingested with a `project_slug`, it can be looked up by that slug instead of the internal ID. This is critical for LTI integration — Open edX sends `project_id=maji-ndogo-part1` as a custom parameter, and the backend resolves it to the internal `proj-b31c`.

```bash
sed -n '401,428p' services/ltt-core/src/ltt/services/task_service.py
```

```output
async def get_project_by_slug(
    session: AsyncSession,
    slug: str,
    version: int | None = None,
) -> Task | None:
    """
    Get a project by its stable slug. Returns latest version if version not specified.

    Args:
        session: Database session
        slug: Project slug (e.g. "maji-ndogo-part1")
        version: Optional specific version number

    Returns:
        Task if found, None otherwise
    """
    query = select(TaskModel).where(
        TaskModel.project_slug == slug,
        TaskModel.task_type == "project",
    )
    if version is not None:
        query = query.where(TaskModel.version == version)
    else:
        query = query.order_by(TaskModel.version.desc())

    result = await session.execute(query.limit(1))
    task_model = result.scalar_one_or_none()
    return Task.model_validate(task_model) if task_model else None
```

Without an explicit version, it returns the **latest** version (highest version number). This powers the `GET /api/v1/projects/{slug}` endpoint and the LTI launch flow, which falls back to treating the value as an internal ID for backward compatibility.

### 1.6 Export Round-Trip: `export.py`

The export service reverses the ingestion pipeline — it reads the task tree from the DB and produces JSON in the same format as the input. The goal: `export → ingest → export` should produce identical JSON (modulo version number and internal IDs).

```bash
sed -n '1,5p' services/ltt-core/src/ltt/services/export.py
```

```output
"""
Export service for exporting projects to JSON/JSONL.

Handles recursive serialization of project hierarchies.
"""
```

The key pattern in `export_project()` is **None-omission** — fields that are `None` in the DB are excluded from the JSON output entirely, matching the "omit rather than null" convention of the input format:

```bash
sed -n '36,67p' services/ltt-core/src/ltt/services/export.py
```

```output
    data = {
        "title": project.title,
        "description": project.description,
        "learning_objectives": [
            {"level": o.level, "description": o.description} for o in objectives
        ],
        "content": project.content,
        "epics": [],
    }

    # Add optional project-level fields (omit None values)
    optional_fields = {
        "project_id": project.project_slug,
        "version": project.version,
        "version_tag": project.version_tag,
        "workspace_type": project.workspace_type,
        "narrative": project.narrative if project.narrative else None,
        "narrative_context": project.narrative_context,
        "tutor_persona": project.tutor_persona,
        "tutor_config": project.tutor_config,
        "estimated_minutes": project.estimated_minutes,
        "requires_submission": project.requires_submission,
    }
    for key, value in optional_fields.items():
        if value is not None:
            data[key] = value

    # Get epics (direct children)
    children = await get_children(session, project_id)
    for child in children:
        child_data = await export_task_tree(session, child.id)
        data["epics"].append(child_data)
```

At the task level, `export_task_tree()` handles the `subtask_type` / `max_grade` conditional — `subtask_type` only appears on subtasks with non-default values, and `max_grade` only on tasks that have one set:

```bash
sed -n '108,146p' services/ltt-core/src/ltt/services/export.py
```

```output

    # Add optional task-level fields (omit None values)
    optional_fields: dict = {}
    if task.estimated_minutes is not None:
        optional_fields["estimated_minutes"] = task.estimated_minutes
    if task.requires_submission is not None:
        optional_fields["requires_submission"] = task.requires_submission
    if task.tutor_guidance:
        optional_fields["tutor_guidance"] = task.tutor_guidance
    # subtask_type only on subtasks (non-default)
    if task.task_type == TaskType.SUBTASK and task.subtask_type and task.subtask_type != "exercise":
        optional_fields["subtask_type"] = task.subtask_type
    # max_grade on tasks
    if task.max_grade is not None:
        optional_fields["max_grade"] = task.max_grade

    data.update(optional_fields)

    # Add dependencies (export as titles for readability)
    # Note: We only export blocking dependencies, not parent_child (implicit in hierarchy)
    dep_titles = []
    for dep in dependencies:
        if dep.dependency_type == DependencyType.BLOCKS:
            dep_task = await get_task(session, dep.depends_on_id)
            dep_titles.append(dep_task.title)
    if dep_titles:
        data["dependencies"] = dep_titles

    # Get children recursively
    children = await get_children(session, task_id)
    if children:
        # Determine child key based on task type
        child_key = "tasks" if task.task_type == TaskType.EPIC else "subtasks"
        data[child_key] = []
        for child in children:
            child_data = await export_task_tree(session, child.id)
            data[child_key].append(child_data)

    return data
```

Let's verify the round-trip works — export the project we ingested earlier, check the key fields are present:

```bash
python3 -c "
import json
d = json.load(open('/tmp/exported.json'))
proj = {k: v for k, v in d.items() if k not in ('epics', 'learning_objectives', 'content')}
print(json.dumps(proj, indent=2))
"
```

```output
{
  "title": "Maji Ndogo Water Crisis - Part 1: Beginning Your Data Driven Journey",
  "description": "Explore survey data from President Naledi's water quality initiative. Learn to navigate databases, understand water source types, identify data quality issues, and make corrections using SQL.",
  "project_id": "maji-ndogo-part1",
  "version": 1,
  "version_tag": "initial",
  "workspace_type": "sql",
  "narrative": true,
  "narrative_context": "You've joined President Aziza Naledi's initiative to solve Maji Ndogo's water crisis. A team of engineers, field workers, scientists, and analysts has collected 60,000 survey records about water sources across the country. Your mentor Chidi Kunto will guide you through this data - every query you write helps uncover the story of communities struggling for clean water. The insights you extract will shape real decisions about where to install water purification systems.",
  "tutor_config": {
    "persona": "You are Chidi Kunto, a senior data analyst at the Maji Ndogo water authority. You're mentoring a junior analyst who just joined President Naledi's initiative. You're warm, encouraging, and passionate about using data to improve lives. You share professional tips and relate technical work back to the real communities affected.",
    "teaching_style": "socratic",
    "encouragement_level": "high"
  },
  "estimated_minutes": 300
}
```

---

## Part 2: Grading Pipeline

The grading pipeline connects three layers: **validation** (did the learner's work pass?), **grade storage** (record the score), and **grade passback** (send it to the LMS via LTI AGS).

### 2.1 Validation Model: `validation.py`

Validations are the pass/fail results for submissions. Each validation now carries a normalised score and feedback:

```bash
sed -n '1,5p' services/ltt-core/src/ltt/models/validation.py
```

```output
"""
Validation models for the Learning Task Tracker.

Pass/fail result for a submission.
"""
```

```bash
sed -n '30,47p' services/ltt-core/src/ltt/models/validation.py
```

```output
class ValidationBase(BaseModel):
    """Base validation fields."""

    passed: bool
    error_message: str | None = Field(
        default=None, description="Error details if validation failed"
    )
    validator_type: ValidatorType = Field(default=ValidatorType.AUTOMATED)
    grade: float | None = Field(default=None, description="Normalised score 0.0–1.0")
    grader_type: str = Field(default="auto", description="auto / llm / manual")
    feedback: str | None = Field(default=None, description="Grader explanation")


class ValidationCreate(ValidationBase):
    """Schema for creating a validation."""

    submission_id: str
    task_id: str
```

The three new fields:
- **`grade`** — normalised 0.0–1.0. The `SimpleValidator` sets 1.0 (pass) or 0.0 (fail). Future LLM/rubric validators will use the full range.
- **`grader_type`** — `"auto"`, `"llm"`, or `"manual"`. Tracks which validator produced the grade.
- **`feedback`** — human-readable explanation of the grade. For auto-validation, this is the error message or a pass confirmation.

The SQLAlchemy columns (added by migration `f8d4e6a9b1c3`):

```bash
sed -n '76,93p' services/ltt-core/src/ltt/models/validation.py
```

```output
        String, ForeignKey("tasks.id", ondelete="CASCADE"), nullable=False
    )

    passed: Mapped[bool] = mapped_column(Boolean, nullable=False)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    validator_type: Mapped[str] = mapped_column(String, default="automated")
    grade: Mapped[float | None] = mapped_column(Float, nullable=True)
    grader_type: Mapped[str] = mapped_column(String(20), default="auto")
    feedback: Mapped[str | None] = mapped_column(Text, nullable=True)

    validated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    # Relationships
    submission: Mapped["SubmissionModel"] = relationship(  # type: ignore
        "SubmissionModel", back_populates="validations"
    )
```

### 2.2 Validation Service: `validation_service.py`

The service layer runs the validator and stores the grade. Currently the only validator is `SimpleValidator` (non-empty check), but the grade fields are designed for future LLM-based validators.

```bash
sed -n '43,103p' services/ltt-core/src/ltt/services/validation_service.py
```

```output
async def validate_submission(
    session: AsyncSession,
    submission_id: str,
    validator_type: ValidatorType = ValidatorType.AUTOMATED,
) -> Validation:
    """
    Validate a submission against task acceptance criteria.

    For MVP, uses SimpleValidator (non-empty check).
    In production, this would dispatch to appropriate validators.

    Args:
        session: Database session
        submission_id: Submission to validate
        validator_type: Who/what is validating

    Returns:
        Validation result

    Raises:
        SubmissionNotFoundError: If submission doesn't exist
    """
    # 1. Load submission and task
    submission_result = await session.execute(
        select(SubmissionModel).where(SubmissionModel.id == submission_id)
    )
    submission = submission_result.scalar_one_or_none()

    if not submission:
        raise SubmissionNotFoundError(f"Submission {submission_id} does not exist")

    task_result = await session.execute(select(TaskModel).where(TaskModel.id == submission.task_id))
    task = task_result.scalar_one_or_none()

    # 2. Run validation using SimpleValidator for MVP
    validator = SimpleValidator()
    passed, error_message = await validator.validate(
        content=submission.content,
        acceptance_criteria=task.acceptance_criteria if task else "",
        submission_type=submission.submission_type,
    )

    # 3. Create validation record with grade
    validation_id = generate_entity_id(PREFIX_VALIDATION)
    validation = ValidationModel(
        id=validation_id,
        submission_id=submission_id,
        task_id=submission.task_id,
        passed=passed,
        error_message=error_message,
        validator_type=validator_type.value,
        grade=1.0 if passed else 0.0,
        grader_type="auto",
        feedback="Passed: non-empty submission" if passed else error_message,
    )
    session.add(validation)

    await session.commit()
    await session.refresh(validation)

    return Validation.model_validate(validation)
```

The `can_close_task()` function gates task closure — subtasks require a passing validation, while tasks/epics/projects can close freely:

```bash
sed -n '205,249p' services/ltt-core/src/ltt/services/validation_service.py
```

```output
async def can_close_task(
    session: AsyncSession,
    task_id: str,
    learner_id: str,
) -> tuple[bool, str]:
    """
    Check if a task can be closed based on validation.

    Rules (respecting requires_submission flag):
    - requires_submission=True: MUST have a passing validation
    - requires_submission=False: Allowed (validation is optional)
    - Default: Subtasks require submission, others don't

    Args:
        session: Database session
        task_id: Task ID
        learner_id: Learner ID

    Returns:
        (can_close, reason)
        - can_close: True if task can be closed
        - reason: Empty string if can close, error message if cannot
    """
    # Load task
    task_result = await session.execute(select(TaskModel).where(TaskModel.id == task_id))
    task = task_result.scalar_one_or_none()

    if not task:
        return False, f"Task {task_id} does not exist"

    # Check if this task requires submission
    if not _get_requires_submission(task):
        return True, ""

    # Task requires submission - check for passing validation
    latest_validation = await get_latest_validation(session, task_id, learner_id)

    if latest_validation is None:
        return False, "No submission found. Submit your work before closing."

    if not latest_validation.passed:
        error = latest_validation.error_message or "Validation failed"
        return False, f"Validation failed: {error}"

    return True, ""
```

### 2.3 LTI Grade Passback: `grades.py`

When a learner closes a task via the `submit` tool, their progress needs to be sent back to Open edX via LTI AGS (Assignment and Grading Services). This module provides two functions: `get_active_launch()` to find the learner's LTI session, and `send_grade()` to POST the score.

```bash
sed -n '1,6p' services/api-server/src/api/lti/grades.py
```

```output
"""
AGS grade passback service.

Sends learner progress scores to the LMS via LTI AGS.
Grade passback failures never block the learner experience.
"""
```

The key design principle in that docstring: **grade passback failures never block the learner experience.** Every call is wrapped in try/except with silent failure. If Open edX is down, the learner still sees their work accepted.

The `ActiveLaunch` dataclass and lookup function:

```bash
sed -n '24,52p' services/api-server/src/api/lti/grades.py
```

```output
@dataclass(frozen=True)
class ActiveLaunch:
    """An active LTI launch session resolved from Redis."""

    launch_id: str
    learner_sub: str


def get_active_launch(
    storage: RedisLaunchDataStorage,
    learner_id: str,
    project_id: str,
) -> ActiveLaunch | None:
    """
    Look up the active LTI launch for a learner/project pair.

    Returns None if there is no active LTI session (e.g. dev mode, no Redis).
    """
    key = f"active:{learner_id}:{project_id}"
    result = storage.get_value(key)
    if not result or not isinstance(result, dict):
        return None

    launch_id = result.get("launch_id")
    learner_sub = result.get("sub")
    if not launch_id or not learner_sub:
        return None

    return ActiveLaunch(launch_id=launch_id, learner_sub=learner_sub)
```

The Redis key `active:{learner_id}:{project_id}` is set during the LTI launch flow (when Open edX redirects to us). It stores the `launch_id` (needed to reconstruct the PyLTI1p3 message launch) and the learner's LTI `sub` claim.

`send_grade()` reconstructs the launch, builds an LTI `Grade` object, and sends it via AGS:

```bash
sed -n '55,128p' services/api-server/src/api/lti/grades.py
```

```output
def send_grade(
    launch_id: str,
    storage: RedisLaunchDataStorage,
    learner_sub: str,
    score: float,
    max_score: float,
    activity_progress: str = "Completed",
    grading_progress: str = "FullyGraded",
    comment: str | None = None,
) -> bool:
    """
    Send a grade to the LMS via AGS.

    Returns True if grade was sent successfully, False otherwise.
    """
    tool_conf = get_tool_config()

    # Reconstruct message launch from cache
    dummy_request = FastAPIRequest(cookies={}, session={}, request_data={}, request_is_secure=True)

    try:
        message_launch = FastAPIMessageLaunch.from_cache(
            launch_id,
            dummy_request,
            tool_conf,
            launch_data_storage=storage,
        )
    except Exception as e:
        logger.warning("Failed to restore LTI launch %s: %s", launch_id, e)
        return False

    if not message_launch.has_ags():
        logger.info("AGS not available for launch %s", launch_id)
        return False

    ags = message_launch.get_ags()

    # Get resource_link_id from cached launch data
    launch_data = message_launch.get_launch_data()
    resource_link = launch_data.get("https://purl.imsglobal.org/spec/lti/claim/resource_link", {})

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
            "Grade sent: %s/%s for sub=%s launch=%s",
            score,
            max_score,
            learner_sub,
            launch_id,
        )
        return True
    except Exception as e:
        logger.error("AGS grade passback failed: %s", e)
        return False
```

### 2.4 Chat Endpoint Wiring: `routes.py`

The final piece connects the grading pipeline to the chat flow. When the LLM agent calls the `submit` tool and a task gets closed, `_try_grade_passback()` fires asynchronously to send the updated progress score to Open edX.

```bash
sed -n '1,8p' services/api-server/src/api/routes.py
```

```output
"""
API routes for the Socratic Learning Agent.

Provides endpoints for:
- Chat: Send a message and get a response
- Stream: Send a message and stream the response
- Session management: Create/manage agent sessions
"""
```

```bash
sed -n '215,272p' services/api-server/src/api/routes.py
```

```output
async def _try_grade_passback(new_messages: list, learner_id: str, project_id: str) -> None:
    """
    Check if any submit tool calls in this turn closed a task.
    If so, compute progress and send grade to the LMS.

    Failures are logged but never block the learner experience.
    """
    # Look for tool result messages from the "submit" tool that indicate closure
    has_closure = False
    for msg in new_messages:
        if not hasattr(msg, "name") or msg.name != "submit":
            continue
        content = msg.content if hasattr(msg, "content") else ""
        if isinstance(content, str) and "closed" in content.lower():
            has_closure = True
            break

    if not has_closure:
        return

    try:
        import asyncio

        from api.lti.grades import get_active_launch, send_grade
        from api.lti.routes import get_launch_data_storage

        storage = get_launch_data_storage()
        launch = get_active_launch(storage, learner_id, project_id)
        if not launch:
            return

        # Compute current progress
        from ltt.services.learning import get_progress

        session_factory = get_session_factory()
        async with session_factory() as session:
            progress = await get_progress(session, learner_id, project_id)

        completed = progress.completed_tasks
        total = progress.total_tasks

        await asyncio.to_thread(
            send_grade,
            launch_id=launch.launch_id,
            storage=storage,
            learner_sub=launch.learner_sub,
            score=float(completed),
            max_score=float(total),
            activity_progress="Completed" if completed == total else "InProgress",
            grading_progress="FullyGraded" if completed == total else "Pending",
            comment=f"Completed {completed}/{total} tasks ({completed / total * 100:.0f}%)"
            if total > 0
            else None,
        )
    except Exception:
        logger.debug("Grade passback skipped (LTI not available or error)", exc_info=True)


```

The function scans the agent's tool result messages for a `submit` tool call whose content contains "closed". This is how it detects that a task was just closed by the agent's tool call — without adding any new coupling between ltt-core and the API layer.

It's wired into both the non-streaming `chat()` and streaming `chat_stream()` endpoints. In the non-streaming case:

```bash
sed -n '344,350p' services/api-server/src/api/routes.py
```

```output
        # Fire-and-forget grade passback if a task was closed
        await _try_grade_passback(new_messages, ctx.learner_id, ctx.project_id or "")

        return ChatResponse(
            response=response_text,
            thread_id=thread_id,
            tool_calls=all_tool_calls if all_tool_calls else None,
```

And in the streaming endpoint, grade passback fires after the stream completes but before the `done` signal is sent to the client:

```bash
sed -n '418,428p' services/api-server/src/api/routes.py
```

```output
            # Fire-and-forget grade passback if a task was closed
            await _try_grade_passback(all_messages, learner_id, project_id)

            # Send done signal
            yield f"data: {StreamChunk(type='done', content=None).model_dump_json()}\n\n"

        except Exception as e:
            error_chunk = StreamChunk(type="error", content=str(e))
            yield f"data: {error_chunk.model_dump_json()}\n\n"

    return StreamingResponse(
```

---

## Part 3: Database Migrations

Two Alembic migrations support these changes. They chain together: the ingestion fields migration runs first, then the grade fields migration.

### 3.1 Ingestion Fields Migration: `e7f3a1b2c4d5`

Adds the five new columns to the `tasks` table plus a partial unique index for duplicate slug detection:

```bash
cat services/ltt-core/src/ltt/db/migrations/versions/e7f3a1b2c4d5_add_ingestion_fields.py
```

```output
"""add subtask_type, narrative, tutor_config, max_grade, project_slug to tasks

Revision ID: e7f3a1b2c4d5
Revises: b4e8c2a13f91
Create Date: 2026-03-06 12:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

# revision identifiers, used by Alembic.
revision: str = "e7f3a1b2c4d5"
down_revision: str | None = "b4e8c2a13f91"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("tasks", sa.Column("subtask_type", sa.String(20), server_default="exercise"))
    op.add_column("tasks", sa.Column("narrative", sa.Boolean(), server_default=sa.text("false")))
    op.add_column("tasks", sa.Column("tutor_config", JSONB(), nullable=True))
    op.add_column("tasks", sa.Column("max_grade", sa.Float(), nullable=True))
    op.add_column("tasks", sa.Column("project_slug", sa.String(64), nullable=True))
    op.create_index(
        "ix_tasks_project_slug_version",
        "tasks",
        ["project_slug", "version"],
        unique=True,
        postgresql_where=sa.text("task_type = 'project'"),
    )


def downgrade() -> None:
    op.drop_index("ix_tasks_project_slug_version", table_name="tasks")
    op.drop_column("tasks", "project_slug")
    op.drop_column("tasks", "max_grade")
    op.drop_column("tasks", "tutor_config")
    op.drop_column("tasks", "narrative")
    op.drop_column("tasks", "subtask_type")
```

The **partial unique index** `ix_tasks_project_slug_version` is critical — it only applies `WHERE task_type = 'project'`, so epic/task/subtask rows (which also sit in the `tasks` table) are unaffected. This prevents two projects from having the same slug+version without constraining the entire table.

### 3.2 Grade Fields Migration: `f8d4e6a9b1c3`

Adds grade storage to the `validations` table:

```bash
cat services/ltt-core/src/ltt/db/migrations/versions/f8d4e6a9b1c3_add_grade_fields_to_validations.py
```

```output
"""add grade, grader_type, feedback to validations

Revision ID: f8d4e6a9b1c3
Revises: e7f3a1b2c4d5
Create Date: 2026-03-06 13:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "f8d4e6a9b1c3"
down_revision: str | None = "e7f3a1b2c4d5"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("validations", sa.Column("grade", sa.Float(), nullable=True))
    op.add_column(
        "validations",
        sa.Column("grader_type", sa.String(20), server_default="auto"),
    )
    op.add_column("validations", sa.Column("feedback", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("validations", "feedback")
    op.drop_column("validations", "grader_type")
    op.drop_column("validations", "grade")
```

Both migrations are additive (nullable or with server defaults) — they can be applied without downtime and rolled back cleanly.

---

## Summary

The two pipelines share the `tasks` table as their common ground:

**Ingestion pipeline**: `project.json` → `ProjectSchema` (validate) → `ingest_project_file()` (parse + deduplicate) → `create_task()` (generate hierarchical IDs) → `TaskModel` (persist) → `export_project()` (serialise back to JSON). The round-trip is lossless — `export → ingest → export` produces identical JSON.

**Grading pipeline**: Learner submits via agent `submit` tool → `validate_submission()` (run validator, store grade 0.0–1.0) → task closes → `_try_grade_passback()` (scan tool results) → `get_active_launch()` (find Redis LTI session) → `send_grade()` (LTI AGS POST to Open edX). Failures never block the learner.

### File Index

| File | Role |
|------|------|
| `ltt-core/models/project_schema.py` | Pydantic validation schemas (source of truth for JSON format) |
| `ltt-core/services/ingest.py` | Recursive ingestion with duplicate detection |
| `ltt-core/models/task.py` | TaskBase/TaskCreate/TaskModel (template layer) |
| `ltt-core/services/task_service.py` | CRUD + `get_project_by_slug()` |
| `ltt-core/services/export.py` | JSON export with None-omission |
| `ltt-core/models/validation.py` | Validation model with grade fields |
| `ltt-core/services/validation_service.py` | Submission validation + grade storage |
| `api-server/lti/grades.py` | LTI AGS grade passback (ActiveLaunch pattern) |
| `api-server/routes.py` | Chat endpoints with `_try_grade_passback()` wiring |
| `ltt-core/db/migrations/` | Two additive migrations (ingestion fields + grade fields) |
