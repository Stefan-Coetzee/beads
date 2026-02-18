"use client";

import { useParams, useSearchParams } from "next/navigation";
import { useEffect, useCallback } from "react";
import Link from "next/link";
import { Panel, Group as PanelGroup, Separator as PanelResizeHandle } from "react-resizable-panels";
import { ArrowLeft, BookOpen, RefreshCw, AlertTriangle } from "lucide-react";

import { Button } from "@/components/ui/button";
import { SqlEditor } from "@/components/workspace/SqlEditor";
import { ResultsPanel } from "@/components/workspace/ResultsPanel";
import { PythonEditor } from "@/components/workspace/PythonEditor";
import { PythonResultsPanel } from "@/components/workspace/PythonResultsPanel";
import { ChatPanel } from "@/components/chat/ChatPanel";
import { TaskDetailDrawer } from "@/components/shared/TaskDetailDrawer";
import { useWorkspaceStore } from "@/stores/workspace-store";
import type { QueryResult, WorkspaceType } from "@/types";

// SQL engine - only imported when needed
import {
  executeQuery,
  isDatabaseReady,
  loadMajiNdogoDatabase,
} from "@/lib/sql-engine";

// Python engine - only imported when needed
import {
  executePython,
  initPythonEngine,
  isPythonReady,
  resetPythonEnvironment,
} from "@/lib/python-engine";

