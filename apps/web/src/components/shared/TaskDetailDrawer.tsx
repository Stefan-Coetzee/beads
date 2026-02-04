"use client";

import { useQuery } from "@tanstack/react-query";
import { X, ExternalLink, BookOpen, Target, AlertCircle } from "lucide-react";
import { Drawer } from "vaul";
import * as VisuallyHidden from "@radix-ui/react-visually-hidden";
import ReactMarkdown from "react-markdown";

import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import { StatusBadge } from "@/components/project/StatusBadge";
import { api } from "@/lib/api";
import type { TaskDetail, BloomLevel, WorkspaceType } from "@/types";

interface TaskDetailDrawerProps {
  taskId: string | null;
  learnerId: string;
  open: boolean;
  onClose: () => void;
  workspaceType?: WorkspaceType;
}

// Mock task detail for development
const mockTaskDetail: TaskDetail = {
  id: "proj-maji-ndogo.1.2.2",
  title: "WHERE clauses",
  description: "Learn to filter data using WHERE clauses with various comparison operators.",
  acceptance_criteria: "- Write a query using WHERE with = operator\n- Write a query using WHERE with > operator\n- Write a query combining multiple conditions with AND",
  notes: "",
  status: "in_progress",
  task_type: "subtask",
  priority: 1,
  parent_id: "proj-maji-ndogo.1.2",
  children: [],
  learning_objectives: [
    { id: "lo-1", level: "apply", description: "Write SQL queries with WHERE clauses" },
    { id: "lo-2", level: "understand", description: "Understand comparison operators in SQL" },
  ],
  content: "## WHERE Clause\n\nThe WHERE clause filters rows based on conditions.\n\n```sql\nSELECT * FROM visits WHERE time_in_queue > 500;\n```",
  tutor_guidance: {
    teaching_approach: "Start with simple equality, then move to comparisons",
    hints_to_give: ["Try SELECT * first to see all data", "Use > for greater than comparisons"],
    common_mistakes: ["Forgetting quotes around strings", "Using = instead of > for comparisons"],
  },
  blocked_by: [],
  blocks: [],
  submission_count: 2,
  latest_validation_passed: false,
  status_summaries: [],
};

function BloomBadge({ level }: { level: BloomLevel }) {
  const colors: Record<BloomLevel, string> = {
    remember: "bg-blue-500/20 text-blue-400",
    understand: "bg-cyan-500/20 text-cyan-400",
    apply: "bg-green-500/20 text-green-400",
    analyze: "bg-yellow-500/20 text-yellow-400",
    evaluate: "bg-orange-500/20 text-orange-400",
    create: "bg-purple-500/20 text-purple-400",
  };

  return (
    <span className={`px-2 py-0.5 rounded text-xs font-medium capitalize ${colors[level]}`}>
      {level}
    </span>
  );
}

