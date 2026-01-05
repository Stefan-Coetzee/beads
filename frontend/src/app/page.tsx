import Link from "next/link";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { BookOpen, Code, MessageSquare } from "lucide-react";

export default function Home() {
  // Default project ID for development
  const defaultProjectId = "proj-maji-ndogo";
  const defaultLearnerId = "learner-dev-001";

  return (
    <main className="min-h-screen bg-background">
      {/* Hero Section */}
      <div className="container mx-auto px-4 py-16">
        <div className="text-center mb-12">
          <h1 className="text-4xl font-bold tracking-tight mb-4">
            Learning Task Tracker
          </h1>
          <p className="text-xl text-muted-foreground max-w-2xl mx-auto">
            Project-based learning with AI guidance. Navigate tasks, write code,
            and receive real-time feedback.
          </p>
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
                href={`/project/${defaultProjectId}?learnerId=${defaultLearnerId}`}
              >
                <Button className="w-full">View Project</Button>
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
                href={`/workspace/${defaultProjectId}?learnerId=${defaultLearnerId}`}
              >
                <Button variant="secondary" className="w-full">
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
