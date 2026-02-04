"use client";

import { useState, useEffect } from "react";
import Link from "next/link";
import { useQuery } from "@tanstack/react-query";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { BookOpen, Code, MessageSquare } from "lucide-react";
import { LearnerIdInput, useLearnerIdState } from "@/components/shared/LearnerIdInput";
import { ProjectSelector } from "@/components/shared/ProjectSelector";
import { api } from "@/lib/api";

export default function Home() {
  const { learnerId, setLearnerId, isLoaded } = useLearnerIdState();
  const [projectId, setProjectId] = useState<string>("");

  // Fetch projects to set default
  const { data: projects } = useQuery({
    queryKey: ["projects"],
    queryFn: () => api.getProjects(),
    staleTime: 5 * 60 * 1000,
  });

  // Set default project when projects load
  useEffect(() => {
    if (projects && projects.length > 0 && !projectId) {
      setProjectId(projects[0].id);
    }
  }, [projects, projectId]);

  // Get selected project's workspace type
  const selectedProject = projects?.find(p => p.id === projectId);
  const workspaceType = selectedProject?.workspace_type;

  if (!isLoaded) {
    return (
      <main className="min-h-screen bg-background flex items-center justify-center">
        <div className="animate-pulse text-muted-foreground">Loading...</div>
      </main>
    );
  }

  return (
    <main className="min-h-screen bg-background">
      {/* Header with Learner ID */}
      <header className="border-b border-border">
        <div className="container mx-auto px-4 py-3 flex items-center justify-between">
          <h2 className="font-semibold">Learning Task Tracker</h2>
          <LearnerIdInput value={learnerId} onChange={setLearnerId} />
        </div>
      </header>

      {/* Hero Section */}
      <div className="container mx-auto px-4 py-12">
        <div className="text-center mb-10">
          <h1 className="text-4xl font-bold tracking-tight mb-4">
            Project-Based Learning
          </h1>
          <p className="text-xl text-muted-foreground max-w-2xl mx-auto">
            Navigate tasks, write SQL, and receive real-time AI guidance.
          </p>
        </div>

        {/* Project Selector */}
        <div className="flex items-center justify-center gap-3 mb-10">
          <span className="text-sm text-muted-foreground">Select project:</span>
          <ProjectSelector value={projectId} onChange={setProjectId} />
        </div>

        {/* Quick Start Cards */}
        <div className="grid md:grid-cols-2 gap-6 max-w-4xl mx-auto mb-12">
          <Card className="hover:border-accent/50 transition-colors">
            <CardHeader>
              <div className="flex items-center gap-3">
                <div className="p-2 rounded-lg bg-accent/10">
                  <BookOpen className="h-6 w-6 text-accent" />
                </div>
                <div>
                  <CardTitle>Project Overview</CardTitle>
                  <CardDescription>
                    View your progress and explore tasks
                  </CardDescription>
                </div>
              </div>
            </CardHeader>
            <CardContent>
              <p className="text-sm text-muted-foreground mb-4">
                See the full project structure with epics, tasks, and subtasks.
                Track your completion status and find your next step.
              </p>
              <Link
                href={projectId ? `/project/${projectId}?learnerId=${learnerId}` : "#"}
              >
                <Button className="w-full" disabled={!projectId}>
                  View Project
                </Button>
              </Link>
            </CardContent>
          </Card>

          <Card className="hover:border-accent/50 transition-colors">
            <CardHeader>
              <div className="flex items-center gap-3">
                <div className="p-2 rounded-lg bg-accent/10">
                  <Code className="h-6 w-6 text-accent" />
                </div>
                <div>
                  <CardTitle>Workspace</CardTitle>
                  <CardDescription>
                    Code with AI assistance
                  </CardDescription>
                </div>
              </div>
            </CardHeader>
            <CardContent>
              <p className="text-sm text-muted-foreground mb-4">
                Write SQL queries, execute them in-browser, and get guidance
                from your AI tutor as you work through tasks.
              </p>
              <Link
                href={projectId ? `/workspace/${projectId}?learnerId=${learnerId}${workspaceType ? `&type=${workspaceType}` : ''}` : "#"}
              >
                <Button variant="secondary" className="w-full" disabled={!projectId}>
                  Open Workspace
                </Button>
              </Link>
            </CardContent>
          </Card>
        </div>

        {/* Features Section */}
        <div className="max-w-4xl mx-auto">
          <h2 className="text-2xl font-semibold text-center mb-8">
            What You Can Do
          </h2>
          <div className="grid md:grid-cols-3 gap-6">
            <div className="text-center">
              <div className="p-3 rounded-full bg-surface w-fit mx-auto mb-3">
                <BookOpen className="h-6 w-6 text-muted-foreground" />
              </div>
              <h3 className="font-medium mb-2">Learn by Doing</h3>
              <p className="text-sm text-muted-foreground">
                Work through structured projects with clear learning objectives
              </p>
            </div>
            <div className="text-center">
              <div className="p-3 rounded-full bg-surface w-fit mx-auto mb-3">
                <Code className="h-6 w-6 text-muted-foreground" />
              </div>
              <h3 className="font-medium mb-2">Code in Browser</h3>
              <p className="text-sm text-muted-foreground">
                Execute SQL queries directly in your browser with instant results
              </p>
            </div>
            <div className="text-center">
              <div className="p-3 rounded-full bg-surface w-fit mx-auto mb-3">
                <MessageSquare className="h-6 w-6 text-muted-foreground" />
              </div>
              <h3 className="font-medium mb-2">AI Guidance</h3>
              <p className="text-sm text-muted-foreground">
                Get help from an AI tutor that understands your code and progress
              </p>
            </div>
          </div>
        </div>
      </div>

      {/* Footer */}
      <footer className="border-t border-border py-6 mt-12">
        <div className="container mx-auto px-4 text-center text-sm text-muted-foreground">
          <p>Learning Task Tracker - Built with Next.js and FastAPI</p>
        </div>
      </footer>
    </main>
  );
}
