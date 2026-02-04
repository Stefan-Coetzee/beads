Based on the PRD and supporting documentation, here's the complete Pydantic schema for ingesting a project into the Learning Task Tracker:
from typing import Optional, List
from pydantic import BaseModel, Field
from enum import Enum


# ========================================
# Enums
# ========================================

class BloomLevel(str, Enum):
    """Bloom's Taxonomy cognitive levels."""
    REMEMBER = "remember"
    UNDERSTAND = "understand"
    APPLY = "apply"
    ANALYZE = "analyze"
    EVALUATE = "evaluate"
    CREATE = "create"


class CriterionType(str, Enum):
    """Type of acceptance criterion."""
    CODE_TEST = "code_test"       # Automated code test
    SQL_RESULT = "sql_result"     # SQL query result check
    TEXT_MATCH = "text_match"     # Text/pattern matching
    MANUAL = "manual"             # Human review required


# ========================================
# Component Schemas
# ========================================

class LearningObjectiveIngest(BaseModel):
    """Learning objective for ingestion."""
    level: Optional[BloomLevel] = Field(
        default=BloomLevel.APPLY,
        description="Bloom's taxonomy level"
    )
    description: str = Field(
        ...,
        min_length=1,
        description="What the learner will be able to do"
    )
    taxonomy: Optional[str] = Field(
        default="bloom",
        description="Taxonomy type (default: bloom)"
    )


class AcceptanceCriterionIngest(BaseModel):
    """Structured acceptance criterion for ingestion."""
    criterion_type: CriterionType = Field(
        default=CriterionType.MANUAL,
        description="Type of validation check"
    )
    description: str = Field(
        ...,
        min_length=1,
        description="What must be true for this criterion to pass"
    )


# ========================================
# Task Hierarchy Schemas
# ========================================

class SubtaskIngest(BaseModel):
    """
    Subtask for ingestion (leaf node with validation requirements).
    Can nest infinitely - subtasks can have subtasks.
    """
    title: str = Field(..., min_length=1, max_length=500)
    description: str = Field(default="", description="What this subtask involves")
    
    # Acceptance criteria (text or structured)
    acceptance_criteria: str = Field(
        default="",
        description="Plain text acceptance criteria (backward compatible)"
    )
    acceptance_criteria_structured: List[AcceptanceCriterionIngest] = Field(
        default_factory=list,
        description="Structured acceptance criteria for automated validation"
    )
    
    # Learning objectives
    learning_objectives: List[LearningObjectiveIngest] = Field(
        default_factory=list,
        description="What the learner will learn from this subtask"
    )
    
    # Content
    content: Optional[str] = Field(
        default=None,
        description="Inline learning content (markdown, instructions, examples)"
    )
    content_refs: List[str] = Field(
        default_factory=list,
        description="References to content IDs (for external content)"
    )
    
    # Metadata
    priority: int = Field(
        default=2,
        ge=0,
        le=4,
        description="Priority: 0=critical, 1=high, 2=normal, 3=low, 4=backlog"
    )
    estimated_minutes: Optional[int] = Field(
        default=None,
        ge=0,
        description="Estimated time to complete"
    )
    notes: str = Field(
        default="",
        description="Internal notes (not shown to learner)"
    )
    
    # Dependencies (referenced by title, resolved during ingestion)
    dependencies: List[str] = Field(
        default_factory=list,
        description="List of task titles this subtask depends on"
    )
    
    # Nested subtasks (allows infinite nesting)
    subtasks: List["SubtaskIngest"] = Field(
        default_factory=list,
        description="Nested subtasks (for further decomposition)"
    )


class TaskIngest(BaseModel):
    """
    Task for ingestion (contains subtasks).
    Sits between Epic and Subtask in the hierarchy.
    """
    title: str = Field(..., min_length=1, max_length=500)
    description: str = Field(default="", description="What this task involves")
    
    # Acceptance criteria
    acceptance_criteria: str = Field(default="")
    acceptance_criteria_structured: List[AcceptanceCriterionIngest] = Field(
        default_factory=list
    )
    
    # Learning objectives
    learning_objectives: List[LearningObjectiveIngest] = Field(
        default_factory=list,
        description="What the learner will learn from this task"
    )
    
    # Content
    content: Optional[str] = Field(default=None)
    content_refs: List[str] = Field(default_factory=list)
    
    # Metadata
    priority: int = Field(default=2, ge=0, le=4)
    estimated_minutes: Optional[int] = Field(default=None, ge=0)
    notes: str = Field(default="")
    
    # Dependencies
    dependencies: List[str] = Field(
        default_factory=list,
        description="List of task titles this task depends on"
    )
    
    # Nested subtasks
    subtasks: List[SubtaskIngest] = Field(
        default_factory=list,
        description="Subtasks that make up this task"
    )


