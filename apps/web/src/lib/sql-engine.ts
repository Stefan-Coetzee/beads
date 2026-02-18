"use client";

// Dynamic import to avoid SSR issues with sql.js
import type { Database, SqlJsStatic } from "sql.js";

let SQL: SqlJsStatic | null = null;
let db: Database | null = null;
let loadingPromise: Promise<void> | null = null;

// IndexedDB cache config
const IDB_NAME = "ltt-sql-cache";
const IDB_STORE = "databases";
const IDB_VERSION = 1;

export const EXECUTION_TIMEOUT_MS = 10_000;

export interface QueryResult {
  success: boolean;
  columns?: string[];
  rows?: unknown[][];
  rowCount?: number;
  duration: number;
  error?: string;
  timedOut?: boolean;
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
 * Execute a SQL query and return results.
 *
 * Note: db.exec() is synchronous and blocks the main thread.
 * A Web Worker is needed to truly kill long-running queries.
 * For now we flag queries that exceeded the timeout threshold.
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

    // Flag if query took longer than timeout (can't kill sync, but warn)
    if (duration > EXECUTION_TIMEOUT_MS) {
      return {
        success: true,
        columns: results.length > 0 ? results[0].columns : [],
        rows: results.length > 0 ? results[0].values : [],
        rowCount: results.length > 0 ? results[0].values.length : 0,
        duration,
        timedOut: true,
      };
    }

    if (results.length === 0) {
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

// =============================================================================
// IndexedDB Cache
// =============================================================================

/**
 * Open the IndexedDB cache database.
 */
function openCacheDB(): Promise<IDBDatabase> {
  return new Promise((resolve, reject) => {
    const request = indexedDB.open(IDB_NAME, IDB_VERSION);
    request.onupgradeneeded = () => {
      request.result.createObjectStore(IDB_STORE);
    };
    request.onsuccess = () => resolve(request.result);
    request.onerror = () => reject(request.error);
  });
}

/**
 * Read a cached database binary from IndexedDB.
 * Returns null if not found or on error.
 */
async function readCache(key: string): Promise<Uint8Array | null> {
  try {
    const idb = await openCacheDB();
    return new Promise((resolve) => {
      const tx = idb.transaction(IDB_STORE, "readonly");
      const req = tx.objectStore(IDB_STORE).get(key);
      req.onsuccess = () => resolve(req.result ?? null);
      req.onerror = () => resolve(null);
    });
  } catch {
    return null;
  }
}

/**
 * Write a database binary to IndexedDB cache.
 */
async function writeCache(key: string, data: Uint8Array): Promise<void> {
  try {
    const idb = await openCacheDB();
    return new Promise((resolve, reject) => {
      const tx = idb.transaction(IDB_STORE, "readwrite");
      tx.objectStore(IDB_STORE).put(data, key);
      tx.oncomplete = () => resolve();
      tx.onerror = () => reject(tx.error);
    });
  } catch {
    // Cache write failures are non-fatal
  }
}

// =============================================================================
// Database Loading
// =============================================================================

export type LoadingPhase = "downloading" | "initializing" | "ready" | "error";

export interface LoadProgress {
  phase: LoadingPhase;
  /** 0-100 percentage for download phase */
  percent: number;
  /** Human-readable status message */
  message: string;
}

/**
 * Load the Maji Ndogo database from public data.
 *
 * On first load: downloads the SQL file, executes it, then caches the built
 * database binary in IndexedDB for instant restore on subsequent visits.
 *
 * @param force - If true, bypasses cache and re-downloads from source
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

      // Try restoring from IndexedDB cache (skip if force refresh)
      if (!force) {
        report("initializing", 10, "Checking cache...");
        const cached = await readCache("maji-ndogo");
        if (cached) {
          report("initializing", 50, "Restoring from cache...");
          db = new SQL.Database(cached);
          report("ready", 100, "Database ready (cached)");
          console.log("[SQL] Database restored from IndexedDB cache");
          return;
        }
      }

      // No cache - download and build from SQL file
      db = new SQL.Database();

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

      // Cache the built database binary in IndexedDB for next time
      report("initializing", 98, "Caching database...");
      const binary = db.export();
      await writeCache("maji-ndogo", binary);
      console.log(`[SQL] Database cached in IndexedDB (${(binary.length / 1024 / 1024).toFixed(1)} MB)`);

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
