"use client";

import { useState } from "react";
import { ChevronRight, ChevronDown, Circle, CheckCircle2, Clock, XCircle } from "lucide-react";
import { cn } from "@/lib/utils";
import { Progress } from "@/components/ui/progress";
import type { TaskNode } from "@/types";

interface TaskTreeNodeProps {
  node: TaskNode;
  depth: number;
  onTaskClick: (taskId: string) => void;
}

function getStatusIcon(status: string) {
  switch (status) {
    case "closed":
      return <CheckCircle2 className="h-4 w-4 text-green-500" />;
    case "in_progress":
      return <Clock className="h-4 w-4 text-amber-500" />;
    case "blocked":
      return <XCircle className="h-4 w-4 text-red-500" />;
    default:
      return <Circle className="h-4 w-4 text-zinc-500" />;
  }
}

export function TaskTreeNode({ node, depth, onTaskClick }: TaskTreeNodeProps) {
  const [isExpanded, setIsExpanded] = useState(depth < 2);
  const hasChildren = node.children && node.children.length > 0;

  const toggleExpand = (e: React.MouseEvent) => {
    e.stopPropagation();
    if (hasChildren) {
      setIsExpanded(!isExpanded);
    }
  };

  const handleClick = () => {
    onTaskClick(node.id);
  };

  // Calculate progress for parent nodes
  const progressPercentage = node.progress
    ? (node.progress.completed / node.progress.total) * 100
    : 0;

  return (
    <div className="select-none">
      {/* Node Row */}
      <div
        className={cn(
          "flex items-center gap-2 py-2 px-3 rounded-md cursor-pointer",
          "hover:bg-elevated transition-colors",
          "group"
        )}
        style={{ paddingLeft: `${depth * 1.5 + 0.75}rem` }}
        onClick={handleClick}
      >
        {/* Expand/Collapse Toggle */}
        <button
          onClick={toggleExpand}
          className={cn(
            "p-0.5 rounded hover:bg-muted transition-colors",
            !hasChildren && "invisible"
          )}
        >
          {isExpanded ? (
            <ChevronDown className="h-4 w-4 text-muted-foreground" />
          ) : (
            <ChevronRight className="h-4 w-4 text-muted-foreground" />
          )}
        </button>

        {/* Status Icon */}
        {getStatusIcon(node.status)}

        {/* Task Title */}
        <span className="flex-1 truncate font-medium text-sm">
          {node.title}
        </span>

        {/* Task Type Badge */}
        <span className="text-xs text-muted-foreground capitalize hidden group-hover:inline">
          {node.task_type}
        </span>

        {/* Progress Bar for parents */}
        {node.progress && node.progress.total > 0 && (
          <div className="flex items-center gap-2 ml-2">
            <Progress value={progressPercentage} className="w-20 h-1.5" />
            <span className="text-xs text-muted-foreground min-w-[3rem]">
              {Math.round(progressPercentage)}%
            </span>
          </div>
        )}
      </div>

      {/* Children */}
      {hasChildren && isExpanded && (
        <div className="border-l border-border/50 ml-6">
          {node.children.map((child) => (
            <TaskTreeNode
              key={child.id}
              node={child}
              depth={depth + 1}
              onTaskClick={onTaskClick}
            />
          ))}
        </div>
      )}
    </div>
  );
}
