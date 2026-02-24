/**
 * Tests for type converter functions that bridge frontend data shapes
 * to the API format the LLM receives. If these are wrong, the LLM gets garbage.
 */

import { describe, it, expect } from "vitest";
import {
  queryResultToExecutionResult,
  pythonResultToExecutionResult,
  type QueryResult,
  type PythonResult,
} from "./index";

describe("queryResultToExecutionResult", () => {
  it("returns undefined for null input", () => {
    expect(queryResultToExecutionResult(null)).toBeUndefined();
  });

  it("maps successful QueryResult with columns and rows", () => {
    const qr: QueryResult = {
      success: true,
      columns: ["id", "name"],
      rows: [[1, "Alice"], [2, "Bob"]],
      rowCount: 2,
      duration: 42,
    };
    const result = queryResultToExecutionResult(qr);
    expect(result).toEqual({
      success: true,
      columns: ["id", "name"],
      rows: [[1, "Alice"], [2, "Bob"]],
      row_count: 2, // camelCase → snake_case
      duration: 42,
      error: undefined,
    });
  });

  it("maps error QueryResult", () => {
    const qr: QueryResult = {
      success: false,
      error: "syntax error at or near \"SELEC\"",
      duration: 10,
    };
    const result = queryResultToExecutionResult(qr);
    expect(result).toEqual({
      success: false,
      error: "syntax error at or near \"SELEC\"",
      duration: 10,
      columns: undefined,
      rows: undefined,
      row_count: undefined,
    });
  });

  it("maps empty successful result", () => {
    const qr: QueryResult = {
      success: true,
      columns: [],
      rows: [],
      rowCount: 0,
      duration: 1,
    };
    const result = queryResultToExecutionResult(qr);
    expect(result?.success).toBe(true);
    expect(result?.columns).toEqual([]);
    expect(result?.rows).toEqual([]);
    expect(result?.row_count).toBe(0);
  });
});

describe("pythonResultToExecutionResult", () => {
  it("returns undefined for null input", () => {
    expect(pythonResultToExecutionResult(null)).toBeUndefined();
  });

  it("maps successful PythonResult with output", () => {
    const pr: PythonResult = {
      success: true,
      output: "Hello, World!",
      duration: 50,
    };
    const result = pythonResultToExecutionResult(pr);
    expect(result).toEqual({
      success: true,
      output: "Hello, World!",
      duration: 50,
      error: undefined,
      error_message: undefined, // camelCase → snake_case
      traceback: undefined,
    });
  });

  it("maps error PythonResult with traceback", () => {
    const pr: PythonResult = {
      success: false,
      error: "ZeroDivisionError: division by zero",
      errorMessage: "division by zero",
      traceback: "Traceback (most recent call last):\n  File \"<stdin>\", line 1\nZeroDivisionError",
      duration: 10,
    };
    const result = pythonResultToExecutionResult(pr);
    expect(result).toEqual({
      success: false,
      error: "ZeroDivisionError: division by zero",
      error_message: "division by zero", // errorMessage → error_message
      traceback: "Traceback (most recent call last):\n  File \"<stdin>\", line 1\nZeroDivisionError",
      duration: 10,
      output: undefined,
    });
  });

  it("maps PythonResult with only output, no error fields", () => {
    const pr: PythonResult = {
      success: true,
      output: "42",
      duration: 5,
    };
    const result = pythonResultToExecutionResult(pr);
    expect(result?.output).toBe("42");
    expect(result?.error).toBeUndefined();
    expect(result?.error_message).toBeUndefined();
    expect(result?.traceback).toBeUndefined();
  });
});
