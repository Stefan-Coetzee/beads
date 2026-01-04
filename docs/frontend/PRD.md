# Learning Workspace Frontend — Product Requirements Document

> A project-based learning environment where learners collaborate with an AI tutor to navigate tasks, write code, and receive real-time feedback.

---

## 1. Vision & Aesthetic Direction

### Core Concept
**"The Focused Craftsperson's Workshop"** — A workspace that feels like a high-end digital studio. Clean, purposeful, with deliberate moments of delight. The interface should convey competence and encourage deep work, not overwhelm with options.

### Design Philosophy
- **Editorial Minimalism**: Generous whitespace, strong typography hierarchy, intentional color restraint
- **Dark Mode Primary**: A sophisticated dark theme that reduces eye strain during extended coding sessions
- **Subtle Depth**: Layered surfaces with soft shadows and blurred backgrounds create spatial hierarchy
- **Accent Color Strategy**: A single vibrant accent color (amber/gold: `#F59E0B`) used sparingly for progress, active states, and success moments
- **Motion with Purpose**: Micro-interactions that confirm actions, not distract from them

### Typography
- **Display/Headers**: `JetBrains Mono` — Monospace with character, readable at all sizes
- **Body/UI**: `Inter` — Clean, professional, excellent for dense information (or `IBM Plex Sans` for more personality)
- **Code**: `Fira Code` with ligatures enabled — Makes code feel crafted

### Color Palette
```css
/* Dark Theme (Primary) */
--bg-deepest:    #0A0A0B;     /* True background */
--bg-surface:    #141415;     /* Card/panel surfaces */
--bg-elevated:   #1C1C1E;     /* Elevated elements, hover states */
--border-subtle: #2A2A2D;     /* Borders, dividers */
--text-primary:  #FAFAFA;     /* Primary text */
--text-secondary: #A1A1AA;    /* Secondary/muted text */
--text-tertiary: #71717A;     /* Disabled, hints */

/* Semantic */
--accent:        #F59E0B;     /* Amber - progress, active, success */
--accent-muted:  #78350F;     /* Amber dark - backgrounds */
--success:       #22C55E;     /* Green - validations passed */
--warning:       #EAB308;     /* Yellow - in progress */
--error:         #EF4444;     /* Red - failed validations */
--info:          #3B82F6;     /* Blue - informational */

/* Task Status Colors */
--status-open:       #71717A;
--status-in-progress: #F59E0B;
--status-blocked:    #EF4444;
--status-closed:     #22C55E;
```

---

## 2. Application Architecture

### Pages
1. **Project Overview** (`/project/:projectId`) — Homepage showing hierarchical task structure with learner progress
2. **Workspace** (`/workspace/:projectId`) — Split-pane coding environment with AI copilot

### Tech Stack Recommendations

| Layer | Recommendation | Rationale |
|-------|---------------|-----------|
| **Framework** | **Next.js 14+ (App Router)** | RSC for fast initial loads, built-in routing, API routes if needed |
| **Styling** | **Tailwind CSS + shadcn/ui** | Utility-first with pre-built accessible components |
| **State Management** | **Zustand** | Minimal boilerplate, perfect for IDE state |
| **Chat Interface** | **AI SDK by Vercel** (ai package) | Built-in streaming, message management, hooks |
| **SQL Editor** | **SQL.js** + **CodeMirror 6** | In-browser SQLite, professional code editing |
| **Code Editor** | **CodeMirror 6** or **Monaco Editor** | SQL highlighting, autocomplete |
| **Task Panel** | **Vaul** (drawer) | Smooth slide-over panels like Jira |
| **Data Fetching** | **TanStack Query** | Caching, background refetch, optimistic updates |
| **Icons** | **Lucide React** | Consistent, lightweight icon set |

