import type {
  ProjectTree,
  TaskDetail,
  ChatResponse,
  SubmitResponse,
  TaskSummary,
  WorkspaceContext,
} from "@/types";

export const API_BASE_URL =
  process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

/**
 * Type-safe API client
 */
export const api = {
  // Project list
  async getProjects(): Promise<{ id: string; title: string; workspace_type: string | null }[]> {
    const res = await fetch(`${API_BASE_URL}/api/v1/projects`);
    if (!res.ok) throw new Error("Failed to fetch projects");
    return res.json();
  },

  // Project endpoints
  async getProjectTree(
    projectId: string,
    learnerId: string
  ): Promise<ProjectTree> {
    const res = await fetch(
      `${API_BASE_URL}/api/v1/project/${projectId}/tree?learner_id=${learnerId}`
    );
    if (!res.ok) throw new Error("Failed to fetch project tree");
    return res.json();
  },

  // Task endpoints
  async getTaskDetails(
    taskId: string,
    learnerId: string
  ): Promise<TaskDetail> {
    const res = await fetch(
      `${API_BASE_URL}/api/v1/task/${taskId}?learner_id=${learnerId}`
    );
    if (!res.ok) throw new Error("Failed to fetch task");
    return res.json();
  },

  async getReadyTasks(
    projectId: string,
    learnerId: string,
    limit: number = 5
  ): Promise<{ tasks: TaskSummary[]; total_ready: number; message: string }> {
    const res = await fetch(
      `${API_BASE_URL}/api/v1/project/${projectId}/ready?learner_id=${learnerId}&limit=${limit}`
    );
    if (!res.ok) throw new Error("Failed to fetch ready tasks");
    return res.json();
  },

  // Progress endpoints
  async startTask(
    taskId: string,
    learnerId: string
  ): Promise<{ success: boolean; status: string; message: string }> {
    const res = await fetch(`${API_BASE_URL}/api/v1/task/${taskId}/start`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ learner_id: learnerId }),
    });
    if (!res.ok) throw new Error("Failed to start task");
    return res.json();
  },

  async submitWork(
    taskId: string,
    learnerId: string,
    content: string,
    submissionType: string = "sql"
  ): Promise<SubmitResponse> {
    const res = await fetch(`${API_BASE_URL}/api/v1/task/${taskId}/submit`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        learner_id: learnerId,
        content,
        submission_type: submissionType,
      }),
    });
    if (!res.ok) throw new Error("Failed to submit work");
    return res.json();
  },

  // Chat endpoints
  async chat(
    message: string,
    learnerId: string,
    projectId: string,
    threadId?: string,
    context?: WorkspaceContext
  ): Promise<ChatResponse> {
    const res = await fetch(`${API_BASE_URL}/api/v1/chat`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        message,
        learner_id: learnerId,
        project_id: projectId,
        thread_id: threadId,
        context,
      }),
    });
    if (!res.ok) throw new Error("Failed to send message");
    return res.json();
  },

  // Stream chat endpoint
  chatStream(
    message: string,
    learnerId: string,
    projectId: string,
    threadId?: string,
    context?: WorkspaceContext
  ): EventSource {
    // Note: For proper streaming, we'll use fetch with ReadableStream
    // EventSource doesn't support POST, so we'll handle this differently
    const url = new URL(`${API_BASE_URL}/api/v1/chat/stream`);
    // This is a placeholder - actual implementation needs POST body streaming
    throw new Error("Use fetch-based streaming instead");
  },

  // Database initialization
  async getDatabaseSchema(
    projectId: string
  ): Promise<{ schema: string; sample_data: string }> {
    const res = await fetch(
      `${API_BASE_URL}/api/v1/project/${projectId}/database`
    );
    if (!res.ok) throw new Error("Failed to fetch database schema");
    return res.json();
  },
};

/**
 * Stream chat messages using fetch
 */
export async function* streamChat(
  message: string,
  learnerId: string,
  projectId: string,
  threadId?: string,
  context?: WorkspaceContext
): AsyncGenerator<{ type: string; content: unknown }> {
  // Ensure context is properly structured for the API
  const requestBody = {
    message,
    learner_id: learnerId,
    project_id: projectId,
    thread_id: threadId,
    context: context ? {
      workspace_type: context.workspace_type || "sql",
      editor_content: context.editor_content || null,
      results: context.results || null,
    } : null,
  };

  const res = await fetch(`${API_BASE_URL}/api/v1/chat/stream`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(requestBody),
  });

  if (!res.ok) throw new Error("Failed to start chat stream");
  if (!res.body) throw new Error("No response body");

  const reader = res.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;

    buffer += decoder.decode(value, { stream: true });
    const lines = buffer.split("\n");
    buffer = lines.pop() || "";

    for (const line of lines) {
      if (line.startsWith("data: ")) {
        try {
          const data = JSON.parse(line.slice(6));
          yield data;
        } catch {
          // Ignore parse errors
        }
      }
    }
  }
}
