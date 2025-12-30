# Data Models Specification

> Complete Pydantic schemas and database models for the Learning Task Tracker.

## Overview

This document defines all data structures used in the system. We use:
- **Pydantic v2** for validation, serialization, and API schemas
- **SQLAlchemy 2.0** for database ORM (async-first)
- **PostgreSQL** as the primary database

### Naming Conventions

| Layer | Convention | Example |
|-------|------------|---------|
| Pydantic Base | `{Entity}Base` | `TaskBase` |
| Pydantic Create | `{Entity}Create` | `TaskCreate` |
| Pydantic Update | `{Entity}Update` | `TaskUpdate` |
| Pydantic Response | `{Entity}` or `{Entity}Detail` | `Task`, `TaskDetail` |
| SQLAlchemy | `{Entity}Model` | `TaskModel` |
| Database Table | `{entities}` (plural, snake_case) | `tasks` |

---

## 1. Task (Core Entity)

> **Note**: Task is a template-layer entity (shared across learners). Per-learner status and progress are tracked in `LearnerTaskProgress` (see Section 1b). See [ADR-001: Two-Layer Architecture](./adr/001-learner-scoped-task-progress.md) for the rationale.

The central entity representing any work item: project, epic, task, or subtask.

### Reference: Beads Issue Model

From [internal/types/types.go:12-103](../internal/types/types.go):
```go
type Issue struct {
    ID                 string
    Title              string
    Description        string
    Design             string
    AcceptanceCriteria string 
    Notes              string
    Status             Status
    Priority           int
    IssueType          IssueType
    Assignee           string
    EstimatedMinutes   *int
    CreatedAt          time.Time
    UpdatedAt          time.Time
    ClosedAt           *time.Time
    CloseReason        string
    // ... additional fields
}
```

### Pydantic Models

```python
from datetime import datetime
from enum import Enum
from typing import Optional, List
from pydantic import BaseModel, Field, ConfigDict


class TaskType(str, Enum):
    """Type of task in the hierarchy."""
    PROJECT = "project"
    EPIC = "epic"
    TASK = "task"
    SUBTASK = "subtask"


class TaskStatus(str, Enum):
    """Task workflow status."""
    OPEN = "open"
    IN_PROGRESS = "in_progress"
    BLOCKED = "blocked"
    CLOSED = "closed"


class TaskBase(BaseModel):
    """Base fields for task creation and updates."""
    title: str = Field(..., min_length=1, max_length=500)
    description: str = Field(default="")
    acceptance_criteria: str = Field(default="")
    notes: str = Field(default="")
    priority: int = Field(default=2, ge=0, le=4)
    task_type: TaskType = Field(default=TaskType.TASK)
    estimated_minutes: Optional[int] = Field(default=None, ge=0)

    # Learning-specific fields
    content: Optional[str] = Field(default=None, description="Inline learning content")
    content_refs: List[str] = Field(default_factory=list, description="References to content IDs")


class TaskCreate(TaskBase):
    """Schema for creating a new task."""
    parent_id: Optional[str] = Field(default=None, description="Parent task ID for hierarchy")
    project_id: Optional[str] = Field(
        default=None,
        description="Project ID. Required for non-project tasks. Auto-set for projects."
    )

    # Optional: provide a custom ID (otherwise generated)
    id: Optional[str] = Field(default=None, pattern=r"^[a-z0-9\-\.]+$")


class TaskUpdate(BaseModel):
    """Schema for updating an existing task. All fields optional."""
    title: Optional[str] = Field(default=None, min_length=1, max_length=500)
    description: Optional[str] = None
    acceptance_criteria: Optional[str] = None
    notes: Optional[str] = None
    priority: Optional[int] = Field(default=None, ge=0, le=4)
    estimated_minutes: Optional[int] = Field(default=None, ge=0)
    content: Optional[str] = None
    content_refs: Optional[List[str]] = None


class Task(TaskBase):
    """Complete task entity returned from database (template layer only)."""
    model_config = ConfigDict(from_attributes=True)

    id: str
    parent_id: Optional[str] = None
    project_id: str

    # Versioning
    version: int = 1
    version_tag: Optional[str] = None

    # Timestamps
    created_at: datetime
    updated_at: datetime


class TaskDetail(Task):
    """Extended task with related data for detailed views."""
    # Computed relationships
    learning_objectives: List["LearningObjective"] = Field(default_factory=list)
    children: List["Task"] = Field(default_factory=list)
    comments: List["Comment"] = Field(default_factory=list)

    # Dependency info
    blocked_by: List["TaskSummary"] = Field(default_factory=list)
    blocks: List["TaskSummary"] = Field(default_factory=list)


class TaskSummary(BaseModel):
    """Minimal task info for lists and references."""
    model_config = ConfigDict(from_attributes=True)

    id: str
    title: str
    task_type: TaskType
    priority: int
```

