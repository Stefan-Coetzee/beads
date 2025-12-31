# Pedagogical Guidance Fields - Enhancement Report

**Date**: 2025-12-31
**Enhancement**: Added `tutor_guidance` and `narrative_context` fields
**Impact**: Enables richer LLM tutoring strategies and real-world context

---

## Overview

Added two new pedagogical fields to enhance the tutoring experience:

1. **`tutor_guidance`** (Task/Subtask level) - Strategic tutoring guidance
2. **`narrative_context`** (Project level) - Real-world story/motivation

These fields provide meta-guidance to LLM tutors on HOW to teach, not just WHAT to teach.

---

## Field Specifications

### `tutor_guidance` (JSONB, optional)

**Purpose**: Guide LLM tutors on teaching strategies for this specific task.

**Structure**:
```json
{
  "teaching_approach": "Start with real-world context before SQL syntax",
  "discussion_prompts": [
    "What does 500 minutes mean in real life?",
    "Why might we want to filter by time spent?"
  ],
  "common_mistakes": [
    "Using = for pattern matching instead of LIKE",
    "Forgetting the % wildcards in LIKE queries"
  ],
  "hints_to_give": [
    "Try SHOW TABLES first to see what's available",
    "Look at the schema - what column contains time data?",
    "Remember LIKE uses % as a wildcard"
  ]
}
```

**All sub-fields are optional**. Use only what makes sense for the task.

### `narrative_context` (Text, optional)

**Purpose**: Provide real-world story that makes work meaningful.

**Example**:
```
"This data comes from President Naledi's water quality initiative. You are helping analyze survey data that will impact real communities in rural areas. The government will use your analysis to determine where to install new water purification systems."
```

**Characteristics**:
- Human-centered
- Shows real impact
- Motivates learners
- 2-4 sentences typically
- Used primarily at project level

---

## Database Changes

### Migration Created
**File**: `a3272ac954e2_add_tutor_guidance_and_narrative_.py`

**Changes**:
```sql
ALTER TABLE tasks ADD COLUMN tutor_guidance JSONB;
ALTER TABLE tasks ADD COLUMN narrative_context TEXT;
```

Both fields nullable (optional).

---

## Code Changes

### Models Updated
- **File**: `src/ltt/models/task.py`
- **Added**:
  - `tutor_guidance: dict | None` (Pydantic)
  - `narrative_context: str | None` (Pydantic)
  - `tutor_guidance: Mapped[dict | None] = mapped_column(JSONB, ...)` (SQLAlchemy)
  - `narrative_context: Mapped[str | None] = mapped_column(Text, ...)` (SQLAlchemy)

### Service Layer Updated

**task_service.py**:
- `create_task()` now includes `tutor_guidance` and `narrative_context` in TaskModel initialization

**ingest.py**:
- `ingest_project_file()` extracts `narrative_context` from project data
- `ingest_epic()` extracts `tutor_guidance` from epic data
- `ingest_task()` extracts `tutor_guidance` from task/subtask data

**export.py**:
- `export_project()` includes `narrative_context` if present
- `export_task_tree()` includes `tutor_guidance` if present

### Agent Tools Updated

**tools/schemas.py**:
- `TaskDetailOutput` now includes `tutor_guidance` and `narrative_context`

**tools/navigation.py**:
- `show_task()` returns both new fields in output

---

## Documentation Updated

### SCHEMA-FOR-LLM-INGESTION.md

Added comprehensive documentation:

#### `narrative_context` (Project Level)
- **What**: Real-world story or context
- **Why**: Motivates learners by connecting to real impact
- **Include**: Who benefits, real scenario, stakes, human element
- **Example**: Full water quality initiative example
- **Tone**: Engaging, human-centered

#### `tutor_guidance` (Task/Subtask Level)
- **What**: Strategic guidance for LLM tutor
- **Why**: Shapes tutoring approach and intervention strategy
- **Fields**:
  - `teaching_approach`: Overall strategy
  - `discussion_prompts`: Open-ended questions for thinking
  - `common_mistakes`: What learners typically get wrong
  - `hints_to_give`: Progressive hints (general to specific)
- **Use Cases**: Complex tasks where tutoring strategy matters
- **Example**: Complete SQL example with discussion prompts

#### Field Reference Schema
- Added `narrative_context` to project section
- Added `tutor_guidance` to task and subtask sections
- Included inline comments explaining purpose

---

## Test Coverage

### New Tests Added (5 total)

**test_ingest.py** (2 tests):
- `test_ingest_with_narrative_context` - Verifies project narrative_context import
- `test_ingest_with_tutor_guidance` - Verifies tutor_guidance at task and subtask levels

**test_export.py** (2 tests):
- `test_export_with_narrative_context` - Verifies narrative_context export
- `test_export_with_tutor_guidance` - Verifies tutor_guidance export with all sub-fields

**test_navigation.py** (1 test):
- `test_show_task_includes_tutor_guidance` - Verifies agent tools return new fields

---

## Usage Examples

### Example 1: Water Quality Project with Narrative

```json
{
  "title": "Analyze Water Access Data",
  "description": "Learn SQL by analyzing real water quality survey data",
  "narrative_context": "This data comes from President Naledi's water quality initiative. You are helping analyze survey data that will impact real communities in rural areas. The government will use your analysis to determine where to install new water purification systems.",
  "epics": [...]
}
```

**Impact**: Learner knows their work has real-world significance.

### Example 2: SQL Task with Tutor Guidance

