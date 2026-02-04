"use client";

import { useCallback } from "react";
import CodeMirror from "@uiw/react-codemirror";
import { sql, SQLite } from "@codemirror/lang-sql";
import { oneDark } from "@codemirror/theme-one-dark";
import { Play, Trash2 } from "lucide-react";
import { Button } from "@/components/ui/button";

interface SqlEditorProps {
  value: string;
  onChange: (value: string) => void;
  onRun: () => void;
  isExecuting?: boolean;
}

export function SqlEditor({
  value,
  onChange,
  onRun,
  isExecuting = false,
}: SqlEditorProps) {
  const handleKeyDown = useCallback(
    (event: React.KeyboardEvent<HTMLDivElement>) => {
      // Ctrl/Cmd + Enter to run query
      if ((event.ctrlKey || event.metaKey) && event.key === "Enter") {
        event.preventDefault();
        onRun();
      }
    },
    [onRun]
  );

  return (
    <div className="flex flex-col h-full">
      <div className="flex-1 overflow-hidden border border-border rounded-t-lg">
        <CodeMirror
          value={value}
          height="100%"
          theme={oneDark}
          extensions={[sql({ dialect: SQLite })]}
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
          }}
          className="h-full text-sm"
        />
      </div>
      <div className="flex items-center gap-2 p-2 bg-surface border-x border-b border-border rounded-b-lg">
        <Button
          onClick={onRun}
          disabled={isExecuting}
          size="sm"
          className="gap-2"
        >
          <Play className="h-4 w-4" />
          {isExecuting ? "Running..." : "Run Query"}
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
        <span className="text-xs text-muted-foreground ml-auto">
          Ctrl+Enter to run
        </span>
      </div>
    </div>
  );
}
