# Multi-Domain Extensibility

> How the project schema and platform extend beyond SQL to Python, data science, soft skills, and other learning domains.

---

## Design Philosophy: YAGNI with Clear Seams

**We are not building any of this yet.** This document identifies where the current schema has natural extension points so that when we add a new domain, we know exactly which fields to add and where. No speculative abstractions, no plugin frameworks — just a map of what would change.

The goal: a new project type (e.g., Python data science) should require **adding fields to the JSON schema and a new validator** — not restructuring the hierarchy or rewriting the tutor.

---

## The Current Model

Today LTT runs one project format well: **narrative-driven SQL exercises** with an AI tutor side panel. The Maji Ndogo water project is the reference implementation.

### What we have now

| Concept | Implementation | Extension point |
|---|---|---|
| Project identity | `project_id` (slug) + `version` + `version_tag` | Stable — same identity model for all domains |
| Project structure | Hierarchical: project → epic → task → subtask | Stable — works for all domains |
| Narrative framing | `narrative: true` + `narrative_context` at project level, story woven through epic `content` | `narrative: false` skips all of this |
| Tutor personality | `tutor_config` at project level (persona, teaching_style) | New `teaching_style` values per domain |
| Subtask types | `exercise` and `conversational` | New types slot in here |
| Submissions | Text strings (SQL queries) | New `submission_type` values |
| Validation | Binary pass/fail (non-empty check) | Validation strategy registry |
| Grading | Task-level `max_grade`, grade on submission | Stable — weighting is domain-agnostic |
| Workspace | `workspace_type: "sql"` on project | New workspace types |
| Subtask-level tutor hints | `tutor_guidance` dict (unstructured JSONB) | Domain-specific keys, same storage |

---

## Domain Profiles

### 1. SQL (current)

**Workspace**: sql.js in browser (WASM)
**Submission**: SQL query text → result set comparison
**Validation**: Can be exact (compare result sets) or semantic (LLM judges correctness)
**Tutor guidance focus**: `answer_rationale`, `hints_to_give`, `common_mistakes`

Already works. No changes needed.

### 2. Python / Data Science

**Workspace**: Pyodide in browser (WASM) — already designed in `WORKSPACE_EXTENSIONS.md`

**What changes**:
- **Submissions are richer**: Code + stdout + variable state + plot images
- **Validation needs output comparison**: "Does the DataFrame have 5 columns?", "Does the plot show a histogram?"
- **Multi-file context**: Learners build up a script across subtasks, each submission adds to the running state
- **Libraries matter**: Need to specify which Pyodide packages are available (pandas, matplotlib, scikit-learn)

**Schema extensions needed**:
```json
{
  "subtask_type": "exercise",
  "submission_type": "python",
  "validation_strategy": "output_check",
  "expected_output": {
    "variables": {"df_shape": [100, 5]},
    "stdout_contains": "accuracy: 0.9"
  },
  "workspace_context": {
    "packages": ["pandas", "matplotlib", "scikit-learn"],
    "preloaded_data": ["survey_data.csv"]
  }
}
```

**Tutor guidance additions**: `expected_approach` (e.g., "Should use groupby, not a loop"), `output_interpretation` (e.g., "The histogram should show a right-skewed distribution because...")

### 3. Cybersecurity / DevOps

**Workspace**: Server-side terminal (SSH to isolated VM) — per `WORKSPACE_EXTENSIONS.md`

**What changes**:
- **Submissions are terminal sessions**: Sequence of commands + their output
- **Validation is state-based**: "Is the firewall rule active?", "Does the user exist?", "Is port 443 open?"
- **Environment provisioning**: Each learner gets an isolated VM with specific pre-configured state
- **Time-boxed**: VMs have cost, sessions need limits
- **Destructive actions**: Learner might `rm -rf /` — need checkpoints/snapshots

**Schema extensions needed**:
```json
{
  "subtask_type": "exercise",
  "submission_type": "terminal_session",
  "validation_strategy": "state_check",
  "environment": {
    "base_image": "ubuntu-22.04-lab-3",
    "pre_state": "user 'alice' exists, nginx installed but misconfigured",
    "check_commands": [
      {"command": "systemctl is-active nginx", "expected": "active"},
      {"command": "curl -s localhost", "expected_contains": "Welcome"}
    ]
  }
}
```

### 4. Soft Skills / Leadership

**Workspace**: Chat-only (no code editor — just the AI tutor panel)

**What changes**:
- **No code submissions at all**: The "work" is the conversation itself
- **All subtasks are conversational or reflective**: Write a memo, discuss a scenario, role-play a difficult conversation
- **Validation is LLM-judged**: Did the learner demonstrate the competency? Rubric-based scoring
- **Submissions are long-form text**: Essays, reflections, case study analyses
- **Peer interaction possible**: "Review a classmate's leadership memo" (future)

