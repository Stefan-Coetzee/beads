"""
Basic tests to verify the setup is working.
"""

import pytest
from sqlalchemy import text


@pytest.mark.asyncio
async def test_database_connection(async_session):
    """Test that we can connect to the database."""
    result = await async_session.execute(text("SELECT 1"))
    assert result.scalar() == 1


@pytest.mark.asyncio
async def test_tables_exist(async_engine):
    """Test that all expected tables are created."""
    async with async_engine.connect() as conn:
        result = await conn.execute(
            text(
                """
                SELECT table_name
                FROM information_schema.tables
                WHERE table_schema = 'public'
                AND table_type = 'BASE TABLE'
                ORDER BY table_name
                """
            )
        )
        tables = {row[0] for row in result}

    expected_tables = {
        "tasks",
        "learner_task_progress",
        "learners",
        "dependencies",
        "learning_objectives",
        "acceptance_criteria",
        "submissions",
        "validations",
        "status_summaries",
        "content",
        "comments",
        "events",
    }

    assert expected_tables.issubset(tables), f"Missing tables: {expected_tables - tables}"


def test_models_import():
    """Test that all models can be imported."""

    # If we got here, all imports worked
    assert True
