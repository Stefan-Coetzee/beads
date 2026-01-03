"""
CLI for running tutor-learner simulations.

Usage:
    python -m simulation.main run --learner-id learner-123 --project-id proj-abc
    python -m simulation.main run -l learner-123 -p proj-abc --max-turns 20
"""

import asyncio

import typer
from rich.console import Console

from agent.config import Config, LearnerSimulatorConfig, ModelConfig, SimulationConfig
from simulation.runner import run_simulation

app = typer.Typer(
    name="simulation",
    help="Run tutor-learner simulations",
)
console = Console()


@app.command()
def run(
    learner_id: str = typer.Option(..., "--learner-id", "-l", help="Learner ID"),
    project_id: str = typer.Option(..., "--project-id", "-p", help="Project ID"),
    max_turns: int = typer.Option(30, "--max-turns", "-t", help="Maximum conversation turns"),
    comprehension: float = typer.Option(
        0.6, "--comprehension", "-c", help="Learner comprehension rate (0.0-1.0)"
    ),
    tutor_model: str = typer.Option(
        "claude-haiku-4-5-20251001", "--tutor-model", help="Model for tutor"
    ),
    learner_model: str = typer.Option(
        "claude-haiku-4-5-20251001", "--learner-model", help="Model for learner"
    ),
    save_log: bool = typer.Option(True, "--save/--no-save", help="Save conversation log"),
    quiet: bool = typer.Option(False, "--quiet", "-q", help="Quiet mode (no output)"),
    show_tools: bool = typer.Option(False, "--show-tools", help="Show tool calls and results"),
):
    """Run a simulation between tutor and simulated learner."""
    # Build configuration
    config = Config(
        model=ModelConfig(
            tutor_model=tutor_model,
            learner_model=learner_model,
        ),
        learner_sim=LearnerSimulatorConfig(
            comprehension_rate=comprehension,
        ),
        simulation=SimulationConfig(
            max_turns=max_turns,
            save_logs=save_log,
        ),
    )

    # Run the simulation
    asyncio.run(
        run_simulation(
            learner_id=learner_id,
            project_id=project_id,
            max_turns=max_turns,
            config=config,
            save_log=save_log,
            verbose=not quiet,
            show_tools=show_tools,
        )
    )


@app.command()
def list_logs():
    """List saved simulation logs."""
    from pathlib import Path

    from agent.config import get_config

    config = get_config()
    log_dir = Path(config.simulation.log_dir)

    if not log_dir.exists():
        console.print("[yellow]No logs directory found.[/yellow]")
        return

    logs = sorted(log_dir.glob("simulation_*.json"), reverse=True)

    if not logs:
        console.print("[yellow]No simulation logs found.[/yellow]")
        return

    console.print(f"\n[bold]Found {len(logs)} simulation logs:[/bold]\n")
    for log in logs[:20]:  # Show last 20
        console.print(f"  {log.name}")


@app.command()
def show_log(
    log_file: str = typer.Argument(..., help="Log file name or path"),
):
    """Display a simulation log."""
    import json
    from pathlib import Path

    from rich.panel import Panel

    from agent.config import get_config

    # Try to find the log file
    log_path = Path(log_file)
    if not log_path.exists():
        config = get_config()
        log_path = Path(config.simulation.log_dir) / log_file

    if not log_path.exists():
        console.print(f"[red]Log file not found: {log_file}[/red]")
        raise typer.Exit(1)

    with open(log_path) as f:
        data = json.load(f)

    console.print(
        Panel(
            f"Learner: {data['learner_id']}\n"
            f"Project: {data['project_id']}\n"
            f"Started: {data['started_at']}\n"
            f"Ended: {data['ended_at']}\n"
            f"Turns: {len(data['turns'])}",
            title="Simulation Log",
            border_style="cyan",
        )
    )

    for turn in data["turns"]:
        if turn["speaker"] == "tutor":
            console.print(
                Panel(turn["message"], title="[green]Tutor[/green]", border_style="green")
            )
        else:
            console.print(Panel(turn["message"], title="[blue]Learner[/blue]", border_style="blue"))


if __name__ == "__main__":
    app()
