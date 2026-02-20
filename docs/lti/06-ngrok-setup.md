# ngrok Setup Guide

> Tunnel your local LTT instance to Open edX at `imbizo.alx-ai-tools.com`.

---

## Why ngrok?

LTI 1.3 requires HTTPS and a publicly accessible URL. During development, your LTT runs on `localhost`. ngrok creates a secure tunnel from a public HTTPS URL to your local machine.

```
imbizo.alx-ai-tools.com (Open edX)
         │
         │  LTI Launch
         ▼
https://ltt-dev.ngrok-free.app  ←─── ngrok tunnel
         │
         │  localhost:3000 (Next.js frontend)
         │  localhost:8000 (FastAPI API server)
         ▼
Your PC (macOS)
```

---

## Prerequisites

### 1. Install ngrok

```bash
# macOS (Homebrew)
brew install ngrok

# Or download from https://ngrok.com/download
```

### 2. Create ngrok Account

1. Sign up at https://dashboard.ngrok.com/signup
2. Get your auth token from https://dashboard.ngrok.com/get-started/your-authtoken
3. Configure:

```bash
ngrok config add-authtoken YOUR_AUTH_TOKEN
```

### 3. Reserve a Domain (Recommended)

Free ngrok URLs change every restart (e.g., `https://abc123.ngrok-free.app`). This means you'd need to reconfigure the LTI tool in Open edX every time.

**Solution**: Reserve a static domain (free on the ngrok free plan):

1. Go to https://dashboard.ngrok.com/domains
2. Click "New Domain"
3. Choose a name like `ltt-dev.ngrok-free.app`

With a reserved domain, the URL stays the same across restarts.

---

## Architecture: Single Tunnel vs. Dual Tunnel

### Option A: Single Tunnel to Frontend (Recommended)

Route all traffic through the Next.js frontend. The frontend proxies API calls to the FastAPI backend.

```
ngrok (port 3000) → Next.js → FastAPI (port 8000)
```

**Pros**: Single ngrok URL, simpler Open edX config
**Cons**: Requires Next.js API proxy configuration

### Option B: Dual Tunnels

Two separate ngrok tunnels for frontend and API.

```
ngrok tunnel 1 (port 3000) → Next.js frontend
ngrok tunnel 2 (port 8000) → FastAPI API
```

**Pros**: No proxy needed
**Cons**: Two URLs to manage, more complex LTI config, CORS complexity

**Recommendation**: Option A with a Next.js API proxy.

---

## Setup: Option A (Single Tunnel)

### Step 1: Configure Next.js API Proxy

Add API proxy rewrites to `apps/web/next.config.js`:

```javascript
/** @type {import('next').NextConfig} */
const nextConfig = {
  async rewrites() {
    return [
      {
        // Proxy /api/* to FastAPI backend
        source: "/api/:path*",
        destination: "http://localhost:8000/api/:path*",
      },
      {
        // Proxy /lti/* to FastAPI LTI endpoints
        source: "/lti/:path*",
        destination: "http://localhost:8000/lti/:path*",
      },
      {
        // Proxy /health to FastAPI
        source: "/health",
        destination: "http://localhost:8000/health",
      },
    ];
  },

  // Allow iframe embedding
  async headers() {
    return [
      {
        source: "/(.*)",
        headers: [
          {
            key: "Content-Security-Policy",
            value: "frame-ancestors https://imbizo.alx-ai-tools.com 'self'",
          },
        ],
      },
    ];
  },
};

module.exports = nextConfig;
```

### Step 2: Update Frontend API Base URL

In LTI mode, API calls should use relative URLs (same origin via proxy):

```typescript
// apps/web/src/lib/api.ts
const API_BASE_URL = typeof window !== "undefined" && isInIframe()
  ? ""  // Relative URL (proxied through Next.js)
  : process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
```

### Step 3: Start Local Services

Terminal 1 -- Database:
```bash
docker-compose up -d  # PostgreSQL, MySQL, Redis
```

Terminal 2 -- FastAPI API Server:
```bash
cd /Users/stefancoetzee/GitHub/beadslocal
PYTHONPATH=services/ltt-core/src:services/api-server/src \
  uv run uvicorn api.app:app --host 0.0.0.0 --port 8000
```

Terminal 3 -- Next.js Frontend:
```bash
cd /Users/stefancoetzee/GitHub/beadslocal/apps/web
npm run dev  # Starts on port 3000
```

