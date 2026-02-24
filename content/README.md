# Content

> Learning project definitions — structured JSON files that get ingested into LTT.

---

## Projects

```
projects/
├── DA/                              # Data Analytics
│   └── MN_Part1/                    # Maji Ndogo Water Analysis
│       ├── water_analysis_project.json  # Full structured project (ingested by default)
│       ├── 00_project_overview.json     # Epic-level breakdowns
│       ├── 01_epic_introduction.json
│       ├── ...
│       ├── aggregate.py                 # Script to combine epics
│       └── MD_water_services_stu_v2.sql # Source SQL schema
│
└── PYTHON/                          # Python
    └── fundamentals/
        └── structured/
            └── python_basics_project.json
```

---

## Ingesting Projects

```bash
# Validate first (dry run)
python -m ltt.cli.main ingest project content/projects/DA/MN_Part1/structured/water_analysis_project.json --dry-run

# Import
python -m ltt.cli.main ingest project content/projects/DA/MN_Part1/structured/water_analysis_project.json
```

The API server auto-ingests `water_analysis_project.json` on startup if no projects exist.

---

## Creating New Projects

Projects are structured JSON files with hierarchical tasks, learning objectives, and tutor guidance.

See [docs/schema/project-ingestion.md](../docs/schema/project-ingestion.md) for the complete JSON schema, or use [docs/SCHEMA-FOR-LLM-INGESTION.md](../docs/SCHEMA-FOR-LLM-INGESTION.md) to have an LLM convert unstructured content into the required format.

### Minimal example

```json
{
  "title": "Learn SQL Basics",
  "description": "Introduction to SQL queries",
  "epics": [
    {
      "title": "SELECT Queries",
      "tasks": [
        {
          "title": "Select all columns",
          "description": "Use SELECT * to retrieve all data",
          "acceptance_criteria": "- Uses SELECT *\n- Returns all rows",
          "subtasks": []
        }
      ]
    }
  ]
}
```

---

## Source Materials

The `source-materials/` directory contains raw course content (PDFs, SQL files, LaTeX) used as input for project generation. These are not ingested directly.
