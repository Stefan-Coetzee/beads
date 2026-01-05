"use client";

import { useState, useEffect } from "react";
import { RefreshCw, Check } from "lucide-react";
import { Button } from "@/components/ui/button";
import {
  getOrCreateLearnerId,
  setLearnerId,
  generateLearnerId,
  isValidLearnerId,
} from "@/lib/learner";

interface LearnerIdInputProps {
  value: string;
  onChange: (value: string) => void;
}

export function LearnerIdInput({ value, onChange }: LearnerIdInputProps) {
  const [isEditing, setIsEditing] = useState(false);
  const [inputValue, setInputValue] = useState(value);

  useEffect(() => {
    setInputValue(value);
  }, [value]);

  const handleGenerate = () => {
    const newId = generateLearnerId();
    setInputValue(newId);
    onChange(newId);
    setLearnerId(newId);
    setIsEditing(false);
  };

  const handleSave = () => {
    if (isValidLearnerId(inputValue)) {
      onChange(inputValue);
      setLearnerId(inputValue);
      setIsEditing(false);
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "Enter") {
      handleSave();
    } else if (e.key === "Escape") {
      setInputValue(value);
      setIsEditing(false);
    }
  };

  return (
    <div className="flex items-center gap-2">
      <label className="text-sm text-muted-foreground whitespace-nowrap">
        Learner ID:
      </label>
      {isEditing ? (
        <div className="flex items-center gap-1">
          <input
            type="text"
            value={inputValue}
            onChange={(e) => setInputValue(e.target.value)}
            onKeyDown={handleKeyDown}
            className="bg-elevated border border-border rounded px-2 py-1 text-sm font-mono w-36 focus:outline-none focus:ring-1 focus:ring-accent"
            autoFocus
          />
          <Button
            variant="ghost"
            size="sm"
            onClick={handleSave}
            disabled={!isValidLearnerId(inputValue)}
            className="h-7 w-7 p-0"
          >
            <Check className="h-3 w-3" />
          </Button>
        </div>
      ) : (
        <button
          onClick={() => setIsEditing(true)}
          className="font-mono text-sm bg-elevated px-2 py-1 rounded hover:bg-elevated/80 transition-colors"
        >
          {value}
        </button>
      )}
      <Button
        variant="ghost"
        size="sm"
        onClick={handleGenerate}
        title="Generate new ID"
        className="h-7 w-7 p-0"
      >
        <RefreshCw className="h-3 w-3" />
      </Button>
    </div>
  );
}

/**
 * Hook to manage learner ID state with cookie persistence
 */
export function useLearnerIdState() {
  const [learnerId, setLearnerIdState] = useState<string>("");
  const [isLoaded, setIsLoaded] = useState(false);

  useEffect(() => {
    // Get or create learner ID on mount
    const id = getOrCreateLearnerId();
    setLearnerIdState(id);
    setIsLoaded(true);
  }, []);

  const updateLearnerId = (id: string) => {
    setLearnerIdState(id);
    setLearnerId(id);
  };

  return { learnerId, setLearnerId: updateLearnerId, isLoaded };
}
