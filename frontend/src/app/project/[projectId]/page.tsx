"use client";

import { useParams, useSearchParams } from "next/navigation";
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

// Mock data for development when API is not available
const mockProjectTree: ProjectTree = {
  project: {
    id: "proj-maji-ndogo",
    title: "Maji Ndogo Water Analysis",
    description: "Analyze water quality data from the Maji Ndogo region to help improve water access for communities.",
    narrative_context: "You've been assigned to analyze water quality survey data collected by President Naledi's water initiative. Your work will directly impact real communities.",
  },
  hierarchy: [
    {
      id: "proj-maji-ndogo.1",
      title: "Data Foundation",
      task_type: "epic",
      status: "in_progress",
      priority: 0,
      children: [
        {
          id: "proj-maji-ndogo.1.1",
          title: "Database Setup",
          task_type: "task",
          status: "closed",
          priority: 0,
          children: [
            { id: "proj-maji-ndogo.1.1.1", title: "Create tables", task_type: "subtask", status: "closed", priority: 0, children: [] },
            { id: "proj-maji-ndogo.1.1.2", title: "Import data", task_type: "subtask", status: "closed", priority: 0, children: [] },
          ],
          progress: { completed: 2, total: 2 },
        },
        {
          id: "proj-maji-ndogo.1.2",
          title: "Basic Queries",
          task_type: "task",
          status: "in_progress",
          priority: 1,
          children: [
            { id: "proj-maji-ndogo.1.2.1", title: "SELECT basics", task_type: "subtask", status: "closed", priority: 0, children: [] },
            { id: "proj-maji-ndogo.1.2.2", title: "WHERE clauses", task_type: "subtask", status: "in_progress", priority: 1, children: [] },
            { id: "proj-maji-ndogo.1.2.3", title: "Aggregations", task_type: "subtask", status: "open", priority: 2, children: [] },
          ],
          progress: { completed: 1, total: 3 },
        },
        {
          id: "proj-maji-ndogo.1.3",
          title: "Data Validation",
          task_type: "task",
          status: "open",
          priority: 2,
          children: [],
        },
      ],
      progress: { completed: 3, total: 7 },
    },
    {
      id: "proj-maji-ndogo.2",
      title: "Analysis",
      task_type: "epic",
      status: "open",
      priority: 1,
      children: [
        {
          id: "proj-maji-ndogo.2.1",
          title: "Water Quality Metrics",
          task_type: "task",
          status: "open",
          priority: 0,
          children: [],
        },
      ],
      progress: { completed: 0, total: 1 },
    },
    {
      id: "proj-maji-ndogo.3",
      title: "Reporting",
      task_type: "epic",
      status: "open",
      priority: 2,
      children: [],
      progress: { completed: 0, total: 0 },
    },
  ],
  progress: {
    total_tasks: 8,
    completed_tasks: 3,
    in_progress: 2,
    blocked: 0,
    percentage: 37.5,
  },
};

export default function ProjectPage() {
  const params = useParams();
  const searchParams = useSearchParams();
  const projectId = params.projectId as string;
  const learnerId = searchParams.get("learnerId") || "learner-dev-001";

  const [selectedTaskId, setSelectedTaskId] = useState<string | null>(null);

  // Fetch project tree - fall back to mock data if API fails
  const { data, isLoading, error, refetch } = useQuery({
    queryKey: ["projectTree", projectId, learnerId],
    queryFn: async () => {
      try {
        return await api.getProjectTree(projectId, learnerId);
      } catch {
        // Fall back to mock data for development
        console.log("Using mock data - API not available");
        return mockProjectTree;
      }
    },
  });

  const projectTree = data || mockProjectTree;

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
                {projectTree.project.title}
              </h1>
              <p className="text-sm text-muted-foreground">
                {projectTree.progress.completed_tasks}/{projectTree.progress.total_tasks} tasks completed
              </p>
            </div>
          </div>
          <div className="flex items-center gap-2">
            <Button variant="ghost" size="icon" onClick={() => refetch()}>
              <RefreshCw className="h-4 w-4" />
            </Button>
            <Link href={`/workspace/${projectId}?learnerId=${learnerId}`}>
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
              {projectTree.project.description}
            </CardDescription>
          </CardHeader>
          <CardContent>
            <div className="space-y-4">
              <div className="flex items-center gap-4">
                <Progress
                  value={projectTree.progress.percentage}
                  className="flex-1 h-3"
                />
                <span className="text-sm font-medium min-w-[4rem] text-right">
                  {Math.round(projectTree.progress.percentage)}%
                </span>
              </div>
              <div className="flex gap-6 text-sm">
                <div className="flex items-center gap-2">
                  <div className="w-3 h-3 rounded-full bg-green-500" />
                  <span className="text-muted-foreground">
                    Completed: {projectTree.progress.completed_tasks}
                  </span>
                </div>
                <div className="flex items-center gap-2">
                  <div className="w-3 h-3 rounded-full bg-amber-500" />
                  <span className="text-muted-foreground">
                    In Progress: {projectTree.progress.in_progress}
                  </span>
                </div>
                <div className="flex items-center gap-2">
                  <div className="w-3 h-3 rounded-full bg-red-500" />
                  <span className="text-muted-foreground">
                    Blocked: {projectTree.progress.blocked}
                  </span>
                </div>
              </div>
            </div>
          </CardContent>
        </Card>

        {/* Narrative Context */}
        {projectTree.project.narrative_context && (
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
              nodes={projectTree.hierarchy}
              isLoading={isLoading}
              onTaskClick={setSelectedTaskId}
            />
          </CardContent>
        </Card>
      </main>

      {/* Task Detail Drawer */}
      <TaskDetailDrawer
        taskId={selectedTaskId}
        learnerId={learnerId}
        open={!!selectedTaskId}
        onClose={() => setSelectedTaskId(null)}
      />
    </div>
  );
}
