"""
CLI entry point for the Socratic Learning Agent.

Provides interactive and batch modes for running the agent.

Usage:
    # Interactive mode
    python -m agent.main chat --learner-id learner-123 --project-id proj-abc

    # Single message
    python -m agent.main ask --learner-id learner-123 --project-id proj-abc "What should I work on?"
"""

import asyncio

import typer
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage
from ltt.db.connection import get_session_factory
from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel
from rich.prompt import Prompt

from agent.graph import create_agent

app = typer.Typer(
    name="agent",
    help="Socratic Learning Agent - A tutoring assistant for structured projects",
)
console = Console()


def print_message(message, show_tools: bool = False):
    """Pretty print a message."""
    if isinstance(message, HumanMessage):
        console.print(Panel(message.content, title="You", border_style="blue"))
    elif isinstance(message, AIMessage):
        # Print the text content
        if message.content:
            console.print(Panel(Markdown(message.content), title="Tutor", border_style="green"))

        # Optionally show tool calls
        if show_tools and message.tool_calls:
            for tc in message.tool_calls:
                console.print(f"  [dim]Tool: {tc['name']}({tc['args']})[/dim]")
    elif isinstance(message, ToolMessage):
        if show_tools:
            # Truncate long tool results
            content = message.content
            if len(content) > 500:
                content = content[:500] + "..."
            console.print(f"  [dim]Result ({message.name}): {content}[/dim]")


async def run_chat(learner_id: str, project_id: str, show_tools: bool = False):
    """Run an interactive chat session."""
    console.print(
        Panel(
            "[bold green]Socratic Learning Agent[/bold green]\n\n"
            f"Learner: {learner_id}\n"
            f"Project: {project_id}\n\n"
            "Type 'quit' or 'exit' to end the session.\n"
            "Type 'status' to see current task and progress.",
            title="Welcome",
            border_style="cyan",
        )
    )

    # Create session and agent
    factory = get_session_factory()
    async with factory() as session:
        agent = create_agent(
            learner_id=learner_id,
            project_id=project_id,
            session=session,
        )

        # Main chat loop
        while True:
            try:
                # Get user input
                user_input = Prompt.ask("\n[bold blue]You[/bold blue]")

                # Check for exit commands
                if user_input.lower() in ("quit", "exit", "q"):
                    console.print("[yellow]Goodbye! Keep learning![/yellow]")
                    break

                # Check for status command
                if user_input.lower() == "status":
                    state = agent.get_state()
                    if state and state.values:
                        values = state.values
                        if values.get("current_task"):
                            task = values["current_task"]
                            console.print(
                                f"\n[bold]Current Task:[/bold] {task.task_title} ({task.task_id})"
                            )
                            console.print(f"[bold]Status:[/bold] {task.status}")
                        if values.get("progress"):
                            prog = values["progress"]
                            console.print(
                                f"[bold]Progress:[/bold] {prog.completed}/{prog.total} "
                                f"({prog.percentage:.1f}%)"
                            )
                    else:
                        console.print(
                            "[dim]No session state yet. Start by asking a question.[/dim]"
                        )
                    continue

                # Skip empty input
                if not user_input.strip():
                    continue

                # Stream the response
                console.print()  # Add spacing
                with console.status("[bold green]Thinking...", spinner="dots"):
                    final_state = None
                    async for state in agent.astream(user_input):
                        final_state = state

                # Print the final AI response
                if final_state and final_state.get("messages"):
                    messages = final_state["messages"]
                    # Find the last AI message that has content
                    for msg in reversed(messages):
                        if isinstance(msg, AIMessage) and msg.content:
                            print_message(msg, show_tools)
                            break

            except KeyboardInterrupt:
                console.print("\n[yellow]Interrupted. Type 'quit' to exit.[/yellow]")
            except Exception as e:
                console.print(f"[red]Error: {e}[/red]")
                if show_tools:
                    import traceback

                    console.print(f"[dim]{traceback.format_exc()}[/dim]")


async def run_single_message(
    learner_id: str, project_id: str, message: str, show_tools: bool = False
):
    """Run a single message through the agent."""
    factory = get_session_factory()
    async with factory() as session:
        agent = create_agent(
            learner_id=learner_id,
            project_id=project_id,
            session=session,
        )

        # Invoke the agent
        result = await agent.ainvoke(message)

        # Print the response
        if result and result.get("messages"):
            for msg in result["messages"]:
                print_message(msg, show_tools)


@app.command()
def chat(
    learner_id: str = typer.Option(..., "--learner-id", "-l", help="Learner ID"),
    project_id: str = typer.Option(..., "--project-id", "-p", help="Project ID"),
    show_tools: bool = typer.Option(False, "--show-tools", "-t", help="Show tool calls"),
):
    """Start an interactive chat session with the learning agent."""
    asyncio.run(run_chat(learner_id, project_id, show_tools))


@app.command()
def ask(
    learner_id: str = typer.Option(..., "--learner-id", "-l", help="Learner ID"),
    project_id: str = typer.Option(..., "--project-id", "-p", help="Project ID"),
    message: str = typer.Argument(..., help="Message to send to the agent"),
    show_tools: bool = typer.Option(False, "--show-tools", "-t", help="Show tool calls"),
):
    """Send a single message to the agent and get a response."""
    asyncio.run(run_single_message(learner_id, project_id, message, show_tools))


@app.command()
def demo(
    show_tools: bool = typer.Option(False, "--show-tools", "-t", help="Show tool calls"),
):
    """
    Run a demo session with a test learner and project.

    Creates temporary learner and project for demonstration.
    """
    console.print(
        "[yellow]Demo mode requires a project in the database.[/yellow]\n"
        "Create one with: python -m ltt.cli.main ingest project <file.json>\n"
        "Then run: python -m agent.main chat -l <learner-id> -p <project-id>"
    )


if __name__ == "__main__":
    app()
