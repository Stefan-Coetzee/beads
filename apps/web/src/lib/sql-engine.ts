"use client";

// Dynamic import to avoid SSR issues with sql.js
import type { Database, SqlJsStatic } from "sql.js";

let SQL: SqlJsStatic | null = null;
let db: Database | null = null;
let loadingPromise: Promise<void> | null = null;

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
 * @param force - If true, forces a reload even if database exists
 */
export async function loadMajiNdogoDatabase(force: boolean = false): Promise<void> {
  // Prevent concurrent loading - return existing promise if loading
  if (loadingPromise && !force) {
    return loadingPromise;
  }

  // Wait for any existing load to complete before forcing a new one
  if (loadingPromise && force) {
    await loadingPromise;
  }

  loadingPromise = (async () => {
    try {
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
            // Convert INSERT to INSERT OR IGNORE to handle any duplicate key issues
            const safeStmt = trimmed.replace(/^INSERT INTO/i, "INSERT OR IGNORE INTO");
            db.run(safeStmt);
          } catch (e) {
            console.error("Error executing SQL:", trimmed.slice(0, 100), e);
          }
        }
      }

      console.log("Maji Ndogo database loaded successfully");
    } finally {
      // Reset loading promise when done (success or failure)
      loadingPromise = null;
    }
  })();

  return loadingPromise;
}

/**
 * Sample schema for fallback/demo (matches Maji Ndogo structure)
 */
export const SAMPLE_SCHEMA = `
-- Maji Ndogo Water Services - Sample Schema
CREATE TABLE IF NOT EXISTS employee (
    assigned_employee_id INTEGER PRIMARY KEY,
    employee_name TEXT,
    phone_number TEXT,
    email TEXT,
    address TEXT,
    town_name TEXT,
    province_name TEXT,
    position TEXT
);

CREATE TABLE IF NOT EXISTS location (
    location_id TEXT PRIMARY KEY,
    address TEXT,
    province_name TEXT,
    town_name TEXT,
    location_type TEXT
);

CREATE TABLE IF NOT EXISTS water_source (
    source_id TEXT PRIMARY KEY,
    type_of_water_source TEXT,
    number_of_people_served INTEGER
);

CREATE TABLE IF NOT EXISTS visits (
    record_id INTEGER PRIMARY KEY,
    location_id TEXT,
    source_id TEXT,
    time_of_record TEXT,
    visit_count INTEGER,
    time_in_queue INTEGER,
    assigned_employee_id INTEGER
);

-- Sample data
INSERT INTO employee VALUES
(1, 'Amara Osei', '+234-555-0101', 'amara@water.gov', '123 Main St', 'Harare', 'Central', 'Field Surveyor'),
(2, 'Kofi Mensah', '+234-555-0102', 'kofi@water.gov', '456 Oak Ave', 'Bulawayo', 'Central', 'Field Surveyor');

INSERT INTO visits VALUES
(1, 'LOC001', 'SRC001', '2024-01-15', 1, 45, 1),
(2, 'LOC002', 'SRC002', '2024-01-16', 2, 120, 1),
(3, 'LOC003', 'SRC003', '2024-01-17', 1, 180, 2);
`;
