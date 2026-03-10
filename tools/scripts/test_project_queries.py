"""
Test SQL queries from project JSON files against the local SQLite database.

Reads `checks` from exercise subtasks in the epic JSON files and runs them
against a fresh SQLite copy of the database. Catches MySQL-vs-SQLite
incompatibilities before user testing.

Usage:
    python tools/scripts/test_project_queries.py content/projects/DA/MN_Part1/structured/
    python tools/scripts/test_project_queries.py content/projects/DA/MN_Part1/structured/ --db apps/web/public/data/md_water_services.sql
"""

import argparse
import json
import sqlite3
import sys
import tempfile
from pathlib import Path


def find_db_path(project_dir: Path) -> Path | None:
    """Try to find the SQL dump for this project."""
    repo_root = Path(__file__).resolve().parent.parent.parent
    # Default: the web app's public data directory
    default = repo_root / "apps" / "web" / "public" / "data" / "md_water_services.sql"
    if default.exists():
        return default
    return None


def load_db(sql_path: Path) -> tuple[sqlite3.Connection, Path]:
    """Load a SQL dump into a fresh SQLite database. Returns (connection, db_path)."""
    db_path = Path(tempfile.mktemp(suffix=".db"))
    conn = sqlite3.connect(str(db_path))
    with open(sql_path, "r") as f:
        conn.executescript(f.read())
    conn.row_factory = sqlite3.Row
    return conn, db_path


def collect_checks(project_dir: Path) -> list[dict]:
    """Walk epic JSONs in order, extract checks from exercise subtasks."""
    checks = []

    # Find epic files (sorted by filename prefix: 01_, 02_, etc.)
    epic_files = sorted(project_dir.glob("[0-9][0-9]_epic_*.json"))
    if not epic_files:
        print(f"  No epic files found in {project_dir}")
        return checks

    for epic_file in epic_files:
        with open(epic_file) as f:
            epic = json.load(f)

        epic_title = epic.get("title", epic_file.stem)
        _walk_tasks(epic.get("tasks", []), epic_title, checks)

    return checks


def _walk_tasks(tasks: list[dict], epic_title: str, checks: list[dict]):
    """Recursively walk tasks and subtasks, collecting checks."""
    for task in tasks:
        task_title = task.get("title", "?")

        # Check subtasks
        for subtask in task.get("subtasks", []):
            subtask_title = subtask.get("title", "?")
            subtask_checks = subtask.get("checks", [])

            if subtask_checks:
                checks.append({
                    "epic": epic_title,
                    "task": task_title,
                    "subtask": subtask_title,
                    "checks": subtask_checks,
                })

        # Recurse into nested tasks (if any)
        _walk_tasks(task.get("tasks", []), epic_title, checks)


def run_check(conn: sqlite3.Connection, check: dict) -> tuple[bool, str, int]:
    """Run a single check. Returns (passed, message, row_count)."""
    query = check.get("sqlite_query") or check["query"]
    expect = check.get("expect", {})

    cursor = conn.execute(query)

    if expect.get("modifies"):
        conn.commit()
        return True, "executed (DDL/DML)", 0

    rows = cursor.fetchall()
    row_count = len(rows)
    columns = [desc[0] for desc in cursor.description] if cursor.description else []

    errors = []

    if "row_count" in expect and row_count != expect["row_count"]:
        errors.append(f"expected {expect['row_count']} rows, got {row_count}")

    if "min_rows" in expect and row_count < expect["min_rows"]:
        errors.append(f"expected >= {expect['min_rows']} rows, got {row_count}")

    if "max_rows" in expect and row_count > expect["max_rows"]:
        errors.append(f"expected <= {expect['max_rows']} rows, got {row_count}")

    if "columns" in expect:
        expected_cols = expect["columns"]
        if columns != expected_cols:
            errors.append(f"columns mismatch: expected {expected_cols}, got {columns}")

    if errors:
        return False, "; ".join(errors), row_count

    return True, f"{row_count} row(s)", row_count


