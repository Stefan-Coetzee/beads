import { clsx, type ClassValue } from "clsx";
import { twMerge } from "tailwind-merge";

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

/**
 * Parse task references from message content
 * Matches patterns like proj-abc123.1.2.3
 */
export function parseTaskReferences(content: string): string[] {
  const taskIdPattern = /\b(proj-[a-z0-9]+(?:\.\d+)*)\b/gi;
  const matches = content.match(taskIdPattern);
  return matches ? [...new Set(matches)] : [];
}

/**
 * Format duration in milliseconds to human readable
 */
export function formatDuration(ms: number): string {
  if (ms < 1000) return `${ms.toFixed(0)}ms`;
  return `${(ms / 1000).toFixed(2)}s`;
}

/**
 * Get status color class
 */
export function getStatusColor(status: string): string {
  switch (status) {
    case "open":
      return "status-open";
    case "in_progress":
      return "status-in-progress";
    case "blocked":
      return "status-blocked";
    case "closed":
      return "status-closed";
    default:
      return "status-open";
  }
}

/**
 * Get status display text
 */
export function getStatusText(status: string): string {
  switch (status) {
    case "open":
      return "Open";
    case "in_progress":
      return "In Progress";
    case "blocked":
      return "Blocked";
    case "closed":
      return "Closed";
    default:
      return status;
  }
}
