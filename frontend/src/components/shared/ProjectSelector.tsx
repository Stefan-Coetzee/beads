"use client";

import { useQuery } from "@tanstack/react-query";
import { ChevronDown } from "lucide-react";
import { api } from "@/lib/api";

interface Project {
  id: string;
  title: string;
}

interface ProjectSelectorProps {
  value: string;
  onChange: (projectId: string) => void;
}

export function ProjectSelector({ value, onChange }: ProjectSelectorProps) {
  const { data: projects, isLoading } = useQuery({
    queryKey: ["projects"],
    queryFn: () => api.getProjects(),
    staleTime: 5 * 60 * 1000, // 5 minutes
  });

  if (isLoading) {
    return (
      <div className="h-9 w-48 bg-elevated rounded animate-pulse" />
    );
  }

  return (
    <div className="relative">
      <select
        value={value}
        onChange={(e) => onChange(e.target.value)}
        className="appearance-none bg-elevated border border-border rounded-lg px-3 py-2 pr-8 text-sm focus:outline-none focus:ring-1 focus:ring-accent cursor-pointer min-w-48"
      >
        {projects?.map((project) => (
          <option key={project.id} value={project.id}>
            {project.title}
          </option>
        ))}
      </select>
      <ChevronDown className="absolute right-2 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground pointer-events-none" />
    </div>
  );
}