**Schema extensions needed**:
```json
{
  "subtask_type": "reflection",
  "submission_type": "text",
  "validation_strategy": "rubric",
  "rubric": {
    "criteria": [
      {
        "name": "Problem identification",
        "description": "Correctly identifies the core leadership challenge",
        "max_points": 3
      },
      {
        "name": "Stakeholder awareness",
        "description": "Considers impact on all affected parties",
        "max_points": 2
      }
    ]
  },
  "tutor_guidance": {
    "teaching_approach": "Socratic — ask probing questions, never give the answer",
    "role_play_scenario": "You are a team lead whose senior engineer disagrees publicly",
    "debrief_prompts": ["What would you do differently?", "How did the other person likely feel?"]
  }
}
```

### 5. Design / UX

**Workspace**: Image upload + annotation viewer (or Figma embed)

**What changes**:
- **Submissions are images or URLs**: Wireframes, mockups, design system components
- **Validation is visual**: LLM with vision capability evaluates the design
- **Iteration-heavy**: Multiple rounds of feedback before "passing"

**Schema extensions needed**:
```json
{
  "subtask_type": "exercise",
  "submission_type": "image",
  "validation_strategy": "visual_review",
  "visual_criteria": [
    "Navigation is visible and follows mobile-first principles",
    "Color contrast meets WCAG AA standards",
    "Typography hierarchy is clear (h1 > h2 > body)"
  ]
}
```

### 6. Research / Analysis

**Workspace**: Document editor (markdown) + data sources

**What changes**:
- **Submissions are structured documents**: Reports with sections, citations, data tables
- **Validation is holistic**: Does the analysis address the question? Is evidence cited?
- **Multi-step**: Hypothesis → data gathering → analysis → conclusion
- **No single "right answer"**: Quality is on a spectrum

---

## What Needs to Change in the Schema

### New fields on subtasks

| Field | Type | Purpose |
|---|---|---|
| `subtask_type` | `exercise \| conversational \| reflection \| research` | Determines validation behavior and grade weight |
| `submission_type` | `sql \| python \| text \| terminal_session \| image \| url` | What the learner submits — drives UI and validation |
| `validation_strategy` | `auto \| output_check \| state_check \| rubric \| visual_review \| llm_judge` | How the submission is evaluated |
| `validation_config` | `dict` | Strategy-specific config (rubric criteria, expected output, check commands) |

### New fields on tasks

| Field | Type | Purpose |
|---|---|---|
| `max_grade` | `float` | Maximum grade points for this task's subtasks |

### New fields on projects

| Field | Type | Purpose |
|---|---|---|
| `workspace_type` | `str` | Default workspace — can be overridden per epic or task |
| `workspace_config` | `dict` | Workspace-specific setup (packages, datasets, VM image) |
| `grading_strategy` | `str` | How task grades aggregate to project grade |

### Workspace type inheritance

Workspace type should cascade down the hierarchy with override capability:

```
Project (workspace_type: "python")
  └── Epic 1 (inherits python)
      ├── Task 1 (inherits python)
      │   └── Subtask 1 (inherits python)
      └── Task 2 (workspace_type: "sql")  ← override
          └── Subtask 2 (uses sql)
```

This lets a data science project mix Python analysis tasks with SQL data exploration tasks.

---

## Subtask Type Taxonomy

The current binary (`exercise` / `conversational`) needs to expand:

| Type | Has submission | Has grade | Validation | Example |
|---|---|---|---|---|
| `exercise` | Yes — code/SQL/output | Yes | Auto or LLM | "Write a SELECT query" |
| `conversational` | No | No | Engagement-based | "Discuss the human impact" |
| `reflection` | Yes — text | Yes (rubric) | LLM rubric | "Write a memo to your manager" |
| `research` | Yes — document | Yes (rubric) | LLM rubric | "Analyze the dataset and write findings" |
| `peer_review` | Yes — feedback text | Yes (rubric) | LLM + peer | "Review a classmate's submission" |
| `portfolio` | Yes — artifact | Yes (rubric) | LLM or manual | "Submit your final project" |

For now, only `exercise` and `conversational` are implemented. The others follow the same pattern — they just need different validators and UI.

---

## Validation Strategy Registry

Instead of hardcoding validation logic, use a strategy pattern:

```python
VALIDATORS = {
    "auto": SimpleValidator,           # Non-empty check (current MVP)
    "output_check": OutputCheckValidator,  # Compare output to expected
    "state_check": StateCheckValidator,    # Run commands, check results
    "rubric": RubricValidator,             # LLM scores against criteria
    "visual_review": VisualReviewValidator, # LLM vision on images
    "llm_judge": LLMJudgeValidator,        # General LLM evaluation
}

async def validate_submission(submission, task):
    strategy = task.validation_strategy or "auto"
    validator = VALIDATORS[strategy]
    return await validator.validate(
        submission=submission,
        config=task.validation_config,
        acceptance_criteria=task.acceptance_criteria,
    )
```

The `validation_config` field on subtasks carries strategy-specific data:

