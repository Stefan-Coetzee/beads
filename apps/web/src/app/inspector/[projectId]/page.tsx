"use client";

import { useParams } from "next/navigation";
import { useEffect, useState, useCallback } from "react";
import { ChevronLeft, ChevronRight } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import { API_BASE_URL } from "@/lib/config";

// ---------------------------------------------------------------------------
// Types (match backend InspectorResponse)
// ---------------------------------------------------------------------------

interface InspectorObjective {
  level: string;
  description: string;
}

interface InspectorTask {
  id: string;
  title: string;
  description: string | null;
  task_type: string;
  subtask_type: string | null;
  acceptance_criteria: string | null;
  content: string | null;
  tutor_guidance: Record<string, unknown> | null;
  learning_objectives: InspectorObjective[];
}

interface InspectorEpic {
  id: string;
  title: string;
  description: string | null;
}

interface InspectorProgress {
  completed: number;
  total: number;
  percentage: number;
  in_progress: number;
  blocked: number;
}

interface InspectorStep {
  step_number: number;
  breadcrumb: string[];
  task: InspectorTask;
  epic: InspectorEpic | null;
  progress: InspectorProgress;
  system_prompt: string;
  tool_results: Record<string, unknown>;
}

interface InspectorData {
  project: {
    id: string;
    title: string;
    description: string | null;
    narrative_context: string | null;
    workspace_type: string | null;
  };
  total_steps: number;
  steps: InspectorStep[];
}

// ---------------------------------------------------------------------------
// start_task result type
// ---------------------------------------------------------------------------

interface StartTaskContext {
  task_id: string;
  title: string;
  task_type: string;
  status: string;
  description: string;
  acceptance_criteria: string;
  content: string | null;
  narrative_context: string | null;
  learning_objectives: { level: string; description: string }[];
  tutor_guidance: Record<string, unknown> | null;
}

interface StartTaskData {
  success: boolean;
  task_id: string;
  status: string;
  message: string;
  context: StartTaskContext;
}

// ---------------------------------------------------------------------------
// Bloom level color map
// ---------------------------------------------------------------------------

const bloomColors: Record<string, string> = {
  remember: "bg-zinc-600 text-zinc-200",
  understand: "bg-blue-600/30 text-blue-300",
  apply: "bg-green-600/30 text-green-300",
  analyze: "bg-amber-600/30 text-amber-300",
  evaluate: "bg-purple-600/30 text-purple-300",
  create: "bg-rose-600/30 text-rose-300",
};

// ---------------------------------------------------------------------------
// Page
// ---------------------------------------------------------------------------

