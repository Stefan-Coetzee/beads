"""
Simulation runner for tutor-learner conversations.

Uses the FastAPI server for agent interactions, which provides
proper database connection pooling.
"""

import asyncio
import json
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

from agent.config import Config, get_config
from api.client import AgentClient, ChatResponse
from learner_sim.simulator import create_learner_simulator
from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel


@dataclass
class ConversationTurn:
    """A single turn in the conversation."""

    speaker: str  # "tutor" or "learner"
    message: str
    timestamp: datetime = field(default_factory=datetime.now)
    metadata: dict = field(default_factory=dict)


@dataclass
class ConversationLog:
    """Complete conversation log."""

    turns: list[ConversationTurn] = field(default_factory=list)
    learner_id: str = ""
    project_id: str = ""
    started_at: datetime = field(default_factory=datetime.now)
    ended_at: datetime | None = None
    config: dict = field(default_factory=dict)

    def add_turn(self, speaker: str, message: str, **metadata):
        """Add a turn to the log."""
        self.turns.append(ConversationTurn(speaker=speaker, message=message, metadata=metadata))

    def save(self, path: Path):
        """Save the conversation log to a JSON file."""
        self.ended_at = datetime.now()
        data = {
            "learner_id": self.learner_id,
            "project_id": self.project_id,
            "started_at": self.started_at.isoformat(),
            "ended_at": self.ended_at.isoformat(),
            "config": self.config,
            "turns": [
                {
                    "speaker": t.speaker,
                    "message": t.message,
                    "timestamp": t.timestamp.isoformat(),
                    "metadata": t.metadata,
                }
                for t in self.turns
            ],
        }
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w") as f:
            json.dump(data, f, indent=2)


