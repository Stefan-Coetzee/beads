"use client";

// Pyodide loaded via CDN script injection (bypasses Turbopack dynamic import issues)
// eslint-disable-next-line @typescript-eslint/no-explicit-any
let pyodide: any = null;
let loadingPromise: Promise<void> | null = null;

export interface PythonResult {
  success: boolean;
  output?: string;
  error?: string;
  errorMessage?: string;  // Short error message (e.g., "NameError: name 'x' is not defined")
  traceback?: string;     // Full traceback for expandable view
  duration: number;
}

// CDN URL for Pyodide
const PYODIDE_CDN = "https://cdn.jsdelivr.net/pyodide/v0.27.0/full/";

/**
 * Load Pyodide script from CDN
 */
function loadPyodideScript(): Promise<void> {
  return new Promise((resolve, reject) => {
    // Check if already loaded
    if ((window as any).loadPyodide) {
      resolve();
      return;
    }

    const script = document.createElement("script");
    script.src = `${PYODIDE_CDN}pyodide.js`;
    script.async = true;
    script.onload = () => resolve();
    script.onerror = () => reject(new Error("Failed to load Pyodide script"));
    document.head.appendChild(script);
  });
}

/**
 * Initialize Pyodide with WebAssembly
 */
export async function initPythonEngine(): Promise<void> {
  if (pyodide) return;

  // Prevent concurrent loading
  if (loadingPromise) {
    return loadingPromise;
  }

  loadingPromise = (async () => {
    try {
      console.log("[Python] Starting Pyodide initialization...");

      // Load Pyodide script from CDN
      await loadPyodideScript();
      console.log("[Python] Pyodide script loaded, initializing WASM (~15MB)...");

      // Load Pyodide using the global function
      const loadPyodide = (window as any).loadPyodide;
      if (!loadPyodide) {
        throw new Error("loadPyodide not found on window");
      }

      pyodide = await loadPyodide({
        indexURL: PYODIDE_CDN,
      });
      console.log("[Python] WASM loaded successfully");

      // Set up stdout/stderr capture
      console.log("[Python] Setting up output capture...");
      await pyodide.runPythonAsync(`
import sys
from io import StringIO

class OutputCapture:
    def __init__(self):
        self.stdout = StringIO()
        self.stderr = StringIO()
        self._old_stdout = None
        self._old_stderr = None

    def start(self):
        self._old_stdout = sys.stdout
        self._old_stderr = sys.stderr
        self.stdout = StringIO()
        self.stderr = StringIO()
        sys.stdout = self.stdout
        sys.stderr = self.stderr

    def stop(self):
        sys.stdout = self._old_stdout
        sys.stderr = self._old_stderr
        return self.stdout.getvalue(), self.stderr.getvalue()

_output_capture = OutputCapture()
`);

      console.log("[Python] Pyodide fully initialized and ready!");
    } catch (error) {
      console.error("[Python] Initialization failed:", error);
      throw error;
    } finally {
      loadingPromise = null;
    }
  })();

  return loadingPromise;
}

/**
 * Parse Python error to extract message and traceback
 */
function parseError(errorText: string): { message: string; traceback: string } {
  const lines = errorText.trim().split('\n');

  // Find the last line that looks like an error message (e.g., "NameError: ...")
  let messageIndex = lines.length - 1;
  for (let i = lines.length - 1; i >= 0; i--) {
    const line = lines[i].trim();
    // Python error messages typically have format "ErrorType: message"
    if (line.match(/^[A-Z][a-zA-Z]*Error:|^[A-Z][a-zA-Z]*Exception:|^[A-Z][a-zA-Z]*Warning:/)) {
      messageIndex = i;
      break;
    }
  }

  const message = lines[messageIndex] || errorText;
  const traceback = lines.slice(0, messageIndex).join('\n').trim();

  return { message, traceback };
}

/**
 * Execute Python code and return results
 */
export async function executePython(code: string): Promise<PythonResult> {
  if (!pyodide) {
    return {
      success: false,
      error: "Python engine not initialized. Please wait for loading to complete.",
      errorMessage: "Python engine not initialized",
      duration: 0,
    };
  }

  const startTime = performance.now();

  try {
    // Start output capture
    await pyodide.runPythonAsync("_output_capture.start()");

    // Execute the user's code
    await pyodide.runPythonAsync(code);

    // Stop capture and get output
    const [stdout, stderr] = await pyodide.runPythonAsync(
      "_output_capture.stop()"
    );
    const duration = performance.now() - startTime;

    const output = stdout as string;
    const errors = stderr as string;

    if (errors && errors.trim()) {
      const { message, traceback } = parseError(errors);
      return {
        success: false,
        output: output || undefined,
        error: errors,
        errorMessage: message,
        traceback: traceback || undefined,
        duration,
      };
    }

    return {
      success: true,
      output: output || "(No output)",
      duration,
    };
  } catch (error) {
    // Stop capture on error
    try {
      await pyodide.runPythonAsync("_output_capture.stop()");
    } catch {
      // Ignore cleanup errors
    }

    const errorText = error instanceof Error ? error.message : "Execution failed";
    const { message, traceback } = parseError(errorText);

    return {
      success: false,
      error: errorText,
      errorMessage: message,
      traceback: traceback || undefined,
      duration: performance.now() - startTime,
    };
  }
}

/**
 * Check if Python engine is initialized
 */
export function isPythonReady(): boolean {
  return pyodide !== null;
}

/**
 * Install a Python package using micropip
 */
export async function installPackage(packageName: string): Promise<boolean> {
  if (!pyodide) return false;

  try {
    await pyodide.loadPackage("micropip");
    const micropip = pyodide.pyimport("micropip");
    await micropip.install(packageName);
    return true;
  } catch (error) {
    console.error(`Failed to install ${packageName}:`, error);
    return false;
  }
}

/**
 * Reset the Python environment (clear variables)
 */
export async function resetPythonEnvironment(): Promise<void> {
  if (!pyodide) return;

  await pyodide.runPythonAsync(`
# Clear user-defined variables but keep system modules
import sys
_keep = set(sys.modules.keys())
_keep.add('_output_capture')
for name in list(globals().keys()):
    if not name.startswith('_') and name not in ['sys', 'OutputCapture']:
        del globals()[name]
`);
}

/**
 * Get list of defined variables in the Python namespace
 */
export async function getDefinedVariables(): Promise<string[]> {
  if (!pyodide) return [];

  const result = await pyodide.runPythonAsync(`
[name for name in dir() if not name.startswith('_')]
`);
  return result.toJs() as string[];
}
