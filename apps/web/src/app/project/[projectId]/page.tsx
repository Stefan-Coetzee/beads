"use client";

import { useParams } from "next/navigation";
import { useQuery } from "@tanstack/react-query";
import Link from "next/link";
import { ArrowLeft, Code, RefreshCw } from "lucide-react";
import { useState } from "react";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Progress } from "@/components/ui/progress";
import { Skeleton } from "@/components/ui/skeleton";
import { TaskTree } from "@/components/project/TaskTree";
import { TaskDetailDrawer } from "@/components/shared/TaskDetailDrawer";
import { api } from "@/lib/api";
import type { ProjectTree } from "@/types";

export default function ProjectPage() {
  const params = useParams();
  const projectId = params.projectId as string;

  const [selectedTaskId, setSelectedTaskId] = useState<string | null>(null);

  const { data: projectTree, isLoading, error, refetch } = useQuery<ProjectTree>({
    queryKey: ["projectTree", projectId],
    queryFn: () => api.getProjectTree(projectId),
  });

  if (error) {
    return (
      <div className="min-h-screen bg-background flex items-center justify-center">
        <div className="text-center space-y-4">
          <p className="text-destructive font-medium">Failed to load project</p>
          <p className="text-sm text-muted-foreground">{String(error)}</p>
          <Button onClick={() => refetch()}>Retry</Button>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-background">
      {/* Header */}
      <header className="border-b border-border">
        <div className="container mx-auto px-4 py-4 flex items-center justify-between">
          <div className="flex items-center gap-4">
            <Link href="/">
              <Button variant="ghost" size="icon">
                <ArrowLeft className="h-4 w-4" />
              </Button>
            </Link>
            <div>
              <h1 className="text-xl font-semibold">
                {projectTree?.project.title ?? projectId}
              </h1>
              <p className="text-sm text-muted-foreground">
                {projectTree ? `${projectTree.progress.completed_tasks}/${projectTree.progress.total_tasks} tasks completed` : "Loading…"}
              </p>
            </div>
          </div>
          <div className="flex items-center gap-2">
            <Button variant="ghost" size="icon" onClick={() => refetch()}>
              <RefreshCw className="h-4 w-4" />
            </Button>
            <Link href={`/workspace/${projectId}?type=${projectTree?.project.workspace_type || 'sql'}`}>
              <Button>
                <Code className="h-4 w-4 mr-2" />
                Open Workspace
              </Button>
            </Link>
          </div>
        </div>
      </header>

      <main className="container mx-auto px-4 py-8">
        {/* Progress Overview */}
        <Card className="mb-8">
          <CardHeader>
            <CardTitle>Progress</CardTitle>
            <CardDescription>
              {projectTree?.project.description}
            </CardDescription>
          </CardHeader>
          <CardContent>
            <div className="space-y-4">
              <div className="flex items-center gap-4">
                <Progress
                  value={projectTree?.progress.percentage ?? 0}
                  className="flex-1 h-3"
                />
                <span className="text-sm font-medium min-w-[4rem] text-right">
                  {Math.round(projectTree?.progress.percentage ?? 0)}%
                </span>
              </div>
              <div className="flex gap-6 text-sm">
                <div className="flex items-center gap-2">
                  <div className="w-3 h-3 rounded-full bg-green-500" />
                  <span className="text-muted-foreground">
                    Completed: {projectTree?.progress.completed_tasks ?? 0}
                  </span>
                </div>
                <div className="flex items-center gap-2">
                  <div className="w-3 h-3 rounded-full bg-amber-500" />
                  <span className="text-muted-foreground">
                    In Progress: {projectTree?.progress.in_progress ?? 0}
                  </span>
                </div>
                <div className="flex items-center gap-2">
                  <div className="w-3 h-3 rounded-full bg-red-500" />
                  <span className="text-muted-foreground">
                    Blocked: {projectTree?.progress.blocked ?? 0}
                  </span>
                </div>
              </div>
            </div>
          </CardContent>
        </Card>

        {/* Narrative Context */}
        {projectTree?.project.narrative_context && (
          <Card className="mb-8 bg-accent/5 border-accent/20">
            <CardContent className="py-4">
              <p className="text-sm italic text-muted-foreground">
                {projectTree.project.narrative_context}
              </p>
            </CardContent>
          </Card>
        )}

        {/* Task Tree */}
        <Card>
          <CardHeader>
            <CardTitle>Project Structure</CardTitle>
            <CardDescription>
              Click on any task to see details. Expand items to see subtasks.
            </CardDescription>
          </CardHeader>
          <CardContent>
            <TaskTree
              nodes={projectTree?.hierarchy ?? []}
              isLoading={isLoading}
              onTaskClick={setSelectedTaskId}
            />
          </CardContent>
        </Card>
      </main>

      {/* Task Detail Drawer */}
      <TaskDetailDrawer
        taskId={selectedTaskId}
        open={!!selectedTaskId}
        onClose={() => setSelectedTaskId(null)}
        workspaceType={projectTree?.project.workspace_type}
      />
    </div>
  );
}
