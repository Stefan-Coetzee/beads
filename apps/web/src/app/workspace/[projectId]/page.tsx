"use client";

import { useParams, useSearchParams } from "next/navigation";
import { useEffect, useCallback, useState, useRef } from "react";
import Link from "next/link";
import { Panel, Group as PanelGroup, Separator as PanelResizeHandle } from "react-resizable-panels";
import { ArrowLeft, BookOpen, RefreshCw, AlertTriangle, Database, Clock } from "lucide-react";

import { Button } from "@/components/ui/button";
import { SqlEditor } from "@/components/workspace/SqlEditor";
import { ResultsPanel } from "@/components/workspace/ResultsPanel";
import { PythonEditor } from "@/components/workspace/PythonEditor";
import { PythonResultsPanel } from "@/components/workspace/PythonResultsPanel";
import { ChatPanel } from "@/components/chat/ChatPanel";
import { TaskDetailDrawer } from "@/components/shared/TaskDetailDrawer";
import { useWorkspaceStore } from "@/stores/workspace-store";
import type { QueryResult, WorkspaceType } from "@/types";
import { parseLTIContext, storeLTIContext, getLTIContext } from "@/lib/lti";

// SQL engine
import {
  executeQuery,
  isDatabaseReady,
  loadMajiNdogoDatabase,
} from "@/lib/sql-engine";
import type { LoadProgress } from "@/lib/sql-engine";

// Python engine
import {
  executePython,
  initPythonEngine,
  isPythonReady,
  resetPythonEnvironment,
  onReadyStateChange,
} from "@/lib/python-engine";

export default function WorkspacePage() {
  const params = useParams();
  const searchParams = useSearchParams();
  const projectId = params.projectId as string;
  const initialTaskId = searchParams.get("taskId");

  // Resolve LTI context: store on first LTI landing, fall back to sessionStorage on re-navigation.
  // Inject projectId from the URL path since it's not a search param.
  const urlLtiCtx = parseLTIContext(searchParams);
  if (urlLtiCtx) storeLTIContext({ ...urlLtiCtx, projectId });
  const ltiCtx = urlLtiCtx ?? getLTIContext();

  const learnerId = searchParams.get("learnerId") ?? ltiCtx?.learnerId ?? "learner-dev-001";

  // Workspace type: URL param → stored LTI context → null (show error)
  const workspaceType = (searchParams.get("type") ?? ltiCtx?.workspaceType ?? null) as WorkspaceType | null;

  // Loading progress state
  const [sqlProgress, setSqlProgress] = useState<LoadProgress | null>(null);
  const [isSqlReady, setIsSqlReady] = useState(isDatabaseReady());

  // Execution timer state
  const [execElapsed, setExecElapsed] = useState(0);
  const execTimerRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const startExecTimer = useCallback(() => {
    setExecElapsed(0);
    execTimerRef.current = setInterval(() => {
      setExecElapsed((prev) => prev + 1);
    }, 1000);
  }, []);

  const stopExecTimer = useCallback(() => {
    if (execTimerRef.current) {
      clearInterval(execTimerRef.current);
      execTimerRef.current = null;
    }
    setExecElapsed(0);
  }, []);

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
    if (workspaceType !== "sql") return;

    async function initSql() {
      if (!isDatabaseReady()) {
        try {
          await loadMajiNdogoDatabase(false, setSqlProgress);
          setIsSqlReady(true);
        } catch (e) {
          console.error("[SQL] Failed to load database:", e);
        }
      } else {
        setIsSqlReady(true);
      }
    }
    initSql();
  }, [workspaceType]);

  // Initialize Python engine ONLY when type=python
  useEffect(() => {
    if (workspaceType !== "python") return;

    // Keep store in sync when worker is terminated (timeout) or re-initialized
    onReadyStateChange(setIsPythonReady);

    async function initPython() {
      if (!isPythonReady()) {
        try {
          await initPythonEngine();
          setIsPythonReady(true);
        } catch (e) {
          console.error("[Python] Failed to initialize:", e);
        }
      }
    }
    initPython();

    return () => { onReadyStateChange(null); };
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
    startExecTimer();

    setTimeout(() => {
      const result = executeQuery(sqlContent);
      setQueryResults(result as QueryResult);
      setIsExecuting(false);
      stopExecTimer();
    }, 100);
  }, [sqlContent, setIsExecuting, setQueryResults, startExecTimer, stopExecTimer]);

  // Handle Python code execution
  const handleRunPython = useCallback(async () => {
    if (!pythonContent.trim()) return;

    setIsExecuting(true);
    startExecTimer();

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
      stopExecTimer();
    }
  }, [pythonContent, setIsExecuting, setPythonResults, startExecTimer, stopExecTimer]);

  // Handle task click from chat
  const handleTaskClick = useCallback(
    (taskId: string) => {
      openDrawer(taskId);
    },
    [openDrawer]
  );

  // Reset SQL database
  const handleResetDatabase = useCallback(async () => {
    setIsSqlReady(false);
    await loadMajiNdogoDatabase(true, setSqlProgress);
    setIsSqlReady(true);
    setQueryResults(null);
  }, [setQueryResults]);

  // Reset Python environment
  const handleResetPython = useCallback(async () => {
    await resetPythonEnvironment();
    setPythonResults(null);
  }, [setPythonResults]);

  // Get current editor content for chat context
  const currentEditorContent = workspaceType === "python" ? pythonContent : sqlContent;

  // Show loading overlay for SQL workspace while DB downloads
  const showSqlLoading = workspaceType === "sql" && !isSqlReady;

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
            <div className="h-full flex flex-col p-4 gap-4 relative">
              {/* SQL Loading Overlay */}
              {showSqlLoading && (
                <div className="absolute inset-0 z-10 flex items-center justify-center bg-background/90 m-4 rounded-lg">
                  <div className="flex flex-col items-center gap-4 max-w-sm">
                    <Database className="h-10 w-10 text-accent" />
                    <h2 className="text-lg font-medium">Preparing Database</h2>
                    <p className="text-sm text-muted-foreground text-center">
                      {sqlProgress?.message || "Initializing..."}
                    </p>
                    {/* Progress bar */}
                    <div className="w-64 h-2 bg-elevated rounded-full overflow-hidden">
                      <div
                        className="h-full bg-accent rounded-full transition-all duration-300"
                        style={{ width: `${sqlProgress?.percent ?? 0}%` }}
                      />
                    </div>
                    <p className="text-xs text-muted-foreground">
                      {sqlProgress?.percent ?? 0}%
                    </p>
                  </div>
                </div>
              )}

              {/* Execution timer warning */}
              {isExecuting && execElapsed >= 1 && (
                <div className="absolute top-6 left-1/2 -translate-x-1/2 z-20 bg-yellow-900/90 border border-yellow-600 rounded-lg px-4 py-2 flex items-center gap-3 shadow-lg">
                  <Clock className="h-4 w-4 text-yellow-400 animate-pulse" />
                  <span className="text-sm text-yellow-200">
                    {execElapsed < 10
                      ? `Running... stopping in ${10 - execElapsed}s — check your code for infinite loops`
                      : "Timed out — execution was stopped"}
                  </span>
                </div>
              )}

              {/* Editor */}
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

              {/* Results Panel */}
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
