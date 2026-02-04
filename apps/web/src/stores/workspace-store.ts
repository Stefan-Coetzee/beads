import { create } from "zustand";
import { persist } from "zustand/middleware";
import type { QueryResult, PythonResult, WorkspaceType } from "@/types";

// Bump this when default editor content changes to reset user's stored content
const EDITOR_SCHEMA_VERSION = 4;

const DEFAULT_SQL_CONTENT = `-- Write your SQL query here
-- Available tables: employee, location, water_source, visits, well_pollution, quality_score
SELECT * FROM visits LIMIT 10;`;

const DEFAULT_PYTHON_CONTENT = `# Write your Python code here
# Use print() to see output

print("Hello, World!")`;

interface WorkspaceState {
  // Schema version for migration
  schemaVersion: number;

  // Workspace type
  workspaceType: WorkspaceType;
  setWorkspaceType: (type: WorkspaceType) => void;

  // SQL Editor
  sqlContent: string;
  setSqlContent: (content: string) => void;
  queryResults: QueryResult | null;
  setQueryResults: (results: QueryResult | null) => void;

  // Python Editor
  pythonContent: string;
  setPythonContent: (content: string) => void;
  pythonResults: PythonResult | null;
  setPythonResults: (results: PythonResult | null) => void;
  isPythonReady: boolean;
  setIsPythonReady: (ready: boolean) => void;

  // Legacy alias for backward compatibility
  editorContent: string;
  setEditorContent: (content: string) => void;

  // Execution state
  isExecuting: boolean;
  setIsExecuting: (executing: boolean) => void;

  // Current Task
  currentTaskId: string | null;
  setCurrentTaskId: (taskId: string | null) => void;

  // Drawer
  drawerTaskId: string | null;
  openDrawer: (taskId: string) => void;
  closeDrawer: () => void;

  // Thread
  threadId: string | null;
  setThreadId: (threadId: string | null) => void;

  // Learner (temporary - would come from auth in production)
  learnerId: string;
  setLearnerId: (learnerId: string) => void;
}

export const useWorkspaceStore = create<WorkspaceState>()(
  persist(
    (set, get) => ({
      schemaVersion: EDITOR_SCHEMA_VERSION,

      // Workspace type
      workspaceType: "sql" as WorkspaceType,
      setWorkspaceType: (type) => set({ workspaceType: type }),

      // SQL Editor
      sqlContent: DEFAULT_SQL_CONTENT,
      setSqlContent: (content) => set({ sqlContent: content }),
      queryResults: null,
      setQueryResults: (results) => set({ queryResults: results }),

      // Python Editor
      pythonContent: DEFAULT_PYTHON_CONTENT,
      setPythonContent: (content) => set({ pythonContent: content }),
      pythonResults: null,
      setPythonResults: (results) => set({ pythonResults: results }),
      isPythonReady: false,
      setIsPythonReady: (ready) => set({ isPythonReady: ready }),

      // Legacy editorContent - defaults to SQL content for backward compatibility
      editorContent: DEFAULT_SQL_CONTENT,
      setEditorContent: (content) => set({ sqlContent: content }),

      // Execution state
      isExecuting: false,
      setIsExecuting: (executing) => set({ isExecuting: executing }),

      currentTaskId: null,
      setCurrentTaskId: (taskId) => set({ currentTaskId: taskId }),

      drawerTaskId: null,
      openDrawer: (taskId) => set({ drawerTaskId: taskId }),
      closeDrawer: () => set({ drawerTaskId: null }),

      threadId: null,
      setThreadId: (threadId) => set({ threadId }),

      // Default learner ID for development
      learnerId: "learner-dev-001",
      setLearnerId: (learnerId) => set({ learnerId }),
    }),
    {
      name: "workspace-storage",
      version: EDITOR_SCHEMA_VERSION,
      partialize: (state) => ({
        schemaVersion: state.schemaVersion,
        sqlContent: state.sqlContent,
        pythonContent: state.pythonContent,
        // Note: workspaceType is NOT persisted - it comes from the project/URL
        learnerId: state.learnerId,
        threadId: state.threadId,
      }),
      migrate: (persistedState: unknown, version: number) => {
        const state = persistedState as Partial<WorkspaceState> & { editorContent?: string };
        // Reset editor content if schema version changed
        if (version < EDITOR_SCHEMA_VERSION) {
          return {
            ...state,
            schemaVersion: EDITOR_SCHEMA_VERSION,
            sqlContent: DEFAULT_SQL_CONTENT,
            pythonContent: DEFAULT_PYTHON_CONTENT,
            workspaceType: "sql" as WorkspaceType,
            // Migrate old editorContent to sqlContent if it exists
            ...(state.editorContent && { sqlContent: state.editorContent }),
          };
        }
        return state as WorkspaceState;
      },
    }
  )
);
