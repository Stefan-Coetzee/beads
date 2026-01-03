"""
Simulation runner for tutor-learner conversations.

Orchestrates the interaction between the Socratic tutor and simulated learner.
"""

import asyncio
import json
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

from langchain_core.messages import AIMessage, ToolMessage
from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel
from rich.syntax import Syntax
from sqlalchemy.ext.asyncio import AsyncSession

from agent.config import Config, get_config
from agent.graph import create_agent
from learner_sim.simulator import create_learner_simulator
from ltt.db.connection import get_session_factory


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
    """

    def __init__(
        self,
        learner_id: str,
        project_id: str,
        session: AsyncSession,
        config: Config | None = None,
    ):
        self.learner_id = learner_id
        self.project_id = project_id
        self.session = session
        self.config = config or get_config()

        # Create the agents
        self.tutor = create_agent(
            learner_id=learner_id,
            project_id=project_id,
            session=session,
            config=self.config,
        )
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
        self.show_tools = False  # Will be set by run()

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

        # Initial tutor response
        current_message = learner_greeting

        while self.turn_count < max_turns:
            self.turn_count += 1

            # Tutor responds
            if verbose:
                with self.console.status("[bold green]Tutor thinking..."):
                    tutor_response = await self._get_tutor_response(current_message)
            else:
                tutor_response = await self._get_tutor_response(current_message)

            self.log.add_turn("tutor", tutor_response, turn=self.turn_count)

            if verbose:
                self._print_message("tutor", tutor_response)
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
            self.console.print(
                Panel(
                    f"[bold green]Simulation Complete[/bold green]\n\n"
                    f"Total Turns: {self.turn_count}\n"
                    f"Messages: {len(self.log.turns)}",
                    title="Summary",
                    border_style="green",
                )
            )
            # Print project status
            await self._print_project_status()

        return self.log

    async def _print_project_status(self):
        """Print the current project status after simulation."""
        from rich.table import Table

        from ltt.services.learning.progress import get_progress
        from ltt.services.dependency_service import get_ready_work

        try:
            # Get progress stats
            progress = await get_progress(self.session, self.learner_id, self.project_id)

            # Get ready tasks
            ready_tasks = await get_ready_work(
                self.session,
                self.project_id,
                self.learner_id,
                limit=10,
            )

            # Create progress table
            self.console.print("\n")
            self.console.print(
                Panel(
                    f"[bold]Progress:[/bold] {progress.completed_tasks}/{progress.total_tasks} "
                    f"({progress.completion_percentage:.1f}%)\n"
                    f"[bold]In Progress:[/bold] {progress.in_progress_tasks}\n"
                    f"[bold]Blocked:[/bold] {progress.blocked_tasks}\n"
                    f"[bold]Objectives:[/bold] {progress.objectives_achieved}/{progress.total_objectives}",
                    title="[bold cyan]Project Status[/bold cyan]",
                    border_style="cyan",
                )
            )

            # Create ready tasks table
            if ready_tasks:
                table = Table(title="Ready Tasks", show_header=True, header_style="bold magenta")
                table.add_column("ID", style="dim")
                table.add_column("Title")
                table.add_column("Type")
                table.add_column("Status", style="green")

                for task in ready_tasks[:5]:
                    # Get status for this task
                    from ltt.services.progress_service import get_or_create_progress
                    task_progress = await get_or_create_progress(
                        self.session, task.id, self.learner_id
                    )
                    table.add_row(
                        task.id,
                        task.title[:40] + "..." if len(task.title) > 40 else task.title,
                        task.task_type.value if hasattr(task.task_type, 'value') else str(task.task_type),
                        task_progress.status.value if hasattr(task_progress.status, 'value') else str(task_progress.status),
                    )

                self.console.print(table)

        except Exception as e:
            self.console.print(f"[dim]Could not fetch project status: {e}[/dim]")

    async def _get_tutor_response(self, message: str, verbose: bool = True) -> str:
        """Get tutor's response to a message, showing tool calls if enabled."""
        tool_calls_made = []
        final_response = ""

        # Use streaming to capture intermediate steps
        async for state in self.tutor.astream(message):
            messages = state.get("messages", [])

            for msg in messages:
                # Capture tool calls from AI messages
                if isinstance(msg, AIMessage) and msg.tool_calls:
                    for tc in msg.tool_calls:
                        tool_calls_made.append({
                            "name": tc["name"],
                            "args": tc["args"],
                        })
                        if self.show_tools and verbose:
                            self._print_tool_call(tc["name"], tc["args"])

                # Capture tool results
                if isinstance(msg, ToolMessage) and self.show_tools and verbose:
                    self._print_tool_result(msg.name, msg.content)

                # Capture final AI response (with content, no tool calls)
                if isinstance(msg, AIMessage) and msg.content and not msg.tool_calls:
                    final_response = msg.content

        # Log tool calls in metadata
        if tool_calls_made:
            self.log.turns[-1].metadata["tool_calls"] = tool_calls_made if self.log.turns else None

        return final_response or "I'm here to help. What would you like to work on?"

    def _print_tool_call(self, name: str, args: dict):
        """Print a tool call to the console."""
        args_json = json.dumps(args, indent=2)
        self.console.print(
            Panel(
                Syntax(args_json, "json", theme="monokai", word_wrap=True),
                title=f"[bold yellow]Tool Call: {name}[/bold yellow]",
                border_style="yellow",
            )
        )

    def _print_tool_result(self, name: str, result: str):
        """Print a tool result to the console."""
        # Try to format as JSON if possible
        try:
            parsed = json.loads(result)
            result_display = json.dumps(parsed, indent=2)
            is_json = True
        except (json.JSONDecodeError, TypeError):
            result_display = str(result)[:500]  # Truncate long results
            is_json = False

        # Truncate if too long
        if len(result_display) > 1000:
            result_display = result_display[:1000] + "\n... (truncated)"

        content = Syntax(result_display, "json" if is_json else "text", theme="monokai", word_wrap=True)

        self.console.print(
            Panel(
                content,
                title=f"[bold magenta]Tool Result: {name}[/bold magenta]",
                border_style="magenta",
            )
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

    def _print_message(self, speaker: str, message: str):
        """Print a message to the console."""
        if speaker == "tutor":
            self.console.print(
                Panel(
                    Markdown(message),
                    title=f"[bold green]Tutor[/bold green] (Turn {self.turn_count})",
                    border_style="green",
                )
            )
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
) -> ConversationLog:
    """
    Run a simulation with automatic session management.

    Args:
        learner_id: The learner ID
        project_id: The project ID
        max_turns: Maximum conversation turns
        config: Optional configuration
        save_log: Whether to save the conversation log
        verbose: Whether to print the conversation
        show_tools: Whether to show tool calls in output

    Returns:
        The conversation log
    """
    if config is None:
        config = get_config()

    factory = get_session_factory()
    async with factory() as session:
        runner = ConversationRunner(
            learner_id=learner_id,
            project_id=project_id,
            session=session,
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
