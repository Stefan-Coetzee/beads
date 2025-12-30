# Learning Task Tracker (LTT)

A Python-based learning task management system adapted from [beads](https://github.com/steveyegge/beads), designed to power AI tutoring agents at scale.

## Overview

LTT provides a **data tooling layer** that enables AI tutoring agents to:
- Guide learners through structured projects
- Track progress through hierarchical tasks
- Validate submissions (proof of work)
- Maintain context across sessions
- Facilitate pedagogically-aware conversations

## Architecture

The system implements a **Template + Instance** architecture:
- **Template Layer**: Shared curriculum content (authored once, used by all learners)
- **Instance Layer**: Per-learner progress and work products

See [PRD](python-port/docs/PRD.md) for detailed architecture and specifications.

## Quick Start

### 1. Install Dependencies

```bash
# Using uv (recommended)
uv sync

# Install with dev dependencies
uv sync --extra dev
```

### 2. Start Database

```bash
# Start PostgreSQL 17
docker-compose up -d

# Verify it's running
docker-compose ps
```

### 3. Run Migrations

```bash
# Create .env file
cp .env.example .env

# Run migrations
uv run alembic upgrade head
```

### 4. Verify Installation

```bash
# Run tests
uv run pytest

# Check code quality
uv run ruff check src/
uv run mypy src/
```

## Project Structure

```
src/ltt/
├── models/          # Pydantic and SQLAlchemy models
├── db/              # Database connection and migrations
├── utils/           # ID generation and utilities
├── services/        # Business logic (coming soon)
├── cli/             # Admin CLI (coming soon)
└── api/             # FastAPI endpoints (coming soon)
```

## Development

See [DATABASE.md](DATABASE.md) for database management.

See [python-port/docs/](python-port/docs/) for detailed specifications:
- [PRD.md](python-port/docs/PRD.md) - Product requirements
- [01-data-models.md](python-port/docs/01-data-models.md) - Data model specifications
- [ADR-001](python-port/docs/adr/001-learner-scoped-task-progress.md) - Architecture decisions

## Tech Stack

- **Language**: Python 3.12+
- **Type Safety**: Pydantic v2
- **Database**: PostgreSQL 17
- **ORM**: SQLAlchemy 2.0 (async)
- **Migrations**: Alembic
- **CLI**: Typer
- **API**: FastAPI
- **Testing**: pytest

## License

MIT