### SQLAlchemy Model

```python
from sqlalchemy import Column, String, Text, Integer, DateTime, ForeignKey, Enum, ARRAY
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from .base import Base


class TaskModel(Base):
    __tablename__ = "tasks"

    # Primary key with hierarchical ID
    id = Column(String, primary_key=True)
    parent_id = Column(String, ForeignKey("tasks.id", ondelete="CASCADE"), nullable=True, index=True)
    project_id = Column(String, nullable=False, index=True)

    # Core fields
    title = Column(String(500), nullable=False)
    description = Column(Text, default="")
    acceptance_criteria = Column(Text, default="")
    notes = Column(Text, default="")

    # Type
    task_type = Column(String, default="task")
    priority = Column(Integer, default=2)

    # Estimation
    estimated_minutes = Column(Integer, nullable=True)

    # Learning content
    content = Column(Text, nullable=True)
    content_refs = Column(ARRAY(String), default=[])

    # Versioning
    version = Column(Integer, default=1)
    version_tag = Column(String, nullable=True)

    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    # Relationships
    parent = relationship("TaskModel", remote_side=[id], backref="children")
    learning_objectives = relationship("LearningObjectiveModel", back_populates="task", cascade="all, delete-orphan")
    acceptance_criteria = relationship("AcceptanceCriterionModel", back_populates="task", cascade="all, delete-orphan")
    status_summaries = relationship("StatusSummaryModel", back_populates="task", cascade="all, delete-orphan")
    comments = relationship("CommentModel", back_populates="task", cascade="all, delete-orphan")
    submissions = relationship("SubmissionModel", back_populates="task", cascade="all, delete-orphan")
    learner_progress = relationship("LearnerTaskProgressModel", back_populates="task", cascade="all, delete-orphan")

    # Dependencies (via association)
    dependencies = relationship(
        "DependencyModel",
        foreign_keys="DependencyModel.task_id",
        back_populates="task",
        cascade="all, delete-orphan"
    )
    dependents = relationship(
        "DependencyModel",
        foreign_keys="DependencyModel.depends_on_id",
        back_populates="depends_on",
        cascade="all, delete-orphan"
    )
```

---

## 1b. LearnerTaskProgress (Instance Layer)

Per-learner status and progress tracking for tasks. This is the instance layer that pairs with Task (template layer).

### Pydantic Models

```python
class LearnerTaskProgressBase(BaseModel):
    """Base fields for learner task progress."""
    status: TaskStatus = Field(default=TaskStatus.OPEN)
    started_at: Optional[datetime] = Field(default=None)
    completed_at: Optional[datetime] = Field(default=None)
    close_reason: Optional[str] = Field(default=None)


class LearnerTaskProgressCreate(LearnerTaskProgressBase):
    """Schema for creating learner task progress."""
    task_id: str
    learner_id: str


class LearnerTaskProgress(LearnerTaskProgressBase):
    """Complete learner task progress entity."""
    model_config = ConfigDict(from_attributes=True)

    id: str
    task_id: str
    learner_id: str
    created_at: datetime
    updated_at: datetime
```

### SQLAlchemy Model

```python
from sqlalchemy import Column, String, DateTime, ForeignKey, UniqueConstraint, Index
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from .base import Base


class LearnerTaskProgressModel(Base):
    __tablename__ = "learner_task_progress"

    id = Column(String, primary_key=True)
    task_id = Column(String, ForeignKey("tasks.id", ondelete="CASCADE"), nullable=False)
    learner_id = Column(String, ForeignKey("learners.id", ondelete="CASCADE"), nullable=False)

    status = Column(String, nullable=False, default="open")
    started_at = Column(DateTime(timezone=True), nullable=True)
    completed_at = Column(DateTime(timezone=True), nullable=True)
    close_reason = Column(Text, nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    # Relationships
    task = relationship("TaskModel", back_populates="learner_progress")
    learner = relationship("LearnerModel", back_populates="task_progress")

    # Constraints and indexes
    __table_args__ = (
        UniqueConstraint("task_id", "learner_id", name="uq_task_learner_progress"),
        Index("idx_learner_task_progress_task_learner", "task_id", "learner_id"),
        Index("idx_learner_task_progress_learner_status", "learner_id", "status"),
    )
```

