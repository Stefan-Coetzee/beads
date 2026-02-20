# Frontend iframe Adaptations

> Changes to the Next.js frontend for running inside an Open edX LTI iframe.

---

## What Changes

The frontend needs to:

1. Detect when running inside an LTI iframe
2. Read launch parameters from the URL
3. Use `launch_id` instead of cookie-based `learner_id` for API calls
4. Auto-resize the iframe to fit content
5. Handle cookie restrictions in cross-origin iframes
6. Hide redundant navigation when embedded

---

## LTI Detection

### `apps/web/src/lib/lti.ts`

```typescript
/**
 * LTI context management.
 *
 * Detects LTI launch context from URL params and provides
 * the launch_id for authenticated API calls.
 */

export interface LTIContext {
  isLTI: boolean;
  launchId: string | null;
  learnerId: string | null;
  projectId: string | null;
  workspaceType: string | null;
}

/**
 * Parse LTI context from URL search params.
 * These are set by the backend during /lti/launch redirect.
 */
export function parseLTIContext(searchParams: URLSearchParams): LTIContext {
  const lti = searchParams.get("lti") === "1";
  return {
    isLTI: lti,
    launchId: searchParams.get("launch_id"),
    learnerId: searchParams.get("learner_id"),
    projectId: searchParams.get("project_id"),
    workspaceType: searchParams.get("workspace_type"),
  };
}

/**
 * Check if the page is running inside an iframe.
 */
export function isInIframe(): boolean {
  try {
    return window.self !== window.top;
  } catch {
    // Cross-origin iframe throws SecurityError
    return true;
  }
}

/**
 * Store LTI context in sessionStorage (survives page refreshes within
 * the iframe, but not new launches).
 */
export function storeLTIContext(ctx: LTIContext): void {
  if (ctx.isLTI) {
    sessionStorage.setItem("lti_context", JSON.stringify(ctx));
  }
}

/**
 * Retrieve stored LTI context.
 */
export function getLTIContext(): LTIContext | null {
  const stored = sessionStorage.getItem("lti_context");
  if (!stored) return null;
  return JSON.parse(stored);
}
```

---

## API Client Changes

### `apps/web/src/lib/api.ts`

Add LTI header support to all API calls:

```typescript
// Before (current):
async getProjectTree(projectId: string, learnerId: string) {
  const res = await fetch(
    `${API_BASE_URL}/api/v1/project/${projectId}/tree?learner_id=${learnerId}`
  );
}

// After (with LTI support):
async getProjectTree(projectId: string, learnerId: string) {
  const headers: Record<string, string> = {};
  const ltiCtx = getLTIContext();

  if (ltiCtx?.isLTI && ltiCtx.launchId) {
    headers["X-LTI-Launch-Id"] = ltiCtx.launchId;
  }

  const res = await fetch(
    `${API_BASE_URL}/api/v1/project/${projectId}/tree?learner_id=${learnerId}`,
    { headers }
  );
}
```

**Pattern**: Create a helper that wraps `fetch` with LTI headers:

```typescript
/**
 * Fetch wrapper that adds LTI headers when in LTI mode.
 */
async function lttFetch(url: string, init?: RequestInit): Promise<Response> {
  const ltiCtx = getLTIContext();
  const headers = new Headers(init?.headers);

  if (ltiCtx?.isLTI && ltiCtx.launchId) {
    headers.set("X-LTI-Launch-Id", ltiCtx.launchId);
  }

  return fetch(url, { ...init, headers });
}
```

Replace all `fetch()` calls in [api.ts](../../apps/web/src/lib/api.ts) with `lttFetch()`.

---

## Learner ID Resolution

### `apps/web/src/lib/learner.ts`

Modify to prefer LTI-provided learner_id:

```typescript
// Before:
export function getOrCreateLearnerId(): string {
  const stored = getLearnerId(); // from cookie
  if (!stored) {
    const newId = generateLearnerId();
    setLearnerId(newId);
    return newId;
  }
  return stored;
}

// After:
export function getOrCreateLearnerId(): string {
  // LTI mode: use the learner_id from the launch
  const ltiCtx = getLTIContext();
  if (ltiCtx?.isLTI && ltiCtx.learnerId) {
    return ltiCtx.learnerId;
  }

  // Standalone mode: use cookie-based ID (existing behavior)
  const stored = getLearnerId();
  if (!stored) {
    const newId = generateLearnerId();
    setLearnerId(newId);
    return newId;
  }
  return stored;
}
```

---

## iframe Auto-Resize

The LTI iframe has a default height that may not fit the workspace. Use `postMessage` to tell Open edX to resize it.

### Option A: Manual postMessage

```typescript
/**
 * Request the parent LMS to resize the iframe.
 * Works with Open edX's xblock-lti-consumer which listens for
 * 'lti.frameResize' messages.
 */
export function requestIframeResize(height?: number): void {
  if (!isInIframe()) return;

  const targetHeight = height || document.body.scrollHeight;

  window.parent.postMessage(
    {
      subject: "lti.frameResize",
      height: targetHeight,
    },
    "*" // Open edX checks the origin on their side
  );
}
```

Call on mount and on content changes:

```typescript
// In the workspace layout component:
useEffect(() => {
  if (isInIframe()) {
    // Initial resize
    requestIframeResize(window.innerHeight);

    // Resize on content changes
    const observer = new ResizeObserver(() => {
      requestIframeResize(document.body.scrollHeight);
    });
    observer.observe(document.body);

    return () => observer.disconnect();
  }
}, []);
```

