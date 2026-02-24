/**
 * LTI 1.3 context management for iframe-embedded sessions.
 *
 * When the app is launched via LTI, the platform redirects to
 * /workspace/:projectId?launch_id=...&learner_id=...&lti=1
 *
 * This module detects, stores, and exposes that context so the rest
 * of the frontend can adapt (header injection, learner ID override,
 * iframe resize, etc.).
 */

const LTI_STORAGE_KEY = "ltt_lti_context";

export interface LTIContext {
  isLTI: boolean;
  launchId: string;
  learnerId: string;
  projectId: string;
  workspaceType: string;
  isInstructor: boolean;
  /** Origin of the embedding platform (for postMessage targeting). */
  platformOrigin?: string;
}

/**
 * Parse LTI context from URL search params (set by the /lti/launch redirect).
 * Returns null if this is not an LTI launch.
 */
export function parseLTIContext(
  searchParams: URLSearchParams
): LTIContext | null {
  if (searchParams.get("lti") !== "1") return null;

  const launchId = searchParams.get("launch_id");
  const learnerId = searchParams.get("learnerId");
  if (!launchId || !learnerId) return null;

  return {
    isLTI: true,
    launchId,
    learnerId,
    projectId: searchParams.get("project_id") || "",
    workspaceType: searchParams.get("type") || "sql",
    isInstructor: searchParams.get("instructor") === "1",
    platformOrigin: searchParams.get("platform_origin") || undefined,
  };
}

/**
 * Store LTI context in sessionStorage (survives page navigation but not
 * new tabs — which is the desired scope for an iframe session).
 */
export function storeLTIContext(ctx: LTIContext): void {
  if (typeof sessionStorage === "undefined") return;
  sessionStorage.setItem(LTI_STORAGE_KEY, JSON.stringify(ctx));
}

/**
 * Retrieve stored LTI context, or null if not in an LTI session.
 */
export function getLTIContext(): LTIContext | null {
  if (typeof sessionStorage === "undefined") return null;
  const raw = sessionStorage.getItem(LTI_STORAGE_KEY);
  if (!raw) return null;
  try {
    return JSON.parse(raw) as LTIContext;
  } catch {
    return null;
  }
}

/**
 * Check if the current page is rendered inside an iframe.
 */
export function isInIframe(): boolean {
  try {
    return window.self !== window.top;
  } catch {
    // Cross-origin iframe — can't access window.top
    return true;
  }
}

/**
 * Send a postMessage to the parent frame requesting an iframe resize.
 * Open edX listens for these when using the `resize` feature.
 */
export function requestIframeResize(height?: number): void {
  if (!isInIframe()) return;
  const h = height ?? document.documentElement.scrollHeight;
  const ctx = getLTIContext();
  // Use the stored platform origin when available; fall back to "*" for
  // dev environments where the origin may not be set.
  const targetOrigin = ctx?.platformOrigin || "*";
  window.parent.postMessage(
    { subject: "lti.frameResize", height: h },
    targetOrigin
  );
}

/**
 * Create a fake LTI session via the dev login endpoint.
 *
 * This exercises the same auth code path as a real LTI launch —
 * a Redis-backed session is created and the launch_id is stored
 * in sessionStorage just like a real launch redirect would.
 *
 * Only works when `auth_enabled=False` on the backend.
 */
export async function devLogin(
  learnerId?: string,
  projectId?: string
): Promise<LTIContext> {
  const res = await fetch("/lti/dev/login", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      learner_id: learnerId,
      project_id: projectId,
    }),
  });

  if (!res.ok) {
    throw new Error(`Dev login failed: ${res.status} ${await res.text()}`);
  }

  const data = await res.json();
  const ctx: LTIContext = {
    isLTI: true,
    launchId: data.launch_id,
    learnerId: data.learner_id,
    projectId: data.project_id || "",
    workspaceType: "sql",
    isInstructor: false,
  };
  storeLTIContext(ctx);
  return ctx;
}

/**
 * Clear the current dev session (frontend + backend).
 */
export async function devLogout(): Promise<void> {
  const ctx = getLTIContext();
  if (ctx?.launchId) {
    try {
      await fetch("/lti/dev/logout", {
        method: "POST",
        headers: { "X-LTI-Launch-Id": ctx.launchId },
      });
    } catch {
      // Best-effort
    }
  }
  if (typeof sessionStorage !== "undefined") {
    sessionStorage.removeItem(LTI_STORAGE_KEY);
  }
}
