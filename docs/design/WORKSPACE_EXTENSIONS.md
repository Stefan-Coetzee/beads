# Workspace Extensions Design Document

> Design specification for extending LTT workspaces to support SQL, Python, and Cybersecurity learning environments.

---

## Table of Contents

1. [Overview](#1-overview)
2. [Interface Extensions](#2-interface-extensions)
3. [SQL Workspace (Current)](#3-sql-workspace-current)
4. [Python Workspace](#4-python-workspace)
5. [Cybersecurity Workspace](#5-cybersecurity-workspace)
6. [Project Specifications](#6-project-specifications)
7. [Infrastructure Design](#7-infrastructure-design)
8. [Implementation Roadmap](#8-implementation-roadmap)

---

## 1. Overview

### Three Workspace Patterns

| Workspace | Execution | Environment | LLM Context |
|-----------|-----------|-------------|-------------|
| **SQL** | Client-side (sql.js WASM) | Browser only | Editor + Query Results |
| **Python** | Client-side (Pyodide WASM) | Browser only | Script + Console Output + Variables |
| **Cybersecurity** | Server-side (SSH/Terminal) | Isolated Linux VMs | Terminal I/O + Session History |

### Core Principle: Minimal Complexity

- **SQL**: Already client-side, no changes needed
- **Python**: Use Pyodide (Python in WASM) - no backend needed
- **Cybersecurity**: Lightweight isolation (Firecracker microVMs or AWS Cloud9)

---

## 2. Interface Extensions

### 2.1 Workspace Type Enum

```typescript
// apps/web/src/types/workspace.ts

export type WorkspaceType = "sql" | "python" | "cybersecurity";

export interface WorkspaceConfig {
  type: WorkspaceType;
  language: string;           // CodeMirror language
  resultType: ResultType;     // How to display output
  engineInit: () => Promise<void>;
  execute: (code: string) => Promise<ExecutionResult>;
}
```

### 2.2 Extended Execution Result

```typescript
// apps/web/src/types/index.ts

export type ResultType = "table" | "console" | "terminal";

export interface ExecutionResult {
  success: boolean;
  type: ResultType;
  duration: number;
  error?: string;
}

// SQL-specific
export interface SqlResult extends ExecutionResult {
  type: "table";
  columns: string[];
  rows: unknown[][];
  rowCount: number;
}

// Python-specific
export interface PythonResult extends ExecutionResult {
  type: "console";
  stdout: string;
  stderr: string;
  returnValue?: unknown;
  variables?: Record<string, string>;  // JSON-serialized
}

// Cybersecurity-specific
export interface TerminalResult extends ExecutionResult {
  type: "terminal";
  output: string;           // Full terminal output
  exitCode: number;
  sessionId: string;        // For session continuity
}
```

### 2.3 Extended Chat Context

```typescript
// apps/web/src/types/index.ts

export interface WorkspaceContext {
  workspaceType: WorkspaceType;
  editorContent: string;
}

export interface SqlContext extends WorkspaceContext {
  workspaceType: "sql";
  queryResults?: SqlResult;
}

export interface PythonContext extends WorkspaceContext {
  workspaceType: "python";
  consoleOutput: string;
  variables?: Record<string, string>;
  lastError?: string;
}

export interface CyberContext extends WorkspaceContext {
  workspaceType: "cybersecurity";
  terminalHistory: string;      // Last N lines
  currentDirectory: string;
  sessionActive: boolean;
  targetHost?: string;
}
```

### 2.4 Backend Submission Types Extension

```python
# services/ltt-core/src/ltt/models/submission.py

class SubmissionType(str, Enum):
    # Existing
    CODE = "code"
    SQL = "sql"
    TEXT = "text"
    JUPYTER_CELL = "jupyter_cell"
    RESULT_SET = "result_set"

    # New
    PYTHON_SCRIPT = "python_script"
    PYTHON_OUTPUT = "python_output"
    TERMINAL_SESSION = "terminal_session"
    TERMINAL_COMMAND = "terminal_command"
    FLAG_CAPTURE = "flag_capture"        # CTF-style
    NETWORK_CAPTURE = "network_capture"  # PCAP file
```

### 2.5 Workspace-Aware Validator Interface

```python
# services/ltt-core/src/ltt/services/validators/base.py

from abc import ABC, abstractmethod
from typing import Optional
from ltt.models import SubmissionModel, ValidationModel

class BaseValidator(ABC):
    """Base validator interface for all workspace types."""

    @abstractmethod
    async def validate(
        self,
        submission: SubmissionModel,
        expected: Optional[dict] = None
    ) -> ValidationModel:
        """
        Validate a submission.

        Args:
            submission: The submission to validate
            expected: Optional expected output/criteria from task

        Returns:
            ValidationModel with passed status and feedback
        """
        pass

    @abstractmethod
    def get_supported_types(self) -> list[str]:
        """Return list of SubmissionType values this validator handles."""
        pass
```

---

## 3. SQL Workspace (Current)

### Already Implemented

- Client-side execution via sql.js (WASM)
- Table-based result display
- Schema loaded from `/data/md_water_services.sql`
- Chat context includes editor + query results

### No Changes Required

The SQL workspace serves as the template for other workspaces.

---

## 4. Python Workspace

### 4.1 Architecture

```
┌─────────────────────────────────────────────────────────┐
│                    Browser (Client)                     │
│  ┌─────────────────────────────────────────────────┐   │
│  │                 Pyodide WASM                     │   │
│  │  ┌───────────┐  ┌───────────┐  ┌────────────┐  │   │
│  │  │  Python   │  │  NumPy    │  │ Micropip   │  │   │
│  │  │  3.11     │  │  Pandas   │  │ (pkg mgr)  │  │   │
│  │  └───────────┘  └───────────┘  └────────────┘  │   │
│  └─────────────────────────────────────────────────┘   │
│                          ↑                              │
│                    Python Script                        │
│                          ↓                              │
│  ┌──────────────────────────────────────────────────┐  │
│  │  stdout/stderr capture  |  Variable inspection   │  │
│  └──────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────┘
```

### 4.2 Python Engine Implementation

```typescript
// apps/web/src/lib/python-engine.ts

import type { PyodideInterface } from "pyodide";

let pyodide: PyodideInterface | null = null;
let loadingPromise: Promise<void> | null = null;

export interface PythonExecutionResult {
  success: boolean;
  stdout: string;
  stderr: string;
  returnValue?: unknown;
  variables?: Record<string, string>;
  duration: number;
  error?: string;
}

/**
 * Initialize Pyodide (Python WASM runtime)
 */
export async function initPythonEngine(): Promise<void> {
  if (loadingPromise) return loadingPromise;

  loadingPromise = (async () => {
    const { loadPyodide } = await import("pyodide");
    pyodide = await loadPyodide({
      indexURL: "https://cdn.jsdelivr.net/pyodide/v0.25.0/full/"
    });

    // Pre-load common packages
    await pyodide.loadPackage(["numpy", "pandas"]);

    console.log("Python engine initialized");
  })();

  return loadingPromise;
}

/**
 * Execute Python code and capture output
 */
export async function executePython(code: string): Promise<PythonExecutionResult> {
  if (!pyodide) {
    return {
      success: false,
      stdout: "",
      stderr: "",
      duration: 0,
      error: "Python engine not initialized"
    };
  }

  const startTime = performance.now();

  // Redirect stdout/stderr
  pyodide.runPython(`
    import sys
    from io import StringIO
    _stdout = StringIO()
    _stderr = StringIO()
    sys.stdout = _stdout
    sys.stderr = _stderr
  `);

  try {
    const result = await pyodide.runPythonAsync(code);

    // Capture output
    const stdout = pyodide.runPython("_stdout.getvalue()");
    const stderr = pyodide.runPython("_stderr.getvalue()");

    // Get user-defined variables (excluding builtins)
    const variables = pyodide.runPython(`
      {k: repr(v)[:100] for k, v in globals().items()
       if not k.startswith('_') and k not in ['sys', 'StringIO']}
    `).toJs();

    return {
      success: true,
      stdout,
      stderr,
      returnValue: result,
      variables: Object.fromEntries(variables),
      duration: performance.now() - startTime
    };
  } catch (e) {
    const stderr = pyodide.runPython("_stderr.getvalue()");
    return {
      success: false,
      stdout: "",
      stderr: stderr || String(e),
      duration: performance.now() - startTime,
      error: String(e)
    };
  } finally {
    // Reset stdout/stderr
    pyodide.runPython(`
      sys.stdout = sys.__stdout__
      sys.stderr = sys.__stderr__
    `);
  }
}

/**
 * Install additional packages via micropip
 */
export async function installPackage(packageName: string): Promise<void> {
  if (!pyodide) throw new Error("Python engine not initialized");

  await pyodide.loadPackage("micropip");
  const micropip = pyodide.pyimport("micropip");
  await micropip.install(packageName);
}

export function isPythonReady(): boolean {
  return pyodide !== null;
}
```

### 4.3 Python Results Panel

```typescript
// apps/web/src/components/workspace/PythonResultsPanel.tsx

interface PythonResultsPanelProps {
  result: PythonExecutionResult | null;
  isExecuting: boolean;
}

export function PythonResultsPanel({ result, isExecuting }: PythonResultsPanelProps) {
  return (
    <div className="h-full flex flex-col bg-card rounded-lg border">
      {/* Console Output */}
      <div className="flex-1 overflow-auto p-4 font-mono text-sm">
        {isExecuting ? (
          <div className="animate-pulse">Running...</div>
        ) : result ? (
          <>
            {result.stdout && (
              <pre className="text-foreground whitespace-pre-wrap">{result.stdout}</pre>
            )}
            {result.stderr && (
              <pre className="text-red-400 whitespace-pre-wrap">{result.stderr}</pre>
            )}
            {result.error && (
              <pre className="text-red-500 whitespace-pre-wrap">{result.error}</pre>
            )}
          </>
        ) : (
          <div className="text-muted-foreground">
            Run your Python script to see output here
          </div>
        )}
      </div>

      {/* Variables Panel */}
      {result?.variables && Object.keys(result.variables).length > 0 && (
        <div className="border-t p-2">
          <div className="text-xs text-muted-foreground mb-1">Variables:</div>
          <div className="flex flex-wrap gap-2">
            {Object.entries(result.variables).map(([name, value]) => (
              <span key={name} className="text-xs bg-muted px-2 py-1 rounded">
                <span className="text-accent">{name}</span> = {value}
              </span>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
```

### 4.4 Python Validator

```python
# services/ltt-core/src/ltt/services/validators/python.py

import ast
import sys
from io import StringIO
from typing import Optional
from contextlib import redirect_stdout, redirect_stderr

from ltt.models import SubmissionModel, ValidationModel
from ltt.services.validators.base import BaseValidator


class PythonValidator(BaseValidator):
    """Validates Python code submissions."""

    def get_supported_types(self) -> list[str]:
        return ["python_script", "python_output"]

    async def validate(
        self,
        submission: SubmissionModel,
        expected: Optional[dict] = None
    ) -> ValidationModel:
        code = submission.content

        # Step 1: Syntax check
        try:
            ast.parse(code)
        except SyntaxError as e:
            return ValidationModel(
                submission_id=submission.id,
                passed=False,
                feedback=f"Syntax error on line {e.lineno}: {e.msg}"
            )

        # Step 2: Execute in sandbox (if expected output provided)
        if expected and "output_contains" in expected:
            stdout = StringIO()
            stderr = StringIO()

            try:
                # Restricted globals for safety
                restricted_globals = {
                    "__builtins__": {
                        "print": print,
                        "len": len,
                        "range": range,
                        "str": str,
                        "int": int,
                        "float": float,
                        "list": list,
                        "dict": dict,
                        "sum": sum,
                        "max": max,
                        "min": min,
                    }
                }

                with redirect_stdout(stdout), redirect_stderr(stderr):
                    exec(code, restricted_globals)

                output = stdout.getvalue()

                # Check if expected strings are in output
                for expected_str in expected["output_contains"]:
                    if expected_str not in output:
                        return ValidationModel(
                            submission_id=submission.id,
                            passed=False,
                            feedback=f"Expected output to contain: {expected_str}"
                        )

                return ValidationModel(
                    submission_id=submission.id,
                    passed=True,
                    feedback="All tests passed!"
                )

            except Exception as e:
                return ValidationModel(
                    submission_id=submission.id,
                    passed=False,
                    feedback=f"Runtime error: {str(e)}"
                )

        # Step 3: Basic validation (non-empty, valid syntax)
        return ValidationModel(
            submission_id=submission.id,
            passed=True,
            feedback="Code syntax is valid."
        )
```

---

## 5. Cybersecurity Workspace

### 5.1 Architecture: Lightweight Isolation

**Goal**: Provide isolated Linux environments without Docker overhead.

```
┌─────────────────────────────────────────────────────────────────┐
│                        Frontend (Browser)                       │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │  xterm.js Terminal  ←──WebSocket──→  Backend Proxy      │   │
│  └─────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ↓ WebSocket
┌─────────────────────────────────────────────────────────────────┐
│                      API Server (FastAPI)                       │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │  Terminal Session Manager                                │   │
│  │  - Session pool management                               │   │
│  │  - Input/output buffering                                │   │
│  │  - History capture for LLM context                       │   │
│  └─────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ↓ SSH
┌─────────────────────────────────────────────────────────────────┐
│                    Isolation Layer (Choose One)                 │
│                                                                 │
│  Option A: AWS Cloud9 Environments (Recommended for AWS)        │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │  - Managed EC2 instances                                 │   │
│  │  - Auto-hibernate when inactive                          │   │
│  │  - Per-learner environments                              │   │
│  │  - Built-in terminal API                                 │   │
│  └─────────────────────────────────────────────────────────┘   │
│                                                                 │
│  Option B: Firecracker microVMs (Self-hosted, efficient)        │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │  - Sub-second boot times                                 │   │
│  │  - Minimal memory overhead (~5MB per VM)                 │   │
│  │  - Strong isolation (separate kernel)                    │   │
│  │  - Snapshot/restore for fast reset                       │   │
│  └─────────────────────────────────────────────────────────┘   │
│                                                                 │
│  Option C: systemd-nspawn containers (Simplest)                 │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │  - Lightweight Linux containers                          │   │
│  │  - No Docker daemon needed                               │   │
│  │  - Uses host kernel                                      │   │
│  │  - Easy filesystem isolation                             │   │
│  └─────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────┘
```

### 5.2 Terminal Engine (Frontend)

```typescript
// apps/web/src/lib/terminal-engine.ts

import { Terminal } from "xterm";
import { FitAddon } from "xterm-addon-fit";
import { WebLinksAddon } from "xterm-addon-web-links";

export interface TerminalSession {
  id: string;
  terminal: Terminal;
  socket: WebSocket;
  history: string[];
  connected: boolean;
}

let session: TerminalSession | null = null;

/**
 * Initialize terminal and connect to backend
 */
export async function initTerminal(
  container: HTMLElement,
  learnerId: string,
  projectId: string
): Promise<TerminalSession> {
  // Create xterm instance
  const terminal = new Terminal({
    cursorBlink: true,
    fontSize: 14,
    fontFamily: "JetBrains Mono, monospace",
    theme: {
      background: "#1a1a2e",
      foreground: "#eaeaea",
      cursor: "#f0f0f0"
    }
  });

  const fitAddon = new FitAddon();
  terminal.loadAddon(fitAddon);
  terminal.loadAddon(new WebLinksAddon());

  terminal.open(container);
  fitAddon.fit();

  // Connect to backend WebSocket
  const wsUrl = `${WS_BASE_URL}/api/v1/terminal/connect?learner_id=${learnerId}&project_id=${projectId}`;
  const socket = new WebSocket(wsUrl);

  const history: string[] = [];

  return new Promise((resolve, reject) => {
    socket.onopen = () => {
      console.log("Terminal connected");

      // Send terminal size
      socket.send(JSON.stringify({
        type: "resize",
        cols: terminal.cols,
        rows: terminal.rows
      }));

      session = {
        id: `term-${Date.now()}`,
        terminal,
        socket,
        history,
        connected: true
      };

      resolve(session);
    };

    socket.onmessage = (event) => {
      const data = JSON.parse(event.data);

      if (data.type === "output") {
        terminal.write(data.content);
        history.push(data.content);

        // Keep last 1000 lines for LLM context
        if (history.length > 1000) {
          history.shift();
        }
      }
    };

    socket.onerror = (error) => {
      console.error("Terminal error:", error);
      reject(error);
    };

    socket.onclose = () => {
      console.log("Terminal disconnected");
      if (session) session.connected = false;
    };

    // Send user input to backend
    terminal.onData((data) => {
      if (socket.readyState === WebSocket.OPEN) {
        socket.send(JSON.stringify({
          type: "input",
          content: data
        }));
      }
    });
  });
}

/**
 * Get terminal history for LLM context
 */
export function getTerminalHistory(): string {
  if (!session) return "";
  return session.history.join("");
}

/**
 * Execute command and wait for output
 */
export async function executeCommand(command: string): Promise<string> {
  if (!session || !session.connected) {
    throw new Error("Terminal not connected");
  }

  return new Promise((resolve) => {
    const outputBuffer: string[] = [];
    let timeout: NodeJS.Timeout;

    const handler = (event: MessageEvent) => {
      const data = JSON.parse(event.data);
      if (data.type === "output") {
        outputBuffer.push(data.content);

        // Reset timeout on each output
        clearTimeout(timeout);
        timeout = setTimeout(() => {
          session!.socket.removeEventListener("message", handler);
          resolve(outputBuffer.join(""));
        }, 500); // Wait 500ms after last output
      }
    };

    session.socket.addEventListener("message", handler);

    // Send command
    session.socket.send(JSON.stringify({
      type: "input",
      content: command + "\n"
    }));
  });
}

export function isTerminalReady(): boolean {
  return session !== null && session.connected;
}

export function disconnectTerminal(): void {
  if (session) {
    session.socket.close();
    session.terminal.dispose();
    session = null;
  }
}
```

### 5.3 Backend Terminal Manager

```python
# services/api-server/src/api/terminal_routes.py

import asyncio
import asyncssh
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Query
from typing import Dict
import json

router = APIRouter(prefix="/api/v1/terminal", tags=["terminal"])

# Session pool: learner_id -> SSH connection
sessions: Dict[str, asyncssh.SSHClientConnection] = {}

# Configuration
SANDBOX_HOST = "sandbox.internal"  # Internal hostname for sandbox VMs
SANDBOX_USER = "learner"
SANDBOX_KEY_PATH = "/etc/ltt/sandbox_key"


class TerminalSession:
    def __init__(self, learner_id: str, project_id: str):
        self.learner_id = learner_id
        self.project_id = project_id
        self.conn: asyncssh.SSHClientConnection = None
        self.process: asyncssh.SSHClientProcess = None
        self.history: list[str] = []

    async def connect(self):
        """Connect to sandbox VM via SSH."""
        # Get or create sandbox for this learner
        sandbox_host = await get_or_create_sandbox(self.learner_id, self.project_id)

        self.conn = await asyncssh.connect(
            sandbox_host,
            username=SANDBOX_USER,
            client_keys=[SANDBOX_KEY_PATH],
            known_hosts=None  # In production, use proper host key verification
        )

        # Start interactive shell
        self.process = await self.conn.create_process(
            term_type="xterm-256color",
            term_size=(80, 24)
        )

    async def send_input(self, data: str):
        """Send input to the terminal."""
        if self.process:
            self.process.stdin.write(data)

    async def read_output(self) -> str:
        """Read output from the terminal."""
        if self.process:
            try:
                output = await asyncio.wait_for(
                    self.process.stdout.read(4096),
                    timeout=0.1
                )
                self.history.append(output)
                return output
            except asyncio.TimeoutError:
                return ""
        return ""

    async def resize(self, cols: int, rows: int):
        """Resize terminal."""
        if self.process:
            self.process.change_terminal_size(cols, rows)

    async def close(self):
        """Close the session."""
        if self.process:
            self.process.close()
        if self.conn:
            self.conn.close()

    def get_history(self, lines: int = 100) -> str:
        """Get recent terminal history."""
        return "".join(self.history[-lines:])


@router.websocket("/connect")
async def terminal_websocket(
    websocket: WebSocket,
    learner_id: str = Query(...),
    project_id: str = Query(...)
):
    """WebSocket endpoint for terminal connection."""
    await websocket.accept()

    session = TerminalSession(learner_id, project_id)

    try:
        await session.connect()

        # Start output reader task
        async def read_output():
            while True:
                output = await session.read_output()
                if output:
                    await websocket.send_json({
                        "type": "output",
                        "content": output
                    })
                await asyncio.sleep(0.05)  # 50ms polling

        output_task = asyncio.create_task(read_output())

        # Handle input from client
        while True:
            data = await websocket.receive_json()

            if data["type"] == "input":
                await session.send_input(data["content"])
            elif data["type"] == "resize":
                await session.resize(data["cols"], data["rows"])

    except WebSocketDisconnect:
        pass
    finally:
        output_task.cancel()
        await session.close()


@router.get("/history")
async def get_terminal_history(
    learner_id: str = Query(...),
    project_id: str = Query(...),
    lines: int = Query(default=100, le=1000)
) -> dict:
    """Get terminal history for LLM context."""
    # In production, store history in Redis/database
    session = sessions.get(learner_id)
    if session:
        return {"history": session.get_history(lines)}
    return {"history": ""}


async def get_or_create_sandbox(learner_id: str, project_id: str) -> str:
    """Get or create a sandbox VM for the learner."""
    # This is where you integrate with your VM provisioning system
    # Options: AWS Cloud9, Firecracker, systemd-nspawn

    # For now, return a static sandbox host
    # In production, implement VM pool management
    return f"sandbox-{learner_id}.internal"
```

### 5.4 Cybersecurity Validator

```python
# services/ltt-core/src/ltt/services/validators/cybersecurity.py

import re
from typing import Optional
from ltt.models import SubmissionModel, ValidationModel
from ltt.services.validators.base import BaseValidator


class CybersecurityValidator(BaseValidator):
    """Validates cybersecurity submissions (CTF flags, commands, etc.)."""

    def get_supported_types(self) -> list[str]:
        return ["flag_capture", "terminal_command", "terminal_session"]

    async def validate(
        self,
        submission: SubmissionModel,
        expected: Optional[dict] = None
    ) -> ValidationModel:
        content = submission.content
        submission_type = submission.submission_type

        if submission_type == "flag_capture":
            return await self._validate_flag(content, expected)
        elif submission_type == "terminal_command":
            return await self._validate_command(content, expected)
        elif submission_type == "terminal_session":
            return await self._validate_session(content, expected)

        return ValidationModel(
            submission_id=submission.id,
            passed=False,
            feedback="Unknown submission type"
        )

    async def _validate_flag(
        self,
        flag: str,
        expected: Optional[dict]
    ) -> ValidationModel:
        """Validate CTF-style flag submission."""
        if not expected or "flag" not in expected:
            return ValidationModel(
                submission_id="",
                passed=False,
                feedback="No expected flag configured"
            )

        # Normalize flag format
        flag = flag.strip()
        expected_flag = expected["flag"]

        # Check flag format (e.g., FLAG{...} or flag{...})
        flag_pattern = r'^[Ff][Ll][Aa][Gg]\{[^}]+\}$'
        if not re.match(flag_pattern, flag):
            return ValidationModel(
                submission_id="",
                passed=False,
                feedback="Invalid flag format. Expected: FLAG{...}"
            )

        if flag.lower() == expected_flag.lower():
            return ValidationModel(
                submission_id="",
                passed=True,
                feedback="Correct! Flag captured successfully."
            )

        return ValidationModel(
            submission_id="",
            passed=False,
            feedback="Incorrect flag. Keep trying!"
        )

    async def _validate_command(
        self,
        command: str,
        expected: Optional[dict]
    ) -> ValidationModel:
        """Validate that correct command was executed."""
        if not expected:
            return ValidationModel(
                submission_id="",
                passed=True,
                feedback="Command recorded."
            )

        # Check if command matches expected pattern
        if "command_pattern" in expected:
            pattern = expected["command_pattern"]
            if re.search(pattern, command):
                return ValidationModel(
                    submission_id="",
                    passed=True,
                    feedback="Correct command!"
                )
            return ValidationModel(
                submission_id="",
                passed=False,
                feedback=f"Command doesn't match expected pattern."
            )

        return ValidationModel(
            submission_id="",
            passed=True,
            feedback="Command executed."
        )

    async def _validate_session(
        self,
        session_output: str,
        expected: Optional[dict]
    ) -> ValidationModel:
        """Validate terminal session contains expected output."""
        if not expected or "output_contains" not in expected:
            return ValidationModel(
                submission_id="",
                passed=True,
                feedback="Session recorded."
            )

        for expected_str in expected["output_contains"]:
            if expected_str not in session_output:
                return ValidationModel(
                    submission_id="",
                    passed=False,
                    feedback=f"Session output missing expected content."
                )

        return ValidationModel(
            submission_id="",
            passed=True,
            feedback="Session completed successfully!"
        )
```

---

## 6. Project Specifications

### 6.1 SQL Project: Maji Ndogo (Existing)

Already implemented. See `content/projects/DA/MN_Part1/`.

### 6.2 Python Project: Programming Fundamentals

**Project File Location**: `content/projects/PYTHON/fundamentals/python_basics.json`

**Project Structure**:
```
python_basics.json
├── Epic 1: Getting Started
│   ├── Task 1.1: Hello World
│   │   ├── Subtask: Print your first message
│   │   └── Subtask: Print multiple lines
│   └── Task 1.2: Variables
│       ├── Subtask: Create string variables
│       ├── Subtask: Create numeric variables
│       └── Subtask: Variable naming rules
│
├── Epic 2: Data Types
│   ├── Task 2.1: Strings
│   ├── Task 2.2: Numbers
│   └── Task 2.3: Lists
│
├── Epic 3: Control Flow
│   ├── Task 3.1: If Statements
│   ├── Task 3.2: For Loops
│   └── Task 3.3: While Loops
│
└── Epic 4: Functions
    ├── Task 4.1: Defining Functions
    ├── Task 4.2: Parameters and Returns
    └── Task 4.3: Scope
```

**Example Subtask with Validation**:
```json
{
  "title": "Print Hello World",
  "description": "Write a Python script that prints 'Hello, World!' to the console.",
  "acceptance_criteria": "- Use the print() function\n- Output exactly: Hello, World!",
  "tutor_guidance": {
    "teaching_approach": "Start with the simplest possible program",
    "hints_to_give": [
      "In Python, we use print() to display text",
      "Text needs to be wrapped in quotes"
    ],
    "common_mistakes": [
      "Forgetting quotes around the text",
      "Using Print() instead of print() (case matters)"
    ]
  },
  "validation": {
    "type": "python_output",
    "expected": {
      "output_contains": ["Hello, World!"]
    }
  }
}
```

### 6.3 Cybersecurity Project: Linux Security Basics

**Project File Location**: `content/projects/CYBER/linux_security/linux_basics.json`

**Project Structure**:
```
linux_basics.json
├── Epic 1: Linux Navigation
│   ├── Task 1.1: File System
│   │   ├── Subtask: List directory contents (ls)
│   │   ├── Subtask: Change directories (cd)
│   │   └── Subtask: Find your location (pwd)
│   └── Task 1.2: File Operations
│       ├── Subtask: Create files (touch)
│       ├── Subtask: View file contents (cat)
│       └── Subtask: Copy and move files
│
├── Epic 2: User Management
│   ├── Task 2.1: User Information
│   ├── Task 2.2: File Permissions
│   └── Task 2.3: Sudo and Root
│
├── Epic 3: Network Basics
│   ├── Task 3.1: Network Configuration
│   ├── Task 3.2: Connectivity Testing
│   └── Task 3.3: Port Scanning Basics
│
└── Epic 4: Capture The Flag
    ├── Task 4.1: Find the Hidden Flag
    ├── Task 4.2: Decode the Message
    └── Task 4.3: Network Reconnaissance
```

**Example CTF Subtask**:
```json
{
  "title": "Find the Hidden Flag",
  "description": "A flag has been hidden somewhere in the /home/learner directory. Use your Linux skills to find it.",
  "acceptance_criteria": "- Find the flag file\n- Submit the flag in format FLAG{...}",
  "tutor_guidance": {
    "teaching_approach": "Guide discovery, don't reveal location",
    "hints_to_give": [
      "Try using 'find' or 'grep' to search",
      "Hidden files start with a dot (.)",
      "The 'cat' command shows file contents"
    ],
    "common_mistakes": [
      "Not checking hidden files",
      "Searching in wrong directory"
    ]
  },
  "validation": {
    "type": "flag_capture",
    "expected": {
      "flag": "FLAG{l1nux_b4s1cs_m4st3r3d}"
    }
  }
}
```

---

## 7. Infrastructure Design

### 7.1 Recommended: AWS-Native Stack

```
┌─────────────────────────────────────────────────────────────────┐
│                         AWS Architecture                        │
│                                                                 │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │                    Frontend (Static)                     │   │
│  │              CloudFront + S3 (Next.js Export)           │   │
│  └─────────────────────────────────────────────────────────┘   │
│                              │                                  │
│                              ↓                                  │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │                    API Gateway + Lambda                  │   │
│  │                 (or ECS Fargate for FastAPI)            │   │
│  └─────────────────────────────────────────────────────────┘   │
│              │                              │                   │
│              ↓                              ↓                   │
│  ┌──────────────────────┐    ┌──────────────────────────────┐  │
│  │   RDS PostgreSQL     │    │      Sandbox Pool            │  │
│  │   (Learner Progress) │    │                              │  │
│  └──────────────────────┘    │  Option A: Cloud9 (Managed)  │  │
│                              │  ┌────────────────────────┐  │  │
│                              │  │ Auto-hibernate EC2     │  │  │
│                              │  │ Per-learner envs       │  │  │
│                              │  │ Built-in terminal API  │  │  │
│                              │  └────────────────────────┘  │  │
│                              │                              │  │
│                              │  Option B: EC2 + Firecracker │  │
│                              │  ┌────────────────────────┐  │  │
│                              │  │ Spot instances (cheap) │  │  │
│                              │  │ MicroVM per learner    │  │  │
│                              │  │ Snapshot restore       │  │  │
│                              │  └────────────────────────┘  │  │
│                              └──────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────┘
```

### 7.2 Sandbox Pool Management

```python
# infrastructure/sandbox/pool_manager.py

import boto3
from typing import Optional
from dataclasses import dataclass
from datetime import datetime, timedelta

@dataclass
class SandboxInstance:
    instance_id: str
    learner_id: Optional[str]
    project_id: Optional[str]
    status: str  # "available", "in_use", "hibernating"
    last_used: datetime
    public_ip: Optional[str]

class SandboxPoolManager:
    """Manages pool of sandbox instances for cybersecurity workspace."""

    def __init__(
        self,
        min_available: int = 5,
        max_instances: int = 50,
        hibernate_after_minutes: int = 30
    ):
        self.ec2 = boto3.client("ec2")
        self.min_available = min_available
        self.max_instances = max_instances
        self.hibernate_after = timedelta(minutes=hibernate_after_minutes)

        # In production, use Redis/DynamoDB for state
        self.instances: dict[str, SandboxInstance] = {}

    async def get_sandbox(self, learner_id: str, project_id: str) -> SandboxInstance:
        """Get or create sandbox for learner."""

        # Check if learner already has a sandbox
        for instance in self.instances.values():
            if instance.learner_id == learner_id:
                if instance.status == "hibernating":
                    await self._wake_instance(instance)
                instance.last_used = datetime.utcnow()
                return instance

        # Find available sandbox
        for instance in self.instances.values():
            if instance.status == "available":
                instance.learner_id = learner_id
                instance.project_id = project_id
                instance.status = "in_use"
                instance.last_used = datetime.utcnow()
                await self._configure_sandbox(instance, project_id)
                return instance

        # Create new sandbox if under limit
        if len(self.instances) < self.max_instances:
            return await self._create_sandbox(learner_id, project_id)

        raise Exception("No sandboxes available")

    async def release_sandbox(self, learner_id: str):
        """Release sandbox back to pool."""
        for instance in self.instances.values():
            if instance.learner_id == learner_id:
                instance.learner_id = None
                instance.project_id = None
                instance.status = "available"
                await self._reset_sandbox(instance)
                break

    async def hibernate_idle(self):
        """Hibernate sandboxes that haven't been used recently."""
        now = datetime.utcnow()
        for instance in self.instances.values():
            if instance.status == "in_use":
                if now - instance.last_used > self.hibernate_after:
                    await self._hibernate_instance(instance)

    async def _create_sandbox(self, learner_id: str, project_id: str) -> SandboxInstance:
        """Launch new EC2 instance for sandbox."""
        response = self.ec2.run_instances(
            ImageId="ami-xxxxx",  # Pre-configured CTF AMI
            InstanceType="t3.micro",
            MinCount=1,
            MaxCount=1,
            KeyName="sandbox-key",
            SecurityGroupIds=["sg-xxxxx"],
            SubnetId="subnet-xxxxx",
            IamInstanceProfile={"Name": "sandbox-role"},
            TagSpecifications=[{
                "ResourceType": "instance",
                "Tags": [
                    {"Key": "Name", "Value": f"sandbox-{learner_id}"},
                    {"Key": "Purpose", "Value": "ltt-sandbox"}
                ]
            }]
        )

        instance_id = response["Instances"][0]["InstanceId"]

        # Wait for instance to be running
        waiter = self.ec2.get_waiter("instance_running")
        waiter.wait(InstanceIds=[instance_id])

        # Get public IP
        describe = self.ec2.describe_instances(InstanceIds=[instance_id])
        public_ip = describe["Reservations"][0]["Instances"][0].get("PublicIpAddress")

        instance = SandboxInstance(
            instance_id=instance_id,
            learner_id=learner_id,
            project_id=project_id,
            status="in_use",
            last_used=datetime.utcnow(),
            public_ip=public_ip
        )

        self.instances[instance_id] = instance
        await self._configure_sandbox(instance, project_id)

        return instance

    async def _configure_sandbox(self, instance: SandboxInstance, project_id: str):
        """Configure sandbox for specific project (e.g., plant flags)."""
        # Use SSM or SSH to configure the instance
        # This runs the project-specific setup script
        pass

    async def _reset_sandbox(self, instance: SandboxInstance):
        """Reset sandbox to clean state."""
        # Restore from snapshot or run cleanup script
        pass

    async def _hibernate_instance(self, instance: SandboxInstance):
        """Hibernate EC2 instance to save costs."""
        self.ec2.stop_instances(
            InstanceIds=[instance.instance_id],
            Hibernate=True
        )
        instance.status = "hibernating"

    async def _wake_instance(self, instance: SandboxInstance):
        """Wake hibernated instance."""
        self.ec2.start_instances(InstanceIds=[instance.instance_id])

        waiter = self.ec2.get_waiter("instance_running")
        waiter.wait(InstanceIds=[instance.instance_id])

        instance.status = "in_use"
```

### 7.3 Firecracker Setup (Alternative - More Efficient)

```yaml
# infrastructure/firecracker/sandbox-config.yaml

# Firecracker microVM configuration
microvm:
  vcpu_count: 1
  mem_size_mib: 512

  boot_source:
    kernel_image_path: "/var/lib/firecracker/vmlinux"
    boot_args: "console=ttyS0 reboot=k panic=1 pci=off"

  drives:
    - drive_id: "rootfs"
      path_on_host: "/var/lib/firecracker/rootfs/ubuntu-22.04.ext4"
      is_root_device: true
      is_read_only: false

  network_interfaces:
    - iface_id: "eth0"
      guest_mac: "AA:FC:00:00:00:01"
      host_dev_name: "tap0"

# Snapshot configuration for fast restore
snapshot:
  base_snapshot: "/var/lib/firecracker/snapshots/base-ctf.snap"
  restore_time_ms: 125  # Sub-second restore
```

### 7.4 Cost Optimization

| Component | Strategy | Estimated Cost |
|-----------|----------|----------------|
| **SQL Workspace** | Client-side only | $0 |
| **Python Workspace** | Client-side (Pyodide) | $0 |
| **Cyber Sandboxes** | Spot instances + hibernate | ~$0.005/hour per learner |
| **API Server** | Lambda or Fargate Spot | ~$20-50/month |
| **Database** | RDS PostgreSQL t3.micro | ~$15/month |
| **Total (100 concurrent learners)** | | ~$50-100/month |

---

## 8. Implementation Roadmap

### Phase 1: Python Workspace (1-2 weeks)

1. **Create python-engine.ts** - Pyodide integration
2. **Create PythonResultsPanel** - Console output + variables
3. **Create Python workspace page** - Fork SQL workspace
4. **Add PythonValidator** - Backend validation
5. **Create Python basics project** - JSON content
6. **Test end-to-end**

### Phase 2: Cybersecurity Infrastructure (2-3 weeks)

1. **Create Terraform/CDK templates** - AWS infrastructure
2. **Build sandbox AMI** - Pre-configured CTF image
3. **Implement SandboxPoolManager** - Instance management
4. **Create terminal-engine.ts** - xterm.js + WebSocket
5. **Add terminal routes** - WebSocket proxy
6. **Test SSH connectivity**

### Phase 3: Cybersecurity Workspace (1-2 weeks)

1. **Create TerminalPanel** - xterm.js component
2. **Create Cyber workspace page** - Three-panel layout
3. **Add CybersecurityValidator** - Flag/command validation
4. **Create Linux basics project** - JSON content
5. **Test CTF flow**

### Phase 4: Polish & Integration (1 week)

1. **Unified workspace selector** - Choose workspace type
2. **Project type detection** - Auto-select workspace
3. **Chat context updates** - Per-workspace context
4. **Documentation** - User guides

---

## Appendix A: File Structure

```
beadslocal/
├── apps/web/
│   └── src/
│       ├── lib/
│       │   ├── sql-engine.ts        # Existing
│       │   ├── python-engine.ts     # New
│       │   └── terminal-engine.ts   # New
│       ├── components/
│       │   └── workspace/
│       │       ├── SqlEditor.tsx           # Existing
│       │       ├── ResultsPanel.tsx        # Existing
│       │       ├── PythonResultsPanel.tsx  # New
│       │       └── TerminalPanel.tsx       # New
│       └── app/
│           └── workspace/
│               ├── [projectId]/page.tsx    # SQL (existing)
│               ├── python/[projectId]/     # New
│               └── cyber/[projectId]/      # New
│
├── services/
│   ├── api-server/src/api/
│   │   ├── terminal_routes.py              # New
│   │   └── ...
│   └── ltt-core/src/ltt/services/validators/
│       ├── base.py                         # New
│       ├── simple.py                       # Existing
│       ├── python.py                       # New
│       └── cybersecurity.py                # New
│
├── content/projects/
│   ├── DA/MN_Part1/                        # Existing SQL
│   ├── PYTHON/fundamentals/                # New
│   └── CYBER/linux_security/               # New
│
└── infrastructure/
    ├── terraform/
    │   └── cyber-sandbox/                  # New
    └── sandbox/
        └── pool_manager.py                 # New
```

---

## Appendix B: Dependencies to Add

### Frontend (package.json)

```json
{
  "dependencies": {
    "pyodide": "^0.25.0",
    "xterm": "^5.3.0",
    "xterm-addon-fit": "^0.8.0",
    "xterm-addon-web-links": "^0.9.0"
  }
}
```

### Backend (pyproject.toml)

```toml
[project.dependencies]
asyncssh = "^2.14.0"
```

---

*Document Version: 1.0*
*Last Updated: 2026-02-04*
