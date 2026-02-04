"use client";

import { formatDuration } from "@/lib/utils";
import type { QueryResult } from "@/types";
import { CheckCircle2, XCircle, Table2 } from "lucide-react";

interface ResultsPanelProps {
  result: QueryResult | null;
  isExecuting?: boolean;
}

export function ResultsPanel({ result, isExecuting = false }: ResultsPanelProps) {
  if (isExecuting) {
    return (
      <div className="h-full flex items-center justify-center bg-surface rounded-lg border border-border">
        <div className="text-center">
          <div className="animate-spin h-8 w-8 border-2 border-accent border-t-transparent rounded-full mx-auto mb-3" />
          <p className="text-sm text-muted-foreground">Executing query...</p>
        </div>
      </div>
    );
  }

  if (!result) {
    return (
      <div className="h-full flex items-center justify-center bg-surface rounded-lg border border-border">
        <div className="text-center text-muted-foreground">
          <Table2 className="h-12 w-12 mx-auto mb-3 opacity-50" />
          <p className="text-sm">Run a query to see results</p>
        </div>
      </div>
    );
  }

  if (!result.success) {
    return (
      <div className="h-full bg-surface rounded-lg border border-border overflow-hidden flex flex-col">
        <div className="flex items-center gap-2 px-4 py-2 bg-red-500/10 border-b border-border">
          <XCircle className="h-4 w-4 text-red-500" />
          <span className="text-sm font-medium text-red-500">Error</span>
          <span className="text-xs text-muted-foreground ml-auto">
            {formatDuration(result.duration)}
          </span>
        </div>
        <div className="flex-1 p-4 overflow-auto">
          <pre className="text-sm text-red-400 whitespace-pre-wrap font-mono">
            {result.error}
          </pre>
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
        <span className="text-xs text-muted-foreground">
          {result.rowCount} row{result.rowCount !== 1 ? "s" : ""} returned
        </span>
        <span className="text-xs text-muted-foreground ml-auto">
          {formatDuration(result.duration)}
        </span>
      </div>

      {/* Results Table */}
      {result.columns && result.columns.length > 0 && result.rows && result.rows.length > 0 ? (
        <div className="flex-1 overflow-auto">
          <table className="w-full text-sm font-mono">
            <thead className="sticky top-0 bg-elevated">
              <tr>
                {result.columns.map((col, i) => (
                  <th
                    key={i}
                    className="text-left px-4 py-2 border-b border-border text-muted-foreground font-medium"
                  >
                    {col}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {result.rows.map((row, i) => (
                <tr key={i} className="hover:bg-elevated/50">
                  {row.map((cell, j) => (
                    <td key={j} className="px-4 py-2 border-b border-border/50">
                      {cell === null ? (
                        <span className="text-muted-foreground italic">NULL</span>
                      ) : (
                        String(cell)
                      )}
                    </td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : (
        <div className="flex-1 flex items-center justify-center text-muted-foreground">
          <p className="text-sm">Query executed successfully with no results</p>
        </div>
      )}
    </div>
  );
}