### Project Structure
```
frontend/
├── app/
│   ├── layout.tsx              # Root layout with providers
│   ├── page.tsx                # Landing/redirect
│   ├── project/
│   │   └── [projectId]/
│   │       └── page.tsx        # Project Overview
│   └── workspace/
│       └── [projectId]/
│           └── page.tsx        # Workspace
│
├── components/
│   ├── ui/                     # shadcn/ui primitives
│   ├── project/
│   │   ├── TaskTree.tsx        # Hierarchical task display
│   │   ├── TaskTreeNode.tsx    # Single expandable node
│   │   ├── ProgressBar.tsx     # Visual progress indicator
│   │   └── StatusBadge.tsx     # Task status pills
│   ├── workspace/
│   │   ├── WorkspaceLayout.tsx # Split pane container
│   │   ├── SqlEditor.tsx       # SQL code editor
│   │   ├── ResultsPanel.tsx    # Query output display
│   │   └── EditorTabs.tsx      # Multiple editor support
│   ├── chat/
│   │   ├── ChatPanel.tsx       # Main chat container
│   │   ├── MessageList.tsx     # Message display
│   │   ├── MessageBubble.tsx   # Individual message
│   │   ├── TaskReference.tsx   # Clickable task IDs in messages
│   │   └── ChatInput.tsx       # Message composition
│   └── shared/
│       ├── TaskDetailDrawer.tsx # Slide-over task details
│       ├── Header.tsx          # App header
│       └── Sidebar.tsx         # Navigation sidebar
│
├── hooks/
│   ├── useChat.ts              # Chat state & API integration
│   ├── useSqlExecution.ts      # SQL.js execution
│   ├── useProject.ts           # Project data fetching
│   └── useTaskProgress.ts      # Learner progress state
│
├── lib/
│   ├── api.ts                  # API client configuration
│   ├── sql-engine.ts           # SQL.js initialization
│   └── utils.ts                # Utility functions
│
├── stores/
│   ├── workspace-store.ts      # Editor state, tabs, results
│   └── drawer-store.ts         # Task drawer state
│
└── types/
    └── index.ts                # Shared TypeScript types
```

---

## 3. Page 1: Project Overview

### URL Pattern
`/project/:projectId?learnerId=:learnerId`

### Purpose
Allow learners to visualize their position in the project, see overall progress, and navigate to specific tasks.

### Layout
```
┌─────────────────────────────────────────────────────────────────┐
│  HEADER: Project Title          Progress: 23/42 (54%)    [→]   │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  Project Description / Narrative Context                        │
│  "You've been assigned to analyze water quality data..."        │
│                                                                 │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  ▼ Epic 1: Data Foundation                         ████░░ 67%  │
│    ├─ ▼ Task 1.1: Database Setup                      ✓ done   │
│    │    ├─ Subtask 1.1.1: Create tables               ✓ done   │
│    │    └─ Subtask 1.1.2: Import data                 ✓ done   │
│    ├─ ● Task 1.2: Basic Queries              ◐ in progress     │
│    │    ├─ Subtask 1.2.1: SELECT basics               ✓ done   │
│    │    ├─ Subtask 1.2.2: WHERE clauses        ● in progress   │
│    │    └─ Subtask 1.2.3: Aggregations              ○ open     │
│    └─ ○ Task 1.3: Data Validation                     ○ open   │
│                                                                 │
│  ▶ Epic 2: Analysis (collapsed)                    ░░░░░░ 0%   │
│  ▶ Epic 3: Reporting (collapsed)                   ░░░░░░ 0%   │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

### Components

#### TaskTree
- Recursive tree structure mirroring the hierarchical data
- Expand/collapse animations using `framer-motion` or CSS transitions
- Visual indentation with connecting lines (like a file tree)
- Status icons and colors coded by task status

#### TaskTreeNode
```tsx
interface TaskTreeNodeProps {
  task: TaskSummary;
  progress: TaskProgress;
  children?: TaskTreeNode[];
  depth: number;
  onTaskClick: (taskId: string) => void;
}
```

Features:
- Click to expand/collapse children
- Click task title to open detail drawer
- Hover to show quick actions (start task, view details)
- Progress bar for parent nodes showing child completion

#### ProgressBar
- Animated fill on progress changes
- Segment visualization for multiple children
- Tooltip showing exact counts

### API Calls Required

```typescript
// Get full project hierarchy with learner progress
GET /api/v1/project/{projectId}/tree?learnerId={learnerId}

