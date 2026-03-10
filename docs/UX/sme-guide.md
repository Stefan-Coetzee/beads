# SME & Mentor Guide -- Evaluating the Learning Task Tracker

> For subject-matter experts and mentors reviewing the AI-tutored learning experience.

---

## Purpose of This Test

We are testing whether an AI tutor, combined with a structured task framework, can facilitate a project-based learning experience **without the learner getting stuck**. You are helping us evaluate this before we release it to learners on the platform.

### Central Questions We're Trying to Answer

1. **Does the AI tutor say the right things?** -- Is the guidance accurate, pedagogically sound, and appropriate for the learner's level?
2. **Does it create productive friction?** -- Does the tutor ask questions and guide discovery rather than giving away answers?
3. **Can learners complete all tasks without getting stuck?** -- Are there dead-ends, confusing instructions, or places where the tutor fails to help?
4. **Does the end-to-end experience work?** -- Login, navigation, SQL editing, chat interaction, task progression.

---

## How the System Works

### Architecture at a Glance

```
Open edX (LMS)
    |
    | LTI 1.3 launch
    v
+-------------------+       +-------------------+
|   Next.js Frontend|<----->|  FastAPI Backend   |
|   (Workspace UI)  |       |  (API Server)     |
+-------------------+       +-------------------+
    |                            |          |
    | Browser-local              |          |
    | SQLite (sql.js)            v          v
    |                     LTT Core     Agent Tutor
    |                     (Task        (LangGraph +
    |                      Engine)      Claude AI)
    |                         |              |
    |                         v              v
    |                     PostgreSQL    MySQL (validation)
    |                     (state)      (read-only)
    +--- IndexedDB (cached DB)
```

**Key insight:** The SQL that learners write runs entirely in their browser (WebAssembly SQLite). The AI tutor has separate read-only access to a MySQL copy of the same database for validation purposes only.

### The Task Framework (LTT Core)

Projects are structured hierarchically:

```
Project
  Epic 1 (major topic area)
    Task 1.1
      Subtask 1.1.1 (atomic work item)
      Subtask 1.1.2
    Task 1.2
      ...
  Epic 2
    ...
```

Each subtask has:
- **Type:** `conversational` (discussion-based) or `exercise` (requires SQL)
- **Acceptance criteria:** What the learner must demonstrate
- **Learning objectives:** Bloom's taxonomy level (remember/understand/apply/analyze/evaluate/create)
- **Tutor guidance:** Teaching approach, hints (progressive), common mistakes, discussion prompts, answer rationale
- **Dependencies:** Tasks that must be completed first

**Status flow:** `open` -> `in_progress` -> `closed` (via formal submission)

Tasks are **templates** (shared across all learners). Progress is tracked **per-learner** in a separate table. This means 1,000 learners can work on the same project with fully independent progress.

### The AI Tutor -- Chidi Kunto

The tutor is a LangGraph ReAct agent powered by Claude (Anthropic). It plays a character: **Chidi Kunto**, a ~30-year-old senior data analyst at the Maji Ndogo water authority.

#### Teaching Approach

The system prompt enforces these pedagogical principles:
1. **Ask Before Telling** -- Respond with guiding questions, not direct answers
2. **Build on Prior Knowledge** -- Connect new concepts to what the learner knows
3. **Encourage Reflection** -- Ask learners to explain their thinking
4. **Celebrate Effort** -- Acknowledge the process, not just correctness
5. **Progressive Disclosure** -- Break complex topics into manageable chunks
6. **Never solve the problem** -- Guide the learner to solve it themselves

#### What the Tutor Can See

On every message, the tutor receives:
- The learner's chat message
- The current SQL code in the editor
- The current query results (as a formatted table)
- Full task context (description, acceptance criteria, tutor guidance, hints)
- Conversation history (persisted across sessions)

#### What the Tutor Can Do (Tools)

| Tool | Purpose |
|------|---------|
| `get_ready_tasks` | Get the next unblocked tasks |
| `start_task` | Begin a task (sets it to in_progress, loads context) |
| `submit` | Submit learner's work for validation and close the task |
| `get_context` | Get full task hierarchy and progress |
| `add_comment` / `get_comments` | Notes on tasks |
| `go_back` | Reopen a closed task |
| `request_help` | Flag for instructor help |
| `run_sql` | Execute a read-only SQL query for validation (NOT for demonstration) |

**Critical constraint:** The tutor is instructed to use `run_sql` **only** to validate learner work, never to explore the database or show example queries. This prevents the tutor from doing the learner's work.

#### Task Lifecycle (Enforced)

1. Tutor calls `start_task(task_id)` -- this is mandatory before any teaching
2. Tutor guides the learner through the task using the tutor guidance
3. Tutor calls `submit(task_id, content, type)` -- this is mandatory to close the task

"Verbal completion means nothing" -- without calling `submit`, the task is not formally complete. The system will not advance without it.

#### Tutor Guidance Per Task

Each task in the project JSON includes structured guidance:

