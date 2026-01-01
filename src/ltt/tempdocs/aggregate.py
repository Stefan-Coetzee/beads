#!/usr/bin/env python3
"""
Aggregates JSON fragments into the final water_analysis_project.json

Usage:
    python aggregate.py

This script:
1. Reads 00_project_overview.json as the base
2. Reads all epic fragments (01-06)
3. Combines them into a single project JSON
4. Writes to water_analysis_project.json
"""

import json
from pathlib import Path


def load_json(filepath: Path) -> dict:
    """Load and parse a JSON file."""
    with open(filepath, encoding="utf-8") as f:
        return json.load(f)


def aggregate_project():
    """Combine all fragments into the final project JSON."""
    base_dir = Path(__file__).parent

    # Load the project overview as base
    project = load_json(base_dir / "00_project_overview.json")

    # Define epic files in order
    epic_files = [
        "01_epic_introduction.json",
        "02_epic_get_to_know_data.json",
        "03_epic_dive_into_sources.json",
        "04_epic_unpack_visits.json",
        "05_epic_water_quality.json",
        "06_epic_pollution_issues.json",
    ]

    # Load and append each epic
    epics = []
    for epic_file in epic_files:
        filepath = base_dir / epic_file
        if filepath.exists():
            epic = load_json(filepath)
            epics.append(epic)
            print(f"  Loaded: {epic_file} ({epic.get('title', 'Untitled')})")
        else:
            print(f"  WARNING: {epic_file} not found, skipping")

    # Add epics to project
    project["epics"] = epics

    # Calculate total estimated time
    total_minutes = sum(epic.get("estimated_minutes", 0) for epic in epics)
    project["estimated_minutes"] = total_minutes

    # Write the combined output
    output_path = base_dir / "water_analysis_project.json"
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(project, f, indent=2, ensure_ascii=False)

    print(f"\nAggregated {len(epics)} epics into {output_path.name}")
    print(f"Total estimated time: {total_minutes} minutes ({total_minutes // 60} hours)")

    return project


def validate_project(project: dict) -> list[str]:
    """Validate the aggregated project for common issues."""
    issues = []

    # Check required fields at project level
    required_project_fields = ["title", "description", "learning_objectives", "epics"]
    for field in required_project_fields:
        if field not in project:
            issues.append(f"Missing required project field: {field}")

    # Check each epic
    for i, epic in enumerate(project.get("epics", [])):
        epic_prefix = f"Epic {i} ({epic.get('title', 'Untitled')})"

        if "title" not in epic:
            issues.append(f"{epic_prefix}: Missing title")
        if "tasks" not in epic:
            issues.append(f"{epic_prefix}: Missing tasks")

        # Check each task
        for j, task in enumerate(epic.get("tasks", [])):
            task_prefix = f"{epic_prefix} > Task {j} ({task.get('title', 'Untitled')})"

            if "title" not in task:
                issues.append(f"{task_prefix}: Missing title")

            # Check subtasks
            for k, subtask in enumerate(task.get("subtasks", [])):
                subtask_prefix = f"{task_prefix} > Subtask {k}"
                subtask_type = subtask.get("subtask_type", "exercise")

                if "title" not in subtask:
                    issues.append(f"{subtask_prefix}: Missing title")

                # Exercise subtasks need acceptance_criteria
                if subtask_type == "exercise" and "acceptance_criteria" not in subtask:
                    issues.append(f"{subtask_prefix}: Exercise missing acceptance_criteria")

    return issues


if __name__ == "__main__":
    print("Aggregating Maji Ndogo Part 1 JSON fragments...\n")

    project = aggregate_project()

    print("\nValidating structure...")
    issues = validate_project(project)

    if issues:
        print(f"\nFound {len(issues)} validation issues:")
        for issue in issues:
            print(f"  - {issue}")
    else:
        print("  No validation issues found!")

    print("\nDone!")