class EpicIngest(BaseModel):
    """
    Epic for ingestion (high-level feature/module).
    Contains tasks and sits under a project.
    """
    title: str = Field(..., min_length=1, max_length=500)
    description: str = Field(
        default="",
        description="What this epic aims to accomplish"
    )
    
    # Learning objectives (high-level)
    learning_objectives: List[LearningObjectiveIngest] = Field(
        default_factory=list,
        description="What the learner will learn from this epic"
    )
    
    # Content
    content: Optional[str] = Field(
        default=None,
        description="Introduction/overview content for this epic"
    )
    content_refs: List[str] = Field(default_factory=list)
    
    # Metadata
    priority: int = Field(default=2, ge=0, le=4)
    estimated_minutes: Optional[int] = Field(default=None, ge=0)
    notes: str = Field(default="")
    
    # Nested tasks
    tasks: List[TaskIngest] = Field(
        default_factory=list,
        description="Tasks that make up this epic"
    )


class ProjectIngest(BaseModel):
    """
    Complete project for ingestion.
    This is the root schema for importing a full project structure.
    """
    title: str = Field(
        ...,
        min_length=1,
        max_length=500,
        description="Project title (e.g., 'Build E-commerce Site')"
    )
    description: str = Field(
        default="",
        description="Overall project description and goals"
    )
    
    # Learning objectives (project-level)
    learning_objectives: List[LearningObjectiveIngest] = Field(
        default_factory=list,
        description="What the learner will achieve by completing this project"
    )
    
    # Content
    content: Optional[str] = Field(
        default=None,
        description="Project introduction, setup instructions, etc."
    )
    content_refs: List[str] = Field(
        default_factory=list,
        description="References to external content (e.g., video tutorials)"
    )
    
    # Metadata
    priority: int = Field(default=2, ge=0, le=4)
    estimated_minutes: Optional[int] = Field(
        default=None,
        ge=0,
        description="Total estimated time for entire project"
    )
    notes: str = Field(
        default="",
        description="Internal notes for instructors"
    )
    
    # ID prefix (optional, defaults to 'proj')
    id_prefix: str = Field(
        default="proj",
        pattern=r"^[a-z0-9\-]+$",
        description="Prefix for generated task IDs (e.g., 'proj' -> 'proj-a1b2')"
    )
    
    # Versioning (optional)
    version_tag: Optional[str] = Field(
        default=None,
        description="Version identifier (e.g., 'v1.0', 'fall-2024')"
    )
    
    # Nested epics
    epics: List[EpicIngest] = Field(
        default_factory=list,
        description="Epics that make up this project"
    )


# ========================================
# Alternative: Flat JSONL Format
# ========================================

class TaskIngestFlat(BaseModel):
    """
    Flat task structure for JSONL ingestion.
    Each line is a complete task with parent reference.
    """
    # Identification
    task_type: str = Field(
        ...,
        description="Type: project, epic, task, or subtask"
    )
    title: str = Field(..., min_length=1, max_length=500)
    parent_title: Optional[str] = Field(
        default=None,
        description="Title of parent task (for hierarchy resolution)"
    )
    
    # Core fields
    description: str = Field(default="")
    acceptance_criteria: str = Field(default="")
    acceptance_criteria_structured: List[AcceptanceCriterionIngest] = Field(
        default_factory=list
    )
    
    # Learning
    learning_objectives: List[LearningObjectiveIngest] = Field(
        default_factory=list
    )
    
    # Content
    content: Optional[str] = Field(default=None)
    content_refs: List[str] = Field(default_factory=list)
    
    # Metadata
    priority: int = Field(default=2, ge=0, le=4)
    estimated_minutes: Optional[int] = Field(default=None, ge=0)
    notes: str = Field(default="")
    
    # Dependencies
    dependencies: List[str] = Field(
        default_factory=list,
        description="List of task titles this depends on"
    )


