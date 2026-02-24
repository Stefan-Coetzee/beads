"""
Tests for CLI commands.

These tests verify CLI behavior, particularly edge cases and fixes.
"""

from unittest.mock import MagicMock, patch

import pytest


class TestDbInit:
    """Tests for the db init command."""

    @patch("subprocess.run")
    def test_db_init_passes_pythonpath_in_env(self, mock_run):
        """
        Regression test: db init should pass PYTHONPATH as an environment variable,
        not as a command argument.

        This tests the fix for the bug where subprocess.run was called with
        ["PYTHONPATH=src", "uv", "run", ...] which tried to execute "PYTHONPATH=src"
        as a command instead of setting it as an environment variable.
        """
        from ltt.cli.main import db_init

        mock_run.return_value = MagicMock(returncode=0)

        # Run the command
        try:
            db_init()
        except SystemExit:
            pass  # Typer may exit, but we just want to verify the call

        # Verify subprocess.run was called
        mock_run.assert_called_once()

        # Get the call arguments
        call_args = mock_run.call_args

        # Verify the command does NOT start with "PYTHONPATH=src"
        cmd = call_args[0][0]  # First positional arg is the command list
        assert cmd[0] != "PYTHONPATH=src", "PYTHONPATH should be in env, not as command argument"
        assert cmd[0] == "uv", "Command should start with 'uv'"

        # Verify PYTHONPATH is in the environment
        env = call_args[1].get("env", {})
        assert "PYTHONPATH" in env, "PYTHONPATH should be in env dict"
        assert env["PYTHONPATH"] == "src", "PYTHONPATH should be set to 'src'"

    @patch("subprocess.run")
    def test_db_init_success_message(self, mock_run, capsys):
        """Test that successful db init shows proper message."""
        from ltt.cli.main import db_init

        mock_run.return_value = MagicMock(returncode=0)

        try:
            db_init()
        except SystemExit:
            pass

        captured = capsys.readouterr()
        assert "Running database migrations" in captured.out
        assert "Database initialized successfully" in captured.out

    @patch("subprocess.run")
    def test_db_init_failure_shows_error(self, mock_run, capsys):
        """Test that failed db init shows error message."""
        from click.exceptions import Exit
        from ltt.cli.main import db_init

        mock_run.return_value = MagicMock(
            returncode=1, stderr=b"Migration failed: table already exists"
        )

        with pytest.raises(Exit) as exc_info:
            db_init()

        assert exc_info.value.exit_code == 1
        captured = capsys.readouterr()
        assert "Error:" in captured.out
        assert "Migration failed" in captured.out