---

## 2. Dependency

Relationships between tasks that control workflow.

### Reference: Beads Dependency Model

From [internal/types/types.go:453-465](../internal/types/types.go):
```go
type Dependency struct {
    IssueID     string
    DependsOnID string
    Type        DependencyType
    CreatedAt   time.Time
    CreatedBy   string
    Metadata    string  // JSON blob for type-specific data
}
```

### Pydantic Models

```python
class DependencyType(str, Enum):
    """Type of dependency relationship."""
    BLOCKS = "blocks"           # Task cannot start until dependency closes
    PARENT_CHILD = "parent_child"  # Hierarchical (implicit via parent_id)
    RELATED = "related"         # Informational, no blocking


class DependencyBase(BaseModel):
    """Base dependency fields."""
    dependency_type: DependencyType = Field(default=DependencyType.BLOCKS)
    metadata: Optional[dict] = Field(default=None, description="Type-specific metadata")


class DependencyCreate(DependencyBase):
    """Schema for creating a dependency."""
    task_id: str = Field(..., description="The task that depends on another")
    depends_on_id: str = Field(..., description="The task being depended upon")


class Dependency(DependencyBase):
    """Complete dependency entity."""
    model_config = ConfigDict(from_attributes=True)

    task_id: str
    depends_on_id: str
    created_at: datetime
    created_by: Optional[str] = None


class DependencyWithTask(Dependency):
    """Dependency with the related task details."""
    depends_on: TaskSummary
```

### SQLAlchemy Model

```python
class DependencyModel(Base):
    __tablename__ = "dependencies"

    task_id = Column(String, ForeignKey("tasks.id", ondelete="CASCADE"), primary_key=True)
    depends_on_id = Column(String, ForeignKey("tasks.id", ondelete="CASCADE"), primary_key=True)

    dependency_type = Column(String, default="blocks")
    metadata = Column(Text, default="{}")  # JSON string
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    created_by = Column(String, nullable=True)

    # Relationships
    task = relationship("TaskModel", foreign_keys=[task_id], back_populates="dependencies")
    depends_on = relationship("TaskModel", foreign_keys=[depends_on_id], back_populates="dependents")
```

---

## 3. Learning Objective

Pedagogical goals attached to tasks.

### Pydantic Models

```python
class BloomLevel(str, Enum):
    """Bloom's Taxonomy cognitive levels."""
    REMEMBER = "remember"
    UNDERSTAND = "understand"
    APPLY = "apply"
    ANALYZE = "analyze"
    EVALUATE = "evaluate"
    CREATE = "create"


class ObjectiveTaxonomy(str, Enum):
    """Supported learning taxonomies."""
    BLOOM = "bloom"
    CUSTOM = "custom"


class LearningObjectiveBase(BaseModel):
    """Base learning objective fields."""
    taxonomy: ObjectiveTaxonomy = Field(default=ObjectiveTaxonomy.BLOOM)
    level: Optional[BloomLevel] = Field(
        default=None,
        description="Cognitive level (for Bloom's taxonomy)"
    )
    description: str = Field(..., min_length=1)


class LearningObjectiveCreate(LearningObjectiveBase):
    """Schema for creating a learning objective."""
    task_id: str


class LearningObjective(LearningObjectiveBase):
    """Complete learning objective entity."""
    model_config = ConfigDict(from_attributes=True)

    id: str
    task_id: str
    created_at: datetime
```

### SQLAlchemy Model

```python
class LearningObjectiveModel(Base):
    __tablename__ = "learning_objectives"

    id = Column(String, primary_key=True)
    task_id = Column(String, ForeignKey("tasks.id", ondelete="CASCADE"), nullable=False, index=True)

    taxonomy = Column(String, default="bloom")
    level = Column(String, nullable=True)
    description = Column(Text, nullable=False)

    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # Relationships
    task = relationship("TaskModel", back_populates="learning_objectives")
```

---

## 4. Learner

User profile for tracking progress.

### Pydantic Models

