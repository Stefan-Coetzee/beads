# Learner Guide -- Maji Ndogo Water Analysis

> Your step-by-step guide to completing the Maji Ndogo project using the Learning Task Tracker.

---

## What You'll Be Doing

You are a junior data analyst joining Maji Ndogo's water authority. President Naledi has tasked the team with solving a nationwide water crisis using survey data from 60,000 records. Your mentor **Chidi Kunto** (an AI tutor) will guide you through the project, one task at a time.

You'll write SQL queries in a browser-based editor, discuss your findings with Chidi, and work through 6 epics covering data exploration, analysis, and problem-solving.

**Estimated time:** ~5 hours (you can stop and resume at any time -- your progress is saved).

---

## Getting Started

### Step 1: Log into Open edX

1. Go to the Open edX instance URL provided to you
2. Log in with the credentials you received
3. You should already be enrolled in the course

### Step 2: Navigate to the Activity

1. Once logged in, find the **course** in your dashboard
2. Navigate to the correct **module** and **activity**
3. The LTI activity will load inline on the page -- this is the Learning Task Tracker

### Step 3: The Workspace Loads

When the activity loads, you'll land on the **SQL Workspace** -- a split-screen interface:

```
+-----------------------------+-------------------------+
|                             |                         |
|   SQL Editor (top-left)     |   AI Chat (right)       |
|   Write your queries here   |   Talk to Chidi here    |
|                             |                         |
+-----------------------------+                         |
|                             |                         |
|   Results (bottom-left)     |                         |
|   Query output appears here |                         |
|                             |                         |
+-----------------------------+-------------------------+
```

**First load:** The database (~10 MB) will download and prepare itself. You'll see a progress bar. This only happens once -- subsequent visits load instantly.

---

## The Workspace

### SQL Editor (top-left)

- Write SQL queries in the editor
- Click **Run Query** (play button) or press **Ctrl+Enter** / **Cmd+Enter** to execute
- Click **Clear** (trash icon) to clear the editor
- Queries run against a local SQLite copy of the Maji Ndogo database

**Available tables:** `employee`, `location`, `water_source`, `visits`, `well_pollution`, `quality_score`

### Results Panel (bottom-left)

- After running a query, results appear as a table below the editor
- Green header = success (shows row count and execution time)
- Red header = error (shows the error message)
- Results scroll horizontally if there are many columns

### AI Chat -- Chidi Kunto (right)

This is where you interact with your AI tutor. Chidi can:
- See your SQL code in the editor
- See your query results
- Guide you through each task
- Ask you questions to deepen your understanding
- Give you hints when you're stuck

**How to use the chat:**
1. Type your message in the input box at the bottom
2. Press **Enter** or click the **Send** button
3. Chidi will respond with guidance, questions, or next steps

**Important:** Chidi teaches using a Socratic approach -- he'll ask questions and give hints rather than giving you direct answers. This is intentional. Working through the problem yourself builds deeper understanding.

### Header Buttons

| Button | Icon | What it does |
|--------|------|--------------|
| **Back arrow** | Arrow left | Go to the Project Overview page |
| **Reset DB** | Database icon | Re-download and rebuild the SQL database (use if data seems wrong) |
| **Overview** | Book icon | Go to the Project Overview page |

---

## The Project Overview Page

Click the **back arrow** or **Overview** button to see the full project:

- **Progress bar** -- your overall completion percentage
- **Status counts** -- green (completed), amber (in progress), red (blocked)
- **Narrative context** -- background story for the project
- **Task tree** -- the full hierarchical list of epics, tasks, and subtasks

### Browsing Tasks

Click any task in the tree to open a **detail panel** on the right showing:
- Task description and acceptance criteria
- Learning objectives
- Hints (if available)
- Dependencies (what you need to complete first)
- An **"Open in Workspace"** button to go back to the workspace

---

## How to Complete Tasks

### The Workflow

1. **Chidi starts a task** -- When you begin the project (or finish a task), Chidi will introduce the next task and set it to "in progress"
2. **Read and discuss** -- For conversational tasks, Chidi will share context (e.g., a letter from President Naledi) and discuss it with you
3. **Write and run SQL** -- For exercise tasks, write the query Chidi is guiding you toward. Run it and share your results
4. **Chidi submits your work** -- When you've met the acceptance criteria, Chidi will formally submit and close the task
5. **Move to the next task** -- Chidi will introduce what's next

### Types of Tasks

- **Conversational** -- Discussion-based. Read content, answer Chidi's questions, reflect on concepts
- **Exercise** -- Hands-on SQL. Write queries, examine results, iterate until correct

### Tips for Working with Chidi

- **Ask questions freely** -- If something is unclear, just ask
- **Share your thinking** -- "I think I need a WHERE clause because..." helps Chidi guide you better
- **Don't worry about getting it wrong** -- Chidi will help you iterate. Errors are part of learning
- **Follow Chidi's lead** -- He knows the task order and will guide the progression
- **If you're stuck**, tell Chidi: "I'm stuck" or "Can you give me a hint?" -- he has progressive hints for each task

### What "Done" Means

A task is only complete when Chidi formally submits it. Just saying "I'm done" or having the right answer in your editor isn't enough -- Chidi needs to verify your work and call the submit function. He'll let you know when a task is closed.

---

## Troubleshooting

| Problem | Solution |
|---------|----------|
| Page shows "Access this tool through your learning management system" | You need to access via Open edX, not directly. Go back to the course. |
| Database is loading for a long time | The first download is ~10 MB. Wait for the progress bar to complete. On slow connections this may take a minute. |
| Query is running forever | Your query may have an infinite loop or be very expensive. After 10 seconds it will time out automatically. Try adding `LIMIT 10` to your query. |
| Chat isn't responding | Wait a moment -- the AI may take a few seconds to think. If it persists, try the **Reset** button on the chat panel. |
| Results look wrong or database seems corrupted | Click **Reset DB** in the header to re-download a fresh copy. |
| Lost your place in the project | Click **Overview** to see your progress and find where you left off. |
| Task says "blocked" | You need to complete prerequisite tasks first. Chidi will guide you to them. |

---

## Quick Reference

| Action | How |
|--------|-----|
| Run a query | Ctrl+Enter (or Cmd+Enter on Mac) |
| Clear the editor | Click the trash icon |
| See project progress | Click the Overview (book) button |
| View a task's details | Click it in the task tree on the Overview page |
| Get back to the workspace | Click "Open in Workspace" in a task's detail panel |
| Reset the conversation | Click the Reset (circular arrow) button on the chat panel |
| Reset the database | Click the Reset DB button in the workspace header |
