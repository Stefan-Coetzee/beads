/**
 * Pyodide Web Worker — follows https://pyodide.org/en/stable/usage/webworker.html
 *
 * Eagerly loads Pyodide on creation. Main thread sends { id, python } messages,
 * worker replies with { id, stdout, stderr, duration } or { id, error, duration }.
 *
 * worker.terminate() from the main thread kills infinite loops for real.
 */
import { loadPyodide } from "https://cdn.jsdelivr.net/pyodide/v0.27.0/full/pyodide.mjs";

const pyodideReady = loadPyodide();

// Signal the main thread as soon as Pyodide is loaded
pyodideReady.then(
  () => self.postMessage({ ready: true }),
  (err) => self.postMessage({ ready: false, error: String(err) }),
);

self.onmessage = async ({ data: { id, python } }) => {
  const pyodide = await pyodideReady;
  const start = performance.now();

  try {
    await pyodide.loadPackagesFromImports(python);

    // Wrap user code to capture stdout/stderr via StringIO
    const wrapped =
      "import sys as _sys\n" +
      "from io import StringIO as _StringIO\n" +
      "_out, _err = _StringIO(), _StringIO()\n" +
      "_sys.stdout, _sys.stderr = _out, _err\n" +
      "try:\n" +
      "    exec(" + JSON.stringify(python) + ", globals())\n" +
      "finally:\n" +
      "    _sys.stdout, _sys.stderr = _sys.__stdout__, _sys.__stderr__\n" +
      "(_out.getvalue(), _err.getvalue())";

    const proxy = await pyodide.runPythonAsync(wrapped);
    const stdout = proxy.get(0);
    const stderr = proxy.get(1);
    proxy.destroy();

    self.postMessage({ id, stdout, stderr, duration: performance.now() - start });
  } catch (error) {
    self.postMessage({ id, error: error.message, duration: performance.now() - start });
  }
};