```python
class LearnerBase(BaseModel):
    """Base learner fields."""
    metadata: dict = Field(default_factory=dict, description="Arbitrary user metadata")


class LearnerCreate(LearnerBase):
    """Schema for creating a learner."""
    id: Optional[str] = Field(default=None, description="External ID if provided")


class Learner(LearnerBase):
    """Complete learner entity."""
    model_config = ConfigDict(from_attributes=True)

    id: str
    created_at: datetime


class LearnerProgress(BaseModel):
    """Learner's progress in a project."""
    learner_id: str
    project_id: str

    # Progress stats
    total_tasks: int
    completed_tasks: int
    in_progress_tasks: int
    blocked_tasks: int

    # Computed
    completion_percentage: float

    # Objectives
    objectives_achieved: int
    total_objectives: int

    # Time
    total_time_spent_minutes: Optional[int] = None
```

### SQLAlchemy Model

```python
class LearnerModel(Base):
    __tablename__ = "learners"

    id = Column(String, primary_key=True)
    metadata = Column(Text, default="{}")  # JSON string
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # Relationships
    submissions = relationship("SubmissionModel", back_populates="learner")
    status_summaries = relationship("StatusSummaryModel", back_populates="learner")
    task_progress = relationship("LearnerTaskProgressModel", back_populates="learner", cascade="all, delete-orphan")
    comments = relationship("CommentModel", back_populates="learner")
```

---

## 5. Submission

Learner's proof of work for a task.

### Pydantic Models

```python
class SubmissionType(str, Enum):
    """Type of submission content."""
    CODE = "code"
    SQL = "sql"
    JUPYTER_CELL = "jupyter_cell"
    TEXT = "text"
    RESULT_SET = "result_set"


class SubmissionBase(BaseModel):
    """Base submission fields."""
    submission_type: SubmissionType
    content: str = Field(..., min_length=1)


class SubmissionCreate(SubmissionBase):
    """Schema for creating a submission."""
    task_id: str
    learner_id: str


class Submission(SubmissionBase):
    """Complete submission entity."""
    model_config = ConfigDict(from_attributes=True)

    id: str
    task_id: str
    learner_id: str

    attempt_number: int = 1
    submitted_at: datetime


class SubmissionWithValidation(Submission):
    """Submission with its validation result."""
    validation: Optional["Validation"] = None
```

### SQLAlchemy Model

```python
class SubmissionModel(Base):
    __tablename__ = "submissions"

    id = Column(String, primary_key=True)
    task_id = Column(String, ForeignKey("tasks.id", ondelete="CASCADE"), nullable=False)
    learner_id = Column(String, ForeignKey("learners.id", ondelete="CASCADE"), nullable=False)

    submission_type = Column(String, nullable=False)
    content = Column(Text, nullable=False)
    attempt_number = Column(Integer, default=1)

    submitted_at = Column(DateTime(timezone=True), server_default=func.now())

    # Relationships
    task = relationship("TaskModel", back_populates="submissions")
    learner = relationship("LearnerModel", back_populates="submissions")
    validations = relationship("ValidationModel", back_populates="submission", cascade="all, delete-orphan")

    # Composite index for efficient lookups
    __table_args__ = (
        Index("idx_submissions_task_learner", "task_id", "learner_id"),
    )
```

---

## 6. Validation

Pass/fail result for a submission.

### Reference: Beads Validation Model

From [internal/types/types.go:885-896](../internal/types/types.go):
```go
type Validation struct {
    Validator *EntityRef
    Outcome   string     // accepted, rejected, revision_requested
    Timestamp time.Time
    Score     *float32   // Optional 0.0-1.0
}
```

### Pydantic Models

```python
class ValidatorType(str, Enum):
    """Type of validator that checked the submission."""
    AUTOMATED = "automated"  # System/test runner
    MANUAL = "manual"        # Human reviewer


class ValidationBase(BaseModel):
    """Base validation fields."""
    passed: bool
    error_message: Optional[str] = Field(
        default=None,
        description="Error details if validation failed"
    )
    validator_type: ValidatorType = Field(default=ValidatorType.AUTOMATED)


class ValidationCreate(ValidationBase):
    """Schema for creating a validation."""
    submission_id: str
    task_id: str


class Validation(ValidationBase):
    """Complete validation entity."""
    model_config = ConfigDict(from_attributes=True)

    id: str
    submission_id: str
    task_id: str
    validated_at: datetime
```

### SQLAlchemy Model

