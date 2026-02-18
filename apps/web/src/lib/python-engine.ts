"use client";

/**
 * Python engine — thin wrapper around a Web Worker running Pyodide.
 *
 * Pattern follows https://pyodide.org/en/stable/usage/webworker.html
 *
 * - Worker eagerly loads Pyodide on creation (no separate init step)
 * - `loadPackagesFromImports` auto-detects imports (no manual regex)
 * - worker.terminate() actually kills infinite loops
 * - Pyodide errors stay inside the worker — never bubble to the page
 */

export const EXECUTION_TIMEOUT_MS = 10_000;

export interface PythonResult {
  success: boolean;
  output?: string;
  error?: string;
  errorMessage?: string;
  traceback?: string;
  duration: number;
  timedOut?: boolean;
}

// ---------------------------------------------------------------------------
// State
// ---------------------------------------------------------------------------

let worker: Worker | null = null;
let isReady = false;
let readyPromise: Promise<void> | null = null;

type ReadyCallback = (ready: boolean) => void;
let readyCallback: ReadyCallback | null = null;

/** Register a callback that fires when the engine's ready state changes. */
export function onReadyStateChange(cb: ReadyCallback | null): void {
  readyCallback = cb;
}

function setReady(ready: boolean) {
  isReady = ready;
  readyCallback?.(ready);
}

// ---------------------------------------------------------------------------
// Request / response helper  (from Pyodide docs workerApi pattern)
// ---------------------------------------------------------------------------

let lastId = 0;

function request(
  w: Worker,
  msg: Record<string, unknown>,
): Promise<Record<string, unknown>> {
  return new Promise((resolve) => {
    const id = ++lastId;
    function listener(event: MessageEvent) {
      if (event.data?.id !== id) return;
      w.removeEventListener("message", listener);
      resolve(event.data as Record<string, unknown>);
    }
    w.addEventListener("message", listener);
    w.postMessage({ id, ...msg });
  });
}

// ---------------------------------------------------------------------------
// Error parsing
// ---------------------------------------------------------------------------

function parseError(text: string): { message: string; traceback: string } {
  const lines = text.trim().split("\n");
  let idx = lines.length - 1;
  for (let i = lines.length - 1; i >= 0; i--) {
    if (
      /^[A-Z][a-zA-Z]*(?:Error|Exception):|^SyntaxError:|^IndentationError:|^TabError:/.test(
        lines[i].trim(),
      )
    ) {
      idx = i;
      break;
    }
  }
  return {
    message: lines[idx] || text,
    traceback: lines.slice(0, idx).join("\n").trim(),
  };
}

// ---------------------------------------------------------------------------
// Worker lifecycle
// ---------------------------------------------------------------------------

function createWorker(): Worker {
  const w = new Worker("/python-worker.mjs", { type: "module" });

  // Prevent worker-level errors from reaching the page / Next.js overlay
  w.onerror = (e) => {
    e.preventDefault();
    console.warn("[Python] Worker error (caught):", e.message);
  };

  return w;
}

// ---------------------------------------------------------------------------
// Public API
// ---------------------------------------------------------------------------

/**
 * Boot the Web Worker and wait for Pyodide to load (~15 MB WASM).
 */
export function initPythonEngine(): Promise<void> {
  if (isReady) return Promise.resolve();
  if (readyPromise) return readyPromise;

  readyPromise = new Promise<void>((resolve, reject) => {
    worker = createWorker();

    function onMessage(e: MessageEvent) {
      if (!e.data?.ready && e.data?.ready !== false) return;
      worker!.removeEventListener("message", onMessage);

      if (e.data.ready) {
        setReady(true);
        readyPromise = null;
        resolve();
      } else {
        readyPromise = null;
        reject(new Error(e.data.error ?? "Pyodide failed to load"));
      }
    }

    worker.addEventListener("message", onMessage);
  });

  return readyPromise;
}

/**
 * Execute Python code. Returns a PythonResult (never throws).
 *
 * If execution exceeds EXECUTION_TIMEOUT_MS the worker is terminated
 * (actually killing the code) and a new worker boots in the background.
 */
export async function executePython(code: string): Promise<PythonResult> {
  // If re-initialising after a timeout, wait for it
  if (readyPromise) {
    try {
      await readyPromise;
    } catch {
      return {
        success: false,
        error: "Python engine failed to initialise. Please refresh the page.",
        errorMessage: "Python engine failed to initialise",
        duration: 0,
      };
    }
  }

  if (!worker || !isReady) {
    return {
      success: false,
      error: "Python engine not initialised. Please wait for loading to complete.",
      errorMessage: "Python engine not initialised",
      duration: 0,
    };
  }

  // Race the worker response against a timeout
  const startTime = performance.now();
  const currentWorker = worker;

  const resultPromise = request(currentWorker, { python: code });
  const timeoutPromise = new Promise<"__TIMEOUT__">((resolve) =>
    setTimeout(() => resolve("__TIMEOUT__"), EXECUTION_TIMEOUT_MS),
  );

  const outcome = await Promise.race([resultPromise, timeoutPromise]);

  if (outcome === "__TIMEOUT__") {
    // Kill the worker — this actually stops the infinite loop
    console.warn(
      `[Python] Execution timed out after ${EXECUTION_TIMEOUT_MS / 1000}s — terminating worker`,
    );
    currentWorker.terminate();
    worker = null;
    setReady(false);

    // Re-boot in the background
    initPythonEngine().catch((e) =>
      console.error("[Python] Failed to re-initialise after timeout:", e),
    );

    return {
      success: false,
      error: `Execution timed out after ${EXECUTION_TIMEOUT_MS / 1000} seconds. Check your code for infinite loops. The Python engine is restarting…`,
      errorMessage: `Timed out after ${EXECUTION_TIMEOUT_MS / 1000}s — possible infinite loop`,
      duration: performance.now() - startTime,
      timedOut: true,
    };
  }

  // Normal result from worker
  const data = outcome as Record<string, unknown>;
  const duration = (data.duration as number) ?? performance.now() - startTime;

  // Worker sent { error } — Python exception during execution
  if (data.error) {
    const { message, traceback } = parseError(data.error as string);
    return {
      success: false,
      error: data.error as string,
      errorMessage: message,
      traceback: traceback || undefined,
      duration,
    };
  }

  const stdout = (data.stdout as string) || "";
  const stderr = (data.stderr as string) || "";

  if (stderr.trim()) {
    const { message, traceback } = parseError(stderr);
    return {
      success: false,
      output: stdout || undefined,
      error: stderr,
      errorMessage: message,
      traceback: traceback || undefined,
      duration,
    };
  }

  return {
    success: true,
    output: stdout || "(No output)",
    duration,
  };
}

export function isPythonReady(): boolean {
  return isReady && worker !== null;
}

export async function resetPythonEnvironment(): Promise<void> {
  if (!worker || !isReady) return;

  await request(worker, {
    python: `
import sys
for _n in list(globals().keys()):
    if not _n.startswith('_') and _n not in ('sys',):
        try: del globals()[_n]
        except: pass
`,
  });
}

export async function installPackage(packageName: string): Promise<boolean> {
  const result = await executePython(
    `import micropip\nawait micropip.install('${packageName}')`,
  );
  return result.success;
}

export async function getDefinedVariables(): Promise<string[]> {
  const result = await executePython(
    `print('\\n'.join(n for n in dir() if not n.startswith('_')))`,
  );
  if (result.success && result.output) {
    return result.output.trim().split("\n").filter(Boolean);
  }
  return [];
}
