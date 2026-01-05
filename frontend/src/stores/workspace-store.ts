import { create } from "zustand";
import { persist } from "zustand/middleware";
import type { QueryResult } from "@/types";

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

  // Thread
  threadId: string | null;
  setThreadId: (threadId: string | null) => void;

  // Learner (temporary - would come from auth in production)
  learnerId: string;
  setLearnerId: (learnerId: string) => void;
}

export const useWorkspaceStore = create<WorkspaceState>()(
  persist(
    (set) => ({
      editorContent: "-- Write your SQL query here\nSELECT * FROM surveys LIMIT 10;",
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

      threadId: null,
      setThreadId: (threadId) => set({ threadId }),

      // Default learner ID for development
      learnerId: "learner-dev-001",
      setLearnerId: (learnerId) => set({ learnerId }),
    }),
    {
      name: "workspace-storage",
      partialize: (state) => ({
        editorContent: state.editorContent,
        learnerId: state.learnerId,
        threadId: state.threadId,
      }),
    }
  )
);