```json
// For output_check:
{"variables": {"result": [1, 2, 3]}, "stdout_contains": "success"}

// For rubric:
{"criteria": [{"name": "Clarity", "max_points": 3}, ...]}

// For state_check:
{"check_commands": [{"command": "cat /etc/passwd", "expected_contains": "alice"}]}
```

---

## Tutor Guidance by Domain

The `tutor_guidance` dict is deliberately unstructured (JSONB), which is correct — different domains need different guidance. But documenting the common patterns helps project authors:

### SQL / Python exercises
```json
{
  "answer_rationale": "This query works because JOIN matches on foreign key...",
  "hints_to_give": ["Start with SELECT *", "Check the column names"],
  "common_mistakes": ["Forgetting GROUP BY with aggregates"],
  "teaching_approach": "Let them try first, then guide"
}
```

### Soft skills / leadership
```json
{
  "teaching_approach": "Socratic questioning — never give answers directly",
  "discussion_prompts": ["How would this affect team morale?"],
  "role_play_scenario": "You are delivering negative feedback to a high performer",
  "debrief_prompts": ["What did you notice about your emotional response?"],
  "competency_indicators": ["Shows empathy", "Addresses the issue directly"]
}
```

### Research / analysis
```json
{
  "teaching_approach": "Guide the methodology, not the conclusion",
  "analysis_framework": "Hypothesis → Evidence → Conclusion",
  "quality_indicators": ["Uses specific data points", "Acknowledges limitations"],
  "follow_up_questions": ["What would change your conclusion?"]
}
```

---

## Grading Across Domains

### Grade flow

```
Subtask submission → Validator scores (0.0 – 1.0) → Weighted by task max_grade
    → Task grade = sum(subtask_scores * weights)
    → Project grade = sum(task_grades) / sum(max_grades)
    → AGS passback to LMS
```

### Domain-specific considerations

| Domain | Grading approach | Notes |
|---|---|---|
| SQL | Auto (result set match) or LLM | Precise — query either works or doesn't |
| Python | Output check + LLM code review | Semi-precise — output matters, code quality is bonus |
| Cybersecurity | State check (automated) | Precise — system either configured correctly or not |
| Soft skills | Rubric (LLM-scored) | Subjective — rubric makes it consistent |
| Design | Visual review (LLM vision) | Subjective — criteria must be specific |
| Research | Rubric (LLM-scored) | Subjective — focus on methodology not conclusions |

### Conversational engagement tracking

Conversational subtasks don't have grade weight, but engagement should still be tracked:

- Did the learner respond substantively (not just "ok")?
- Did they engage with the discussion prompts?
- How many turns of dialogue before progressing?

This data is valuable for learning analytics even though it doesn't affect the grade.

---

## Implementation Priority

### Build now (current project needs these)

| What | Why |
|---|---|
| Add `subtask_type` to model/DB/ingest | Conversational vs exercise distinction — currently lost on ingest |
| Add `narrative` + `tutor_config` to project level | Project-level tutor behaviour — currently scattered or missing |
| Wire grade passback in submit flow | Grades should appear in LMS — infrastructure exists, just not called |
| Add `max_grade` to tasks + grade storage on validations | Weighted grading with local history |
| Pass `estimated_minutes` + epic `priority` through ingest | Currently dropped silently |

### Build when we need the second project type (not before)

| What | Triggered by |
|---|---|
| `submission_type` enum on subtasks | First Python project (submissions aren't just text) |
| `validation_strategy` + `validation_config` | First project needing non-trivial validation |
| Pyodide workspace | First Python/data science project |
| Rubric validator | First soft skills / research project |

### Build when there's a paying customer for it

| What | Triggered by |
|---|---|
| Terminal workspace (SSH to isolated VM) | Cybersecurity curriculum |
| Visual review validator (LLM vision) | Design/UX curriculum |
| Peer review mechanics | Collaborative learning requirements |
| Workspace type inheritance (override per epic/task) | Multi-language project |

---

## How to Add a New Project Type

When the time comes, here's the checklist. Everything else stays the same.

1. **Add a `workspace_type` value** — e.g., `"python"`. This drives which editor the frontend shows.
2. **Add a `submission_type` value** (if text isn't enough) — e.g., `"python"` for code + stdout + variables.
3. **Add a validator** — implement the `validate_submission()` interface for the new strategy.
4. **Add `tutor_guidance` conventions** — document which keys are meaningful for this domain (the field is unstructured JSONB, so no schema change needed).
5. **Create a reference project JSON** — like `water_analysis_project.json` is for SQL.
6. **Set `narrative: true/false`** — narrative framing is orthogonal to domain. A Python project can be narrative ("You're building a weather prediction model for farmers in Maji Ndogo") or purely technical.

The hierarchy (project → epic → task → subtask), the grading model (`max_grade` on tasks, grades on submissions), the dependency system, and the tutor config all stay exactly the same. The project JSON structure is stable — new domains add field values, not new structures.
