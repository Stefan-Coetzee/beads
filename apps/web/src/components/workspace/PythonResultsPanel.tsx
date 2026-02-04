"use client";

import { useState } from "react";
import { formatDuration } from "@/lib/utils";
import type { PythonResult } from "@/lib/python-engine";
import { CheckCircle2, XCircle, Terminal, ChevronDown, ChevronRight } from "lucide-react";

interface PythonResultsPanelProps {
  result: PythonResult | null;
  isExecuting?: boolean;
}

export function PythonResultsPanel({ result, isExecuting = false }: PythonResultsPanelProps) {
  const [showTraceback, setShowTraceback] = useState(false);

  if (isExecuting) {
    return (
      <div className="h-full flex items-center justify-center bg-surface rounded-lg border border-border">
        <div className="text-center">
          <div className="animate-spin h-8 w-8 border-2 border-accent border-t-transparent rounded-full mx-auto mb-3" />
          <p className="text-sm text-muted-foreground">Running Python...</p>
        </div>
      </div>
    );
  }

  if (!result) {
    return (
      <div className="h-full flex items-center justify-center bg-surface rounded-lg border border-border">
        <div className="text-center text-muted-foreground">
          <Terminal className="h-12 w-12 mx-auto mb-3 opacity-50" />
          <p className="text-sm">Run your code to see output</p>
          <p className="text-xs mt-2 opacity-70">Imports like numpy, pandas are available via micropip</p>
        </div>
      </div>
    );
  }

  if (!result.success) {
    const hasTraceback = result.traceback && result.traceback.trim().length > 0;
    const errorMessage = result.errorMessage || result.error || "Unknown error";

    return (
      <div className="h-full bg-surface rounded-lg border border-border overflow-hidden flex flex-col">
        <div className="flex items-center gap-2 px-4 py-2 bg-red-500/10 border-b border-border">
          <XCircle className="h-4 w-4 text-red-500" />
          <span className="text-sm font-medium text-red-500">Error</span>
          <span className="text-xs text-muted-foreground ml-auto">
            {formatDuration(result.duration)}
          </span>
        </div>
        <div className="flex-1 p-4 overflow-auto bg-[#1a1a1a]">
          {/* Show stdout if any */}
          {result.output && (
            <pre className="text-sm text-foreground whitespace-pre-wrap font-mono mb-4 pb-4 border-b border-border/50">
              {result.output}
            </pre>
          )}

          {/* Error message (always visible) */}
          <div className="text-sm font-mono">
            <pre className="text-red-400 whitespace-pre-wrap font-semibold">
              {errorMessage}
            </pre>
          </div>

          {/* Expandable traceback */}
          {hasTraceback && (
            <div className="mt-3">
              <button
                onClick={() => setShowTraceback(!showTraceback)}
                className="flex items-center gap-1 text-xs text-muted-foreground hover:text-foreground transition-colors"
              >
                {showTraceback ? (
                  <ChevronDown className="h-3 w-3" />
                ) : (
                  <ChevronRight className="h-3 w-3" />
                )}
                {showTraceback ? "Hide traceback" : "Show traceback"}
              </button>
              {showTraceback && (
                <pre className="mt-2 text-xs text-red-400/70 whitespace-pre-wrap font-mono pl-2 border-l-2 border-red-500/30">
                  {result.traceback}
                </pre>
              )}
            </div>
          )}
        </div>
      </div>
    );
  }

  return (
    <div className="h-full bg-surface rounded-lg border border-border overflow-hidden flex flex-col">
      {/* Header */}
      <div className="flex items-center gap-2 px-4 py-2 bg-green-500/10 border-b border-border">
        <CheckCircle2 className="h-4 w-4 text-green-500" />
        <span className="text-sm font-medium text-green-500">Success</span>
        <span className="text-xs text-muted-foreground ml-auto">
          {formatDuration(result.duration)}
        </span>
      </div>

      {/* Output */}
      <div className="flex-1 p-4 overflow-auto bg-[#1a1a1a]">
        <pre className="text-sm text-foreground whitespace-pre-wrap font-mono">
          {result.output || "(No output)"}
        </pre>
      </div>
    </div>
  );
}
