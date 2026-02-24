/**
 * Tests for ChatPanel — verifies that workspace data (editor content + results)
 * is correctly assembled into a WorkspaceContext and passed to streamChat.
 *
 * This is the integration point: user types message → ChatPanel builds context
 * from props → calls streamChat with the right payload.
 */

import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

import type { QueryResult, PythonResult, WorkspaceContext } from "@/types";

// Mock streamChat to capture what ChatPanel sends
const mockStreamChat = vi.fn();

vi.mock("@/lib/api", () => ({
  streamChat: (...args: unknown[]) => mockStreamChat(...args),
}));

import { ChatPanel } from "./ChatPanel";

// Helper: create an async generator that yields chunks then stops
function fakeStream(...chunks: { type: string; content: unknown }[]) {
  return async function* () {
    for (const chunk of chunks) {
      yield chunk;
    }
  };
}

describe("ChatPanel context assembly", () => {
  beforeEach(() => {
    mockStreamChat.mockReset();
    // Default: return a stream that immediately finishes with a text response
    mockStreamChat.mockImplementation(() =>
      fakeStream(
        { type: "text", content: "Got it!" },
        { type: "done", content: null }
      )()
    );
  });

  it("sends SQL workspace context on submit", async () => {
    const user = userEvent.setup();
    const queryResults: QueryResult = {
      success: true,
      columns: ["id", "name"],
      rows: [[1, "Alice"]],
      rowCount: 1,
      duration: 42,
    };

    render(
      <ChatPanel
        editorContent="SELECT * FROM users;"
        queryResults={queryResults}
        currentTaskId={null}
        onTaskClick={() => {}}
        workspaceType="sql"
      />
    );

    const input = screen.getByPlaceholderText("Ask a question...");
    await user.type(input, "explain this query");
    await user.click(screen.getByRole("button", { name: /send message/i }));

    await waitFor(() => {
      expect(mockStreamChat).toHaveBeenCalledTimes(1);
    });

    const [message, , context] = mockStreamChat.mock.calls[0] as [string, string | undefined, WorkspaceContext];
    expect(message).toBe("explain this query");
    expect(context.workspace_type).toBe("sql");
    expect(context.editor_content).toBe("SELECT * FROM users;");
    expect(context.results).toEqual({
      success: true,
      columns: ["id", "name"],
      rows: [[1, "Alice"]],
      row_count: 1,
      duration: 42,
      error: undefined,
    });
  });

  it("sends Python workspace context on submit", async () => {
    const user = userEvent.setup();
    const pythonResults: PythonResult = {
      success: true,
      output: "42",
      duration: 10,
    };

    render(
      <ChatPanel
        editorContent="print(42)"
        queryResults={null}
        pythonResults={pythonResults}
        currentTaskId={null}
        onTaskClick={() => {}}
        workspaceType="python"
      />
    );

    const input = screen.getByPlaceholderText("Ask a question...");
    await user.type(input, "is this right?");
    await user.click(screen.getByRole("button", { name: /send message/i }));

    await waitFor(() => {
      expect(mockStreamChat).toHaveBeenCalledTimes(1);
    });

    const [, , context] = mockStreamChat.mock.calls[0] as [string, string | undefined, WorkspaceContext];
    expect(context.workspace_type).toBe("python");
    expect(context.editor_content).toBe("print(42)");
    expect(context.results).toEqual({
      success: true,
      output: "42",
      duration: 10,
      error: undefined,
      error_message: undefined,
      traceback: undefined,
    });
  });

  it("sends undefined editor_content when editor is empty", async () => {
    const user = userEvent.setup();

    render(
      <ChatPanel
        editorContent=""
        queryResults={null}
        currentTaskId={null}
        onTaskClick={() => {}}
        workspaceType="sql"
      />
    );

    const input = screen.getByPlaceholderText("Ask a question...");
    await user.type(input, "hello");
    await user.click(screen.getByRole("button", { name: /send message/i }));

    await waitFor(() => {
      expect(mockStreamChat).toHaveBeenCalledTimes(1);
    });

    const [, , context] = mockStreamChat.mock.calls[0] as [string, string | undefined, WorkspaceContext];
    expect(context.editor_content).toBeUndefined();
  });

  it("sends undefined results when queryResults is null", async () => {
    const user = userEvent.setup();

    render(
      <ChatPanel
        editorContent="SELECT 1;"
        queryResults={null}
        currentTaskId={null}
        onTaskClick={() => {}}
        workspaceType="sql"
      />
    );

    const input = screen.getByPlaceholderText("Ask a question...");
    await user.type(input, "hello");
    await user.click(screen.getByRole("button", { name: /send message/i }));

    await waitFor(() => {
      expect(mockStreamChat).toHaveBeenCalledTimes(1);
    });

    const [, , context] = mockStreamChat.mock.calls[0] as [string, string | undefined, WorkspaceContext];
    expect(context.results).toBeUndefined();
  });
});