Response: {
  project: {
    id: string;
    title: string;
    description: string;
    narrative_context: string;
  };
  hierarchy: TaskNode[]; // Nested structure
  progress: {
    total_tasks: number;
    completed_tasks: number;
    in_progress: number;
    blocked: number;
    percentage: number;
  };
}

interface TaskNode {
  id: string;
  title: string;
  task_type: 'epic' | 'task' | 'subtask';
  status: 'open' | 'in_progress' | 'blocked' | 'closed';
  priority: number;
  children: TaskNode[];
  progress?: {  // For parents
    completed: number;
    total: number;
  };
}
```

### New Backend Endpoint Needed
The existing API has individual task queries but needs a consolidated endpoint for the tree view:

```python
# src/api/routes.py - ADD THIS

@router.get("/project/{project_id}/tree")
async def get_project_tree(
    project_id: str,
    learner_id: str = Query(..., description="Learner ID")
):
    """Get full project hierarchy with learner-specific progress."""
    # Use task_service.get_task() for root
    # Use task_service.get_children(recursive=True) for hierarchy
    # Join with learner_task_progress for status
    # Aggregate child progress for parent nodes
```

---

## 4. Page 2: Workspace

### URL Pattern
`/workspace/:projectId?learnerId=:learnerId&taskId=:taskId`

### Purpose
The primary learning environment. Learners code, execute queries, and receive AI guidance.

### Layout (Resizable Split Panes)
```
┌─────────────────────────────────────────────────────────────────────────┐
│  HEADER: Task 1.2.2 — WHERE Clauses      [📋 Overview] [🔄 Reset]      │
├────────────────────────────────────┬────────────────────────────────────┤
│                                    │                                    │
│  CODE EDITOR                       │  CHAT PANEL                        │
│  ┌──────────────────────────────┐  │  ┌──────────────────────────────┐  │
│  │ -- Find surveys > 500 mins  │  │  │ TUTOR:                       │  │
│  │ SELECT *                     │  │  │ Great! Now let's find        │  │
│  │ FROM surveys                 │  │  │ surveys where queue_time     │  │
│  │ WHERE queue_time > 500;      │  │  │ exceeds 500 minutes.         │  │
│  │                              │  │  │                              │  │
│  │                              │  │  │ Try writing a SELECT with    │  │
│  │                              │  │  │ a WHERE clause!              │  │
│  │                              │  │  │                              │  │
│  └──────────────────────────────┘  │  │ [Task 1.2.2] ← clickable     │  │
│  [▶ Run Query]  [Clear]            │  │                              │  │
│                                    │  │ ─────────────────────────    │  │
│  RESULTS PANEL                     │  │ YOU:                         │  │
│  ┌──────────────────────────────┐  │  │ I wrote the query, is this   │  │
│  │ survey_id │ location │ time │  │  │ correct?                     │  │
│  │───────────┼──────────┼──────│  │  │                              │  │
│  │ 1042      │ North    │ 612  │  │  │ [📎 Code attached]           │  │
│  │ 1089      │ South    │ 534  │  │  │                              │  │
│  │ 1156      │ Central  │ 589  │  │  └──────────────────────────────┘  │
│  └──────────────────────────────┘  │                                    │
│  3 rows returned (12ms)            │  ┌──────────────────────────────┐  │
│                                    │  │ Type your message...     [→] │  │
│                                    │  └──────────────────────────────┘  │
└────────────────────────────────────┴────────────────────────────────────┘
```

### Components

#### WorkspaceLayout
- Uses `react-resizable-panels` for drag-to-resize split panes
- Persists panel sizes to localStorage
- Responsive: stacks vertically on mobile

```tsx
import { Panel, PanelGroup, PanelResizeHandle } from 'react-resizable-panels';

function WorkspaceLayout() {
  return (
    <PanelGroup direction="horizontal">
      <Panel defaultSize={50} minSize={30}>
        <EditorPane />
      </Panel>
      <PanelResizeHandle className="w-2 bg-border hover:bg-accent transition-colors" />
      <Panel defaultSize={50} minSize={30}>
        <ChatPane />
      </Panel>
    </PanelGroup>
  );
}
```

#### SqlEditor (CodeMirror 6)
```tsx
import { sql, SQLite } from '@codemirror/lang-sql';
import { oneDark } from '@codemirror/theme-one-dark';
import CodeMirror from '@uiw/react-codemirror';