### Option B: lti-iframe-autoresizer (npm package)

```bash
cd apps/web && npm install lti-iframe-autoresizer
```

```typescript
// In your root layout or workspace page:
import { useEffect } from "react";

export function useIframeAutoResize() {
  useEffect(() => {
    if (isInIframe()) {
      import("lti-iframe-autoresizer").then(({ default: resizer }) => {
        resizer();
      });
    }
  }, []);
}
```

---

## UI Adaptations for iframe Context

When embedded in Open edX, some UI elements are redundant:

```typescript
// In your layout component:
function WorkspaceLayout() {
  const inIframe = isInIframe();
  const ltiCtx = getLTIContext();

  return (
    <div>
      {/* Hide top navigation bar when embedded */}
      {!inIframe && <TopNavBar />}

      {/* Hide project selector (Open edX determines the project) */}
      {!ltiCtx?.isLTI && <ProjectSelector />}

      {/* Always show the workspace */}
      <Workspace />
    </div>
  );
}
```

### What to Hide in LTI Mode

| Element | Reason |
|---|---|
| Top navigation bar | Open edX provides its own navigation |
| Project selector | Project is determined by the LTI link |
| Login/signup | Authentication handled by Open edX |
| Home/landing page | Learner goes directly to workspace |
| Footer | Avoid double footer with Open edX |

### What to Keep

| Element | Reason |
|---|---|
| Code editor | Core functionality |
| Chat panel | Core functionality |
| Task tree/progress | Learner needs to see progress |
| Submit button | Core functionality |

---

## Cookie Handling

### The Problem

Modern browsers block third-party cookies in iframes:
- Safari: Blocks all third-party cookies by default
- Chrome: Deprecating third-party cookies (delayed but coming)
- Firefox: Blocks known trackers, may block others

This means our cookie-based `learner_id` won't work in the iframe.

### The Solution

We don't need cookies at all in LTI mode:
1. `learner_id` comes from the LTI launch (URL param → sessionStorage)
2. `launch_id` comes from the LTI launch (URL param → sessionStorage)
3. `sessionStorage` is per-origin and works in iframes (not blocked)
4. The LTI flow's own cookies (`SameSite=None; Secure`) are set by PyLTI1p3 during the launch redirect -- they only need to survive the OIDC flow (seconds), not the entire session

**Key insight**: After the LTI launch completes and redirects to our app, we use `sessionStorage` for state, not cookies. This avoids all third-party cookie issues.

---

## CSS Adjustments

Prevent double scrollbars when embedded:

```css
/* apps/web/src/app/globals.css */

/* When in iframe, prevent double scrollbar */
html.lti-iframe {
  overflow: hidden;
  height: 100%;
}

html.lti-iframe body {
  overflow: auto;
  height: 100%;
}
```

Apply the class:

```typescript
useEffect(() => {
  if (isInIframe()) {
    document.documentElement.classList.add("lti-iframe");
  }
}, []);
```

---

## Full-Width Display

Open edX supports `display_type: "full_width_in_course"` for LTI components, which removes the course sidebar and gives the iframe full width. This is ideal for the workspace view.

Configure this in Studio when setting up the LTI component (see [07-openedx-config.md](07-openedx-config.md)).

---

## Entry Point Changes

### Workspace Page (`apps/web/src/app/workspace/[projectId]/page.tsx`)

Add LTI context initialization:

```typescript
"use client";

import { useSearchParams } from "next/navigation";
import { useEffect } from "react";
import { parseLTIContext, storeLTIContext } from "@/lib/lti";

export default function WorkspacePage({ params }: { params: { projectId: string } }) {
  const searchParams = useSearchParams();

  useEffect(() => {
    // Parse and store LTI context on first load
    const ltiCtx = parseLTIContext(searchParams);
    if (ltiCtx.isLTI) {
      storeLTIContext(ltiCtx);
    }
  }, [searchParams]);

  // Rest of the workspace component...
}
```

---

## Security Considerations

1. **X-Frame-Options**: Our server must NOT set `X-Frame-Options: DENY`. Use `SAMEORIGIN` or remove the header entirely (rely on CSP instead).

2. **Content-Security-Policy**: Allow framing by Open edX:
   ```
   Content-Security-Policy: frame-ancestors https://imbizo.alx-ai-tools.com 'self';
   ```

3. **CORS**: Our API must accept requests from the iframe origin (our own domain served inside the iframe). This should already work since the iframe loads our domain.

4. **`launch_id` exposure**: The `launch_id` is in the URL and sessionStorage. It expires after 2 hours (Redis TTL). This is acceptable for the session lifetime.

### FastAPI CORS/Headers Configuration

```python
# In app.py
from fastapi.middleware.cors import CORSMiddleware

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Or restrict to your frontend domain
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*", "X-LTI-Launch-Id"],
    expose_headers=["*"],
)

# Add CSP header for iframe embedding
@app.middleware("http")
async def add_security_headers(request, call_next):
    response = await call_next(request)
    response.headers["Content-Security-Policy"] = (
        "frame-ancestors https://imbizo.alx-ai-tools.com 'self'"
    )
    # Remove X-Frame-Options if set elsewhere
    response.headers.pop("X-Frame-Options", None)
    return response
```
