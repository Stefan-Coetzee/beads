"""
Tests that workspace data (editor code + execution results) flows correctly
to the LLM via format_workspace_context() and build_message_with_context().

These are the two pure functions that sit on the critical path between the
frontend workspace and the agent.  If they break, the LLM sees no code/results.
"""

from __future__ import annotations

import sys
import types as _types

# ---------------------------------------------------------------------------
# Prevent the agent stack (langchain_anthropic, etc.) from being imported.
# api.routes imports api.agents at module level, so we stub it before import.
# ---------------------------------------------------------------------------
if "api" not in sys.modules:
    _api_src = str(__import__("pathlib").Path(__file__).resolve().parents[1] / "src" / "api")
    sys.modules["api"] = _types.ModuleType("api")
    sys.modules["api"].__path__ = [_api_src]  # type: ignore[attr-defined]

# Stub api.agents so api.routes can import without pulling in langchain
_fake_agents = _types.ModuleType("api.agents")
_fake_agents.get_or_create_agent = lambda **kw: None  # type: ignore[attr-defined]
sys.modules["api.agents"] = _fake_agents

from api.routes import (  # noqa: E402
    ExecutionResult,
    WorkspaceContext,
    build_message_with_context,
    format_workspace_context,
)

# =========================================================================
# format_workspace_context — SQL workspace
# =========================================================================


class TestFormatWorkspaceContextSQL:
    """SQL editor content and query results reach the formatted output."""

    def test_sql_editor_content_included(self):
        ctx = WorkspaceContext(
            workspace_type="sql",
            editor_content="SELECT * FROM surveys;",
            results=None,
        )
        out = format_workspace_context(ctx)
        assert "[Workspace: SQL]" in out
        assert "```sql" in out
        assert "SELECT * FROM surveys;" in out

    def test_sql_tabular_results_included(self):
        ctx = WorkspaceContext(
            workspace_type="sql",
            editor_content="SELECT id, name FROM users;",
            results=ExecutionResult(
                success=True,
                duration=42.5,
                columns=["id", "name"],
                rows=[[1, "Alice"], [2, "Bob"]],
                row_count=2,
            ),
        )
        out = format_workspace_context(ctx)

        # Editor content present
        assert "SELECT id, name FROM users;" in out
        # Table header
        assert "| id | name |" in out
        # Row data
        assert "| 1 | Alice |" in out
        assert "| 2 | Bob |" in out
        # Metadata
        assert "2 rows" in out

    def test_sql_empty_result_set(self):
        ctx = WorkspaceContext(
            workspace_type="sql",
            editor_content="SELECT * FROM empty_table;",
            results=ExecutionResult(
                success=True,
                duration=5.0,
                columns=["id"],
                rows=[],
                row_count=0,
            ),
        )
        out = format_workspace_context(ctx)
        assert "No rows returned" in out

    def test_sql_error_result(self):
        ctx = WorkspaceContext(
            workspace_type="sql",
            editor_content="SELEC * FROM bad;",
            results=ExecutionResult(
                success=False,
                duration=1.0,
                error='syntax error at or near "SELEC"',
            ),
        )
        out = format_workspace_context(ctx)
        assert "**Error**" in out
        assert "syntax error" in out

    def test_sql_large_result_truncated_to_10_rows(self):
        rows = [[i, f"row-{i}"] for i in range(25)]
        ctx = WorkspaceContext(
            workspace_type="sql",
            editor_content="SELECT * FROM big;",
            results=ExecutionResult(
                success=True,
                duration=100.0,
                columns=["id", "val"],
                rows=rows,
                row_count=25,
            ),
        )
        out = format_workspace_context(ctx)
        # First 10 rows present
        assert "| 0 | row-0 |" in out
        assert "| 9 | row-9 |" in out
        # 11th row NOT present
        assert "| 10 | row-10 |" not in out
        # Truncation notice
        assert "15 more rows" in out


# =========================================================================
# format_workspace_context — Python workspace
# =========================================================================


