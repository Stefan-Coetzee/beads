// Task types
export type TaskType = "project" | "epic" | "task" | "subtask";
export type TaskStatus = "open" | "in_progress" | "blocked" | "closed";

export interface TaskNode {
  id: string;
  title: string;
  description?: string;
  task_type: TaskType;
  status: TaskStatus;
  priority: number;
  parent_id?: string;
  children: TaskNode[];
  progress?: {
    completed: number;
    total: number;
  };
}

export interface TaskDetail {
  id: string;
  title: string;
  description: string;
  acceptance_criteria: string;
  notes: string;
  status: TaskStatus;
  task_type: TaskType;
  priority: number;
  parent_id?: string;
  children: TaskSummary[];
  learning_objectives: LearningObjective[];
  content?: string;
  tutor_guidance?: TutorGuidance;
  narrative_context?: string;
  blocked_by: TaskSummary[];
  blocks: TaskSummary[];
  submission_count: number;
  latest_validation_passed?: boolean;
  status_summaries: StatusSummary[];
}

export interface TaskSummary {
  id: string;
  title: string;
  status: TaskStatus;
  task_type: TaskType;
  priority: number;
  has_children: boolean;
  parent_id?: string;
  description?: string;
  content?: string;
  summary?: string;
}

export interface LearningObjective {
  id: string;
  level: BloomLevel;
  description: string;
}

export type BloomLevel =
  | "remember"
  | "understand"
  | "apply"
  | "analyze"
  | "evaluate"
  | "create";

export interface TutorGuidance {
  teaching_approach?: string;
  discussion_prompts?: string[];
  common_mistakes?: string[];
  hints_to_give?: string[];
  answer_rationale?: string;
}

export interface StatusSummary {
  id: string;
  summary: string;
  created_at: string;
}

// Project types
export interface Project {
  id: string;
  title: string;
  description: string;
  narrative_context?: string;
  workspace_type?: WorkspaceType;
}

export interface ProjectTree {
  project: Project;
  hierarchy: TaskNode[];
  progress: ProjectProgress;
}

export interface ProjectProgress {
  total_tasks: number;
  completed_tasks: number;
  in_progress: number;
  blocked: number;
  percentage: number;
}

// Chat types
export interface ChatMessage {
  id: string;
  role: "user" | "assistant" | "system";
  content: string;
  tool_calls?: ToolCall[];
  created_at?: string;
}

export interface ToolCall {
  id: string;
  name: string;
  args: Record<string, unknown>;
}

// Query result types (used by SQL components)
export interface QueryResult {
  success: boolean;
  columns?: string[];
  rows?: unknown[][];
  rowCount?: number;
  duration: number;
  error?: string;
}

// Python result types (used by Python components)
export interface PythonResult {
  success: boolean;
  output?: string;
  error?: string;
  errorMessage?: string;  // Short error message
  traceback?: string;     // Full traceback for expandable view
  duration: number;
}

// Unified execution result for API communication
export interface ExecutionResult {
  success: boolean;
  duration: number;
  // For successful results
  output?: string;           // Text output (Python stdout, or messages)
  columns?: string[];        // Column names (SQL only)
  rows?: unknown[][];        // Result rows (SQL only)
  row_count?: number;        // Number of rows (SQL only)
  // For errors
  error?: string;            // Error message
  error_message?: string;    // Short error message (Python)
  traceback?: string;        // Full traceback (Python)
}

// Workspace context for chat API
export interface WorkspaceContext {
  editor_content?: string;
  results?: ExecutionResult;
  workspace_type?: WorkspaceType;
}

// Workspace types
export type WorkspaceType = "sql" | "python" | "cybersecurity";

// Helper to convert QueryResult to ExecutionResult
export function queryResultToExecutionResult(qr: QueryResult | null): ExecutionResult | undefined {
  if (!qr) return undefined;
  return {
    success: qr.success,
    duration: qr.duration,
    columns: qr.columns,
    rows: qr.rows,
    row_count: qr.rowCount,
    error: qr.error,
  };
}

// Helper to convert PythonResult to ExecutionResult
export function pythonResultToExecutionResult(pr: PythonResult | null): ExecutionResult | undefined {
  if (!pr) return undefined;
  return {
    success: pr.success,
    duration: pr.duration,
    output: pr.output,
    error: pr.error,
    error_message: pr.errorMessage,
    traceback: pr.traceback,
  };
}

// API response types
export interface ChatResponse {
  response: string;
  thread_id: string;
  tool_calls?: ToolCall[];
}

export interface SubmitResponse {
  success: boolean;
  submission_id: string;
  attempt_number: number;
  validation_passed?: boolean;
  validation_message?: string;
  status: TaskStatus;
  message: string;
  ready_tasks?: TaskSummary[];
  auto_closed?: { id: string; title: string; task_type: TaskType }[];
}