### Step 4: Start ngrok Tunnel

Terminal 4:
```bash
# With reserved domain:
ngrok http 3000 --domain ltt-dev.ngrok-free.app

# Without reserved domain (URL changes each restart):
ngrok http 3000
```

You should see:

```
Session Status                online
Account                       your-email@example.com
Version                       3.x.x
Region                        United States (us)
Forwarding                    https://ltt-dev.ngrok-free.app -> http://localhost:3000
```

### Step 5: Verify the Tunnel

```bash
# Frontend
curl https://ltt-dev.ngrok-free.app

# API (through proxy)
curl https://ltt-dev.ngrok-free.app/health

# LTI JWKS (through proxy)
curl https://ltt-dev.ngrok-free.app/lti/jwks
```

---

## Setup: Option B (Dual Tunnels)

If you prefer not to proxy through Next.js:

### ngrok Configuration File

Create `~/.ngrok/ngrok.yml` (or add to existing):

```yaml
version: "3"
agent:
  authtoken: YOUR_AUTH_TOKEN

tunnels:
  frontend:
    proto: http
    addr: 3000
    domain: ltt-dev.ngrok-free.app  # Reserved domain for frontend

  api:
    proto: http
    addr: 8000
    # Free plan only allows one reserved domain, so this gets a random URL
```

Start both tunnels:

```bash
ngrok start --all
```

**Note**: The free plan only supports one reserved domain. The API tunnel will get a random URL. For dual reserved domains, you need a paid plan.

Update the frontend to point to the API tunnel URL:

```bash
# apps/web/.env.local
NEXT_PUBLIC_API_URL=https://random-abc123.ngrok-free.app
```

---

## ngrok Gotchas for LTI 1.3

### 1. HTTPS is Required

ngrok provides HTTPS by default. LTI 1.3 requires all URLs to be HTTPS. This works out of the box.

### 2. `X-Forwarded-Proto` Header

ngrok sets `X-Forwarded-Proto: https` on proxied requests. Our FastAPI `_is_secure()` function checks this header to correctly identify HTTPS requests (since the local server receives HTTP from ngrok).

### 3. ngrok Interstitial Page

Free ngrok accounts show a "Visit Site" interstitial page on first access. This breaks LTI launches because the OIDC redirect hits the interstitial instead of the login endpoint.

**Solutions**:

1. **Add `ngrok-skip-browser-warning` header** (works for API calls):
   ```typescript
   headers["ngrok-skip-browser-warning"] = "1";
   ```

2. **Use a reserved domain** (recommended): Reserved domains on free plans may still show the interstitial for browser requests, but FORM POSTs from the LTI launch should bypass it.

3. **Upgrade to ngrok paid plan**: Paid plans don't show interstitials.

4. **Use `--request-header-add` flag**:
   ```bash
   ngrok http 3000 --domain ltt-dev.ngrok-free.app \
     --request-header-add "ngrok-skip-browser-warning:1"
   ```

### 4. Cookie SameSite Issues

LTI launches happen in iframes. Cookies need `SameSite=None; Secure` to work cross-origin. Our PyLTI1p3 adapter handles this (see [02-implementation.md](02-implementation.md)).

After the initial launch, we use `sessionStorage` instead of cookies, avoiding the issue entirely (see [05-frontend-iframe.md](05-frontend-iframe.md)).

### 5. URL Stability

| Plan | URL Behavior | Recommendation |
|---|---|---|
| Free (no domain) | Changes every restart | Bad for LTI (must reconfigure in Studio each time) |
| Free (reserved domain) | Stable | Good for development |
| Paid | Stable + custom domains | Good for staging |

### 6. Rate Limits

Free ngrok has rate limits (40 connections/minute). For development this is fine. For demo/staging with multiple concurrent learners, consider a paid plan.

---

## Environment Configuration

### `.env` (Backend)

```bash
# Database
DATABASE_URL=postgresql+asyncpg://ltt_user:ltt_password@localhost:5432/ltt_dev

# LTI
LTI_PLATFORM_CONFIG=configs/lti/platform.json
LTI_PRIVATE_KEY=configs/lti/private.key
LTI_PUBLIC_KEY=configs/lti/public.key
LTI_REDIS_URL=redis://localhost:6379/0

# Frontend URL (the ngrok URL)
LTT_FRONTEND_URL=https://ltt-dev.ngrok-free.app
```