class ConversationRunner:
    """
    Runs a conversation between the tutor and simulated learner.

    Uses the FastAPI server for agent interactions, which provides
    proper database connection pooling.
    """

    def __init__(
        self,
        learner_id: str,
        project_id: str,
        api_client: AgentClient,
        config: Config | None = None,
    ):
        self.learner_id = learner_id
        self.project_id = project_id
        self.api_client = api_client
        self.config = config or get_config()
        self.thread_id = f"{learner_id}-{project_id}"

        # Create the learner simulator (local, no DB needed)
        self.learner = create_learner_simulator(config=self.config)

        # Conversation state
        self.log = ConversationLog(
            learner_id=learner_id,
            project_id=project_id,
            config={
                "tutor_model": self.config.model.tutor_model,
                "learner_model": self.config.model.learner_model,
                "comprehension_rate": self.config.learner_sim.comprehension_rate,
            },
        )
        self.console = Console()
        self.turn_count = 0
        self.show_tools = False

    async def run(
        self,
        max_turns: int | None = None,
        delay: float | None = None,
        verbose: bool = True,
        show_tools: bool = False,
    ) -> ConversationLog:
        """
        Run the conversation between tutor and learner.

        Args:
            max_turns: Maximum number of conversation turns
            delay: Delay between turns (seconds)
            verbose: Whether to print the conversation
            show_tools: Whether to show tool calls in output

        Returns:
            The complete conversation log
        """
        if max_turns is None:
            max_turns = self.config.simulation.max_turns
        if delay is None:
            delay = self.config.simulation.turn_delay
        self.show_tools = show_tools

        if verbose:
            self.console.print(
                Panel(
                    f"[bold cyan]Simulation Starting[/bold cyan]\n\n"
                    f"Learner ID: {self.learner_id}\n"
                    f"Project ID: {self.project_id}\n"
                    f"Max Turns: {max_turns}\n"
                    f"Tutor Model: {self.config.model.tutor_model}\n"
                    f"Learner Model: {self.config.model.learner_model}",
                    title="Configuration",
                    border_style="cyan",
                )
            )

        # Start with learner greeting
        learner_greeting = await self.learner.get_greeting()
        self.log.add_turn("learner", learner_greeting)

        if verbose:
            self._print_message("learner", learner_greeting)

        current_message = learner_greeting

        while self.turn_count < max_turns:
            self.turn_count += 1

            # Tutor responds via API
            if verbose:
                with self.console.status("[bold green]Tutor thinking..."):
                    response = await self._get_tutor_response(current_message)
            else:
                response = await self._get_tutor_response(current_message)

            tutor_response = response.response
            tool_calls = response.tool_calls or []

            # Log tutor turn
            tutor_metadata = {"turn": self.turn_count}
            if tool_calls:
                tutor_metadata["tool_calls"] = tool_calls
            self.log.add_turn("tutor", tutor_response, **tutor_metadata)

            if verbose:
                self._print_message("tutor", tutor_response, tool_calls)
                await asyncio.sleep(delay)

            # Check for natural ending
            if self._should_end_conversation(tutor_response):
                if verbose:
                    self.console.print("\n[dim]Conversation reached natural end.[/dim]")
                break

            # Learner responds
            if verbose:
                with self.console.status("[bold blue]Learner thinking..."):
                    learner_response = await self.learner.respond(tutor_response)
            else:
                learner_response = await self.learner.respond(tutor_response)

            self.log.add_turn("learner", learner_response, turn=self.turn_count)

            if verbose:
                self._print_message("learner", learner_response)
                await asyncio.sleep(delay)

            current_message = learner_response

        if verbose:
            self._print_summary()

        return self.log

    def _print_summary(self):
        """Print detailed simulation summary."""
        from rich.table import Table

        # Calculate duration
        duration = (datetime.now() - self.log.started_at).total_seconds()

        # Count tool calls by name
        tool_counts: dict[str, int] = {}
        for t in self.log.turns:
            if t.speaker == "tutor":
                for tc in t.metadata.get("tool_calls", []):
                    if isinstance(tc, dict) and "name" in tc:
                        name = tc["name"]
                        tool_counts[name] = tool_counts.get(name, 0) + 1

        total_tool_calls = sum(tool_counts.values())
        tutor_turns = len([t for t in self.log.turns if t.speaker == "tutor"])

        # Basic summary
        self.console.print(
            Panel(
                f"[bold green]Simulation Complete[/bold green]\n\n"
                f"Total Turns: {self.turn_count}\n"
                f"Messages: {len(self.log.turns)}\n"
                f"Duration: {duration:.1f}s\n"
                f"Total Tool Calls: {total_tool_calls}\n"
                f"Avg Calls/Turn: {total_tool_calls / max(1, tutor_turns):.1f}",
                title="Summary",
                border_style="green",
            )
        )

        # Tool calls breakdown table
        if tool_counts:
            table = Table(title="Tool Call Breakdown", show_header=True)
            table.add_column("Tool", style="cyan")
            table.add_column("Count", justify="right")
            table.add_column("% of Total", justify="right")

            for name, count in sorted(tool_counts.items(), key=lambda x: -x[1]):
                pct = (count / total_tool_calls * 100) if total_tool_calls > 0 else 0
                table.add_row(name, str(count), f"{pct:.1f}%")

            self.console.print(table)

        # Try to extract project state from last tool calls
        self._print_project_state()

    def _print_project_state(self):
        """Print current project state based on logged data."""
        # Count submissions from tool calls
        submissions = 0
        tasks_started = set()
        tasks_completed = set()

        for t in self.log.turns:
            for tc in t.metadata.get("tool_calls", []):
                if isinstance(tc, dict):
                    name = tc.get("name", "")
                    args = tc.get("args", {})

                    if name == "submit":
                        submissions += 1
                        task_id = args.get("task_id")
                        if task_id:
                            tasks_completed.add(task_id)

                    if name == "start_task":
                        task_id = args.get("task_id")
                        if task_id:
                            tasks_started.add(task_id)

        if tasks_started or submissions:
            self.console.print(
                Panel(
                    f"Tasks Started: {len(tasks_started)}\n"
                    f"Submissions Made: {submissions}\n"
                    f"Tasks IDs Started: {', '.join(sorted(tasks_started)) if tasks_started else 'None'}",
                    title="Project Progress",
                    border_style="blue",
                )
            )

    async def _get_tutor_response(self, message: str) -> ChatResponse:
        """Get tutor's response via the API."""
        return await self.api_client.chat(
            message=message,
            learner_id=self.learner_id,
            project_id=self.project_id,
            thread_id=self.thread_id,
        )

    def _should_end_conversation(self, message: str) -> bool:
        """Check if the conversation should end naturally."""
        end_phrases = [
            "goodbye",
            "see you next time",
            "great progress today",
            "we'll continue",
            "that's all for today",
            "well done for today",
        ]
        message_lower = message.lower()
        return any(phrase in message_lower for phrase in end_phrases)

    def _print_message(self, speaker: str, message: str, tool_calls: list[dict] | None = None):
        """Print a message to the console."""
        if speaker == "tutor":
            tool_summary = ""
            if tool_calls and not self.show_tools:
                tool_names = [tc.get("name", "unknown") for tc in tool_calls]
                tool_summary = f"[dim]Tools: {', '.join(tool_names)}[/dim]"

            self.console.print(
                Panel(
                    Markdown(message),
                    title=f"[bold green]Tutor[/bold green] (Turn {self.turn_count})",
                    border_style="green",
                )
            )
            if tool_summary:
                self.console.print(tool_summary)
        else:
            self.console.print(
                Panel(
                    message,
                    title="[bold blue]Thabo (Learner)[/bold blue]",
                    border_style="blue",
                )
            )