function SqlEditor({ value, onChange, onRun }) {
  return (
    <div className="flex flex-col h-full">
      <CodeMirror
        value={value}
        height="100%"
        theme={oneDark}
        extensions={[sql({ dialect: SQLite })]}
        onChange={onChange}
        basicSetup={{
          lineNumbers: true,
          highlightActiveLineGutter: true,
          foldGutter: true,
          autocompletion: true,
        }}
      />
      <div className="flex gap-2 p-2 border-t border-border">
        <Button onClick={onRun} size="sm">
          <Play className="w-4 h-4 mr-1" /> Run Query
        </Button>
        <kbd className="text-xs text-muted-foreground">Ctrl+Enter</kbd>
      </div>
    </div>
  );
}
```

#### ResultsPanel
- Data grid for query results using `@tanstack/react-table`
- Shows execution time, row count
- Error display for failed queries
- Empty state with helpful messaging

#### ChatPanel (AI SDK Integration)

Using Vercel's AI SDK for streaming chat:

```tsx
import { useChat } from 'ai/react';

function ChatPanel({ learnerId, projectId, editorContent, queryResults }) {
  const { messages, input, handleInputChange, handleSubmit, isLoading } = useChat({
    api: '/api/chat',
    body: {
      learner_id: learnerId,
      project_id: projectId,
      // Send current IDE state with each message
      context: {
        editor_content: editorContent,
        query_results: queryResults,
      },
    },
  });

  return (
    <div className="flex flex-col h-full">
      <MessageList messages={messages} />
      <ChatInput
        value={input}
        onChange={handleInputChange}
        onSubmit={handleSubmit}
        isLoading={isLoading}
      />
    </div>
  );
}
```

#### TaskReference (Clickable Task IDs)
Parse messages for task ID patterns and render as interactive elements:

```tsx
function TaskReference({ taskId, onClick }) {
  return (
    <button
      onClick={() => onClick(taskId)}
      className="inline-flex items-center px-2 py-0.5 rounded bg-accent/10
                 text-accent hover:bg-accent/20 transition-colors font-mono text-sm"
    >
      <Hash className="w-3 h-3 mr-1" />
      {taskId}
    </button>
  );
}

// Message parsing utility
function parseTaskReferences(content: string): (string | TaskRefNode)[] {
  const taskIdPattern = /\b(proj-[a-z0-9]+(?:\.\d+)+)\b/gi;
  // Split and map to components
}
```

#### TaskDetailDrawer (Vaul)
Slide-over panel showing full task details when clicking a task reference:

```tsx
import { Drawer } from 'vaul';

function TaskDetailDrawer({ taskId, open, onClose }) {
  const { data: task } = useQuery(['task', taskId], () => fetchTaskDetails(taskId));

  return (
    <Drawer.Root open={open} onOpenChange={onClose}>
      <Drawer.Portal>
        <Drawer.Overlay className="fixed inset-0 bg-black/40" />
        <Drawer.Content className="fixed right-0 top-0 bottom-0 w-[400px] bg-surface">
          <div className="p-6">
            <StatusBadge status={task.status} />
            <h2 className="text-xl font-semibold mt-2">{task.title}</h2>
            <p className="text-muted-foreground mt-2">{task.description}</p>

            <section className="mt-6">
              <h3 className="text-sm font-medium text-muted-foreground">
                Acceptance Criteria
              </h3>
              <div className="mt-2 prose prose-sm prose-invert">
                <ReactMarkdown>{task.acceptance_criteria}</ReactMarkdown>
              </div>
            </section>

            <section className="mt-6">
              <h3 className="text-sm font-medium text-muted-foreground">
                Learning Objectives
              </h3>
              <ul className="mt-2 space-y-2">
                {task.learning_objectives.map(obj => (
                  <li key={obj.id} className="flex items-start gap-2">
                    <BloomBadge level={obj.level} />
                    <span>{obj.description}</span>
                  </li>
                ))}
              </ul>
            </section>
          </div>
        </Drawer.Content>
      </Drawer.Portal>
    </Drawer.Root>
  );
}
```

### SQL.js Integration

Initialize SQL.js with a pre-loaded database:

```typescript
// lib/sql-engine.ts
import initSqlJs, { Database } from 'sql.js';

