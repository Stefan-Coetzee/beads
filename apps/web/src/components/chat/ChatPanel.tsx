"use client";

import { useState, useRef, useEffect, useCallback } from "react";
import { Send, RotateCcw, Loader2 } from "lucide-react";
import ReactMarkdown from "react-markdown";

import { Button } from "@/components/ui/button";
import { cn, parseTaskReferences } from "@/lib/utils";
import { streamChat } from "@/lib/api";
import type { QueryResult, WorkspaceType, PythonResult, WorkspaceContext } from "@/types";
import { queryResultToExecutionResult, pythonResultToExecutionResult } from "@/types";

interface Message {
  id: string;
  role: "user" | "assistant";
  content: string;
}

interface ChatPanelProps {
  learnerId: string;
  projectId: string;
  editorContent: string;
  queryResults: QueryResult | null;
  pythonResults?: PythonResult | null;
  currentTaskId: string | null;
  onTaskClick: (taskId: string) => void;
  workspaceType?: WorkspaceType;
}

// Contextual welcome messages based on workspace type
const WELCOME_MESSAGES: Record<WorkspaceType, string> = {
  sql: "Hello! I'm your learning assistant. I can see your SQL editor and query results. Feel free to ask me questions about SQL, your current task, or the project. What would you like to work on?",
  python: "Hello! I'm your learning assistant. I can see your Python editor and output. You can use packages like **numpy**, **pandas**, **matplotlib**, and more - they'll be loaded automatically when you import them. Ask me about Python, data analysis, or your current task!",
  cybersecurity: "Hello! I'm your learning assistant for cybersecurity. I can help you understand security concepts, analyze code for vulnerabilities, and guide you through security-related tasks. What would you like to explore?",
};