```json
{
  "title": "Filter Long Queue Times",
  "description": "Write a WHERE clause to find queues over 500 minutes",
  "acceptance_criteria": "- Query returns only queues > 500 minutes\n- Uses correct column name\n- SQL syntax is valid",
  "tutor_guidance": {
    "teaching_approach": "Start with the real-world context before the SQL",
    "discussion_prompts": [
      "What does 500 minutes mean in real life? How many hours?",
      "What activities would someone miss while waiting?"
    ],
    "common_mistakes": [
      "Using = for pattern matching instead of LIKE",
      "Not checking column names with SHOW COLUMNS"
    ],
    "hints_to_give": [
      "Try SHOW TABLES first to see what's available",
      "Look at the schema - which column contains time data?",
      "Remember the > operator for numeric comparisons"
    ]
  }
}
```

**Impact**: LLM tutor knows to:
1. Start with human impact discussion
2. Watch for specific mistakes
3. Give progressive hints rather than answers

---

## Benefits for LLM Tutors

### Before (without tutor_guidance)
- Tutor relies on general teaching knowledge
- May not know common student mistakes for this specific task
- Might give hints in wrong order (too specific too fast)
- No guidance on preferred teaching approach

### After (with tutor_guidance)
- Tutor has task-specific teaching strategy
- Knows exactly what mistakes to watch for and prevent
- Can provide progressive hints (stored in order)
- Can use discussion prompts to promote deeper thinking

### Before (without narrative_context)
- Project feels like abstract exercise
- Learner doesn't know why it matters
- Motivation comes only from learning itself

### After (with narrative_context)
- Work feels meaningful and impactful
- Learner understands real-world application
- Motivation enhanced by knowing people benefit

---

## Integration Points

### Ingestion
- Fields parsed from JSON during `ingest_project_file()`
- Included in roundtrip (export → import → same data)
- Validated as part of structure validation

### Export
- Fields included in JSON/JSONL export
- Preserved in backups
- Enables project sharing with full pedagogical context

### Agent Tools
- `show_task()` returns `tutor_guidance` for current task
- `get_context()` includes `narrative_context` from project
- LLM agents can access and use this guidance

### Database
- JSONB type for `tutor_guidance` (flexible structure)
- Text type for `narrative_context` (narrative content)
- Nullable (optional enrichment)
- Indexed for efficient queries

---

## Implementation Statistics

- **Models Updated**: 1 (task.py)
- **Migrations Created**: 1
- **Services Updated**: 3 (task_service, ingest, export)
- **Agent Tools Updated**: 2 (schemas, navigation)
- **Tests Added**: 5
- **Documentation Updated**: 1 major file (SCHEMA-FOR-LLM-INGESTION.md)
- **Total Tests**: 167 (all passing)
- **Ruff Errors**: 0

---

## Example: Complete Water Quality Subtask

```json
{
  "title": "Filter surveys by queue time",
  "description": "Write a WHERE clause to find all surveys where people waited more than 500 minutes (8+ hours) to collect water.",

  "acceptance_criteria": "- Query returns only surveys with queue_time > 500\n- Uses correct column name (queue_time)\n- SQL syntax is valid\n- Query can be executed without errors",

  "learning_objectives": [
    {"level": "apply", "description": "Apply WHERE clause for numeric filtering"},
    {"level": "understand", "description": "Understand comparison operators in SQL"}
  ],

  "content": "## WHERE Clause Basics\n\nThe WHERE clause filters rows based on conditions:\n```sql\nSELECT * FROM surveys WHERE queue_time > 500;\n```\n\n### Comparison Operators\n- `>` greater than\n- `<` less than\n- `=` equals\n- `>=` greater than or equal\n- `<=` less than or equal\n- `<>` not equal",

  "tutor_guidance": {
    "teaching_approach": "Start with the human impact, then introduce the technical solution. Ask what 500 minutes feels like before showing SQL syntax.",

    "discussion_prompts": [
      "500 minutes is over 8 hours. What does it mean to wait 8+ hours just for water?",
      "What daily activities would you miss while waiting?",
      "How would this affect children getting to school? Parents working?"
    ],

    "common_mistakes": [
      "Using quotes around numbers (queue_time > '500' instead of queue_time > 500)",
      "Using = instead of > (finding exact 500, not 'more than')",
      "Misspelling column name (queuetime vs queue_time)"
    ],

    "hints_to_give": [
      "First, what column contains the wait time data? Try SHOW COLUMNS FROM surveys;",
      "We want times GREATER than 500. Which SQL operator means 'greater than'?",
      "Numbers in SQL don't need quotes. Compare: queue_time > 500"
    ]
  }
}
```

**With this enriched task**:
1. Learner understands real human impact (narrative_context from project)
2. Tutor starts with discussion, not code (teaching_approach)
3. Tutor asks about human impact before syntax (discussion_prompts)
4. Tutor watches for specific errors (common_mistakes)
5. Tutor gives structured hints (hints_to_give)

**Result**: Deeper learning, better motivation, more effective tutoring.

---

## Future Enhancements

### Tutor Guidance Extensions
- **`scaffolding_level`**: How much structure to provide (high/medium/low)
- **`socratic_depth`**: How many questions before giving answer (1-5)
- **`prerequisite_checks`**: Verify understanding before proceeding
- **`reflection_prompts`**: Post-completion reflection questions

### Narrative Context Extensions
- **`stakeholders`**: List of people/groups affected
- **`impact_metrics`**: Quantified impact (e.g., "affects 50,000 people")
- **`multimedia_refs`**: Videos, images showing real-world context

---

## Completion Status

✅ All functionality implemented
✅ All tests passing (167 total)
✅ Documentation comprehensive
✅ Ruff linting clean
✅ Migration applied
✅ Roundtrip tested (export → import)

**Ready for production use with enriched pedagogical guidance.**
