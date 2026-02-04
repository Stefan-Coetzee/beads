"use client";

import { TaskTreeNode } from "./TaskTreeNode";
import { Skeleton } from "@/components/ui/skeleton";
import type { TaskNode } from "@/types";

interface TaskTreeProps {
  nodes: TaskNode[];
  isLoading?: boolean;
  onTaskClick: (taskId: string) => void;
}

export function TaskTree({ nodes, isLoading, onTaskClick }: TaskTreeProps) {
  if (isLoading) {
    return (
      <div className="space-y-3 p-4">
        {[...Array(5)].map((_, i) => (
          <div key={i} className="flex items-center gap-3">
            <Skeleton className="h-4 w-4 rounded" />
            <Skeleton className="h-4 flex-1" />
            <Skeleton className="h-2 w-16" />
          </div>
        ))}
      </div>
    );
  }

  if (!nodes || nodes.length === 0) {
    return (
      <div className="p-8 text-center text-muted-foreground">
        <p>No tasks found in this project.</p>
      </div>
    );
  }

  return (
    <div className="py-2">
      {nodes.map((node) => (
        <TaskTreeNode
          key={node.id}
          node={node}
          depth={0}
          onTaskClick={onTaskClick}
        />
      ))}
    </div>
  );
}
