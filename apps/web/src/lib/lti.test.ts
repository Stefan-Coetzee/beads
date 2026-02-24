/**
 * Tests for LTI context management — parse, store, retrieve, dev auth.
 */

import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import {
  parseLTIContext,
  storeLTIContext,
  getLTIContext,
  devLogin,
  devLogout,
  type LTIContext,
} from "./lti";

describe("parseLTIContext", () => {
  it("returns null when lti param is not '1'", () => {
    const params = new URLSearchParams("lti=0&launch_id=abc&learnerId=x");
    expect(parseLTIContext(params)).toBeNull();
  });

  it("returns null when lti=1 but launch_id is missing", () => {
    const params = new URLSearchParams("lti=1&learnerId=x");
    expect(parseLTIContext(params)).toBeNull();
  });

  it("returns null when lti=1 but learnerId is missing", () => {
    const params = new URLSearchParams("lti=1&launch_id=abc");
    expect(parseLTIContext(params)).toBeNull();
  });

  it("parses full LTI params correctly", () => {
    const params = new URLSearchParams(
      "lti=1&launch_id=abc&learnerId=learner-1&project_id=proj-1&type=python&instructor=1&platform_origin=https://example.com"
    );
    expect(parseLTIContext(params)).toEqual({
      isLTI: true,
      launchId: "abc",
      learnerId: "learner-1",
      projectId: "proj-1",
      workspaceType: "python",
      isInstructor: true,
      platformOrigin: "https://example.com",
    });
  });

  it("uses defaults for optional params", () => {
    const params = new URLSearchParams("lti=1&launch_id=abc&learnerId=learner-1");
    const ctx = parseLTIContext(params);
    expect(ctx?.projectId).toBe("");
    expect(ctx?.workspaceType).toBe("sql");
    expect(ctx?.isInstructor).toBe(false);
    expect(ctx?.platformOrigin).toBeUndefined();
  });
});

describe("storeLTIContext / getLTIContext", () => {
  beforeEach(() => {
    sessionStorage.clear();
  });

  it("stores and retrieves identical context", () => {
    const ctx: LTIContext = {
      isLTI: true,
      launchId: "abc",
      learnerId: "learner-1",
      projectId: "proj-1",
      workspaceType: "sql",
      isInstructor: false,
    };
    storeLTIContext(ctx);
    expect(getLTIContext()).toEqual(ctx);
  });

  it("returns null when nothing stored", () => {
    expect(getLTIContext()).toBeNull();
  });

  it("returns null when sessionStorage contains invalid JSON", () => {
    sessionStorage.setItem("ltt_lti_context", "not-valid-json{{{");
    expect(getLTIContext()).toBeNull();
  });
});

describe("devLogin", () => {
  const originalFetch = globalThis.fetch;

  beforeEach(() => {
    sessionStorage.clear();
  });

  afterEach(() => {
    globalThis.fetch = originalFetch;
    vi.restoreAllMocks();
  });

  it("POSTs to /lti/dev/login with correct body", async () => {
    globalThis.fetch = vi.fn().mockResolvedValue(
      new Response(JSON.stringify({
        launch_id: "dev-launch-1",
        learner_id: "learner-dev",
        project_id: "proj-1",
      }), { status: 200 })
    );

    await devLogin("learner-dev", "proj-1");

    const call = vi.mocked(globalThis.fetch).mock.calls[0];
    expect(call[0]).toBe("/lti/dev/login");
    const body = JSON.parse(call[1]?.body as string);
    expect(body.learner_id).toBe("learner-dev");
    expect(body.project_id).toBe("proj-1");
  });

  it("stores returned context in sessionStorage", async () => {
    globalThis.fetch = vi.fn().mockResolvedValue(
      new Response(JSON.stringify({
        launch_id: "dev-launch-1",
        learner_id: "learner-dev",
        project_id: "proj-1",
      }), { status: 200 })
    );

    await devLogin("learner-dev", "proj-1");

    const stored = getLTIContext();
    expect(stored).not.toBeNull();
    expect(stored?.launchId).toBe("dev-launch-1");
    expect(stored?.isLTI).toBe(true);
  });

  it("throws on non-ok response", async () => {
    globalThis.fetch = vi.fn().mockResolvedValue(
      new Response("Not found", { status: 404 })
    );

    await expect(devLogin()).rejects.toThrow("Dev login failed");
  });
});

describe("devLogout", () => {
  const originalFetch = globalThis.fetch;

  beforeEach(() => {
    sessionStorage.clear();
  });

  afterEach(() => {
    globalThis.fetch = originalFetch;
    vi.restoreAllMocks();
  });

  it("sends POST with X-LTI-Launch-Id header", async () => {
    // Store a context first
    storeLTIContext({
      isLTI: true,
      launchId: "launch-123",
      learnerId: "learner-1",
      projectId: "proj-1",
      workspaceType: "sql",
      isInstructor: false,
    });

    globalThis.fetch = vi.fn().mockResolvedValue(new Response("ok", { status: 200 }));

    await devLogout();

    const call = vi.mocked(globalThis.fetch).mock.calls[0];
    expect(call[0]).toBe("/lti/dev/logout");
    expect(call[1]?.method).toBe("POST");
    const headers = call[1]?.headers as Record<string, string>;
    expect(headers["X-LTI-Launch-Id"]).toBe("launch-123");
  });

  it("removes context from sessionStorage", async () => {
    storeLTIContext({
      isLTI: true,
      launchId: "launch-123",
      learnerId: "learner-1",
      projectId: "proj-1",
      workspaceType: "sql",
      isInstructor: false,
    });

    globalThis.fetch = vi.fn().mockResolvedValue(new Response("ok", { status: 200 }));
    await devLogout();

    expect(getLTIContext()).toBeNull();
  });

  it("handles fetch failure gracefully", async () => {
    storeLTIContext({
      isLTI: true,
      launchId: "launch-123",
      learnerId: "learner-1",
      projectId: "proj-1",
      workspaceType: "sql",
      isInstructor: false,
    });

    globalThis.fetch = vi.fn().mockRejectedValue(new Error("Network error"));

    // Should not throw
    await devLogout();

    // Should still clear sessionStorage
    expect(getLTIContext()).toBeNull();
  });
});