export default function InspectorPage() {
  const params = useParams();
  const projectId = params.projectId as string;

  const [data, setData] = useState<InspectorData | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [currentStep, setCurrentStep] = useState(0);

  // Fetch once
  useEffect(() => {
    fetch(`${API_BASE_URL}/api/v1/debug/inspector/${projectId}`)
      .then((res) => {
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        return res.json();
      })
      .then(setData)
      .catch((err) => setError(err.message))
      .finally(() => setLoading(false));
  }, [projectId]);

  // Navigation
  const goNext = useCallback(() => {
    if (data) setCurrentStep((s) => Math.min(s + 1, data.total_steps - 1));
  }, [data]);
  const goPrev = useCallback(() => {
    setCurrentStep((s) => Math.max(s - 1, 0));
  }, []);

  // Keyboard: left/right arrows
  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if (e.key === "ArrowRight") goNext();
      if (e.key === "ArrowLeft") goPrev();
    };
    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  }, [goNext, goPrev]);

  // ---------------------------------------------------------------------------
  // States
  // ---------------------------------------------------------------------------

  if (loading) {
    return (
      <div className="min-h-screen bg-background p-8 space-y-4">
        <Skeleton className="h-8 w-64" />
        <Skeleton className="h-4 w-96" />
        <Skeleton className="h-64 w-full" />
        <Skeleton className="h-48 w-full" />
      </div>
    );
  }

  if (error) {
    return (
      <div className="min-h-screen bg-background flex items-center justify-center">
        <div className="text-center space-y-2">
          <p className="text-error font-medium">Failed to load inspector data</p>
          <p className="text-sm text-muted-foreground">{error}</p>
          <p className="text-xs text-muted-foreground">
            Make sure the backend is running with DEBUG=true
          </p>
        </div>
      </div>
    );
  }

  if (!data || data.total_steps === 0) {
    return (
      <div className="min-h-screen bg-background flex items-center justify-center">
        <p className="text-muted-foreground">No tasks found in project.</p>
      </div>
    );
  }

  const step = data.steps[currentStep];

  return (
    <div className="min-h-screen bg-background text-foreground">
      {/* ----------------------------------------------------------------- */}
      {/* Header                                                            */}
      {/* ----------------------------------------------------------------- */}
      <header className="sticky top-0 z-10 bg-background/95 backdrop-blur border-b border-border px-6 py-3">
        <div className="max-w-5xl mx-auto flex items-center justify-between gap-4">
          {/* Left: project info */}
          <div className="min-w-0">
            <h1 className="text-base font-semibold truncate">
              LLM Inspector
              <span className="ml-2 text-muted-foreground font-normal">
                {data.project.title}
              </span>
            </h1>
          </div>

          {/* Right: navigation */}
          <div className="flex items-center gap-2 shrink-0">
            {/* Step picker */}
            <select
              value={currentStep}
              onChange={(e) => setCurrentStep(Number(e.target.value))}
              className="bg-surface border border-border rounded-md px-2 py-1.5 text-xs max-w-[260px] truncate"
            >
              {data.steps.map((s) => (
                <option key={s.step_number} value={s.step_number}>
                  {s.step_number + 1}. {s.breadcrumb.at(-1) ?? s.task.title}
                </option>
              ))}
            </select>

            <Button
              onClick={goPrev}
              disabled={currentStep === 0}
              variant="outline"
              size="sm"
            >
              <ChevronLeft className="h-4 w-4" />
            </Button>

            <span className="text-xs tabular-nums text-muted-foreground w-16 text-center">
              {currentStep + 1} / {data.total_steps}
            </span>

            <Button
              onClick={goNext}
              disabled={currentStep === data.total_steps - 1}
              variant="outline"
              size="sm"
            >
              <ChevronRight className="h-4 w-4" />
            </Button>
          </div>
        </div>

        {/* Breadcrumb */}
        <div className="max-w-5xl mx-auto mt-1">
          <p className="text-xs text-muted-foreground truncate">
            {step.breadcrumb.join("  /  ")}
          </p>
        </div>
      </header>

      {/* ----------------------------------------------------------------- */}
      {/* Main content                                                      */}
      {/* ----------------------------------------------------------------- */}
      <main className="max-w-5xl mx-auto px-6 py-6 space-y-5">
        {/* Progress bar */}
        <div className="flex items-center gap-3 text-xs text-muted-foreground">
          <span className="tabular-nums">
            {step.progress.completed}/{step.progress.total}
          </span>
          <div className="flex-1 h-1.5 bg-surface rounded-full overflow-hidden">
            <div
              className="h-full bg-accent rounded-full transition-all duration-300"
              style={{ width: `${step.progress.percentage}%` }}
            />
          </div>
          <span className="tabular-nums">{step.progress.percentage}%</span>
        </div>

        {/* ============================================================= */}
        {/* Section 1: System Prompt (collapsed)                          */}
        {/* ============================================================= */}
        <Section title="System Prompt" badge={`${step.system_prompt.length.toLocaleString()} chars`}>
          <pre className="whitespace-pre-wrap text-xs leading-relaxed bg-surface p-4 rounded-lg overflow-auto max-h-[600px] font-mono">
            {step.system_prompt}
          </pre>
        </Section>

        {/* ============================================================= */}
        {/* Section 2: Context (expanded)                                 */}
        {/* ============================================================= */}
        <Section title="Context" defaultOpen>
          <div className="space-y-5">
            {/* Task header */}
            <div>
              <div className="flex items-center gap-2 mb-1">
                <h3 className="font-semibold">{step.task.title}</h3>
                <Badge variant="outline" className="text-[10px]">
                  {step.task.task_type}
                </Badge>
                {step.task.subtask_type && (
                  <Badge variant="secondary" className="text-[10px]">
                    {step.task.subtask_type}
                  </Badge>
                )}
              </div>
              <p className="text-xs text-muted-foreground font-mono">{step.task.id}</p>
              {step.task.description && (
                <p className="text-sm mt-2">{step.task.description}</p>
              )}
            </div>

            {/* Acceptance Criteria */}
            {step.task.acceptance_criteria && (
              <Field label="Acceptance Criteria">
                <pre className="text-sm whitespace-pre-wrap">
                  {step.task.acceptance_criteria}
                </pre>
              </Field>
            )}

            {/* Learning Objectives */}
            {step.task.learning_objectives.length > 0 && (
              <Field label="Learning Objectives">
                <ul className="space-y-1.5">
                  {step.task.learning_objectives.map((obj, i) => (
                    <li key={i} className="flex items-start gap-2 text-sm">
                      <span
                        className={`inline-block rounded px-1.5 py-0.5 text-[10px] font-semibold uppercase shrink-0 mt-0.5 ${bloomColors[obj.level] ?? "bg-zinc-700 text-zinc-300"}`}
                      >
                        {obj.level}
                      </span>
                      <span>{obj.description}</span>
                    </li>
                  ))}
                </ul>
              </Field>
            )}

            {/* Tutor Guidance */}
            {step.task.tutor_guidance && (
              <Field label="Tutor Guidance">
                <TutorGuidance guidance={step.task.tutor_guidance} />
              </Field>
            )}

            {/* Content */}
            {step.task.content && (
              <Field label="Content">
                <pre className="text-sm whitespace-pre-wrap bg-surface p-3 rounded-lg max-h-[400px] overflow-auto">
                  {step.task.content}
                </pre>
              </Field>
            )}

            {/* Epic context */}
            {step.epic && (
              <Field label={`Epic: ${step.epic.title}`}>
                <p className="text-xs text-muted-foreground font-mono mb-1">
                  {step.epic.id}
                </p>
                {step.epic.description && (
                  <p className="text-sm">{step.epic.description}</p>
                )}
              </Field>
            )}
          </div>
        </Section>

        {/* ============================================================= */}
        {/* Section 3: Tool Call Results (expanded)                       */}
        {/* ============================================================= */}
        <Section title="Tool Call Results" badge="start_task" defaultOpen>
          <StartTaskResult data={step.tool_results.start_task as StartTaskData | undefined} />
        </Section>
      </main>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Sub-components
// ---------------------------------------------------------------------------

function Section({
  title,
  badge,
  defaultOpen = false,
  children,
}: {
  title: string;
  badge?: string;
  defaultOpen?: boolean;
  children: React.ReactNode;
}) {
  return (
    <details
      open={defaultOpen || undefined}
      className="group border border-border rounded-lg"
    >
      <summary className="px-4 py-3 cursor-pointer select-none flex items-center gap-2 hover:bg-surface/50 transition-colors">
        <span className="text-xs text-muted-foreground group-open:rotate-90 transition-transform">
          &#9654;
        </span>
        <span className="font-medium text-sm">{title}</span>
        {badge && (
          <span className="ml-auto text-xs text-muted-foreground font-mono">
            {badge}
          </span>
        )}
      </summary>
      <div className="px-4 pb-4">{children}</div>
    </details>
  );
}

function Field({
  label,
  children,
}: {
  label: string;
  children: React.ReactNode;
}) {
  return (
    <div>
      <h4 className="text-[10px] font-semibold uppercase tracking-wider text-muted-foreground mb-1.5">
        {label}
      </h4>
      {children}
    </div>
  );
}

function TutorGuidance({ guidance }: { guidance: Record<string, unknown> }) {
  const {
    teaching_approach,
    hints_to_give,
    common_mistakes,
    discussion_prompts,
    answer_rationale,
  } = guidance as {
    teaching_approach?: string;
    hints_to_give?: string[];
    common_mistakes?: string[];
    discussion_prompts?: string[];
    answer_rationale?: string;
  };

  return (
    <div className="space-y-3 text-sm">
      {teaching_approach && (
        <div>
          <span className="text-muted-foreground text-xs">Approach: </span>
          {teaching_approach}
        </div>
      )}
      {hints_to_give && hints_to_give.length > 0 && (
        <div>
          <span className="text-muted-foreground text-xs block mb-1">
            Hints (progressive):
          </span>
          <ol className="list-decimal list-inside space-y-0.5 pl-1">
            {hints_to_give.map((h, i) => (
              <li key={i}>{h}</li>
            ))}
          </ol>
        </div>
      )}
      {common_mistakes && common_mistakes.length > 0 && (
        <div>
          <span className="text-muted-foreground text-xs block mb-1">
            Watch for:
          </span>
          <ul className="list-disc list-inside space-y-0.5 pl-1">
            {common_mistakes.map((m, i) => (
              <li key={i}>{m}</li>
            ))}
          </ul>
        </div>
      )}
      {discussion_prompts && discussion_prompts.length > 0 && (
        <div>
          <span className="text-muted-foreground text-xs block mb-1">
            Discussion prompts:
          </span>
          <ul className="list-disc list-inside space-y-0.5 pl-1">
            {discussion_prompts.map((p, i) => (
              <li key={i}>{p}</li>
            ))}
          </ul>
        </div>
      )}
      {answer_rationale && (
        <div>
          <span className="text-muted-foreground text-xs">Rationale: </span>
          {answer_rationale}
        </div>
      )}
    </div>
  );
}

function StartTaskResult({ data }: { data: StartTaskData | undefined }) {
  if (!data) {
    return <p className="text-sm text-muted-foreground">No tool result data.</p>;
  }

  const ctx = data.context;

  return (
    <div className="space-y-4">
      {/* Response header */}
      <div className="flex items-center gap-3">
        <Badge variant={data.success ? "closed" : "destructive"} className="text-[10px]">
          {data.success ? "success" : "failed"}
        </Badge>
        <span className="text-sm font-mono text-muted-foreground">{data.task_id}</span>
        <Badge variant="in_progress" className="text-[10px]">{data.status}</Badge>
      </div>
      <p className="text-sm text-muted-foreground">{data.message}</p>

      {/* Context returned to LLM */}
      <div className="border border-border rounded-lg divide-y divide-border">
        {/* Task identity */}
        <div className="px-4 py-3">
          <div className="flex items-center gap-2 mb-1">
            <h4 className="font-semibold text-sm">{ctx.title}</h4>
            <Badge variant="outline" className="text-[10px]">{ctx.task_type}</Badge>
          </div>
          {ctx.description && (
            <p className="text-sm text-muted-foreground">{ctx.description}</p>
          )}
        </div>

        {/* Acceptance criteria */}
        {ctx.acceptance_criteria && (
          <div className="px-4 py-3">
            <h5 className="text-[10px] font-semibold uppercase tracking-wider text-muted-foreground mb-1">
              Acceptance Criteria
            </h5>
            <pre className="text-sm whitespace-pre-wrap">{ctx.acceptance_criteria}</pre>
          </div>
        )}

        {/* Learning objectives */}
        {ctx.learning_objectives.length > 0 && (
          <div className="px-4 py-3">
            <h5 className="text-[10px] font-semibold uppercase tracking-wider text-muted-foreground mb-1.5">
              Learning Objectives
            </h5>
            <ul className="space-y-1">
              {ctx.learning_objectives.map((obj, i) => (
                <li key={i} className="flex items-start gap-2 text-sm">
                  <span
                    className={`inline-block rounded px-1.5 py-0.5 text-[10px] font-semibold uppercase shrink-0 mt-0.5 ${bloomColors[obj.level] ?? "bg-zinc-700 text-zinc-300"}`}
                  >
                    {obj.level}
                  </span>
                  <span>{obj.description}</span>
                </li>
              ))}
            </ul>
          </div>
        )}

        {/* Tutor guidance */}
        {ctx.tutor_guidance && (
          <div className="px-4 py-3">
            <h5 className="text-[10px] font-semibold uppercase tracking-wider text-muted-foreground mb-1.5">
              Tutor Guidance
            </h5>
            <TutorGuidance guidance={ctx.tutor_guidance} />
          </div>
        )}

        {/* Content */}
        {ctx.content && (
          <div className="px-4 py-3">
            <h5 className="text-[10px] font-semibold uppercase tracking-wider text-muted-foreground mb-1">
              Content
            </h5>
            <pre className="text-sm whitespace-pre-wrap bg-surface p-3 rounded-lg max-h-[300px] overflow-auto">
              {ctx.content}
            </pre>
          </div>
        )}

        {/* Narrative context */}
        {ctx.narrative_context && (
          <div className="px-4 py-3">
            <h5 className="text-[10px] font-semibold uppercase tracking-wider text-muted-foreground mb-1">
              Narrative Context
            </h5>
            <p className="text-sm">{ctx.narrative_context}</p>
          </div>
        )}
      </div>
    </div>
  );
}
