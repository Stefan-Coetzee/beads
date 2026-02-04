"use client";

import { useParams, useSearchParams } from "next/navigation";
import { useEffect, useCallback, useState } from "react";
import Link from "next/link";
import { Panel, Group as PanelGroup, Separator as PanelResizeHandle } from "react-resizable-panels";
import { ArrowLeft, BookOpen, RefreshCw } from "lucide-react";

import { Button } from "@/components/ui/button";
import { SqlEditor } from "@/components/workspace/SqlEditor";
import { ResultsPanel } from "@/components/workspace/ResultsPanel";
import { PythonEditor } from "@/components/workspace/PythonEditor";
import { PythonResultsPanel } from "@/components/workspace/PythonResultsPanel";
import { ChatPanel } from "@/components/chat/ChatPanel";
import { TaskDetailDrawer } from "@/components/shared/TaskDetailDrawer";
import { useWorkspaceStore } from "@/stores/workspace-store";
import {
  executeQuery,
  isDatabaseReady,
  loadMajiNdogoDatabase,
} from "@/lib/sql-engine";
import {
  executePython,
  initPythonEngine,
  isPythonReady,
  resetPythonEnvironment,
} from "@/lib/python-engine";
import type { QueryResult, WorkspaceType } from "@/types";

export default function WorkspacePage() {
  const params = useParams();
  const searchParams = useSearchParams();
  const projectId = params.projectId as string;
  const learnerId = searchParams.get("learnerId") || "learner-dev-001";
  const initialTaskId = searchParams.get("taskId");
  const workspaceTypeParam = searchParams.get("type") as WorkspaceType | null;

  // Use URL param directly for rendering (don't wait for useEffect)
  const effectiveWorkspaceType: WorkspaceType = workspaceTypeParam || "sql";

  const {
    workspaceType,
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

  // Set workspace type from URL param (always takes precedence)
  useEffect(() => {
    if (workspaceTypeParam) {
      setWorkspaceType(workspaceTypeParam);
    }
  }, [workspaceTypeParam, setWorkspaceType]);

  // Initialize SQL database on mount (for SQL workspace)
  useEffect(() => {
    async function initSql() {
      if (effectiveWorkspaceType === "sql" && !isDatabaseReady()) {
        try {
          await loadMajiNdogoDatabase();
          console.log("Database initialized with Maji Ndogo data");
        } catch (e) {
          console.error("Failed to load database:", e);
        }
      }
    }
    initSql();
  }, [effectiveWorkspaceType]);

  // Initialize Python engine on mount (for Python workspace)
  useEffect(() => {
    async function initPython() {
      if (effectiveWorkspaceType === "python" && !isPythonReady()) {
        try {
          await initPythonEngine();
          setIsPythonReady(true);
          console.log("Python engine initialized");
        } catch (e) {
          console.error("Failed to initialize Python:", e);
        }
      }
    }
    initPython();
  }, [effectiveWorkspaceType, setIsPythonReady]);

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

    // Small delay for UX
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
    await loadMajiNdogoDatabase(true); // Force fresh reload
    setQueryResults(null);
  }, [setQueryResults]);

  // Reset Python environment
  const handleResetPython = useCallback(async () => {
    await resetPythonEnvironment();
    setPythonResults(null);
  }, [setPythonResults]);

  // Get current editor content for chat context
  const currentEditorContent = effectiveWorkspaceType === "python" ? pythonContent : sqlContent;
  const currentResults = effectiveWorkspaceType === "python" ? pythonResults : queryResults;

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
              {effectiveWorkspaceType === "python" ? "Python Workspace" : "SQL Workspace"}
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
          {effectiveWorkspaceType === "sql" && (
            <Button variant="ghost" size="sm" onClick={handleResetDatabase}>
              <RefreshCw className="h-4 w-4 mr-1" />
              Reset DB
            </Button>
          )}
          {effectiveWorkspaceType === "python" && (
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
              {/* Editor */}
              <div className="flex-1 min-h-0">
                {effectiveWorkspaceType === "python" ? (
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

              {/* Results Panel */}
              <div className="flex-1 min-h-0">
                {effectiveWorkspaceType === "python" ? (
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
                queryResults={currentResults as QueryResult | null}
                currentTaskId={currentTaskId}
                onTaskClick={handleTaskClick}
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
        workspaceType={effectiveWorkspaceType}
      />
    </div>
  );
}
