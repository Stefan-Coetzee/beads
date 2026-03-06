# Add REST endpoint for project ingestion

## Summary

There is no API endpoint to ingest a project — it's CLI-only (`python -m ltt.cli.main ingest project`). This means populating a deployed environment requires either direct DB access or running the CLI inside an ECS task. We need a proper REST endpoint.

## Requirements

### Endpoint
`POST /api/v1/projects/ingest`

### Input
- Accept the project JSON structure (same schema as `docs/schema/project-ingestion.md`)
- Support both `application/json` body and `multipart/form-data` file upload

### Validation
- Validate the full JSON schema before touching the database
- Return **descriptive, remedial error messages** — not just "validation failed", but exactly which field is wrong and how to fix it (e.g., `"epics[2].tasks[0].dependencies[1]: references 'Nonexistent Task' which does not exist in this project"`)
- Validate Bloom's taxonomy levels, task types, dependency references, and required fields
- Support `?dry_run=true` query param to validate without persisting

### Response
- On success, return the stable `project_id` (author-defined slug from the JSON) and the auto-generated `internal_id`
- The `project_id` slug is what gets configured in Open edX LTI custom parameters
- Include version, task count, objective count, and any warnings
- Example:
  ```json
  {
    "project_id": "maji-ndogo-part1",
    "internal_id": "proj-9b46",
    "version": 1,
    "title": "Maji Ndogo Water Crisis - Part 1",
    "task_count": 42,
    "objective_count": 18,
    "warnings": []
  }
  ```

### Auth
- This is an admin operation — require auth (or restrict to instructor LTI roles)

## Context

- The ingestion logic already exists in `ltt.services.ingest.ingest_project_file()`
- The CLI dry-run validation exists in `ltt.cli.main`
- `project_id` is now an author-defined slug in the project JSON (e.g., `"maji-ndogo-part1"`) — this stable slug is what gets configured in Open edX as an LTI custom parameter
- The auto-generated internal ID (`proj-XXXX`) remains an implementation detail

## Motivation

Currently the only way to populate a deployed database is to run the CLI against the RDS instance, which requires either SSH tunnel access or an ad-hoc ECS task. An API endpoint lets instructors upload projects through a future admin UI and immediately get the ID needed for Open edX configuration.
