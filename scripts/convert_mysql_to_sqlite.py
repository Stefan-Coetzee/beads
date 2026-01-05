#!/usr/bin/env python3
"""
Convert MySQL dump to SQLite format for browser-based SQL.js
"""

import re
from pathlib import Path


def convert_mysql_to_sqlite(mysql_file: Path, output_file: Path):
    """Convert MySQL dump to SQLite-compatible SQL."""

    with open(mysql_file, "r", encoding="utf-8") as f:
        content = f.read()

    sqlite_statements = []

    # SQLite CREATE TABLE statements
    create_tables = {
        "employee": """
CREATE TABLE IF NOT EXISTS employee (
    assigned_employee_id INTEGER PRIMARY KEY,
    employee_name TEXT,
    phone_number TEXT,
    email TEXT,
    address TEXT,
    town_name TEXT,
    province_name TEXT,
    position TEXT
);""",
        "location": """
CREATE TABLE IF NOT EXISTS location (
    location_id TEXT PRIMARY KEY,
    address TEXT,
    province_name TEXT,
    town_name TEXT,
    location_type TEXT
);""",
        "water_source": """
CREATE TABLE IF NOT EXISTS water_source (
    source_id TEXT PRIMARY KEY,
    type_of_water_source TEXT,
    number_of_people_served INTEGER
);""",
        "visits": """
CREATE TABLE IF NOT EXISTS visits (
    record_id INTEGER PRIMARY KEY,
    location_id TEXT,
    source_id TEXT,
    time_of_record TEXT,
    visit_count INTEGER,
    time_in_queue INTEGER,
    assigned_employee_id INTEGER
);""",
        "well_pollution": """
CREATE TABLE IF NOT EXISTS well_pollution (
    source_id TEXT,
    date TEXT,
    description TEXT,
    pollutant_ppm REAL,
    biological REAL,
    results TEXT
);""",
        "quality_score": """
CREATE TABLE IF NOT EXISTS quality_score (
    record_id INTEGER PRIMARY KEY,
    subjective_quality_score INTEGER,
    visit_count INTEGER
);""",
        "global_water_access": """
CREATE TABLE IF NOT EXISTS global_water_access (
    name TEXT,
    region TEXT,
    year INTEGER,
    pop_n REAL,
    pop_u REAL,
    wat_bas_n REAL,
    wat_lim_n REAL,
    wat_unimp_n REAL,
    wat_sur_n REAL,
    wat_bas_r REAL,
    wat_lim_r REAL,
    wat_unimp_r REAL,
    wat_sur_r REAL,
    wat_bas_u REAL,
    wat_lim_u REAL,
    wat_unimp_u REAL,
    wat_sur_u REAL
);""",
        "column_legend": """
CREATE TABLE IF NOT EXISTS column_legend (
    column_name TEXT,
    description TEXT
);""",
    }

    # Order matters for foreign keys (even though SQLite doesn't enforce them by default)
    table_order = [
        "employee",
        "location",
        "water_source",
        "visits",
        "well_pollution",
        "quality_score",
        "global_water_access",
        "column_legend",
    ]

    # Add CREATE TABLE statements
    for table in table_order:
        if table in create_tables:
            sqlite_statements.append(create_tables[table])

    # Extract and convert INSERT statements
    # Pattern to match INSERT INTO `table` VALUES (...)
    insert_pattern = r"INSERT INTO `(\w+)` VALUES\s*(.*?);"

    for match in re.finditer(insert_pattern, content, re.DOTALL):
        table_name = match.group(1)
        values_str = match.group(2)

        if table_name not in create_tables:
            continue

        # Clean up the values
        values_str = values_str.strip()

        # The values string contains multiple rows like: (v1,v2),(v1,v2),...
        # We need to properly parse this respecting quotes

        # Parse individual value tuples properly
        rows = []
        current_row = []
        current_value = ""
        in_string = False
        paren_depth = 0
        i = 0

        while i < len(values_str):
            char = values_str[i]

            if char == "'" and (i == 0 or values_str[i-1] != "\\"):
                in_string = not in_string
                current_value += char
            elif char == "(" and not in_string:
                paren_depth += 1
                if paren_depth == 1:
                    current_value = ""
                else:
                    current_value += char
            elif char == ")" and not in_string:
                paren_depth -= 1
                if paren_depth == 0:
                    current_row.append(current_value)
                    rows.append(current_row)
                    current_row = []
                    current_value = ""
                else:
                    current_value += char
            elif char == "," and not in_string and paren_depth == 1:
                current_row.append(current_value)
                current_value = ""
            elif char == "," and not in_string and paren_depth == 0:
                # Between rows, skip
                pass
            else:
                current_value += char

            i += 1

        # Convert rows to SQLite INSERT statements
        # Process in batches to avoid huge statements
        batch_size = 500
        for batch_start in range(0, len(rows), batch_size):
            batch = rows[batch_start:batch_start + batch_size]

            # Build value strings, escaping single quotes properly
            value_strs = []
            for row in batch:
                escaped_values = []
                for val in row:
                    val = val.strip()
                    if val.startswith("'") and val.endswith("'"):
                        # String value - need to escape internal single quotes
                        inner = val[1:-1]
                        # Replace any unescaped single quotes with escaped ones
                        # First, un-escape MySQL's escaped quotes, then re-escape for SQLite
                        inner = inner.replace("\\'", "'")  # MySQL escape
                        inner = inner.replace("''", "'")   # SQL standard escape
                        inner = inner.replace("'", "''")   # SQLite escape
                        escaped_values.append(f"'{inner}'")
                    else:
                        escaped_values.append(val)
                value_strs.append(f"({','.join(escaped_values)})")

            insert_stmt = f"INSERT INTO {table_name} VALUES\n" + ",\n".join(value_strs) + ";"
            sqlite_statements.append(insert_stmt)

    # Write output
    output_content = "\n\n".join(sqlite_statements)

    with open(output_file, "w", encoding="utf-8") as f:
        f.write(output_content)

    print(f"Converted {mysql_file} to {output_file}")
    print(f"Total size: {len(output_content) / 1024:.1f} KB")


if __name__ == "__main__":
    mysql_file = Path("project_data/DA/MN_Part1/MD_water_services_stu_v2.sql")
    output_file = Path("frontend/public/data/md_water_services.sql")

    # Create output directory
    output_file.parent.mkdir(parents=True, exist_ok=True)

    convert_mysql_to_sqlite(mysql_file, output_file)
