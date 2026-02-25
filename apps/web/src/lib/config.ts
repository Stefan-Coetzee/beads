/**
 * Centralized frontend configuration.
 *
 * This is the single place where environment variables are read in the
 * frontend.  All other modules must import from here — no direct
 * `process.env` access elsewhere.
 *
 * Next.js variable rules (enforced here, not scattered):
 *   NEXT_PUBLIC_*  — baked into the JS bundle at build time; safe for browser
 *   Everything else — server-only; never reaches the client
 */

/** True in production Next.js builds (`NODE_ENV === "production"`). */
export const IS_PRODUCTION = process.env.NODE_ENV === "production";

/**
 * Base URL for browser-side API calls.
 *
 * Intentionally empty in all deployed environments — the browser always uses
 * relative URLs (/api/..., /lti/...) which are either proxied by the Next.js
 * server (local dev via LTT_API_URL rewrite) or routed directly by the ALB
 * (staging/prod).  Chrome's Private Network Access policy blocks loopback
 * fetches from public HTTPS origins, so the proxy must stay server-side.
 *
 * Only override NEXT_PUBLIC_API_URL if you need a completely different origin
 * (not localhost — that will be blocked by the browser).
 */
export const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL ?? "";
