"use client";

import { useParams, useSearchParams } from "next/navigation";
import { useEffect, useCallback } from "react";
import Link from "next/link";
import { Panel, Group as PanelGroup, Separator as PanelResizeHandle } from "react-resizable-panels";
import { ArrowLeft, BookOpen, RefreshCw } from "lucide-react";

import { Button } from "@/components/ui/button";
import { SqlEditor } from "@/components/workspace/SqlEditor";
import { ResultsPanel } from "@/components/workspace/ResultsPanel";
import { ChatPanel } from "@/components/chat/ChatPanel";
import { TaskDetailDrawer } from "@/components/shared/TaskDetailDrawer";
import { useWorkspaceStore } from "@/stores/workspace-store";
import {
  executeQuery,
  isDatabaseReady,
  loadMajiNdogoDatabase,
} from "@/lib/sql-engine";
import type { QueryResult } from "@/types";

export default function WorkspacePage() {
  const params = useParams();
  const searchParams = useSearchParams();
  const projectId = params.projectId as string;
  const learnerId = searchParams.get("learnerId") || "learner-dev-001";
  const initialTaskId = searchParams.get("taskId");

  const {
    editorContent,
    setEditorContent,
    queryResults,
    setQueryResults,
    isExecuting,
    setIsExecuting,
    currentTaskId,
    setCurrentTaskId,
    drawerTaskId,
    openDrawer,
    closeDrawer,
  } = useWorkspaceStore();

  // Initialize database on mount
  useEffect(() => {
    async function init() {
      if (!isDatabaseReady()) {
        try {
          await loadMajiNdogoDatabase();
          console.log("Database initialized with Maji Ndogo data");
        } catch (e) {
          console.error("Failed to load database:", e);
        }
      }
    }
    init();
  }, []);

  // Set initial task if provided
  useEffect(() => {
    if (initialTaskId) {
      setCurrentTaskId(initialTaskId);
    }
  }, [initialTaskId, setCurrentTaskId]);

  // Handle query execution
  const handleRunQuery = useCallback(() => {
    if (!editorContent.trim()) return;

    setIsExecuting(true);

    // Small delay for UX
    setTimeout(() => {
      const result = executeQuery(editorContent);
      setQueryResults(result as QueryResult);
      setIsExecuting(false);
    }, 100);
  }, [editorContent, setIsExecuting, setQueryResults]);

  // Handle task click from chat
  const handleTaskClick = useCallback(
    (taskId: string) => {
      openDrawer(taskId);
    },
    [openDrawer]
  );

  // Reset database
  const handleResetDatabase = useCallback(async () => {
    await createDatabase(SAMPLE_SCHEMA);
    setQueryResults(null);
  }, [setQueryResults]);

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
            <h1 className="font-semibold">Workspace</h1>
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
          <Button variant="ghost" size="sm" onClick={handleResetDatabase}>
            <RefreshCw className="h-4 w-4 mr-1" />
            Reset DB
          </Button>
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
              {/* SQL Editor */}
              <div className="flex-1 min-h-0">
                <SqlEditor
                  value={editorContent}
                  onChange={setEditorContent}
                  onRun={handleRunQuery}
                  isExecuting={isExecuting}
                />
              </div>

              {/* Results Panel */}
              <div className="flex-1 min-h-0">
                <ResultsPanel result={queryResults} isExecuting={isExecuting} />
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
                editorContent={editorContent}
                queryResults={queryResults}
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
      />
    </div>
  );
}