let db: Database | null = null;

export async function initDatabase(dataUrl?: string): Promise<Database> {
  const SQL = await initSqlJs({
    locateFile: file => `https://sql.js.org/dist/${file}`
  });

  if (dataUrl) {
    // Load pre-existing database file
    const response = await fetch(dataUrl);
    const buffer = await response.arrayBuffer();
    db = new SQL.Database(new Uint8Array(buffer));
  } else {
    db = new SQL.Database();
  }

  return db;
}

export function executeQuery(sql: string): QueryResult {
  if (!db) throw new Error('Database not initialized');

  const startTime = performance.now();
  try {
    const results = db.exec(sql);
    const duration = performance.now() - startTime;

    return {
      success: true,
      columns: results[0]?.columns || [],
      rows: results[0]?.values || [],
      rowCount: results[0]?.values.length || 0,
      duration,
    };
  } catch (error) {
    return {
      success: false,
      error: error.message,
      duration: performance.now() - startTime,
    };
  }
}
```

### Sending Context to LLM

The key requirement is that the LLM always knows what the learner sees. Modify the chat API call:

```typescript
// hooks/useWorkspaceChat.ts
import { useChat } from 'ai/react';
import { useWorkspaceStore } from '@/stores/workspace-store';

export function useWorkspaceChat(learnerId: string, projectId: string) {
  const { editorContent, queryResults, currentTaskId } = useWorkspaceStore();

  return useChat({
    api: `${process.env.NEXT_PUBLIC_API_URL}/api/v1/chat`,
    body: {
      learner_id: learnerId,
      project_id: projectId,
    },
    // Append context to every message
    onFinish: () => {},
    experimental_prepareRequestBody: ({ messages }) => {
      // Add current workspace state as system context
      const contextMessage = {
        role: 'system',
        content: `
Current workspace state:
- Task: ${currentTaskId}
- Editor content:
\`\`\`sql
${editorContent}
\`\`\`
- Last query result: ${JSON.stringify(queryResults, null, 2)}
        `.trim(),
      };

      return {
        messages: [contextMessage, ...messages],
        learner_id: learnerId,
        project_id: projectId,
      };
    },
  });
}
```

---

## 5. State Management

### Workspace Store (Zustand)

```typescript
// stores/workspace-store.ts
import { create } from 'zustand';
import { persist } from 'zustand/middleware';

interface WorkspaceState {
  // Editor
  editorContent: string;
  setEditorContent: (content: string) => void;

  // Query Results
  queryResults: QueryResult | null;
  setQueryResults: (results: QueryResult | null) => void;
  isExecuting: boolean;
  setIsExecuting: (executing: boolean) => void;

  // Current Task
  currentTaskId: string | null;
  setCurrentTaskId: (taskId: string | null) => void;

  // Drawer
  drawerTaskId: string | null;
  openDrawer: (taskId: string) => void;
  closeDrawer: () => void;
}

export const useWorkspaceStore = create<WorkspaceState>()(
  persist(
    (set) => ({
      editorContent: '',
      setEditorContent: (content) => set({ editorContent: content }),

      queryResults: null,
      setQueryResults: (results) => set({ queryResults: results }),
      isExecuting: false,
      setIsExecuting: (executing) => set({ isExecuting: executing }),

      currentTaskId: null,
      setCurrentTaskId: (taskId) => set({ currentTaskId: taskId }),

      drawerTaskId: null,
      openDrawer: (taskId) => set({ drawerTaskId: taskId }),
      closeDrawer: () => set({ drawerTaskId: null }),
    }),
    {
      name: 'workspace-storage',
      partialize: (state) => ({
        editorContent: state.editorContent,
      }),
    }
  )
);
```

---

## 6. API Client Configuration

```typescript
// lib/api.ts
import { QueryClient } from '@tanstack/react-query';

export const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

export const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 1000 * 60, // 1 minute
      retry: 1,
    },
  },
});