def run_all_checks(conn: sqlite3.Connection, all_checks: list[dict]):
    """Run all collected checks and report results."""
    passed = 0
    failed = 0
    sqlite_overrides = []
    failures = []

    print("=" * 78)
    print("  SQL Project Checks")
    print("=" * 78)
    print()

    for entry in all_checks:
        label = f"{entry['epic']} > {entry['task']} > {entry['subtask']}"
        subtask_passed = True
        subtask_messages = []

        for i, check in enumerate(entry["checks"]):
            query_display = check["query"][:60]
            has_override = check.get("sqlite_query") is not None

            try:
                ok, msg, _ = run_check(conn, check)
                if not ok:
                    subtask_passed = False
                    subtask_messages.append(f"  check {i+1}: FAIL -- {msg}")
                    subtask_messages.append(f"           query: {check['query'][:70]}")
                else:
                    subtask_messages.append(f"  check {i+1}: OK -- {msg}")

                if has_override:
                    sqlite_overrides.append((
                        label,
                        check["query"][:60],
                        check["sqlite_query"][:60],
                    ))

            except Exception as e:
                subtask_passed = False
                subtask_messages.append(f"  check {i+1}: ERROR -- {e}")
                subtask_messages.append(f"           query: {check['query'][:70]}")

        if subtask_passed:
            print(f"  PASS  {label}")
            passed += 1
        else:
            print(f"  FAIL  {label}")
            failed += 1
            failures.append(label)

        for msg in subtask_messages:
            print(f"        {msg}")
        print()

    # Summary
    print("=" * 78)
    print("  SUMMARY")
    print("=" * 78)
    print(f"  Exercise subtasks:  {passed + failed}")
    print(f"  Passed:             {passed}")
    print(f"  Failed:             {failed}")
    print()

    if sqlite_overrides:
        print("  SQLITE OVERRIDES (learner will type the MySQL version):")
        for label, mysql_q, sqlite_q in sqlite_overrides:
            print(f"    {label}")
            print(f"      MySQL:  {mysql_q}")
            print(f"      SQLite: {sqlite_q}")
        print()

    if failures:
        print("  FAILURES:")
        for label in failures:
            print(f"    - {label}")
        print()

    return failed == 0


def main():
    parser = argparse.ArgumentParser(
        description="Test SQL project checks against SQLite database"
    )
    parser.add_argument(
        "project_dir",
        type=Path,
        help="Path to the structured/ project directory containing epic JSONs",
    )
    parser.add_argument(
        "--db",
        type=Path,
        default=None,
        help="Path to the SQL dump file (auto-detected if not provided)",
    )
    args = parser.parse_args()

    project_dir = args.project_dir.resolve()
    if not project_dir.is_dir():
        print(f"ERROR: Not a directory: {project_dir}")
        sys.exit(1)

    # Find database
    db_sql = args.db
    if db_sql is None:
        db_sql = find_db_path(project_dir)
    if db_sql is None or not db_sql.exists():
        print(f"ERROR: SQL dump not found. Use --db to specify the path.")
        sys.exit(1)

    # Collect checks from JSON
    print(f"Project dir: {project_dir}")
    print(f"Database:    {db_sql}")
    print()

    all_checks = collect_checks(project_dir)
    if not all_checks:
        print("No checks found in epic JSON files.")
        print("Add 'checks' arrays to exercise subtasks.")
        sys.exit(1)

    print(f"Found {len(all_checks)} exercise subtask(s) with checks")
    total_queries = sum(len(c["checks"]) for c in all_checks)
    print(f"Total queries to run: {total_queries}")
    print()

    # Load database and run
    conn, db_path = load_db(db_sql)
    try:
        all_passed = run_all_checks(conn, all_checks)
    finally:
        conn.close()
        db_path.unlink(missing_ok=True)

    sys.exit(0 if all_passed else 1)


if __name__ == "__main__":
    main()