async def run_simulation(
    learner_id: str,
    project_id: str,
    max_turns: int | None = None,
    config: Config | None = None,
    save_log: bool = True,
    verbose: bool = True,
    show_tools: bool = False,
    api_url: str = "http://localhost:8000",
) -> ConversationLog:
    """
    Run a simulation using the FastAPI server.

    Prerequisites:
        Start the API server first:
        $ PYTHONPATH=src uvicorn api.app:app --reload

    Args:
        learner_id: The learner ID
        project_id: The project ID
        max_turns: Maximum conversation turns
        config: Optional configuration
        save_log: Whether to save the conversation log
        verbose: Whether to print the conversation
        show_tools: Whether to show tool calls in output
        api_url: URL of the FastAPI server

    Returns:
        The conversation log
    """
    if config is None:
        config = get_config()

    async with AgentClient(api_url) as client:
        # Check if API is available
        if not await client.health_check():
            raise RuntimeError(
                f"API server not available at {api_url}. "
                "Start it with: PYTHONPATH=src uvicorn api.app:app --reload"
            )

        runner = ConversationRunner(
            learner_id=learner_id,
            project_id=project_id,
            api_client=client,
            config=config,
        )

        log = await runner.run(max_turns=max_turns, verbose=verbose, show_tools=show_tools)

        if save_log:
            log_dir = Path(config.simulation.log_dir)
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            log_path = log_dir / f"simulation_{timestamp}.json"
            log.save(log_path)
            if verbose:
                Console().print(f"\n[dim]Log saved to: {log_path}[/dim]")

        return log


# CLI entry point
if __name__ == "__main__":
    import sys

    if len(sys.argv) < 3:
        print("Usage: python -m simulation.runner <learner_id> <project_id> [max_turns]")
        print("\nMake sure the API server is running:")
        print("  PYTHONPATH=src uvicorn api.app:app --reload")
        sys.exit(1)

    learner_id = sys.argv[1]
    project_id = sys.argv[2]
    max_turns = int(sys.argv[3]) if len(sys.argv) > 3 else 10

    asyncio.run(run_simulation(learner_id, project_id, max_turns=max_turns))
