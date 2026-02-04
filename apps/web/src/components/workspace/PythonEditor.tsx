"use client";

import { useCallback } from "react";
import CodeMirror from "@uiw/react-codemirror";
import { python } from "@codemirror/lang-python";
import { oneDark } from "@codemirror/theme-one-dark";
import { Play, Trash2, RotateCcw } from "lucide-react";
import { Button } from "@/components/ui/button";

interface PythonEditorProps {
  value: string;
  onChange: (value: string) => void;
  onRun: () => void;
  onReset?: () => void;
  isExecuting?: boolean;
  isReady?: boolean;
}

export function PythonEditor({
  value,
  onChange,
  onRun,
  onReset,
  isExecuting = false,
  isReady = true,
}: PythonEditorProps) {
  const handleKeyDown = useCallback(
    (event: React.KeyboardEvent<HTMLDivElement>) => {
      // Ctrl/Cmd + Enter to run code
      if ((event.ctrlKey || event.metaKey) && event.key === "Enter") {
        event.preventDefault();
        if (isReady) {
          onRun();
        }
      }
    },
    [onRun, isReady]
  );

  return (
    <div className="flex flex-col h-full">
      <div className="flex-1 overflow-hidden border border-border rounded-t-lg">
        <CodeMirror
          value={value}
          height="100%"
          theme={oneDark}
          extensions={[python()]}
          onChange={onChange}
          onKeyDown={handleKeyDown}
          basicSetup={{
            lineNumbers: true,
            highlightActiveLineGutter: true,
            foldGutter: true,
            autocompletion: true,
            bracketMatching: true,
            closeBrackets: true,
            highlightActiveLine: true,
            indentOnInput: true,
          }}
          className="h-full text-sm"
        />
      </div>
      <div className="flex items-center gap-2 p-2 bg-surface border-x border-b border-border rounded-b-lg">
        <Button
          onClick={onRun}
          disabled={isExecuting || !isReady}
          size="sm"
          className="gap-2"
        >
          <Play className="h-4 w-4" />
          {!isReady ? "Loading Python..." : isExecuting ? "Running..." : "Run Code"}
        </Button>
        <Button
          variant="ghost"
          size="sm"
          onClick={() => onChange("")}
          className="gap-2"
        >
          <Trash2 className="h-4 w-4" />
          Clear
        </Button>
        {onReset && (
          <Button
            variant="ghost"
            size="sm"
            onClick={onReset}
            className="gap-2"
            title="Reset Python environment"
          >
            <RotateCcw className="h-4 w-4" />
            Reset Env
          </Button>
        )}
        <span className="text-xs text-muted-foreground ml-auto">
          Ctrl+Enter to run
        </span>
      </div>
    </div>
  );
}
