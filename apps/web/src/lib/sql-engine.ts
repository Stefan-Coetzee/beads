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

export type LoadingPhase = "downloading" | "initializing" | "ready" | "error";

export interface LoadProgress {
  phase: LoadingPhase;
  /** 0-100 percentage for download phase */
  percent: number;
  /** Human-readable status message */
  message: string;
}

/**
 * Load the Maji Ndogo database from public data
 * @param force - If true, forces a reload even if database exists
 * @param onProgress - Callback for loading progress updates
 */
export async function loadMajiNdogoDatabase(
  force: boolean = false,
  onProgress?: (progress: LoadProgress) => void,
): Promise<void> {
  // Prevent concurrent loading - return existing promise if loading
  if (loadingPromise && !force) {
    return loadingPromise;
  }

  // Wait for any existing load to complete before forcing a new one
  if (loadingPromise && force) {
    await loadingPromise;
  }

  const report = (phase: LoadingPhase, percent: number, message: string) => {
    onProgress?.({ phase, percent, message });
  };

  loadingPromise = (async () => {
    try {
      report("downloading", 0, "Initializing SQL engine...");
      await initSqlEngine();
      if (!SQL) throw new Error("SQL.js not initialized");

      // Create fresh database
      db = new SQL.Database();

      // Fetch the SQL file with progress tracking
      report("downloading", 5, "Downloading database (~10 MB)...");
      const response = await fetch("/data/md_water_services.sql");
      if (!response.ok) {
        throw new Error("Failed to load database schema");
      }

      const contentLength = response.headers.get("content-length");
      const totalBytes = contentLength ? parseInt(contentLength, 10) : 0;

      let sqlContent: string;

      if (totalBytes && response.body) {
        // Stream with progress
        const reader = response.body.getReader();
        const chunks: Uint8Array[] = [];
        let receivedBytes = 0;

        while (true) {
          const { done, value } = await reader.read();
          if (done) break;

          chunks.push(value);
          receivedBytes += value.length;

          const percent = Math.round((receivedBytes / totalBytes) * 80) + 5; // 5-85%
          const mb = (receivedBytes / 1024 / 1024).toFixed(1);
          const totalMb = (totalBytes / 1024 / 1024).toFixed(1);
          report("downloading", percent, `Downloading database... ${mb} / ${totalMb} MB`);
        }

        // Decode all chunks
        const decoder = new TextDecoder();
        sqlContent = chunks.map(c => decoder.decode(c, { stream: true })).join("") + decoder.decode();
      } else {
        // Fallback: no content-length header
        sqlContent = await response.text();
      }

      report("initializing", 85, "Building database tables...");

      // Split into statements and execute
      const statements = sqlContent.split(/;\s*\n/);
      const totalStatements = statements.length;

      for (let i = 0; i < statements.length; i++) {
        const trimmed = statements[i].trim();
        if (trimmed) {
          try {
            const safeStmt = trimmed.replace(/^INSERT INTO/i, "INSERT OR IGNORE INTO");
            db.run(safeStmt);
          } catch (e) {
            console.error("Error executing SQL:", trimmed.slice(0, 100), e);
          }
        }

        // Update progress during statement execution (85-100%)
        if (i % 50 === 0) {
          const percent = 85 + Math.round((i / totalStatements) * 15);
          report("initializing", percent, "Loading data...");
        }
      }

      report("ready", 100, "Database ready");
      console.log("[SQL] Maji Ndogo database loaded successfully");
    } catch (e) {
      report("error", 0, e instanceof Error ? e.message : "Failed to load database");
      throw e;
    } finally {
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