```python
class ValidationModel(Base):
    __tablename__ = "validations"

    id = Column(String, primary_key=True)
    submission_id = Column(String, ForeignKey("submissions.id", ondelete="CASCADE"), nullable=False)
    task_id = Column(String, ForeignKey("tasks.id", ondelete="CASCADE"), nullable=False)

    passed = Column(Boolean, nullable=False)
    error_message = Column(Text, nullable=True)
    validator_type = Column(String, default="automated")

    validated_at = Column(DateTime(timezone=True), server_default=func.now())

    # Relationships
    submission = relationship("SubmissionModel", back_populates="validations")
```

---

## 7. Acceptance Criterion

Structured validation rules for tasks.

### Pydantic Models

```python
class CriterionType(str, Enum):
    """Type of acceptance criterion."""
    CODE_TEST = "code_test"       # Automated code test
    SQL_RESULT = "sql_result"     # SQL query result check
    TEXT_MATCH = "text_match"     # Text/pattern matching
    MANUAL = "manual"             # Human review required


class AcceptanceCriterionBase(BaseModel):
    """Base acceptance criterion fields."""
    criterion_type: CriterionType
    description: str = Field(..., min_length=1)


class AcceptanceCriterionCreate(AcceptanceCriterionBase):
    """Schema for creating an acceptance criterion."""
    task_id: str


class AcceptanceCriterion(AcceptanceCriterionBase):
    """Complete acceptance criterion entity."""
    model_config = ConfigDict(from_attributes=True)

    id: str
    task_id: str
    created_at: datetime
```

### SQLAlchemy Model

```python
class AcceptanceCriterionModel(Base):
    __tablename__ = "acceptance_criteria"

    id = Column(String, primary_key=True)
    task_id = Column(String, ForeignKey("tasks.id", ondelete="CASCADE"), nullable=False, index=True)

    criterion_type = Column(String, nullable=False)
    description = Column(Text, nullable=False)

    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # Relationships
    task = relationship("TaskModel", back_populates="acceptance_criteria")
```

---

## 8. Status Summary

Versioned status updates and progress notes per learner per task.

### Pydantic Models

```python
class StatusSummaryBase(BaseModel):
    """Base status summary fields."""
    summary: str = Field(..., min_length=1)


class StatusSummaryCreate(StatusSummaryBase):
    """Schema for creating a status summary."""
    task_id: str
    learner_id: str


class StatusSummary(StatusSummaryBase):
    """Complete status summary entity."""
    model_config = ConfigDict(from_attributes=True)

    id: str
    task_id: str
    learner_id: str
    version: int = 1
    created_at: datetime
```

### SQLAlchemy Model

```python
class StatusSummaryModel(Base):
    __tablename__ = "status_summaries"

    id = Column(String, primary_key=True)
    task_id = Column(String, ForeignKey("tasks.id", ondelete="CASCADE"), nullable=False)
    learner_id = Column(String, ForeignKey("learners.id", ondelete="CASCADE"), nullable=False)

    summary = Column(Text, nullable=False)
    version = Column(Integer, default=1)

    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # Relationships
    task = relationship("TaskModel", back_populates="status_summaries")
    learner = relationship("LearnerModel", back_populates="status_summaries")

    # Composite index for efficient lookups
    __table_args__ = (
        Index("idx_status_summaries_task_learner", "task_id", "learner_id"),
    )
```

---

## 9. Content

Learning materials that can be attached to tasks.

### Pydantic Models

```python
class ContentType(str, Enum):
    """Type of learning content."""
    MARKDOWN = "markdown"
    CODE = "code"
    VIDEO_REF = "video_ref"
    EXTERNAL_LINK = "external_link"


class ContentBase(BaseModel):
    """Base content fields."""
    content_type: ContentType
    body: str
    metadata: dict = Field(default_factory=dict)


class ContentCreate(ContentBase):
    """Schema for creating content."""
    id: Optional[str] = None


class Content(ContentBase):
    """Complete content entity."""
    model_config = ConfigDict(from_attributes=True)

    id: str
    created_at: datetime
```

### SQLAlchemy Model

```python
class ContentModel(Base):
    __tablename__ = "content"

    id = Column(String, primary_key=True)
    content_type = Column(String, nullable=False)
    body = Column(Text, nullable=False)
    metadata = Column(Text, default="{}")  # JSON string

    created_at = Column(DateTime(timezone=True), server_default=func.now())
```

---

## 10. Comment

Feedback and discussion on tasks. Comments can be shared (visible to all learners) or private to a specific learner.

### Reference: Beads Comment Model

From [internal/types/types.go:607-614](../internal/types/types.go):
```go
type Comment struct {
    ID        int64
    IssueID   string
    Author    string
    Text      string
    CreatedAt time.Time
}
```