export function ChatPanel({
  learnerId,
  projectId,
  editorContent,
  queryResults,
  pythonResults,
  currentTaskId,
  onTaskClick,
  workspaceType = "sql",
}: ChatPanelProps) {
  const [messages, setMessages] = useState<Message[]>([
    {
      id: "welcome",
      role: "assistant",
      content: WELCOME_MESSAGES[workspaceType],
    },
  ]);
  const [input, setInput] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const [threadId, setThreadId] = useState<string | null>(null);
  const messagesEndRef = useRef<HTMLDivElement>(null);

  // Auto-scroll to bottom
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  const handleSubmit = useCallback(
    async (e: React.FormEvent) => {
      e.preventDefault();
      if (!input.trim() || isLoading) return;

      const userMessage: Message = {
        id: `user-${Date.now()}`,
        role: "user",
        content: input.trim(),
      };

      setMessages((prev) => [...prev, userMessage]);
      setInput("");
      setIsLoading(true);

      // Create placeholder for assistant response
      const assistantId = `assistant-${Date.now()}`;
      setMessages((prev) => [
        ...prev,
        { id: assistantId, role: "assistant", content: "" },
      ]);

      try {
        // Stream response
        let fullContent = "";
        let lastToolCall = "";
        // Build unified context for the API
        const context: WorkspaceContext = {
          editor_content: editorContent || undefined,
          workspace_type: workspaceType,
          results: workspaceType === "python"
            ? pythonResultToExecutionResult(pythonResults ?? null)
            : queryResultToExecutionResult(queryResults),
        };

        const stream = streamChat(
          userMessage.content,
          learnerId,
          projectId,
          threadId || undefined,
          context
        );

        for await (const chunk of stream) {
          if (chunk.type === "text" && typeof chunk.content === "string") {
            fullContent += chunk.content;
            setMessages((prev) =>
              prev.map((m) =>
                m.id === assistantId ? { ...m, content: fullContent } : m
              )
            );
          } else if (chunk.type === "tool_call") {
            // Track tool calls for display if no text response
            const toolName = typeof chunk.content === "object" && chunk.content
              ? (chunk.content as { name?: string }).name || "tool"
              : "tool";
            lastToolCall = toolName;
          } else if (chunk.type === "tool_result") {
            // Check if this is the final response (name is null and result contains the message)
            if (typeof chunk.content === "object" && chunk.content) {
              const resultContent = chunk.content as { name?: string | null; result?: string };
              if (resultContent.name === null && resultContent.result) {
                // This is the final formatted response from the agent
                fullContent = resultContent.result;
                setMessages((prev) =>
                  prev.map((m) =>
                    m.id === assistantId ? { ...m, content: fullContent } : m
                  )
                );
              }
            }
          } else if (chunk.type === "done") {
            break;
          } else if (chunk.type === "error") {
            fullContent = `Error: ${typeof chunk.content === "string" ? chunk.content : "Unknown error"}`;
            setMessages((prev) =>
              prev.map((m) =>
                m.id === assistantId ? { ...m, content: fullContent } : m
              )
            );
          }
        }

        // Ensure message has content after stream completes
        if (!fullContent) {
          fullContent = lastToolCall
            ? `[Used ${lastToolCall} - waiting for response...]`
            : "I processed your request but have no text response.";
          setMessages((prev) =>
            prev.map((m) =>
              m.id === assistantId ? { ...m, content: fullContent } : m
            )
          );
        }

        // Set thread ID for conversation continuity
        if (!threadId) {
          setThreadId(`${learnerId}-${projectId}`);
        }
      } catch (error) {
        console.error("Chat error:", error);
        setMessages((prev) =>
          prev.map((m) =>
            m.id === assistantId
              ? {
                  ...m,
                  content:
                    "Sorry, I encountered an error. Please make sure the backend server is running at http://localhost:8000",
                }
              : m
          )
        );
      } finally {
        setIsLoading(false);
      }
    },
    [input, isLoading, learnerId, projectId, threadId, editorContent, queryResults, pythonResults, workspaceType]
  );

  const handleReset = () => {
    setMessages([
      {
        id: "welcome",
        role: "assistant",
        content: WELCOME_MESSAGES[workspaceType],
      },
    ]);
    setThreadId(null);
  };

  // Render message content with clickable task references
  const renderContent = (content: string) => {
    const taskIds = parseTaskReferences(content);

    if (taskIds.length === 0) {
      return (
        <div className="prose prose-sm prose-invert max-w-none">
          <ReactMarkdown
            components={{
              code: ({ className, children, ...props }) => {
                const isInline = !className;
                return isInline ? (
                  <code className="bg-elevated px-1 py-0.5 rounded text-sm" {...props}>
                    {children}
                  </code>
                ) : (
                  <code className={cn("block bg-elevated p-3 rounded-lg text-sm overflow-x-auto", className)} {...props}>
                    {children}
                  </code>
                );
              },
            }}
          >
            {content}
          </ReactMarkdown>
        </div>
      );
    }

    // Replace task IDs with clickable buttons
    let processedContent = content;
    taskIds.forEach((taskId) => {
      processedContent = processedContent.replace(
        new RegExp(taskId, "g"),
        `[TASK:${taskId}]`
      );
    });

    const parts = processedContent.split(/\[TASK:(proj-[a-z0-9]+(?:\.\d+)*)\]/gi);

    return (
      <div className="prose prose-sm prose-invert max-w-none">
        {parts.map((part, i) => {
          if (taskIds.includes(part)) {
            return (
              <button
                key={i}
                onClick={() => onTaskClick(part)}
                className="inline-flex items-center px-2 py-0.5 rounded bg-accent/10 text-accent hover:bg-accent/20 transition-colors font-mono text-sm mx-0.5"
              >
                #{part}
              </button>
            );
          }
          return (
            <span key={i} className="inline">
              <ReactMarkdown
                components={{
                  p: ({ children }) => <span>{children}</span>,
                }}
              >
                {part}
              </ReactMarkdown>
            </span>
          );
        })}
      </div>
    );
  };

  return (
    <div className="flex flex-col h-full bg-surface rounded-lg border border-border">
      {/* Header */}
      <div className="flex items-center justify-between px-4 py-3 border-b border-border">
        <div>
          <h3 className="font-medium">AI Assistant</h3>
          {currentTaskId && (
            <p className="text-xs text-muted-foreground">
              Working on: {currentTaskId}
            </p>
          )}
        </div>
        <Button variant="ghost" size="sm" onClick={handleReset}>
          <RotateCcw className="h-4 w-4 mr-1" />
          Reset
        </Button>
      </div>

      {/* Messages */}
      <div className="flex-1 overflow-y-auto p-4 space-y-4">
        {messages.map((message) => (
          <div
            key={message.id}
            className={cn(
              "flex",
              message.role === "user" ? "justify-end" : "justify-start"
            )}
          >
            <div
              className={cn(
                "max-w-[85%] rounded-lg px-4 py-3",
                message.role === "user"
                  ? "bg-accent text-accent-foreground"
                  : "bg-elevated"
              )}
            >
              {message.role === "user" ? (
                <p className="text-sm">{message.content}</p>
              ) : message.content ? (
                renderContent(message.content)
              ) : (
                <div className="flex items-center gap-2 text-muted-foreground">
                  <Loader2 className="h-4 w-4 animate-spin" />
                  <span className="text-sm">Thinking...</span>
                </div>
              )}
            </div>
          </div>
        ))}
        <div ref={messagesEndRef} />
      </div>

      {/* Input */}
      <form onSubmit={handleSubmit} className="p-4 border-t border-border">
        <div className="flex gap-2">
          <input
            type="text"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            placeholder="Ask a question..."
            disabled={isLoading}
            className="flex-1 bg-elevated border border-border rounded-lg px-4 py-2 text-sm focus:outline-none focus:ring-1 focus:ring-accent"
          />
          <Button type="submit" disabled={isLoading || !input.trim()}>
            <Send className="h-4 w-4" />
          </Button>
        </div>
        <p className="text-xs text-muted-foreground mt-2">
          {workspaceType === "python"
            ? "I can see your Python code and output"
            : workspaceType === "cybersecurity"
            ? "I can help analyze security concepts and code"
            : "I can see your SQL code and query results"}
        </p>
      </form>
    </div>
  );
}