```json
{
  "teaching_approach": "Start with real-world context before SQL",
  "discussion_prompts": ["What does 500 minutes mean in real life?"],
  "common_mistakes": ["Using = instead of >"],
  "hints_to_give": ["Try SHOW TABLES first", "Check column names"],
  "answer_rationale": "Explains WHY the answer works"
}
```

The tutor uses this guidance to:
- Frame the conversation appropriately
- Ask the right discussion questions
- Recognize and address common mistakes
- Deliver hints progressively (not all at once)
- Explain the reasoning behind correct answers

---

## The Maji Ndogo Project (What You'll Be Testing)

### Narrative

Learners are junior data analysts joining President Naledi's initiative to address Maji Ndogo's water crisis. They work through 60,000 survey records using SQL, guided by their mentor Chidi.

### Epic Structure

| Epic | Focus | Tasks |
|------|-------|-------|
| 1. Introduction | Story setup -- President's letter, meet Chidi, roadmap | 1 task, 3 subtasks (conversational) |
| 2. Get to Know Our Data | Table exploration -- `SHOW TABLES`, `SELECT`, foreign keys | 4 tasks with exercise subtasks |
| 3. Dive into the Sources | Water source type analysis | Multiple exercise subtasks |
| 4. Unpack the Visits | Visit frequency, queue times | Multiple exercise subtasks |
| 5. Assess Water Quality | Quality scores, frequently visited sources | Multiple exercise subtasks |
| 6. Investigate Pollution Issues | Contamination detection, data corrections | Multiple exercise subtasks |

### What a "Good" Interaction Looks Like

**Conversational subtask (Epic 1):**
- Chidi shares the president's letter
- Asks the learner to reflect on what the mission means
- Acknowledges the learner's response thoughtfully
- Submits the task when the learner has engaged meaningfully

**Exercise subtask (Epics 2-6):**
- Chidi introduces the task with context ("We need to understand what tables are in our database")
- Asks the learner what query they think they should write
- If the learner writes the wrong query, Chidi asks questions ("What does that column represent?") rather than giving the answer
- Delivers hints progressively if the learner is stuck
- When the learner gets the right result, Chidi submits the task and transitions to the next one

---

## What to Look For During Testing

### Tutor Quality

- [ ] Does Chidi introduce each task with appropriate context?
- [ ] Does Chidi ask guiding questions rather than giving answers?
- [ ] Are the hints progressive (getting more specific if the learner is stuck)?
- [ ] Does Chidi recognize common mistakes and address them?
- [ ] Does Chidi connect the SQL work back to the real-world narrative?
- [ ] Does Chidi formally submit tasks (not just say "great, you're done")?
- [ ] Is the teaching approach appropriate for the Bloom's taxonomy level of the task?

### Accuracy

- [ ] Are Chidi's SQL explanations correct?
- [ ] Does the expected SQL work against the provided database?
- [ ] Are the results Chidi describes consistent with what the database returns?
- [ ] Does the tutor correctly validate learner submissions?

### Flow and Pacing

- [ ] Does the tutor move at an appropriate pace?
- [ ] Are transitions between tasks smooth?
- [ ] Does the dependency ordering make sense (are prerequisites completed before dependent tasks)?
- [ ] Is there ever a dead-end where the learner can't progress?

### User Experience

- [ ] Can you log in and reach the workspace without issues?
- [ ] Does the SQL editor work (syntax highlighting, run query, results)?
- [ ] Does the chat work (send messages, receive responses, see task references)?
- [ ] Does the Overview page show accurate progress?
- [ ] Can you navigate between workspace and overview and back?

### Edge Cases to Try

- Give a completely wrong answer and see if Chidi handles it well
- Say "I don't understand" and see if Chidi simplifies
- Try to get Chidi to give you the direct answer
- Try to skip ahead to a later task
- Close the browser and return -- does your progress persist?
- Type something unrelated to the task and see how Chidi redirects

---

## Known Limitations

These are known issues, not things you need to report (but do note if they significantly impact the experience):

1. **"Open in Workspace" button** -- Opens the workspace but does not navigate to the specific task. The tutor manages task navigation through the conversation.
2. **Root page placeholder** -- The back arrow on the Project Overview goes to a placeholder page that says to access via LMS. This should be removed or redirected.
3. **SimpleValidator** -- The current validator only checks that submissions are non-empty. The tutor's own judgment is the real validation layer for now.
4. **Browser-local SQL** -- The SQL runs in SQLite in the browser, which may have minor syntax differences from the MySQL that the project was originally designed for (e.g., `SHOW TABLES` doesn't work in SQLite -- the tutor and content may need adjustment for this).

---

## Providing Feedback

After completing your review, please fill out the feedback questionnaire (link will be provided separately). Focus your written feedback on:

1. **Specific moments** where the tutor did something well or poorly (quote the exchange if possible)
2. **Tasks** where you got stuck or confused (reference the task ID, e.g., `maji-ndogo-part1.1.1.2`)
3. **Suggestions** for improving the tutor's guidance or the task content