describe("ChatPanel form behavior", () => {
  beforeEach(() => {
    mockStreamChat.mockReset();
    mockStreamChat.mockImplementation(() =>
      fakeStream(
        { type: "text", content: "Response" },
        { type: "done", content: null }
      )()
    );
  });

  it("does not submit when input is empty", async () => {
    const user = userEvent.setup();

    render(
      <ChatPanel
        editorContent=""
        queryResults={null}
        currentTaskId={null}
        onTaskClick={() => {}}
      />
    );

    // The send button should be disabled
    const sendButton = screen.getByRole("button", { name: /send message/i });
    expect(sendButton).toBeDisabled();

    // Try to submit anyway
    await user.click(sendButton);
    expect(mockStreamChat).not.toHaveBeenCalled();
  });

  it("displays streamed text in assistant message", async () => {
    const user = userEvent.setup();

    mockStreamChat.mockImplementation(() =>
      fakeStream(
        { type: "text", content: "Hello from AI" },
        { type: "done", content: null }
      )()
    );

    render(
      <ChatPanel
        editorContent=""
        queryResults={null}
        currentTaskId={null}
        onTaskClick={() => {}}
      />
    );

    const input = screen.getByPlaceholderText("Ask a question...");
    await user.type(input, "hi");
    await user.click(screen.getByRole("button", { name: /send message/i }));

    await waitFor(() => {
      expect(screen.getByText("Hello from AI")).toBeInTheDocument();
    });
  });
});

describe("ChatPanel welcome messages", () => {
  it("shows SQL welcome message by default", () => {
    render(
      <ChatPanel
        editorContent=""
        queryResults={null}
        currentTaskId={null}
        onTaskClick={() => {}}
        workspaceType="sql"
      />
    );

    expect(screen.getByText(/I can see your SQL editor/)).toBeInTheDocument();
  });

  it("shows Python welcome message", () => {
    render(
      <ChatPanel
        editorContent=""
        queryResults={null}
        currentTaskId={null}
        onTaskClick={() => {}}
        workspaceType="python"
      />
    );

    expect(screen.getByText(/I can see your Python editor/)).toBeInTheDocument();
  });

  it("shows cybersecurity welcome message", () => {
    render(
      <ChatPanel
        editorContent=""
        queryResults={null}
        currentTaskId={null}
        onTaskClick={() => {}}
        workspaceType="cybersecurity"
      />
    );

    expect(screen.getByText(/cybersecurity/i)).toBeInTheDocument();
  });
});

describe("ChatPanel reset", () => {
  beforeEach(() => {
    mockStreamChat.mockReset();
    mockStreamChat.mockImplementation(() =>
      fakeStream(
        { type: "text", content: "AI response" },
        { type: "done", content: null }
      )()
    );
  });

  it("reset clears messages and shows welcome", async () => {
    const user = userEvent.setup();

    render(
      <ChatPanel
        editorContent=""
        queryResults={null}
        currentTaskId={null}
        onTaskClick={() => {}}
        workspaceType="sql"
      />
    );

    // Send a message
    const input = screen.getByPlaceholderText("Ask a question...");
    await user.type(input, "hello");
    await user.click(screen.getByRole("button", { name: /send message/i }));

    await waitFor(() => {
      expect(screen.getByText("AI response")).toBeInTheDocument();
    });

    // Click reset
    await user.click(screen.getByText("Reset"));

    // User message should be gone, welcome should be back
    expect(screen.queryByText("hello")).not.toBeInTheDocument();
    expect(screen.getByText(/I can see your SQL editor/)).toBeInTheDocument();
  });
});