### Pydantic Models

```python
class CommentBase(BaseModel):
    """Base comment fields."""
    text: str = Field(..., min_length=1)
    author: str = Field(..., description="Author ID: learner_id, 'system', or 'tutor'")
    learner_id: Optional[str] = Field(
        default=None,
        description="If set, comment is private to this learner. If NULL, comment is shared/visible to all."
    )


class CommentCreate(CommentBase):
    """Schema for creating a comment."""
    task_id: str


class Comment(CommentBase):
    """Complete comment entity."""
    model_config = ConfigDict(from_attributes=True)

    id: str
    task_id: str
    created_at: datetime
```

### SQLAlchemy Model

```python
class CommentModel(Base):
    __tablename__ = "comments"

    id = Column(String, primary_key=True)
    task_id = Column(String, ForeignKey("tasks.id", ondelete="CASCADE"), nullable=False, index=True)
    learner_id = Column(String, ForeignKey("learners.id", ondelete="CASCADE"), nullable=True)

    author = Column(String, nullable=False)
    text = Column(Text, nullable=False)

    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # Relationships
    task = relationship("TaskModel", back_populates="comments")
    learner = relationship("LearnerModel", back_populates="comments")

    # Index for efficient learner-scoped queries
    __table_args__ = (
        Index("idx_comments_task_learner", "task_id", "learner_id"),
    )
```

---

## 11. Event (Audit Trail)

Record of all changes for debugging and history.

### Reference: Beads Event Model

From [internal/types/types.go:617-626](../internal/types/types.go):
```go
type Event struct {
    ID        int64
    IssueID   string
    EventType EventType
    Actor     string
    OldValue  *string
    NewValue  *string
    Comment   *string
    CreatedAt time.Time
}
```

### Pydantic Models

```python
class EventType(str, Enum):
    """Types of audit events."""
    CREATED = "created"
    UPDATED = "updated"
    STATUS_CHANGED = "status_changed"
    CLOSED = "closed"
    REOPENED = "reopened"
    DEPENDENCY_ADDED = "dependency_added"
    DEPENDENCY_REMOVED = "dependency_removed"
    COMMENT_ADDED = "comment_added"
    SUBMISSION_CREATED = "submission_created"
    VALIDATION_COMPLETED = "validation_completed"
    OBJECTIVE_ACHIEVED = "objective_achieved"


class EventBase(BaseModel):
    """Base event fields."""
    entity_type: str = Field(..., description="Type of entity: task, submission, session, etc.")
    entity_id: str
    event_type: EventType
    actor: str = Field(..., description="Who triggered the event")
    old_value: Optional[str] = None
    new_value: Optional[str] = None


class EventCreate(EventBase):
    """Schema for creating an event."""
    pass


class Event(EventBase):
    """Complete event entity."""
    model_config = ConfigDict(from_attributes=True)

    id: int
    created_at: datetime
```

### SQLAlchemy Model

```python
class EventModel(Base):
    __tablename__ = "events"

    id = Column(Integer, primary_key=True, autoincrement=True)
    entity_type = Column(String, nullable=False)
    entity_id = Column(String, nullable=False)
    event_type = Column(String, nullable=False)
    actor = Column(String, nullable=False)
    old_value = Column(Text, nullable=True)
    new_value = Column(Text, nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # Composite index for efficient entity lookups
    __table_args__ = (
        Index("idx_events_entity", "entity_type", "entity_id"),
    )
```

---

## 12. Task Context (Composite)

Not stored in DB - computed at runtime for agent. Session/conversation management is handled by LangGraph.

```python
from dataclasses import dataclass


@dataclass
class TaskContext:
    """
    Complete context loaded for a stateless agent.
    Computed from database, not persisted.

    Note: Session and conversation history are managed by LangGraph,
    not by this system.
    """
    # Current position
    current_task: Task
    task_ancestors: List[Task]  # [parent, grandparent, ..., project]

    # Task details
    learning_objectives: List[LearningObjective]
    acceptance_criteria: List[AcceptanceCriterion]
    task_content: Optional[str]

    # History for this learner
    submissions: List[Submission]
    latest_validation: Optional[Validation]
    status_summaries: List[StatusSummary]

    # Navigation
    ready_tasks: List[TaskSummary]  # in_progress first, then open
    blocked_by: List[TaskSummary]   # What's blocking current task
    children: List[TaskSummary]     # Child tasks

    # Progress
    project_progress: LearnerProgress
```

