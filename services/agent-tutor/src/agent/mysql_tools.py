"""
MySQL tools for the Socratic Learning Agent.

Provides read-only database access for learners to practice SQL queries.
"""

import os
from typing import Any

import aiomysql
from langchain_core.tools import StructuredTool
from pydantic import BaseModel, Field

# =============================================================================
# Configuration
# =============================================================================

MYSQL_CONFIG = {
    "host": os.getenv("MYSQL_HOST", "localhost"),
    "port": int(os.getenv("MYSQL_PORT", "3306")),
    "user": os.getenv("MYSQL_USER", "learner"),
    "password": os.getenv("MYSQL_PASSWORD", "learner_password"),
    "db": os.getenv("MYSQL_DATABASE", "md_water_services"),
}

# Maximum rows to return from queries
MAX_ROWS = 100

# Read-only keywords (queries must start with these)
READONLY_PREFIXES = ("SELECT", "SHOW", "DESCRIBE", "DESC", "EXPLAIN")

# =============================================================================
# Tool Input Schemas
# =============================================================================


class RunSQLToolInput(BaseModel):
    """Execute a read-only SQL query."""

    query: str = Field(
        ...,
        description="The SQL query to execute. Must be read-only (SELECT, SHOW, DESCRIBE, EXPLAIN).",
    )


# =============================================================================
# MySQL Connection
# =============================================================================


async def get_mysql_connection():
    """Get a MySQL connection from the pool."""
    return await aiomysql.connect(**MYSQL_CONFIG)


async def execute_readonly_query(query: str) -> dict[str, Any]:
    """
    Execute a read-only SQL query and return results.

    Args:
        query: SQL query string (must be read-only)

    Returns:
        Dict with columns, rows, row_count, and any error message
    """
    # Check if query is read-only
    query_upper = query.strip().upper()
    if not any(query_upper.startswith(prefix) for prefix in READONLY_PREFIXES):
        return {
            "success": False,
            "error": f"Only read-only queries are allowed. Query must start with: {', '.join(READONLY_PREFIXES)}",
            "columns": [],
            "rows": [],
            "row_count": 0,
        }

    try:
        conn = await get_mysql_connection()
        try:
            async with conn.cursor() as cursor:
                await cursor.execute(query)
                rows = await cursor.fetchmany(MAX_ROWS + 1)

                # Check if there are more rows
                truncated = len(rows) > MAX_ROWS
                if truncated:
                    rows = rows[:MAX_ROWS]

                # Get column names
                columns = [desc[0] for desc in cursor.description] if cursor.description else []

                return {
                    "success": True,
                    "columns": columns,
                    "rows": [list(row) for row in rows],
                    "row_count": len(rows),
                    "truncated": truncated,
                    "message": f"Query returned {len(rows)} rows"
                    + (" (truncated to 100)" if truncated else ""),
                }
        finally:
            conn.close()
    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "columns": [],
            "rows": [],
            "row_count": 0,
        }


# =============================================================================
# Tool Factory Functions
# =============================================================================


def create_mysql_tools() -> list[StructuredTool]:
    """
    Create MySQL-related tools for the agent.

    Returns:
        List of StructuredTool instances (just run_sql)
    """
    import json

    async def run_sql(query: str) -> str:
        """Execute a SQL query TO VALIDATE what the learner submitted.

        IMPORTANT: Only use this when the learner provides a SQL query to check.
        DO NOT use this to explore the database yourself or to demonstrate queries.
        The learner should run their own queries in MySQL Workbench.

        Only SELECT, SHOW, DESCRIBE, and EXPLAIN queries are allowed.
        Results are limited to 100 rows.
        """
        result = await execute_readonly_query(query)
        return json.dumps(result, indent=2, default=str)

    tools = [
        StructuredTool.from_function(
            coroutine=run_sql,
            name="run_sql",
            description=(
                "VALIDATION ONLY: Execute a SQL query that the LEARNER submitted to verify their work. "
                "The database (md_water_services) contains ~60,000 records about water access in Maji Ndogo. "
                "DO NOT use to explore the database yourself - guide the learner to run queries in MySQL Workbench. "
                "Only SELECT, SHOW, DESCRIBE, EXPLAIN allowed."
            ),
            args_schema=RunSQLToolInput,
        ),
    ]

    return tools


def create_learner_mysql_tools() -> list[StructuredTool]:
    """
    Create MySQL tools for the LEARNER simulator.

    Different from tutor tools - learner can explore freely.

    Returns:
        List of StructuredTool instances
    """
    import json

    async def run_sql(query: str) -> str:
        """Execute a SQL query on the database.

        Use this to explore the database, test your queries, and verify your work.
        Only SELECT, SHOW, DESCRIBE, and EXPLAIN queries are allowed.
        Results are limited to 100 rows.
        """
        result = await execute_readonly_query(query)
        return json.dumps(result, indent=2, default=str)

    tools = [
        StructuredTool.from_function(
            coroutine=run_sql,
            name="run_sql",
            description=(
                "Execute a SQL query on the md_water_services database (~60,000 records about water access in Maji Ndogo). "
                "Use this to explore table structures, run SELECT queries, and verify your work. "
                "Only SELECT, SHOW, DESCRIBE, EXPLAIN allowed."
            ),
            args_schema=RunSQLToolInput,
        ),
    ]

    return tools