### `apps/web/.env.local` (Frontend)

```bash
# For Option A (single tunnel with proxy):
NEXT_PUBLIC_API_URL=

# For Option B (dual tunnels):
# NEXT_PUBLIC_API_URL=https://api-random.ngrok-free.app
```

---

## LTI URLs for Open edX Configuration

After starting ngrok, these are the URLs to enter in Open edX Studio:

| Setting | URL |
|---|---|
| Tool Launch URL | `https://ltt-dev.ngrok-free.app/lti/launch` |
| OIDC Login URL | `https://ltt-dev.ngrok-free.app/lti/login` |
| Tool Public Key | Contents of `configs/lti/public.key` (PEM text) |
| Tool Keyset URL | `https://ltt-dev.ngrok-free.app/lti/jwks` |
| Deep Linking URL | `https://ltt-dev.ngrok-free.app/lti/launch` (same as launch) |

See [07-openedx-config.md](07-openedx-config.md) for the full Open edX configuration walkthrough.

---

## Startup Script

Create a convenience script for starting everything:

### `tools/scripts/start-lti-dev.sh`

```bash
#!/usr/bin/env bash
set -euo pipefail

NGROK_DOMAIN="${NGROK_DOMAIN:-ltt-dev.ngrok-free.app}"
API_PORT=8000
FRONTEND_PORT=3000

echo "=== LTT LTI Development Setup ==="
echo ""

# 1. Check prerequisites
command -v ngrok >/dev/null 2>&1 || { echo "ngrok not installed. Run: brew install ngrok"; exit 1; }
command -v uv >/dev/null 2>&1 || { echo "uv not installed. See: https://docs.astral.sh/uv/"; exit 1; }

# 2. Start Docker services
echo "[1/4] Starting Docker services (postgres, mysql, redis)..."
docker-compose up -d
sleep 2

# 3. Start API server (background)
echo "[2/4] Starting FastAPI API server on port $API_PORT..."
PYTHONPATH=services/ltt-core/src:services/api-server/src \
  uv run uvicorn api.app:app --host 0.0.0.0 --port $API_PORT &
API_PID=$!
sleep 3

# 4. Start frontend (background)
echo "[3/4] Starting Next.js frontend on port $FRONTEND_PORT..."
cd apps/web && npm run dev &
FRONTEND_PID=$!
cd ../..
sleep 5

# 5. Start ngrok
echo "[4/4] Starting ngrok tunnel..."
echo ""
echo "=== URLs for Open edX Studio ==="
echo "  Launch URL:  https://$NGROK_DOMAIN/lti/launch"
echo "  Login URL:   https://$NGROK_DOMAIN/lti/login"
echo "  JWKS URL:    https://$NGROK_DOMAIN/lti/jwks"
echo ""
echo "Press Ctrl+C to stop all services."
echo ""

# Trap Ctrl+C to kill background processes
trap "kill $API_PID $FRONTEND_PID 2>/dev/null; docker-compose stop; exit" INT

ngrok http $FRONTEND_PORT --domain "$NGROK_DOMAIN"
```

```bash
chmod +x tools/scripts/start-lti-dev.sh
./tools/scripts/start-lti-dev.sh
```

---

## Troubleshooting

### "ERR_BLOCKED_BY_RESPONSE" in iframe

The response includes `X-Frame-Options: DENY` or a restrictive CSP.

**Fix**: Ensure the CSP header allows framing by Open edX:
```
Content-Security-Policy: frame-ancestors https://imbizo.alx-ai-tools.com 'self';
```

### "Cookies are blocked" warning

Third-party cookies blocked by the browser.

**Fix**: We don't rely on cookies after launch. Ensure `sessionStorage` is used for LTI state (see [05-frontend-iframe.md](05-frontend-iframe.md)).

### ngrok shows "Tunnel not found"

The reserved domain isn't configured or authtoken is missing.

**Fix**: Run `ngrok config add-authtoken YOUR_TOKEN` and verify the domain at https://dashboard.ngrok.com/domains.

### OIDC redirect fails with 502

The FastAPI server isn't running or isn't reachable on the expected port.

**Fix**: Verify `curl http://localhost:8000/health` returns OK before starting ngrok.

### "Invalid redirect_uri" from Open edX

The launch URL in Open edX doesn't match the ngrok URL.

**Fix**: Update the LTI tool configuration in Studio with the current ngrok URL.