class TestFormatWorkspaceContextPython:
    """Python editor content and execution output reach the formatted output."""

    def test_python_editor_content_included(self):
        ctx = WorkspaceContext(
            workspace_type="python",
            editor_content="print('hello world')",
            results=None,
        )
        out = format_workspace_context(ctx)
        assert "[Workspace: Python]" in out
        assert "```python" in out
        assert "print('hello world')" in out

    def test_python_stdout_output_included(self):
        ctx = WorkspaceContext(
            workspace_type="python",
            editor_content="for i in range(3): print(i)",
            results=ExecutionResult(
                success=True,
                duration=10.0,
                output="0\n1\n2",
            ),
        )
        out = format_workspace_context(ctx)
        assert "**Output**" in out
        assert "0\n1\n2" in out

    def test_python_error_with_traceback(self):
        ctx = WorkspaceContext(
            workspace_type="python",
            editor_content="1/0",
            results=ExecutionResult(
                success=False,
                duration=2.0,
                error_message="ZeroDivisionError: division by zero",
                traceback='Traceback (most recent call last):\n  File "<stdin>", line 1\nZeroDivisionError: division by zero',
            ),
        )
        out = format_workspace_context(ctx)
        assert "**Error**" in out
        assert "ZeroDivisionError" in out
        assert "Traceback" in out

    def test_python_no_output_execution(self):
        ctx = WorkspaceContext(
            workspace_type="python",
            editor_content="x = 42",
            results=ExecutionResult(
                success=True,
                duration=1.0,
            ),
        )
        out = format_workspace_context(ctx)
        assert "Execution completed" in out


# =========================================================================
# format_workspace_context — edge cases
# =========================================================================


class TestFormatWorkspaceContextEdgeCases:
    def test_none_context_returns_empty_string(self):
        assert format_workspace_context(None) == ""

    def test_empty_editor_content_omitted(self):
        ctx = WorkspaceContext(
            workspace_type="sql",
            editor_content="   ",
            results=None,
        )
        out = format_workspace_context(ctx)
        assert "Current Code" not in out

    def test_missing_workspace_type_defaults_to_sql(self):
        ctx = WorkspaceContext(
            editor_content="SELECT 1;",
            results=None,
        )
        out = format_workspace_context(ctx)
        assert "[Workspace: SQL]" in out
        assert "```sql" in out

    def test_cybersecurity_workspace_type(self):
        ctx = WorkspaceContext(
            workspace_type="cybersecurity",
            editor_content="nmap scan",
            results=None,
        )
        out = format_workspace_context(ctx)
        assert "[Workspace: Cybersecurity]" in out


# =========================================================================
# build_message_with_context — context is prepended to user message
# =========================================================================


class TestBuildMessageWithContext:
    """Workspace context is prepended so the LLM sees code+results before the user's question."""

    def test_message_only_when_no_context(self):
        result = build_message_with_context("What is SQL?", None)
        assert result == "What is SQL?"

    def test_context_prepended_to_message(self):
        ctx = WorkspaceContext(
            workspace_type="sql",
            editor_content="SELECT COUNT(*) FROM users;",
            results=ExecutionResult(
                success=True,
                duration=3.0,
                columns=["count"],
                rows=[[42]],
                row_count=1,
            ),
        )
        result = build_message_with_context("Why does this return 42?", ctx)

        # Context comes first
        assert result.index("[Workspace: SQL]") < result.index("Why does this return 42?")
        # Editor code present
        assert "SELECT COUNT(*) FROM users;" in result
        # Results present
        assert "| 42 |" in result
        # User message present with label
        assert "**User Message:** Why does this return 42?" in result

    def test_full_sql_round_trip(self):
        """End-to-end: SQL code + error result + user question → single string for LLM."""
        ctx = WorkspaceContext(
            workspace_type="sql",
            editor_content="SELECT * FORM users;",
            results=ExecutionResult(
                success=False,
                duration=1.0,
                error='ERROR: syntax error at or near "FORM"',
            ),
        )
        result = build_message_with_context("What's wrong with my query?", ctx)

        # All three pieces present in the final string
        assert "SELECT * FORM users;" in result
        assert "syntax error" in result
        assert "What's wrong with my query?" in result

    def test_full_python_round_trip(self):
        """End-to-end: Python code + output + user question → single string for LLM."""
        ctx = WorkspaceContext(
            workspace_type="python",
            editor_content="data = [1, 2, 3]\nprint(sum(data))",
            results=ExecutionResult(
                success=True,
                duration=5.0,
                output="6",
            ),
        )
        result = build_message_with_context("Is this correct?", ctx)

        assert "[Workspace: Python]" in result
        assert "print(sum(data))" in result
        assert "6" in result
        assert "**User Message:** Is this correct?" in result
