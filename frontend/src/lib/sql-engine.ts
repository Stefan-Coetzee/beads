"use client";

// Dynamic import to avoid SSR issues with sql.js
import type { Database, SqlJsStatic } from "sql.js";

let SQL: SqlJsStatic | null = null;
let db: Database | null = null;

export interface QueryResult {
  success: boolean;
  columns?: string[];
  rows?: unknown[][];
  rowCount?: number;
  duration: number;
  error?: string;
}

/**
 * Initialize SQL.js with WebAssembly
 */
export async function initSqlEngine(): Promise<void> {
  if (SQL) return;

  // Dynamic import to avoid SSR issues
  const initSqlJs = (await import("sql.js")).default;
  SQL = await initSqlJs({
    locateFile: (file: string) => `https://sql.js.org/dist/${file}`,
  });
}

/**
 * Create a new in-memory database
 */
export async function createDatabase(schema?: string): Promise<void> {
  await initSqlEngine();
  if (!SQL) throw new Error("SQL.js not initialized");

  db = new SQL.Database();

  // If schema provided, execute it
  if (schema) {
    db.run(schema);
  }
}

/**
 * Load a database from binary data
 */
export async function loadDatabase(data: Uint8Array): Promise<void> {
  await initSqlEngine();
  if (!SQL) throw new Error("SQL.js not initialized");

  db = new SQL.Database(data);
}

/**
 * Execute a SQL query and return results
 */
export function executeQuery(sql: string): QueryResult {
  if (!db) {
    return {
      success: false,
      error: "Database not initialized. Please refresh the page.",
      duration: 0,
    };
  }

  const startTime = performance.now();

  try {
    const results = db.exec(sql);
    const duration = performance.now() - startTime;

    if (results.length === 0) {
      // Statement executed but returned no results (e.g., INSERT, UPDATE)
      return {
        success: true,
        columns: [],
        rows: [],
        rowCount: 0,
        duration,
      };
    }

    return {
      success: true,
      columns: results[0].columns,
      rows: results[0].values,
      rowCount: results[0].values.length,
      duration,
    };
  } catch (error) {
    return {
      success: false,
      error: error instanceof Error ? error.message : "Query execution failed",
      duration: performance.now() - startTime,
    };
  }
}

/**
 * Check if database is initialized
 */
export function isDatabaseReady(): boolean {
  return db !== null;
}

/**
 * Get database as binary (for saving)
 */
export function exportDatabase(): Uint8Array | null {
  return db?.export() || null;
}

/**
 * Load the Maji Ndogo database from public data
 */
export async function loadMajiNdogoDatabase(): Promise<void> {
  await initSqlEngine();
  if (!SQL) throw new Error("SQL.js not initialized");

  // Create fresh database
  db = new SQL.Database();

  // Fetch the SQL file from public directory
  const response = await fetch("/data/md_water_services.sql");
  if (!response.ok) {
    throw new Error("Failed to load database schema");
  }

  const sqlContent = await response.text();

  // Split into statements and execute
  // Be careful with semicolons in strings
  const statements = sqlContent.split(/;\s*\n/);

  for (const stmt of statements) {
    const trimmed = stmt.trim();
    if (trimmed) {
      try {
        db.run(trimmed);
      } catch (e) {
        console.error("Error executing SQL:", trimmed.slice(0, 100), e);
      }
    }
  }

  console.log("Maji Ndogo database loaded successfully");
}

/**
 * Sample schema for fallback/demo
 */
export const SAMPLE_SCHEMA = `
-- Water source locations (demo data)
CREATE TABLE IF NOT EXISTS water_sources (
    source_id INTEGER PRIMARY KEY,
    location_name TEXT NOT NULL,
    source_type TEXT,
    latitude REAL,
    longitude REAL
);

-- Survey data
CREATE TABLE IF NOT EXISTS surveys (
    survey_id INTEGER PRIMARY KEY,
    source_id INTEGER,
    visit_date TEXT,
    queue_time INTEGER,
    water_quality TEXT,
    infrastructure_score INTEGER,
    FOREIGN KEY (source_id) REFERENCES water_sources(source_id)
);

-- Sample data
INSERT INTO water_sources VALUES
(1, 'North Village Well', 'well', -1.2345, 36.8219),
(2, 'Central Pump Station', 'pump', -1.2367, 36.8234),
(3, 'South River Access', 'river', -1.2401, 36.8256),
(4, 'East Community Tap', 'tap', -1.2312, 36.8298),
(5, 'West Spring', 'spring', -1.2389, 36.8167);

INSERT INTO surveys VALUES
(1, 1, '2024-01-15', 45, 'good', 8),
(2, 1, '2024-01-22', 62, 'fair', 7),
(3, 2, '2024-01-16', 120, 'poor', 5),
(4, 2, '2024-01-23', 95, 'fair', 6),
(5, 3, '2024-01-17', 180, 'poor', 4);
`;
