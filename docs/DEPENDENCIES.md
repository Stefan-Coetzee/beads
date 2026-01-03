# LTT Dependency Analysis

> Generated using snakefood3

## Dependency Graph

A GraphViz DOT file has been generated: [`dependencies.dot`](dependencies.dot)

To visualize:
```bash
dot -Tpng docs/dependencies.dot -o docs/dependencies.png
dot -Tsvg docs/dependencies.dot -o docs/dependencies.svg
```

## Architecture Layers

### Layer 1: Models (Data Layer)
**No internal dependencies** - Models depend only on SQLAlchemy and standard library.

All models inherit from `ltt.models.base` and are exported through `ltt.models.__init__.py`:
- `task`, `learner`, `learning`, `submission`, `validation`
- `dependency`, `comment`, `event`, `status_summary`
- `content`, `acceptance_criterion`, `learner_task_progress`, `context`

### Layer 2: Services (Business Logic)
**Depends on**: Models layer

Services are organized by domain:
- **Core services**: `task_service`, `progress_service`, `dependency_service`
- **Submission flow**: `submission_service`, `validation_service`
- **Learning services**: `learning/` package (objectives, progress, summarization, content)
- **Data management**: `ingest`, `export`

**Key service dependencies**:
```
dependency_service → progress_service → task_service → models
submission_service → validation_service → models
learning/* → progress_service → models
```

### Layer 3: Tools (Agent Interface)
**Depends on**: Services layer, Models layer

Tools provide stateless functions for LLM agents:
- **Navigation tools**: `navigation.py` (get_ready, show_task, get_context)
- **Progress tools**: `progress.py` (start_task, submit)
- **Feedback tools**: `feedback.py` (add_comment, get_comments)
- **Control tools**: `control.py` (go_back, request_help)

**Tool dependencies**:
```
tools.progress → services.{validation, submission, dependency, progress, task}
tools.navigation → services.{learning, validation, submission, dependency, progress, task}
tools.feedback → services.task_service
tools.control → services.{progress, task}
```

All tools depend on `tools.schemas` for input/output models.

### Layer 4: CLI (Admin Interface)
**Depends on**: Services layer

Not included in dependency graph (lives in `cli/main.py`).

## Dependency Statistics

**Total modules analyzed**: ~30 LTT modules
**External dependencies**:
- `sqlalchemy` - Database ORM
- `pydantic` - Validation and serialization
- `typer` - CLI framework
- Python stdlib: `datetime`, `typing`, `enum`, `dataclasses`, `collections`, `hashlib`, `uuid`

## Dependency Rules

1. **Layered architecture** - Dependencies flow downward:
   ```
   CLI → Tools → Services → Models → SQLAlchemy/Pydantic
   ```

2. **No circular dependencies** - Each layer depends only on layers below

3. **Models are pure** - No business logic, only data structures

4. **Services encapsulate logic** - All business rules in service layer

5. **Tools are stateless** - No state management, just orchestration

## Key Observations

### Clean Separation
- **Models** have zero internal dependencies (only external: SQLAlchemy)
- **Services** depend on models but not on tools or CLI
- **Tools** depend on services but not on CLI
- **CLI** depends on services but not on tools (separate interfaces)

### Service Independence
Most services are independent:
- `task_service` - Base CRUD operations
- `submission_service` - Independent submission logic
- `validation_service` - Independent validation logic
- `learning/*` - Learning-specific operations

Only `progress_service` and `dependency_service` have cross-dependencies due to blocking logic.

### Tool Composition
Tools compose multiple services:
- `navigation.py` uses 6 services (most complex)
- `progress.py` uses 5 services
- `feedback.py` uses 1 service (simplest)
- `control.py` uses 2 services

This composition pattern allows tools to provide high-level workflows while services remain focused.

## Potential Improvements

1. **Consider splitting large services**:
   - `task_service.py` is large (~300 lines) - could split CRUD from hierarchy operations
   - `dependency_service.py` handles both dependency management and ready work calculation

2. **Service layer interfaces**:
   - Could introduce Protocol/ABC for service interfaces
   - Would make testing and mocking easier

3. **Circular import prevention**:
   - Current architecture prevents circular imports by design
   - Continue to enforce layered dependencies

## Full Dependency Graph

See [`dependencies.dot`](dependencies.dot) for the complete GraphViz diagram.

To generate a visual graph:
```bash
# Install graphviz (macOS)
brew install graphviz

# Generate PNG
dot -Tpng docs/dependencies.dot -o docs/dependencies.png

# Generate SVG (better for web)
dot -Tsvg docs/dependencies.dot -o docs/dependencies.svg

# Generate interactive HTML
dot -Tsvg docs/dependencies.dot | dot -Tcmapx > docs/dependencies.html
```
