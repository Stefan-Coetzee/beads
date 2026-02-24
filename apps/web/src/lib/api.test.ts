/**
 * Tests for the API layer — verifies that the frontend sends workspace data
 * to the backend in the correct format so the LLM receives it.
 */

import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import type { WorkspaceContext } from "@/types";

// Mock the lti module before importing api
vi.mock("@/lib/lti", () => ({
  getLTIContext: vi.fn(() => null),
}));

import { lttFetch, streamChat } from "./api";
import { getLTIContext } from "@/lib/lti";

const mockedGetLTIContext = vi.mocked(getLTIContext);

describe("lttFetch", () => {
  const originalFetch = globalThis.fetch;

  beforeEach(() => {
    globalThis.fetch = vi.fn().mockResolvedValue(new Response("ok", { status: 200 }));
    mockedGetLTIContext.mockReturnValue(null);
  });

  afterEach(() => {
    globalThis.fetch = originalFetch;
    vi.restoreAllMocks();
  });

  it("always sets ngrok-skip-browser-warning header", async () => {
    await lttFetch("/api/test");
    const call = vi.mocked(globalThis.fetch).mock.calls[0];
    const headers = call[1]?.headers as Headers;
    expect(headers.get("ngrok-skip-browser-warning")).toBe("1");
  });

  it("sets X-LTI-Launch-Id when LTI context exists", async () => {
    mockedGetLTIContext.mockReturnValue({
      isLTI: true,
      launchId: "launch-abc",
      learnerId: "learner-1",
      projectId: "proj-1",
      workspaceType: "sql",
      isInstructor: false,
    });

    await lttFetch("/api/test");
    const call = vi.mocked(globalThis.fetch).mock.calls[0];
    const headers = call[1]?.headers as Headers;
    expect(headers.get("X-LTI-Launch-Id")).toBe("launch-abc");
  });

  it("does not set X-LTI-Launch-Id when no LTI context", async () => {
    mockedGetLTIContext.mockReturnValue(null);

    await lttFetch("/api/test");
    const call = vi.mocked(globalThis.fetch).mock.calls[0];
    const headers = call[1]?.headers as Headers;
    expect(headers.has("X-LTI-Launch-Id")).toBe(false);
  });

  it("passes through method and body", async () => {
    await lttFetch("/api/test", {
      method: "POST",
      body: JSON.stringify({ foo: "bar" }),
    });
    const call = vi.mocked(globalThis.fetch).mock.calls[0];
    expect(call[1]?.method).toBe("POST");
    expect(call[1]?.body).toBe(JSON.stringify({ foo: "bar" }));
  });
});

describe("streamChat", () => {
  const originalFetch = globalThis.fetch;

  beforeEach(() => {
    mockedGetLTIContext.mockReturnValue(null);
  });

  afterEach(() => {
    globalThis.fetch = originalFetch;
    vi.restoreAllMocks();
  });

  function mockSSEResponse(...lines: string[]) {
    const body = lines.join("\n") + "\n";
    const stream = new ReadableStream({
      start(controller) {
        controller.enqueue(new TextEncoder().encode(body));
        controller.close();
      },
    });
    globalThis.fetch = vi.fn().mockResolvedValue(
      new Response(stream, { status: 200 })
    );
  }

  it("POSTs to /api/v1/chat/stream with correct content type", async () => {
    mockSSEResponse('data: {"type":"done","content":null}');

    const gen = streamChat("hello");
    for await (const _ of gen) { /* drain */ }

    const call = vi.mocked(globalThis.fetch).mock.calls[0];
    expect(call[0]).toContain("/api/v1/chat/stream");
    expect(call[1]?.method).toBe("POST");
  });

  it("sends correct body with full SQL context", async () => {
    mockSSEResponse('data: {"type":"done","content":null}');

    const context: WorkspaceContext = {
      workspace_type: "sql",
      editor_content: "SELECT * FROM users;",
      results: {
        success: true,
        duration: 42,
        columns: ["id", "name"],
        rows: [[1, "Alice"]],
        row_count: 1,
      },
    };

    const gen = streamChat("explain this", "thread-1", context);
    for await (const _ of gen) { /* drain */ }

    const call = vi.mocked(globalThis.fetch).mock.calls[0];
    const body = JSON.parse(call[1]?.body as string);

    expect(body.message).toBe("explain this");
    expect(body.thread_id).toBe("thread-1");
    expect(body.context).toEqual({
      workspace_type: "sql",
      editor_content: "SELECT * FROM users;",
      results: {
        success: true,
        duration: 42,
        columns: ["id", "name"],
        rows: [[1, "Alice"]],
        row_count: 1,
      },
    });
  });

  it("sends correct body with full Python context", async () => {
    mockSSEResponse('data: {"type":"done","content":null}');

    const context: WorkspaceContext = {
      workspace_type: "python",
      editor_content: "print('hi')",
      results: {
        success: true,
        duration: 10,
        output: "hi",
      },
    };

    const gen = streamChat("is this right?", undefined, context);
    for await (const _ of gen) { /* drain */ }

    const call = vi.mocked(globalThis.fetch).mock.calls[0];
    const body = JSON.parse(call[1]?.body as string);

    expect(body.context.workspace_type).toBe("python");
    expect(body.context.editor_content).toBe("print('hi')");
    expect(body.context.results.output).toBe("hi");
  });

  it("sends null context when not provided", async () => {
    mockSSEResponse('data: {"type":"done","content":null}');

    const gen = streamChat("hello");
    for await (const _ of gen) { /* drain */ }

    const call = vi.mocked(globalThis.fetch).mock.calls[0];
    const body = JSON.parse(call[1]?.body as string);

    expect(body.context).toBeNull();
  });

  it("yields text chunks from SSE stream", async () => {
    mockSSEResponse(
      'data: {"type":"text","content":"Hello "}',
      'data: {"type":"text","content":"world"}',
      'data: {"type":"done","content":null}',
    );

    const chunks = [];
    for await (const chunk of streamChat("test")) {
      chunks.push(chunk);
    }

    expect(chunks).toEqual([
      { type: "text", content: "Hello " },
      { type: "text", content: "world" },
      { type: "done", content: null },
    ]);
  });

  it("yields tool_call and tool_result chunks", async () => {
    mockSSEResponse(
      'data: {"type":"tool_call","content":{"name":"get_ready","args":{}}}',
      'data: {"type":"tool_result","content":{"name":"get_ready","result":"done"}}',
      'data: {"type":"done","content":null}',
    );

    const chunks = [];
    for await (const chunk of streamChat("test")) {
      chunks.push(chunk);
    }

    expect(chunks[0].type).toBe("tool_call");
    expect(chunks[1].type).toBe("tool_result");
  });

  it("ignores malformed JSON in data lines", async () => {
    mockSSEResponse(
      'data: not-json',
      'data: {"type":"text","content":"ok"}',
      'data: {"type":"done","content":null}',
    );

    const chunks = [];
    for await (const chunk of streamChat("test")) {
      chunks.push(chunk);
    }

    // Malformed line skipped, only valid chunks yielded
    expect(chunks).toHaveLength(2);
    expect(chunks[0]).toEqual({ type: "text", content: "ok" });
  });

  it("throws on non-ok response", async () => {
    globalThis.fetch = vi.fn().mockResolvedValue(
      new Response("error", { status: 500 })
    );

    const gen = streamChat("test");
    await expect(async () => {
      for await (const _ of gen) { /* drain */ }
    }).rejects.toThrow("Failed to start chat stream");
  });
});
