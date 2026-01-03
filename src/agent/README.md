# Socratic Learning Agent

A LangGraph-based AI tutoring assistant that guides learners through structured projects using Socratic teaching methods.

## Overview

The Socratic Learning Agent helps learners work through structured data analytics and data science projects by:

- Asking guiding questions rather than giving direct answers
- Using the Learning Task Tracker (LTT) tools to manage progress
- Adapting to learner's current context and understanding
- Following pedagogical best practices for effective learning

## Quick Start

```bash
# Interactive chat with a learner
PYTHONPATH=src python -m agent.main chat -l <learner-id> -p <project-id>

# Single message
PYTHONPATH=src python -m agent.main ask -l <learner-id> -p <project-id> "What should I work on?"

# Run a simulation (tutor + simulated learner)
PYTHONPATH=src python -m simulation.main run -l <learner-id> -p <project-id>
```

## Architecture

```
src/
├── agent/                    # Tutor agent
│   ├── __init__.py
│   ├── config.py            # Centralized configuration
│   ├── graph.py             # LangGraph agent definition
│   ├── prompts.py           # Socratic teaching prompts
│   ├── state.py             # Agent state definitions
│   ├── tools.py             # LTT tool wrappers
│   └── main.py              # CLI entry point
│
├── learner_sim/             # Learner simulator
│   ├── __init__.py
│   ├── prompts.py           # Learner persona prompts
│   └── simulator.py         # Simulator implementation
│
└── simulation/              # Simulation runner
    ├── __init__.py
    ├── runner.py            # Conversation orchestration
    └── main.py              # Simulation CLI
```

## Configuration

All configuration is centralized in `agent/config.py`:

```python
from agent.config import Config, create_config, get_config

# Use default configuration
config = get_config()

# Create custom configuration
config = create_config(
    model=ModelConfig(
        tutor_model="claude-haiku-4-5-20250514",
        learner_model="claude-haiku-4-5-20250514",
        tutor_temperature=0.7,
    ),
    learner_sim=LearnerSimulatorConfig(
        comprehension_rate=0.6,
        mistake_rate=0.4,
    ),
)
```

### Configuration Options

| Setting | Default | Description |
|---------|---------|-------------|
| `model.tutor_model` | `claude-haiku-4-5-20250514` | Model for tutor agent |
| `model.learner_model` | `claude-haiku-4-5-20250514` | Model for learner simulator |
| `model.tutor_temperature` | `0.7` | Temperature for tutor responses |
| `model.learner_temperature` | `0.9` | Temperature for learner (more variable) |
| `learner_sim.comprehension_rate` | `0.6` | How often learner understands correctly |
| `learner_sim.mistake_rate` | `0.4` | How often learner makes mistakes |
| `simulation.max_turns` | `30` | Maximum conversation turns |

## Usage

### Tutor Agent

```python
from agent import create_agent, get_config
from ltt.db.connection import get_session_factory

async def main():
    factory = get_session_factory()
    async with factory() as session:
        agent = create_agent(
            learner_id="learner-123",
            project_id="proj-abc",
            session=session,
        )

        # Single message
        result = await agent.ainvoke("What should I work on today?")
        print(result["messages"][-1].content)

        # Streaming
        async for state in agent.astream("Help me with SQL"):
            if state.get("messages"):
                print(state["messages"][-1].content)
```

### Learner Simulator

```python
from learner_sim import create_learner_simulator

learner = create_learner_simulator()

# Get greeting
greeting = await learner.get_greeting()
print(greeting)

# Respond to tutor
response = await learner.respond("Let's start with SELECT statements.")
print(response)
```

### Running Simulations

```python
from simulation import run_simulation

log = await run_simulation(
    learner_id="learner-123",
    project_id="proj-abc",
    max_turns=20,
    verbose=True,
)

# Access conversation
for turn in log.turns:
    print(f"{turn.speaker}: {turn.message[:100]}...")
```

## CLI Commands

### Agent CLI

```bash
# Interactive chat
python -m agent.main chat -l <learner-id> -p <project-id>

# Show tool calls during chat
python -m agent.main chat -l <learner-id> -p <project-id> --show-tools

# Single message
python -m agent.main ask -l <learner-id> -p <project-id> "message"
```

### Simulation CLI

```bash
# Run simulation
python -m simulation.main run -l <learner-id> -p <project-id>

# Custom settings
python -m simulation.main run \
    -l <learner-id> \
    -p <project-id> \
    --max-turns 50 \
    --comprehension 0.7 \
    --tutor-model claude-haiku-4-5-20250514

# List saved logs
python -m simulation.main list-logs

# View a log
python -m simulation.main show-log simulation_20240101_120000.json
```

## Available Tools

The tutor agent has access to these LTT tools:

| Tool | Description |
|------|-------------|
| `get_ready` | Get tasks that are unblocked and ready to work on |
| `show_task` | Show detailed task information |
| `get_context` | Get full context (hierarchy, progress, objectives) |
| `start_task` | Begin working on a task |
| `submit` | Submit work for validation |
| `add_comment` | Add notes to a task |
| `get_comments` | Retrieve task comments |
| `go_back` | Reopen a closed task |
| `request_help` | Request instructor assistance |

## Learner Simulator Persona

The simulated learner (Thabo) has these characteristics:

- **Background**: South African, learning data analytics
- **Language**: English as second language (Zulu/Sotho first)
- **Knowledge**: Basic SQL (SELECT, WHERE, simple JOINs)
- **Behavior**: Variable understanding, realistic mistakes, asks questions

### Example Behaviors

- Sometimes understands immediately, sometimes needs explanation
- Makes common SQL mistakes (forgetting WHERE, wrong syntax)
- Asks clarifying questions in imperfect English
- Shows genuine learning emotions (confusion, excitement)

## Testing

```bash
# Run agent tests
PYTHONPATH=src uv run pytest tests/agent/ -v

# Run all tests
PYTHONPATH=src uv run pytest tests/ -v
```

## Environment Variables

Copy `.env.example` to `.env` in the project root and configure:

```bash
# Required for agent
ANTHROPIC_API_KEY=your-api-key-here

# Database (has defaults)
DATABASE_URL=postgresql+asyncpg://ltt_user:ltt_password@localhost:5432/ltt_dev

# Optional: LangSmith tracing
LANGCHAIN_TRACING_V2=true
LANGCHAIN_API_KEY=your-langsmith-key
```

## Dependencies

- `langgraph>=1.0.5` - Agent framework
- `langchain>=1.2.0` - LLM abstractions
- `langchain-anthropic>=1.3.0` - Claude integration
- `rich>=14.2.0` - CLI formatting
