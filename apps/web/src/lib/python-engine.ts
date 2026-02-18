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
    if (line.match(/^[A-Z][a-zA-Z]*Error:|^[A-Z][a-zA-Z]*Exception:|^SyntaxError:|^IndentationError:|^TabError:/)) {
      messageIndex = i;
      break;
    }
  }

  const message = lines[messageIndex] || errorText;
  const traceback = lines.slice(0, messageIndex).join('\n').trim();

  return { message, traceback };
}

// Packages that are pre-built for Pyodide (fast loading from CDN)
const PYODIDE_PACKAGES: Record<string, string> = {
  'numpy': 'numpy',
  'pandas': 'pandas',
  'matplotlib': 'matplotlib',
  'scipy': 'scipy',
  'scikit-learn': 'scikit-learn',
  'sklearn': 'scikit-learn',
  'sympy': 'sympy',
  'networkx': 'networkx',
  'pillow': 'pillow',
  'PIL': 'pillow',
};

// Standard library modules (no need to install)
const STDLIB_MODULES = new Set([
  'sys', 'os', 'math', 'json', 're', 'datetime', 'collections', 'itertools',
  'functools', 'random', 'string', 'io', 'typing', 'copy', 'time', 'calendar',
  'csv', 'hashlib', 'base64', 'urllib', 'html', 'xml', 'email', 'sqlite3',
  'pickle', 'struct', 'array', 'bisect', 'heapq', 'statistics', 'decimal',
  'fractions', 'numbers', 'cmath', 'operator', 'pathlib', 'tempfile', 'glob',
  'fnmatch', 'shutil', 'zipfile', 'tarfile', 'gzip', 'bz2', 'lzma', 'zlib',
  'pprint', 'textwrap', 'difflib', 'enum', 'dataclasses', 'abc', 'contextlib',
  'warnings', 'traceback', 'inspect', 'dis', 'ast', 'tokenize', 'token',
]);

// Track loaded packages
const loadedPackages = new Set<string>();
let micropipLoaded = false;

/**
 * Load micropip for installing packages from PyPI
 */
async function ensureMicropip(): Promise<boolean> {
  if (micropipLoaded) return true;
  try {
    await pyodide.loadPackage('micropip');
    micropipLoaded = true;
    return true;
  } catch (e) {
    console.error('[Python] Failed to load micropip:', e);
    return false;
  }
}

/**
 * Detect and load required packages from import statements
 */
async function loadRequiredPackages(code: string): Promise<string[]> {
  const loaded: string[] = [];

  // Match import statements: "import numpy", "from pandas import", etc.
  const importRegex = /(?:^|\n)\s*(?:import|from)\s+([a-zA-Z_][a-zA-Z0-9_]*)/g;
  let match;

  while ((match = importRegex.exec(code)) !== null) {
    const moduleName = match[1];

    // Skip stdlib modules
    if (STDLIB_MODULES.has(moduleName)) continue;

    // Skip already loaded
    if (loadedPackages.has(moduleName)) continue;

    const pyodidePackage = PYODIDE_PACKAGES[moduleName];

    if (pyodidePackage) {
      // Use pre-built Pyodide package (fast)
      console.log(`[Python] Loading Pyodide package: ${pyodidePackage}`);
      try {
        await pyodide.loadPackage(pyodidePackage);
        loadedPackages.add(moduleName);
        loaded.push(pyodidePackage);
      } catch (e) {
        console.warn(`[Python] Failed to load ${pyodidePackage}:`, e);
      }
    } else {
      // Try micropip for other packages (slower, from PyPI)
      console.log(`[Python] Trying micropip for: ${moduleName}`);
      try {
        if (await ensureMicropip()) {
          await pyodide.runPythonAsync(`
import micropip
await micropip.install('${moduleName}')
`);
          loadedPackages.add(moduleName);
          loaded.push(`${moduleName} (via pip)`);
        }
      } catch (e) {
        console.warn(`[Python] Failed to install ${moduleName} via micropip:`, e);
        // Don't throw - let the actual import fail with a clearer error
      }
    }
  }

  return loaded;
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
    // Auto-load any required packages
    const packagesLoaded = await loadRequiredPackages(code);
    if (packagesLoaded.length > 0) {
      console.log(`[Python] Loaded packages: ${packagesLoaded.join(', ')}`);
    }

    // Use pyodide's built-in stdout capture
    pyodide.setStdout({ batched: (text: string) => {} });
    pyodide.setStderr({ batched: (text: string) => {} });

    // Run the code and capture output using Python's approach
    const wrappedCode = `
import sys
from io import StringIO

_stdout_capture = StringIO()
_stderr_capture = StringIO()
_old_stdout = sys.stdout
_old_stderr = sys.stderr
sys.stdout = _stdout_capture
sys.stderr = _stderr_capture

try:
    exec(${JSON.stringify(code)}, globals())
finally:
    sys.stdout = _old_stdout
    sys.stderr = _old_stderr

(_stdout_capture.getvalue(), _stderr_capture.getvalue())
`;

    const result = await pyodide.runPythonAsync(wrappedCode);
    const duration = performance.now() - startTime;

    // Result is a tuple [stdout, stderr]
    const stdout = result.get(0) as string;
    const stderr = result.get(1) as string;
    result.destroy(); // Clean up the Python proxy

    if (stderr && stderr.trim()) {
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
  } catch (error: any) {
    const duration = performance.now() - startTime;

    // Pyodide wraps Python errors - extract the full error message
    let errorText = "Execution failed";

    if (error) {
      // Try to get the full Python traceback from the error
      if (error.message) {
        errorText = error.message;
      }
      // Some Pyodide versions have the error as a string representation
      if (typeof error === 'string') {
        errorText = error;
      }
      // Try toString which often has the full traceback
      if (error.toString && error.toString() !== '[object Object]') {
        const errStr = error.toString();
        if (errStr.length > errorText.length) {
          errorText = errStr;
        }
      }
    }

    console.error("[Python] Execution error:", errorText);
    const { message, traceback } = parseError(errorText);

    return {
      success: false,
      error: errorText,
      errorMessage: message,
      traceback: traceback || undefined,
      duration,
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
for name in list(globals().keys()):
    if not name.startswith('_') and name not in ['sys', '__builtins__', '__name__', '__doc__']:
        try:
            del globals()[name]
        except:
            pass
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
  const vars = result.toJs() as string[];
  result.destroy();
  return vars;
}