# Update forward references
SubtaskIngest.model_rebuild()
Usage Examples
1. Nested JSON Format (Recommended)
{
  "title": "Build E-commerce Site",
  "description": "Complete e-commerce project with FastAPI backend and React frontend",
  "id_prefix": "ecom",
  "version_tag": "v1.0",
  "estimated_minutes": 12000,
  "learning_objectives": [
    {
      "level": "create",
      "description": "Build a full-stack web application from scratch"
    },
    {
      "level": "apply",
      "description": "Apply REST API design principles in production code"
    }
  ],
  "content": "# E-commerce Project\n\nIn this project, you'll build...",
  "epics": [
    {
      "title": "Build FastAPI Backend",
      "description": "Create a complete REST API backend with authentication",
      "estimated_minutes": 6000,
      "learning_objectives": [
        {
          "level": "apply",
          "description": "Build REST APIs using FastAPI framework"
        }
      ],
      "tasks": [
        {
          "title": "Set up project structure",
          "description": "Initialize FastAPI project with proper directory structure",
          "priority": 0,
          "estimated_minutes": 120,
          "acceptance_criteria": "- Project runs with `uvicorn main:app`\n- /health endpoint returns 200\n- Tests pass",
          "learning_objectives": [
            {
              "level": "remember",
              "description": "Recall FastAPI project structure best practices"
            }
          ],
          "subtasks": [
            {
              "title": "Create main.py",
              "description": "Create the main FastAPI application entry point",
              "estimated_minutes": 30,
              "acceptance_criteria_structured": [
                {
                  "criterion_type": "code_test",
                  "description": "FastAPI app instance is created and importable"
                },
                {
                  "criterion_type": "code_test",
                  "description": "Health endpoint returns {'status': 'ok'}"
                }
              ],
              "content": "Create a file called `main.py` with:\n\n```python\nfrom fastapi import FastAPI\n\napp = FastAPI()\n\n@app.get('/health')\ndef health():\n    return {'status': 'ok'}\n```",
              "learning_objectives": [
                {
                  "level": "apply",
                  "description": "Create a FastAPI application instance"
                }
              ]
            },
            {
              "title": "Add requirements.txt",
              "description": "Define project dependencies",
              "estimated_minutes": 15,
              "dependencies": ["Create main.py"],
              "acceptance_criteria": "- requirements.txt exists\n- Contains fastapi and uvicorn\n- pip install -r requirements.txt succeeds"
            }
          ]
        },
        {
          "title": "Create user endpoints",
          "description": "Implement CRUD operations for user management",
          "dependencies": ["Set up project structure"],
          "estimated_minutes": 480,
          "subtasks": [
            {
              "title": "Create GET /users endpoint",
              "description": "List all users with pagination",
              "acceptance_criteria_structured": [
                {
                  "criterion_type": "code_test",
                  "description": "GET /users returns list of users as JSON"
                },
                {
                  "criterion_type": "code_test",
                  "description": "Supports ?limit and ?offset query parameters"
                }
              ],
              "learning_objectives": [
                {
                  "level": "apply",
                  "description": "Implement pagination in REST APIs"
                }
              ]
            },
            {
              "title": "Create POST /users endpoint",
              "description": "Create a new user",
              "dependencies": ["Create GET /users endpoint"],
              "acceptance_criteria_structured": [
                {
                  "criterion_type": "code_test",
                  "description": "POST /users creates user and returns 201"
                },
                {
                  "criterion_type": "code_test",
                  "description": "Validates email format"
                },
                {
                  "criterion_type": "code_test",
                  "description": "Rejects duplicate emails with 409"
                }
              ]
            }
          ]
        }
      ]
    },
    {
      "title": "Build React Frontend",
      "description": "Create a responsive React application",
      "dependencies": ["Build FastAPI Backend"],
      "tasks": []
    }
  ]
}
2. JSONL Format (Alternative - for large projects)
{"task_type": "project", "title": "Build E-commerce Site", "description": "Complete e-commerce project", "learning_objectives": [{"level": "create", "description": "Build a full-stack web application"}]}
{"task_type": "epic", "title": "Build FastAPI Backend", "parent_title": "Build E-commerce Site", "description": "Create REST API backend"}
{"task_type": "task", "title": "Set up project structure", "parent_title": "Build FastAPI Backend", "priority": 0}
{"task_type": "subtask", "title": "Create main.py", "parent_title": "Set up project structure", "acceptance_criteria_structured": [{"criterion_type": "code_test", "description": "FastAPI app created"}]}
{"task_type": "subtask", "title": "Add requirements.txt", "parent_title": "Set up project structure", "dependencies": ["Create main.py"]}
Key Design Points
Hierarchical Structure: Project → Epic → Task → Subtask (unlimited nesting)
Dependencies by Title: Reference other tasks by title (resolved to IDs during ingestion)
Dual Acceptance Criteria: Both plain text (acceptance_criteria) and structured (acceptance_criteria_structured)
Learning Objectives at All Levels: Every hierarchy level can have pedagogical goals
Inline or Referenced Content: Use content for inline markdown or content_refs for external resources
Flexible Validation: Use criterion_type to specify automated vs. manual validation
This schema covers all template-layer entities needed for project ingestion as specified in the PRD!