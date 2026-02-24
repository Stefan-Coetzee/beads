/**
 * Tests for the Zustand workspace store.
 */

import { describe, it, expect, beforeEach } from "vitest";
import { useWorkspaceStore } from "./workspace-store";

// Reset store state between tests
beforeEach(() => {
  useWorkspaceStore.setState(useWorkspaceStore.getInitialState());
});

describe("workspace store initial state", () => {
  it("defaults workspaceType to sql", () => {
    expect(useWorkspaceStore.getState().workspaceType).toBe("sql");
  });

  it("has default SQL content", () => {
    expect(useWorkspaceStore.getState().sqlContent).toContain("SELECT");
  });

  it("has default Python content", () => {
    expect(useWorkspaceStore.getState().pythonContent).toContain("print");
  });

  it("defaults queryResults to null", () => {
    expect(useWorkspaceStore.getState().queryResults).toBeNull();
  });

  it("defaults pythonResults to null", () => {
    expect(useWorkspaceStore.getState().pythonResults).toBeNull();
  });

  it("defaults currentTaskId to null", () => {
    expect(useWorkspaceStore.getState().currentTaskId).toBeNull();
  });

  it("defaults isExecuting to false", () => {
    expect(useWorkspaceStore.getState().isExecuting).toBe(false);
  });
});

describe("workspace store setters", () => {
  it("setWorkspaceType updates workspaceType", () => {
    useWorkspaceStore.getState().setWorkspaceType("python");
    expect(useWorkspaceStore.getState().workspaceType).toBe("python");
  });

  it("setSqlContent updates sqlContent", () => {
    useWorkspaceStore.getState().setSqlContent("SELECT 1;");
    expect(useWorkspaceStore.getState().sqlContent).toBe("SELECT 1;");
  });

  it("setPythonContent updates pythonContent", () => {
    useWorkspaceStore.getState().setPythonContent("x = 42");
    expect(useWorkspaceStore.getState().pythonContent).toBe("x = 42");
  });

  it("setQueryResults updates queryResults", () => {
    const result = { success: true, columns: ["a"], rows: [[1]], rowCount: 1, duration: 10 };
    useWorkspaceStore.getState().setQueryResults(result);
    expect(useWorkspaceStore.getState().queryResults).toEqual(result);
  });

  it("setPythonResults updates pythonResults", () => {
    const result = { success: true, output: "hi", duration: 5 };
    useWorkspaceStore.getState().setPythonResults(result);
    expect(useWorkspaceStore.getState().pythonResults).toEqual(result);
  });

  it("setCurrentTaskId updates currentTaskId", () => {
    useWorkspaceStore.getState().setCurrentTaskId("proj-abc.1.1");
    expect(useWorkspaceStore.getState().currentTaskId).toBe("proj-abc.1.1");
  });

  it("setIsExecuting updates isExecuting", () => {
    useWorkspaceStore.getState().setIsExecuting(true);
    expect(useWorkspaceStore.getState().isExecuting).toBe(true);
  });

  it("setThreadId updates threadId", () => {
    useWorkspaceStore.getState().setThreadId("thread-abc");
    expect(useWorkspaceStore.getState().threadId).toBe("thread-abc");
  });
});

describe("workspace store drawer", () => {
  it("openDrawer sets drawerTaskId", () => {
    useWorkspaceStore.getState().openDrawer("proj-abc.1");
    expect(useWorkspaceStore.getState().drawerTaskId).toBe("proj-abc.1");
  });

  it("closeDrawer sets drawerTaskId to null", () => {
    useWorkspaceStore.getState().openDrawer("proj-abc.1");
    useWorkspaceStore.getState().closeDrawer();
    expect(useWorkspaceStore.getState().drawerTaskId).toBeNull();
  });
});

describe("workspace store legacy alias", () => {
  it("setEditorContent updates sqlContent", () => {
    useWorkspaceStore.getState().setEditorContent("SELECT 42;");
    expect(useWorkspaceStore.getState().sqlContent).toBe("SELECT 42;");
  });
});
