"use client";

import { Badge } from "@/components/ui/badge";
import type { TaskStatus } from "@/types";
import { getStatusText } from "@/lib/utils";

interface StatusBadgeProps {
  status: TaskStatus;
  className?: string;
}

export function StatusBadge({ status, className }: StatusBadgeProps) {
  return (
    <Badge variant={status} className={className}>
      {getStatusText(status)}
    </Badge>
  );
}
