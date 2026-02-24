import type {
  ProjectTree,
  TaskDetail,
  ChatResponse,
  // SubmitResponse,  // Disabled: direct submit (see ADR-004)
  TaskSummary,
  WorkspaceContext,
} from "@/types";
import { getLTIContext } from "./lti";

// Empty string = relative URLs → proxied through Next.js → FastAPI.
// Set NEXT_PUBLIC_API_URL to override (e.g. direct FastAPI for local dev without proxy).
export const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || "";

/**
 * Thin fetch wrapper that attaches LTI headers when running inside
 * an LTI session and the ngrok skip-browser-warning header.
 */
export function lttFetch(
  input: RequestInfo | URL,
  init?: RequestInit
): Promise<Response> {
  const headers = new Headers(init?.headers);

  // Attach LTI launch ID so the backend can resolve the launch context
  const lti = getLTIContext();
  if (lti?.isLTI && lti.launchId) {
    headers.set("X-LTI-Launch-Id", lti.launchId);
  }

  // Skip the ngrok browser interstitial page
  headers.set("ngrok-skip-browser-warning", "1");

  return fetch(input, { ...init, headers });
}

/**
 * Type-safe API client.
 *
 * Learner identity is resolved server-side from the X-LTI-Launch-Id header
 * (injected by lttFetch).  No client-side learnerId params needed.
 */
export const api = {
  // Project list
  async getProjects(): Promise<{ id: string; title: string; workspace_type: string | null }[]> {
    const res = await lttFetch(`${API_BASE_URL}/api/v1/projects`);
    if (!res.ok) throw new Error("Failed to fetch projects");
    return res.json();
  },

  // Project endpoints
  async getProjectTree(projectId: string): Promise<ProjectTree> {
    const res = await lttFetch(
      `${API_BASE_URL}/api/v1/project/${projectId}/tree`
    );
    if (!res.ok) throw new Error("Failed to fetch project tree");
    return res.json();
  },

  // Task endpoints
  async getTaskDetails(taskId: string): Promise<TaskDetail> {
    const res = await lttFetch(
      `${API_BASE_URL}/api/v1/task/${taskId}`
    );
    if (!res.ok) throw new Error("Failed to fetch task");
    return res.json();
  },

  async getReadyTasks(
    projectId: string,
    limit: number = 5
  ): Promise<{ tasks: TaskSummary[]; total_ready: number; message: string }> {
    const res = await lttFetch(
      `${API_BASE_URL}/api/v1/project/${projectId}/ready?limit=${limit}`
    );
    if (!res.ok) throw new Error("Failed to fetch ready tasks");
    return res.json();
  },

  // Progress endpoints
  async startTask(
    taskId: string
  ): Promise<{ success: boolean; status: string; message: string }> {
    const res = await lttFetch(`${API_BASE_URL}/api/v1/task/${taskId}/start`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({}),
    });
    if (!res.ok) throw new Error("Failed to start task");
    return res.json();
  },

  // --- Disabled: direct submit (see ADR-004) ---
  // All submissions go through the agent chat flow until custom validators exist.
  // async submitWork(
  //   taskId: string,
  //   content: string,
  //   submissionType: string = "sql"
  // ): Promise<SubmitResponse> {
  //   const res = await lttFetch(`${API_BASE_URL}/api/v1/task/${taskId}/submit`, {
  //     method: "POST",
  //     headers: { "Content-Type": "application/json" },
  //     body: JSON.stringify({ content, submission_type: submissionType }),
  //   });
  //   if (!res.ok) throw new Error("Failed to submit work");
  //   return res.json();
  // },

  // Chat endpoints
  async chat(
    message: string,
    threadId?: string,
    context?: WorkspaceContext
  ): Promise<ChatResponse> {
    const res = await lttFetch(`${API_BASE_URL}/api/v1/chat`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        message,
        thread_id: threadId,
        context,
      }),
    });
    if (!res.ok) throw new Error("Failed to send message");
    return res.json();
  },

  // Database initialization
  async getDatabaseSchema(
    projectId: string
  ): Promise<{ schema: string; sample_data: string }> {
    const res = await lttFetch(
      `${API_BASE_URL}/api/v1/project/${projectId}/database`
    );
    if (!res.ok) throw new Error("Failed to fetch database schema");
    return res.json();
  },
};

/**
 * Stream chat messages using fetch.
 *
 * Learner/project identity resolved server-side from the LTI launch header.
 */
export async function* streamChat(
  message: string,
  threadId?: string,
  context?: WorkspaceContext
): AsyncGenerator<{ type: string; content: unknown }> {
  // Ensure context is properly structured for the API
  const requestBody = {
    message,
    thread_id: threadId,
    context: context ? {
      workspace_type: context.workspace_type || "sql",
      editor_content: context.editor_content || null,
      results: context.results || null,
    } : null,
  };

  const res = await lttFetch(`${API_BASE_URL}/api/v1/chat/stream`, {
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