// Type-safe API functions
export const api = {
  // Project
  getProjectTree: async (projectId: string, learnerId: string) => {
    const res = await fetch(
      `${API_BASE_URL}/api/v1/project/${projectId}/tree?learner_id=${learnerId}`
    );
    if (!res.ok) throw new Error('Failed to fetch project tree');
    return res.json();
  },

  // Tasks
  getTaskDetails: async (taskId: string, learnerId: string) => {
    const res = await fetch(
      `${API_BASE_URL}/api/v1/task/${taskId}?learner_id=${learnerId}`
    );
    if (!res.ok) throw new Error('Failed to fetch task');
    return res.json();
  },

  // Progress
  startTask: async (taskId: string, learnerId: string) => {
    const res = await fetch(`${API_BASE_URL}/api/v1/task/${taskId}/start`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ learner_id: learnerId }),
    });
    if (!res.ok) throw new Error('Failed to start task');
    return res.json();
  },

  // Submissions
  submitWork: async (taskId: string, learnerId: string, content: string, type: string) => {
    const res = await fetch(`${API_BASE_URL}/api/v1/task/${taskId}/submit`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        learner_id: learnerId,
        content,
        submission_type: type,
      }),
    });
    if (!res.ok) throw new Error('Failed to submit');
    return res.json();
  },
};
```

---

## 7. Backend Modifications Required

### New Endpoints Needed

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/api/v1/project/{id}/tree` | GET | Full hierarchy with progress |
| `/api/v1/task/{id}` | GET | Task details for drawer |
| `/api/v1/task/{id}/start` | POST | Start task (transition to in_progress) |
| `/api/v1/task/{id}/submit` | POST | Submit work for validation |
| `/api/v1/chat/context` | POST | Chat with workspace context |

### Modifications to Existing `/api/v1/chat`

The current chat endpoint needs to accept additional context:

```python
class ChatRequest(BaseModel):
    message: str
    learner_id: str
    project_id: str
    thread_id: str | None = None
    # NEW: Workspace context
    context: dict | None = Field(None, description="Current workspace state")

# In the chat handler, inject context into the agent's system prompt
```

### Database Initialization Endpoint

For SQL.js, we need to provide the database schema and sample data:

```
GET /api/v1/project/{id}/database
Returns: SQLite database file binary or SQL initialization script
```

---

## 8. Package Dependencies

### Frontend (`package.json`)

```json
{
  "dependencies": {
    "next": "^14.0.0",
    "react": "^18.2.0",
    "react-dom": "^18.2.0",

    "ai": "^3.0.0",
    "@tanstack/react-query": "^5.0.0",
    "zustand": "^4.4.0",

    "@uiw/react-codemirror": "^4.21.0",
    "@codemirror/lang-sql": "^6.5.0",
    "@codemirror/theme-one-dark": "^6.1.0",

    "sql.js": "^1.8.0",

    "react-resizable-panels": "^2.0.0",
    "vaul": "^0.9.0",

    "@radix-ui/react-accordion": "^1.1.0",
    "@radix-ui/react-dialog": "^1.0.0",
    "@radix-ui/react-tooltip": "^1.0.0",

    "lucide-react": "^0.300.0",
    "clsx": "^2.0.0",
    "tailwind-merge": "^2.0.0",

    "@tanstack/react-table": "^8.10.0",
    "react-markdown": "^9.0.0"
  },
  "devDependencies": {
    "typescript": "^5.3.0",
    "tailwindcss": "^3.4.0",
    "@types/react": "^18.2.0",
    "@types/node": "^20.0.0"
  }
}
```

---

## 9. Implementation Phases

### Phase 1: Project Setup & Core Infrastructure
- [ ] Initialize Next.js project with TypeScript
- [ ] Configure Tailwind CSS with custom theme
- [ ] Set up shadcn/ui components
- [ ] Create API client with TanStack Query
- [ ] Implement Zustand stores

### Phase 2: Project Overview Page
- [ ] Build TaskTree component with expand/collapse
- [ ] Create TaskTreeNode with status indicators
- [ ] Implement progress bars and badges
- [ ] Add task click → drawer behavior
- [ ] Backend: Add `/project/{id}/tree` endpoint