export function TaskDetailDrawer({
  taskId,
  learnerId,
  open,
  onClose,
  workspaceType,
}: TaskDetailDrawerProps) {
  const { data: task, isLoading } = useQuery({
    queryKey: ["taskDetail", taskId, learnerId],
    queryFn: async () => {
      if (!taskId) return null;
      try {
        return await api.getTaskDetails(taskId, learnerId);
      } catch {
        // Fall back to mock data
        return mockTaskDetail;
      }
    },
    enabled: !!taskId,
  });

  return (
    <Drawer.Root open={open} onOpenChange={(isOpen) => !isOpen && onClose()}>
      <Drawer.Portal>
        <Drawer.Overlay className="fixed inset-0 bg-black/40 z-40" />
        <Drawer.Content className="fixed right-0 top-0 bottom-0 w-[450px] max-w-[90vw] bg-surface border-l border-border z-50 flex flex-col">
          <VisuallyHidden.Root>
            <Drawer.Title>Task Details</Drawer.Title>
          </VisuallyHidden.Root>
          {/* Header */}
          <div className="flex items-center justify-between p-4 border-b border-border">
            <div className="flex items-center gap-2">
              <span className="text-sm text-muted-foreground font-mono">
                {taskId}
              </span>
            </div>
            <Button variant="ghost" size="icon" onClick={onClose}>
              <X className="h-4 w-4" />
            </Button>
          </div>

          {/* Content */}
          <div className="flex-1 overflow-y-auto p-6">
            {isLoading ? (
              <div className="space-y-4">
                <Skeleton className="h-6 w-3/4" />
                <Skeleton className="h-4 w-full" />
                <Skeleton className="h-4 w-2/3" />
                <Skeleton className="h-20 w-full" />
              </div>
            ) : task ? (
              <div className="space-y-6">
                {/* Title & Status */}
                <div>
                  <div className="flex items-center gap-2 mb-2">
                    <StatusBadge status={task.status} />
                    <span className="text-xs text-muted-foreground capitalize">
                      {task.task_type}
                    </span>
                  </div>
                  <h2 className="text-xl font-semibold">{task.title}</h2>
                  <p className="text-muted-foreground mt-2">
                    {task.description}
                  </p>
                </div>

                {/* Acceptance Criteria */}
                <section>
                  <h3 className="text-sm font-medium text-muted-foreground flex items-center gap-2 mb-3">
                    <Target className="h-4 w-4" />
                    Acceptance Criteria
                  </h3>
                  <div className="prose prose-sm prose-invert max-w-none bg-elevated rounded-lg p-4">
                    <ReactMarkdown>{task.acceptance_criteria}</ReactMarkdown>
                  </div>
                </section>

                {/* Learning Objectives */}
                {task.learning_objectives?.length > 0 && (
                  <section>
                    <h3 className="text-sm font-medium text-muted-foreground flex items-center gap-2 mb-3">
                      <BookOpen className="h-4 w-4" />
                      Learning Objectives
                    </h3>
                    <ul className="space-y-2">
                      {task.learning_objectives.map((obj) => (
                        <li
                          key={obj.id}
                          className="flex items-start gap-2 text-sm"
                        >
                          <BloomBadge level={obj.level} />
                          <span>{obj.description}</span>
                        </li>
                      ))}
                    </ul>
                  </section>
                )}

                {/* Content */}
                {task.content && (
                  <section>
                    <h3 className="text-sm font-medium text-muted-foreground mb-3">
                      Content
                    </h3>
                    <div className="prose prose-sm prose-invert max-w-none bg-elevated rounded-lg p-4">
                      <ReactMarkdown>{task.content}</ReactMarkdown>
                    </div>
                  </section>
                )}

                {/* Tutor Hints */}
                {task.tutor_guidance?.hints_to_give && task.tutor_guidance.hints_to_give.length > 0 && (
                  <section>
                    <h3 className="text-sm font-medium text-muted-foreground flex items-center gap-2 mb-3">
                      <AlertCircle className="h-4 w-4" />
                      Hints
                    </h3>
                    <ul className="space-y-1 text-sm text-muted-foreground">
                      {task.tutor_guidance.hints_to_give.map((hint, i) => (
                        <li key={i} className="flex items-start gap-2">
                          <span className="text-accent">•</span>
                          {hint}
                        </li>
                      ))}
                    </ul>
                  </section>
                )}

                {/* Submission Info */}
                {task.submission_count > 0 && (
                  <section className="border-t border-border pt-4">
                    <div className="flex items-center justify-between text-sm">
                      <span className="text-muted-foreground">Submissions</span>
                      <span>{task.submission_count}</span>
                    </div>
                    {task.latest_validation_passed !== null && (
                      <div className="flex items-center justify-between text-sm mt-2">
                        <span className="text-muted-foreground">Latest Result</span>
                        <Badge variant={task.latest_validation_passed ? "closed" : "blocked"}>
                          {task.latest_validation_passed ? "Passed" : "Failed"}
                        </Badge>
                      </div>
                    )}
                  </section>
                )}

                {/* Dependencies */}
                {(task.blocked_by?.length > 0 || task.blocks?.length > 0) && (
                  <section className="border-t border-border pt-4">
                    {task.blocked_by?.length > 0 && (
                      <div className="mb-3">
                        <span className="text-sm text-muted-foreground">Blocked by: </span>
                        {task.blocked_by.map((t) => (
                          <Badge key={t.id} variant="outline" className="ml-1">
                            {t.title}
                          </Badge>
                        ))}
                      </div>
                    )}
                    {task.blocks?.length > 0 && (
                      <div>
                        <span className="text-sm text-muted-foreground">Blocks: </span>
                        {task.blocks.map((t) => (
                          <Badge key={t.id} variant="outline" className="ml-1">
                            {t.title}
                          </Badge>
                        ))}
                      </div>
                    )}
                  </section>
                )}
              </div>
            ) : (
              <div className="text-center text-muted-foreground py-8">
                Task not found
              </div>
            )}
          </div>

          {/* Footer Actions */}
          {task && (
            <div className="border-t border-border p-4">
              <Button className="w-full" asChild>
                <a href={`/workspace/${task.id.split(".")[0]}?learnerId=${learnerId}&taskId=${task.id}${workspaceType ? `&type=${workspaceType}` : ''}`}>
                  <ExternalLink className="h-4 w-4 mr-2" />
                  Open in Workspace
                </a>
              </Button>
            </div>
          )}
        </Drawer.Content>
      </Drawer.Portal>
    </Drawer.Root>
  );
}