---

## 13. ID Generation

Following beads pattern for hierarchical, collision-free IDs.

### Reference: Beads ID Generation

From [internal/storage/sqlite/ids.go](../internal/storage/sqlite/ids.go):
- Root tasks get hash-based IDs: `prefix-xxxx`
- Child tasks get sequential IDs: `parent.N`

### Implementation

```python
import hashlib
from uuid import uuid4


def generate_task_id(
    parent_id: Optional[str],
    project_prefix: str,
    get_next_child_number: Callable[[str], int]
) -> str:
    """
    Generate a hierarchical task ID.

    Args:
        parent_id: ID of parent task, or None for root
        project_prefix: Prefix for project (e.g., "proj")
        get_next_child_number: Function to get next child counter for parent

    Returns:
        Hierarchical ID like "proj-a1b2" or "proj-a1b2.1.1"
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
        prefix: Entity type prefix (e.g., "sub", "val", "sess")

    Returns:
        ID like "sub-a1b2c3d4"
    """
    unique_bytes = uuid4().bytes
    hash_digest = hashlib.sha256(unique_bytes).hexdigest()[:8]
    return f"{prefix}-{hash_digest}"
```

---

## 14. Database Initialization

Complete Alembic migration for initial schema.

```python
# alembic/versions/001_initial_schema.py

from alembic import op
import sqlalchemy as sa


def upgrade():
    # Tasks table (template layer - no status, closed_at, close_reason)
    op.create_table(
        "tasks",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("parent_id", sa.String(), sa.ForeignKey("tasks.id", ondelete="CASCADE"), nullable=True),
        sa.Column("project_id", sa.String(), nullable=False),
        sa.Column("title", sa.String(500), nullable=False),
        sa.Column("description", sa.Text(), default=""),
        sa.Column("acceptance_criteria", sa.Text(), default=""),
        sa.Column("notes", sa.Text(), default=""),
        sa.Column("task_type", sa.String(), default="task"),
        sa.Column("priority", sa.Integer(), default=2),
        sa.Column("estimated_minutes", sa.Integer(), nullable=True),
        sa.Column("content", sa.Text(), nullable=True),
        sa.Column("content_refs", sa.ARRAY(sa.String()), default=[]),
        sa.Column("version", sa.Integer(), default=1),
        sa.Column("version_tag", sa.String(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("idx_tasks_parent", "tasks", ["parent_id"])
    op.create_index("idx_tasks_project", "tasks", ["project_id"])

    # Dependencies table
    op.create_table(
        "dependencies",
        sa.Column("task_id", sa.String(), sa.ForeignKey("tasks.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("depends_on_id", sa.String(), sa.ForeignKey("tasks.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("dependency_type", sa.String(), default="blocks"),
        sa.Column("metadata", sa.Text(), default="{}"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("created_by", sa.String(), nullable=True),
    )
    op.create_index("idx_deps_task", "dependencies", ["task_id"])
    op.create_index("idx_deps_depends_on", "dependencies", ["depends_on_id"])

    # Learning objectives table
    op.create_table(
        "learning_objectives",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("task_id", sa.String(), sa.ForeignKey("tasks.id", ondelete="CASCADE"), nullable=False),
        sa.Column("taxonomy", sa.String(), default="bloom"),
        sa.Column("level", sa.String(), nullable=True),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("idx_objectives_task", "learning_objectives", ["task_id"])

    # Learners table
    op.create_table(
        "learners",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("metadata", sa.Text(), default="{}"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    # Learner task progress table (instance layer)
    op.create_table(
        "learner_task_progress",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("task_id", sa.String(), sa.ForeignKey("tasks.id", ondelete="CASCADE"), nullable=False),
        sa.Column("learner_id", sa.String(), sa.ForeignKey("learners.id", ondelete="CASCADE"), nullable=False),
        sa.Column("status", sa.String(), nullable=False, default="open"),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("close_reason", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_unique_constraint("uq_task_learner_progress", "learner_task_progress", ["task_id", "learner_id"])
    op.create_index("idx_learner_task_progress_task_learner", "learner_task_progress", ["task_id", "learner_id"])
    op.create_index("idx_learner_task_progress_learner_status", "learner_task_progress", ["learner_id", "status"])

    # Submissions table
    op.create_table(
        "submissions",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("task_id", sa.String(), sa.ForeignKey("tasks.id", ondelete="CASCADE"), nullable=False),
        sa.Column("learner_id", sa.String(), sa.ForeignKey("learners.id", ondelete="CASCADE"), nullable=False),
        sa.Column("submission_type", sa.String(), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("attempt_number", sa.Integer(), default=1),
        sa.Column("submitted_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("idx_submissions_task_learner", "submissions", ["task_id", "learner_id"])

    # Validations table
    op.create_table(
        "validations",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("submission_id", sa.String(), sa.ForeignKey("submissions.id", ondelete="CASCADE"), nullable=False),
        sa.Column("task_id", sa.String(), sa.ForeignKey("tasks.id", ondelete="CASCADE"), nullable=False),
        sa.Column("passed", sa.Boolean(), nullable=False),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("validator_type", sa.String(), default="automated"),
        sa.Column("validated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    # Acceptance criteria table
    op.create_table(
        "acceptance_criteria",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("task_id", sa.String(), sa.ForeignKey("tasks.id", ondelete="CASCADE"), nullable=False),
        sa.Column("criterion_type", sa.String(), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("idx_acceptance_criteria_task", "acceptance_criteria", ["task_id"])

    # Status summaries table
    op.create_table(
        "status_summaries",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("task_id", sa.String(), sa.ForeignKey("tasks.id", ondelete="CASCADE"), nullable=False),
        sa.Column("learner_id", sa.String(), sa.ForeignKey("learners.id", ondelete="CASCADE"), nullable=False),
        sa.Column("summary", sa.Text(), nullable=False),
        sa.Column("version", sa.Integer(), default=1),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("idx_status_summaries_task_learner", "status_summaries", ["task_id", "learner_id"])

    # Content table
    op.create_table(
        "content",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("content_type", sa.String(), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("metadata", sa.Text(), default="{}"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    # Comments table (with optional learner_id for private comments)
    op.create_table(
        "comments",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("task_id", sa.String(), sa.ForeignKey("tasks.id", ondelete="CASCADE"), nullable=False),
        sa.Column("learner_id", sa.String(), sa.ForeignKey("learners.id", ondelete="CASCADE"), nullable=True),
        sa.Column("author", sa.String(), nullable=False),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("idx_comments_task_learner", "comments", ["task_id", "learner_id"])

    # Events table (audit trail)
    op.create_table(
        "events",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("entity_type", sa.String(), nullable=False),
        sa.Column("entity_id", sa.String(), nullable=False),
        sa.Column("event_type", sa.String(), nullable=False),
        sa.Column("actor", sa.String(), nullable=False),
        sa.Column("old_value", sa.Text(), nullable=True),
        sa.Column("new_value", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("idx_events_entity", "events", ["entity_type", "entity_id"])


def downgrade():
    op.drop_table("events")
    op.drop_table("comments")
    op.drop_table("content")
    op.drop_table("status_summaries")
    op.drop_table("acceptance_criteria")
    op.drop_table("validations")
    op.drop_table("submissions")
    op.drop_table("learner_task_progress")
    op.drop_table("learners")
    op.drop_table("learning_objectives")
    op.drop_table("dependencies")
    op.drop_table("tasks")
```