### Phase 3: Workspace — Editor Pane
- [ ] Set up CodeMirror 6 with SQL mode
- [ ] Initialize SQL.js with sample database
- [ ] Build ResultsPanel with data grid
- [ ] Add query execution (Ctrl+Enter)
- [ ] Backend: Add database initialization endpoint

### Phase 4: Workspace — Chat Pane
- [ ] Integrate AI SDK useChat hook
- [ ] Build MessageList and MessageBubble
- [ ] Implement task reference parsing
- [ ] Add context injection to API calls
- [ ] Backend: Modify chat endpoint for context

### Phase 5: Task Detail Drawer
- [ ] Build drawer using Vaul
- [ ] Show task details, acceptance criteria
- [ ] Display learning objectives with Bloom levels
- [ ] Add "Start Task" action button
- [ ] Backend: Add task detail endpoint

### Phase 6: Polish & Integration
- [ ] Add loading states and skeletons
- [ ] Implement error boundaries
- [ ] Add keyboard shortcuts
- [ ] Test responsive behavior
- [ ] Performance optimization

---

## 10. UX Considerations

### Keyboard Shortcuts
| Shortcut | Action |
|----------|--------|
| `Ctrl+Enter` | Execute SQL query |
| `Ctrl+/` | Toggle comment |
| `Escape` | Close drawer |
| `Ctrl+K` | Focus chat input |

### Loading States
- Skeleton loaders for task tree
- Pulsing indicator while query executes
- Streaming text animation for AI responses

### Error Handling
- Toast notifications for transient errors
- Inline error messages in results panel
- Retry buttons for failed API calls

### Accessibility
- ARIA labels on all interactive elements
- Focus management for drawer
- High contrast mode support
- Screen reader announcements for status changes

---

## 11. Future Considerations (Out of Scope for V1)

- **Kanban Board**: Visual epic/task board view
- **Python/JavaScript Terminals**: Using WebContainers or Pyodide
- **Multi-file Editor**: Tabs for multiple SQL files
- **Collaborative Features**: Real-time presence, shared cursors
- **Authentication**: User accounts, OAuth
- **Progress Persistence**: Sync workspace state to backend
- **Mobile Optimization**: Touch-friendly interactions

---

## Appendix A: Existing API Reference

### Current Endpoints (from `src/api/routes.py`)

```
POST /api/v1/chat
  Request: { message, learner_id, project_id, thread_id? }
  Response: { response, thread_id, tool_calls? }

POST /api/v1/chat/stream
  Request: Same as above
  Response: SSE stream of { type, content }

POST /api/v1/session
  Request: { learner_id, project_id }
  Response: { session_id, learner_id, project_id }

GET /api/v1/session/{session_id}/state
  Response: { session_id, status }

GET /health
  Response: { status: "healthy" }
```

### Agent Tools Available (from `src/ltt/tools/schemas.py`)

The LLM agent has access to these tools which can be called during chat:
- `get_ready`: Get unblocked tasks for learner
- `show_task`: Get detailed task info
- `get_context`: Get full context for a task
- `start_task`: Begin working on a task
- `submit`: Submit work for validation
- `add_comment`: Add comment to task
- `get_comments`: Retrieve task comments
- `go_back`: Reopen a closed task
- `request_help`: Flag task for help

---

## Appendix B: Design Mockup Specifications

### Task Status Badge Variants
```css
.status-badge {
  @apply inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium;
}
.status-open { @apply bg-zinc-700 text-zinc-300; }
.status-in-progress { @apply bg-amber-500/20 text-amber-400; }
.status-blocked { @apply bg-red-500/20 text-red-400; }
.status-closed { @apply bg-green-500/20 text-green-400; }
```

### Tree Node Depth Styling
```css
.tree-node {
  padding-left: calc(var(--depth) * 1.5rem);
  border-left: 2px solid var(--border-subtle);
}
.tree-node:hover {
  background: var(--bg-elevated);
}
```

### Results Table Styling
```css
.results-table {
  @apply w-full text-sm font-mono;
}
.results-table th {
  @apply text-left p-2 bg-surface border-b border-border text-muted-foreground;
}
.results-table td {
  @apply p-2 border-b border-border/50;
}
.results-table tr:hover td {
  @apply bg-elevated;
}
```