export default function WorkspacePage() {
  const params = useParams();
  const searchParams = useSearchParams();
  const projectId = params.projectId as string;
  const learnerId = searchParams.get("learnerId") || "learner-dev-001";
  const initialTaskId = searchParams.get("taskId");

  // Workspace type MUST be explicitly set via URL param - no defaults
  const workspaceType = searchParams.get("type") as WorkspaceType | null;

  const {
    setWorkspaceType,
    sqlContent,
    setSqlContent,
    queryResults,
    setQueryResults,
    pythonContent,
    setPythonContent,
    pythonResults,
    setPythonResults,
    isPythonReady: pythonReady,
    setIsPythonReady,
    isExecuting,
    setIsExecuting,
    currentTaskId,
    setCurrentTaskId,
    drawerTaskId,
    openDrawer,
    closeDrawer,
  } = useWorkspaceStore();

  // Set workspace type in store from URL param
  useEffect(() => {
    if (workspaceType) {
      setWorkspaceType(workspaceType);
    }
  }, [workspaceType, setWorkspaceType]);

  // Initialize SQL database ONLY when type=sql
  useEffect(() => {
    if (workspaceType !== "sql") return; // Guard: only for SQL workspace

    async function initSql() {
      if (!isDatabaseReady()) {
        try {
          await loadMajiNdogoDatabase();
          console.log("[SQL] Database initialized with Maji Ndogo data");
        } catch (e) {
          console.error("[SQL] Failed to load database:", e);
        }
      }
    }
    initSql();
  }, [workspaceType]);

  // Initialize Python engine ONLY when type=python
  useEffect(() => {
    if (workspaceType !== "python") return; // Guard: only for Python workspace

    async function initPython() {
      if (!isPythonReady()) {
        try {
          await initPythonEngine();
          setIsPythonReady(true);
          console.log("[Python] Engine initialized");
        } catch (e) {
          console.error("[Python] Failed to initialize:", e);
        }
      }
    }
    initPython();
  }, [workspaceType, setIsPythonReady]);

  // Set initial task if provided
  useEffect(() => {
    if (initialTaskId) {
      setCurrentTaskId(initialTaskId);
    }
  }, [initialTaskId, setCurrentTaskId]);

  // Handle SQL query execution
  const handleRunQuery = useCallback(() => {
    if (!sqlContent.trim()) return;

    setIsExecuting(true);

    setTimeout(() => {
      const result = executeQuery(sqlContent);
      setQueryResults(result as QueryResult);
      setIsExecuting(false);
    }, 100);
  }, [sqlContent, setIsExecuting, setQueryResults]);

  // Handle Python code execution
  const handleRunPython = useCallback(async () => {
    if (!pythonContent.trim()) return;

    setIsExecuting(true);

    try {
      const result = await executePython(pythonContent);
      setPythonResults(result);
    } catch (e) {
      setPythonResults({
        success: false,
        error: e instanceof Error ? e.message : "Execution failed",
        duration: 0,
      });
    } finally {
      setIsExecuting(false);
    }
  }, [pythonContent, setIsExecuting, setPythonResults]);

  // Handle task click from chat
  const handleTaskClick = useCallback(
    (taskId: string) => {
      openDrawer(taskId);
    },
    [openDrawer]
  );

  // Reset SQL database
  const handleResetDatabase = useCallback(async () => {
    await loadMajiNdogoDatabase(true);
    setQueryResults(null);
  }, [setQueryResults]);

  // Reset Python environment
  const handleResetPython = useCallback(async () => {
    await resetPythonEnvironment();
    setPythonResults(null);
  }, [setPythonResults]);

  // Get current editor content for chat context
  const currentEditorContent = workspaceType === "python" ? pythonContent : sqlContent;

  // Error state: no workspace type specified
  if (!workspaceType) {
    return (
      <div className="h-screen flex flex-col items-center justify-center bg-background">
        <AlertTriangle className="h-12 w-12 text-yellow-500 mb-4" />
        <h1 className="text-xl font-semibold mb-2">Workspace Type Required</h1>
        <p className="text-muted-foreground mb-4">
          Please specify a workspace type in the URL: ?type=sql or ?type=python
        </p>
        <Link href={`/project/${projectId}?learnerId=${learnerId}`}>
          <Button>Back to Project</Button>
        </Link>
      </div>
    );
  }

  return (
    <div className="h-screen flex flex-col bg-background">
      {/* Header */}
      <header className="flex items-center justify-between px-4 py-3 border-b border-border">
        <div className="flex items-center gap-4">
          <Link href={`/project/${projectId}?learnerId=${learnerId}`}>
            <Button variant="ghost" size="icon">
              <ArrowLeft className="h-4 w-4" />
            </Button>
          </Link>
          <div>
            <h1 className="font-semibold">
              {workspaceType === "python" ? "Python Workspace" : "SQL Workspace"}
            </h1>
            {currentTaskId && (
              <button
                onClick={() => openDrawer(currentTaskId)}
                className="text-sm text-muted-foreground hover:text-accent transition-colors"
              >
                {currentTaskId}
              </button>
            )}
          </div>
        </div>
        <div className="flex items-center gap-2">
          {workspaceType === "sql" && (
            <Button variant="ghost" size="sm" onClick={handleResetDatabase}>
              <RefreshCw className="h-4 w-4 mr-1" />
              Reset DB
            </Button>
          )}
          {workspaceType === "python" && (
            <Button variant="ghost" size="sm" onClick={handleResetPython}>
              <RefreshCw className="h-4 w-4 mr-1" />
              Reset Env
            </Button>
          )}
          <Link href={`/project/${projectId}?learnerId=${learnerId}`}>
            <Button variant="outline" size="sm">
              <BookOpen className="h-4 w-4 mr-1" />
              Overview
            </Button>
          </Link>
        </div>
      </header>

      {/* Main Content */}
      <main className="flex-1 overflow-hidden">
        <PanelGroup orientation="horizontal" className="h-full">
          {/* Left Panel - Editor & Results */}
          <Panel defaultSize={55} minSize={35}>
            <div className="h-full flex flex-col p-4 gap-4">
              {/* Editor - conditionally render based on workspace type */}
              <div className="flex-1 min-h-0">
                {workspaceType === "python" ? (
                  <PythonEditor
                    value={pythonContent}
                    onChange={setPythonContent}
                    onRun={handleRunPython}
                    onReset={handleResetPython}
                    isExecuting={isExecuting}
                    isReady={pythonReady}
                  />
                ) : (
                  <SqlEditor
                    value={sqlContent}
                    onChange={setSqlContent}
                    onRun={handleRunQuery}
                    isExecuting={isExecuting}
                  />
                )}
              </div>

              {/* Results Panel - conditionally render based on workspace type */}
              <div className="flex-1 min-h-0">
                {workspaceType === "python" ? (
                  <PythonResultsPanel result={pythonResults} isExecuting={isExecuting} />
                ) : (
                  <ResultsPanel result={queryResults} isExecuting={isExecuting} />
                )}
              </div>
            </div>
          </Panel>

          {/* Resize Handle */}
          <PanelResizeHandle className="w-2 bg-border hover:bg-accent/50 transition-colors" />

          {/* Right Panel - Chat */}
          <Panel defaultSize={45} minSize={30}>
            <div className="h-full p-4">
              <ChatPanel
                learnerId={learnerId}
                projectId={projectId}
                editorContent={currentEditorContent}
                queryResults={workspaceType === "sql" ? queryResults : null}
                pythonResults={workspaceType === "python" ? pythonResults : null}
                currentTaskId={currentTaskId}
                onTaskClick={handleTaskClick}
                workspaceType={workspaceType}
              />
            </div>
          </Panel>
        </PanelGroup>
      </main>

      {/* Task Detail Drawer */}
      <TaskDetailDrawer
        taskId={drawerTaskId}
        learnerId={learnerId}
        open={!!drawerTaskId}
        onClose={closeDrawer}
        workspaceType={workspaceType}
      />
    </div>
  );
}