---

## 15. File Structure

Recommended organization for models:

```
src/
└── ltt/                          # Learning Task Tracker
    ├── __init__.py
    ├── models/
    │   ├── __init__.py           # Export all models
    │   ├── base.py               # SQLAlchemy Base, common utilities
    │   ├── task.py               # Task, TaskType, TaskStatus
    │   ├── learner_task_progress.py  # LearnerTaskProgress (instance layer)
    │   ├── dependency.py         # Dependency, DependencyType
    │   ├── learning.py           # LearningObjective, BloomLevel
    │   ├── learner.py            # Learner, LearnerProgress
    │   ├── submission.py         # Submission, SubmissionType
    │   ├── validation.py         # Validation, ValidatorType
    │   ├── acceptance_criterion.py  # AcceptanceCriterion, CriterionType
    │   ├── status_summary.py     # StatusSummary
    │   ├── content.py            # Content, ContentType
    │   ├── comment.py            # Comment
    │   ├── event.py              # Event, EventType
    │   └── context.py            # TaskContext (dataclass)
    ├── db/
    │   ├── __init__.py
    │   ├── connection.py         # Async engine, session factory
    │   └── migrations/           # Alembic migrations
    └── utils/
        ├── __init__.py
        └── ids.py                # ID generation utilities
```
