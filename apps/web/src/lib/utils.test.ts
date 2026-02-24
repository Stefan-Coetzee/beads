/**
 * Tests for utility functions.
 */

import { describe, it, expect } from "vitest";
import { parseTaskReferences, formatDuration, getStatusColor, getStatusText } from "./utils";

describe("parseTaskReferences", () => {
  it("extracts a single task ID", () => {
    expect(parseTaskReferences("Look at proj-abc123.1.2")).toEqual(["proj-abc123.1.2"]);
  });

  it("extracts multiple task IDs", () => {
    const result = parseTaskReferences("Check proj-a1b2.1 and proj-a1b2.2");
    expect(result).toContain("proj-a1b2.1");
    expect(result).toContain("proj-a1b2.2");
    expect(result).toHaveLength(2);
  });

  it("deduplicates repeated IDs", () => {
    expect(parseTaskReferences("proj-a1.1 then proj-a1.1 again")).toEqual(["proj-a1.1"]);
  });

  it("returns empty array when no matches", () => {
    expect(parseTaskReferences("no tasks here")).toEqual([]);
  });

  it("handles project-level ID (no dots)", () => {
    expect(parseTaskReferences("see proj-abc123")).toEqual(["proj-abc123"]);
  });

  it("handles deeply nested IDs", () => {
    expect(parseTaskReferences("proj-abc123.1.2.3.4")).toEqual(["proj-abc123.1.2.3.4"]);
  });
});

describe("formatDuration", () => {
  it("formats sub-second as milliseconds", () => {
    expect(formatDuration(42)).toBe("42ms");
  });

  it("rounds sub-second values", () => {
    expect(formatDuration(42.7)).toBe("43ms");
  });

  it("formats exactly 1 second", () => {
    expect(formatDuration(1000)).toBe("1.00s");
  });

  it("formats multi-second values", () => {
    expect(formatDuration(1234)).toBe("1.23s");
  });

  it("formats zero", () => {
    expect(formatDuration(0)).toBe("0ms");
  });
});

describe("getStatusColor", () => {
  it.each([
    ["open", "status-open"],
    ["in_progress", "status-in-progress"],
    ["blocked", "status-blocked"],
    ["closed", "status-closed"],
  ])("returns correct class for %s", (status, expected) => {
    expect(getStatusColor(status)).toBe(expected);
  });

  it("returns default for unknown status", () => {
    expect(getStatusColor("unknown")).toBe("status-open");
  });
});

describe("getStatusText", () => {
  it.each([
    ["open", "Open"],
    ["in_progress", "In Progress"],
    ["blocked", "Blocked"],
    ["closed", "Closed"],
  ])("returns display text for %s", (status, expected) => {
    expect(getStatusText(status)).toBe(expected);
  });

  it("returns raw string for unknown status", () => {
    expect(getStatusText("custom_status")).toBe("custom_status");
  });
});
