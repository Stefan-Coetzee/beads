# End-to-End Testing Guide

> How to verify the LTI integration works from Open edX to LTT and back.

---

## Testing Phases

1. **Unit tests** -- Adapter classes, user mapping, grade service
2. **Local integration** -- LTI endpoints with mock JWT
3. **ngrok integration** -- Full flow through tunnel to Open edX
4. **Production validation** -- Real learners on `imbizo.alx-ai-tools.com`

---

## Phase 1: Unit Tests

### Adapter Tests

```python
# tests/lti/test_adapter.py

import pytest
from api.lti.adapter import FastAPIRequest, FastAPICookieService


class TestFastAPIRequest:
    def test_get_param(self):
        req = FastAPIRequest(
            cookies={},
            session={},
            request_data={"iss": "https://example.com", "login_hint": "user1"},
            request_is_secure=True,
        )
        assert req.get_param("iss") == "https://example.com"
        assert req.get_param("missing") is None

    def test_is_secure(self):
        req = FastAPIRequest(
            cookies={}, session={}, request_data={}, request_is_secure=True
        )
        assert req.is_secure() is True

    def test_get_cookie(self):
        req = FastAPIRequest(
            cookies={"session": "abc"},
            session={},
            request_data={},
            request_is_secure=False,
        )
        assert req.get_cookie("session") == "abc"
        assert req.get_cookie("missing") is None


class TestFastAPICookieService:
    def test_set_and_update_response(self):
        req = FastAPIRequest(
            cookies={}, session={}, request_data={}, request_is_secure=True
        )
        service = FastAPICookieService(req)
        service.set_cookie("state", "xyz", exp=3600)

        from starlette.responses import Response
        response = Response()
        service.update_response(response)

        # Check that Set-Cookie header was added
        cookie_header = response.headers.get("set-cookie", "")
        assert "lti1p3-state" in cookie_header
        assert "xyz" in cookie_header
        assert "SameSite=none" in cookie_header.lower() or "samesite=none" in cookie_header.lower()
```

### User Mapping Tests

```python
# tests/lti/test_user_mapping.py

import pytest
from api.lti.users import get_or_create_lti_learner, get_learner_by_lti


@pytest.mark.asyncio
async def test_first_launch_creates_learner(async_session):
    """First LTI launch creates a new learner and mapping."""
    learner_id = await get_or_create_lti_learner(
        session=async_session,
        lti_sub="edx-user-42",
        lti_iss="https://imbizo.alx-ai-tools.com",
        name="Alice Smith",
        email="alice@example.com",
    )

    assert learner_id.startswith("learner-")

    # Verify mapping exists
    found = await get_learner_by_lti(
        async_session, "edx-user-42", "https://imbizo.alx-ai-tools.com"
    )
    assert found == learner_id


@pytest.mark.asyncio
async def test_subsequent_launch_returns_same_learner(async_session):
    """Subsequent launches return the same learner_id."""
    id1 = await get_or_create_lti_learner(
        async_session, "edx-user-42", "https://imbizo.alx-ai-tools.com"
    )
    id2 = await get_or_create_lti_learner(
        async_session, "edx-user-42", "https://imbizo.alx-ai-tools.com"
    )
    assert id1 == id2


@pytest.mark.asyncio
async def test_different_platforms_create_different_learners(async_session):
    """Same sub from different platforms creates different learners."""
    id1 = await get_or_create_lti_learner(
        async_session, "user-42", "https://platform-a.com"
    )
    id2 = await get_or_create_lti_learner(
        async_session, "user-42", "https://platform-b.com"
    )
    assert id1 != id2
```

### Grade Service Tests

```python
# tests/lti/test_grades.py

import pytest
from unittest.mock import MagicMock, patch
from api.lti.grades import send_grade


def test_send_grade_without_ags():
    """Grade passback is silently skipped when AGS is unavailable."""
    # Mock a message launch without AGS
    with patch("api.lti.grades.FastAPIMessageLaunch") as MockLaunch:
        mock_launch = MagicMock()
        mock_launch.has_ags.return_value = False
        MockLaunch.from_cache.return_value = mock_launch

        storage = MagicMock()
        result = send_grade(
            launch_id="test-launch",
            storage=storage,
            learner_sub="user-42",
            score=15.0,
            max_score=42.0,
        )
        assert result is False


def test_send_grade_expired_launch():
    """Grade passback handles expired launch gracefully."""
    with patch("api.lti.grades.FastAPIMessageLaunch") as MockLaunch:
        MockLaunch.from_cache.side_effect = Exception("Launch not found")

        storage = MagicMock()
        result = send_grade(
            launch_id="expired-launch",
            storage=storage,
            learner_sub="user-42",
            score=15.0,
            max_score=42.0,
        )
        assert result is False
```

### Run Unit Tests

```bash
uv run pytest tests/lti/ -v
```

---

## Phase 2: Local Integration Tests

Test the LTI endpoints without Open edX using crafted requests.

### Test JWKS Endpoint

```bash
curl http://localhost:8000/lti/jwks | python -m json.tool
```

Expected response:
```json
{
  "keys": [
    {
      "kty": "RSA",
      "e": "AQAB",
      "n": "...",
      "kid": "...",
      "alg": "RS256",
      "use": "sig"
    }
  ]
}
```

### Test Login Endpoint

```bash
curl -X POST http://localhost:8000/lti/login \
  -d "iss=https://imbizo.alx-ai-tools.com" \
  -d "login_hint=test-user" \
  -d "target_link_uri=http://localhost:8000/lti/launch" \
  -d "lti_message_hint=test-hint" \
  -d "client_id=test-client-id" \
  -v
```

Expected: 302 redirect to the platform's `auth_login_url` with OIDC parameters.

### Test with PyLTI1p3 Test Utilities

PyLTI1p3 includes a `FakeLaunch` utility for testing:

```python
# tests/lti/test_launch_integration.py

import pytest
from fastapi.testclient import TestClient
from api.app import app


@pytest.fixture
def client():
    return TestClient(app)


def test_jwks_returns_valid_keys(client):
    response = client.get("/lti/jwks")
    assert response.status_code == 200
    data = response.json()
    assert "keys" in data
    assert len(data["keys"]) > 0
    assert data["keys"][0]["kty"] == "RSA"


def test_login_without_params_returns_400(client):
    response = client.post("/lti/login")
    assert response.status_code == 400


def test_login_with_params_redirects(client):
    response = client.post(
        "/lti/login",
        data={
            "iss": "https://imbizo.alx-ai-tools.com",
            "login_hint": "test-user",
            "target_link_uri": "http://localhost:8000/lti/launch",
            "lti_message_hint": "test",
            "client_id": "test-client",
        },
        follow_redirects=False,
    )
    # Should redirect to platform auth URL
    assert response.status_code in (302, 200)  # 200 if JS redirect
```

---

## Phase 3: ngrok Integration Test

Full end-to-end test through Open edX.

### Pre-flight Checklist

- [ ] Docker services running (postgres, mysql, redis)
- [ ] FastAPI server running on port 8000
- [ ] Next.js dev server running on port 3000
- [ ] ngrok tunnel active (`https://ltt-dev.ngrok-free.app → localhost:3000`)
- [ ] `configs/lti/platform.json` configured with Open edX values
- [ ] LTI component configured in Open edX Studio

### Test Script

```bash
#!/usr/bin/env bash
# tools/scripts/test-lti-integration.sh

echo "=== LTI Integration Test ==="

NGROK_URL="https://ltt-dev.ngrok-free.app"

# 1. Test ngrok is reachable
echo -n "[1/4] Testing ngrok tunnel... "
HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" "$NGROK_URL/health")
if [ "$HTTP_CODE" = "200" ]; then
    echo "OK (health check passed)"
else
    echo "FAIL (HTTP $HTTP_CODE)"
    exit 1
fi

# 2. Test JWKS endpoint
echo -n "[2/4] Testing JWKS endpoint... "
JWKS=$(curl -s "$NGROK_URL/lti/jwks")
if echo "$JWKS" | python3 -c "import sys,json; d=json.load(sys.stdin); assert 'keys' in d" 2>/dev/null; then
    echo "OK (valid JWKS)"
else
    echo "FAIL (invalid JWKS response)"
    exit 1
fi

# 3. Test login endpoint rejects bad requests
echo -n "[3/4] Testing login validation... "
HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" -X POST "$NGROK_URL/lti/login")
if [ "$HTTP_CODE" = "400" ]; then
    echo "OK (rejects missing params)"
else
    echo "FAIL (expected 400, got $HTTP_CODE)"
    exit 1
fi

# 4. Test frontend loads
echo -n "[4/4] Testing frontend... "
HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" "$NGROK_URL")
if [ "$HTTP_CODE" = "200" ]; then
    echo "OK (frontend loaded)"
else
    echo "FAIL (HTTP $HTTP_CODE)"
    exit 1
fi

echo ""
echo "=== All pre-flight checks passed ==="
echo ""
echo "Next: Open your course on imbizo.alx-ai-tools.com and test the LTI launch."
```

### Manual Test Steps

1. **Log in to Open edX** as a student account
2. **Navigate to the course unit** with the LTI component
3. **Click the LTI link** -- you should see:
   - Brief redirect (OIDC flow, ~1-2 seconds)
   - LTT workspace loads in the iframe
   - AI tutor chat is available
   - Code editor works

4. **Verify identity mapping**:
   ```bash
   # Check the database for the new learner
   docker-compose exec postgres psql -U ltt_user -d ltt_dev -c \
     "SELECT * FROM lti_user_mappings ORDER BY created_at DESC LIMIT 5;"
   ```

5. **Test task completion and grade passback**:
   - Start a task in the workspace
   - Submit work
   - Check the Open edX gradebook for the updated score

6. **Test session persistence**:
   - Complete some tasks
   - Navigate away from the course unit
   - Return to the unit -- progress should be preserved

---

## Phase 4: Production Validation

### Smoke Tests (Per Deploy)

| Test | Expected Result |
|---|---|
| LTI launch as student | Workspace loads with correct project |
| LTI launch as instructor | Instructor view (if implemented) |
| Complete a task | Grade appears in Open edX gradebook |
| Refresh the page | Progress preserved (sessionStorage + database) |
| Multiple students simultaneously | Each sees their own progress |
| Launch expiry (after 2h) | Graceful "please relaunch" message |

### Load Testing

For staging environments with multiple concurrent learners:

```bash
# Simulate N concurrent LTI sessions
# (Requires a script that creates test users in Open edX
# and triggers LTI launches)
```

### Monitoring Checklist

- [ ] FastAPI logs show successful LTI launches
- [ ] Redis has active launch_id entries
- [ ] AGS grade passback logs show successful calls
- [ ] No JWT validation errors
- [ ] No "Unknown platform issuer" errors

---

## Common Test Failures

### Launch shows blank iframe

**Cause**: CSP blocks the iframe
**Fix**: Check `Content-Security-Policy: frame-ancestors` header

### "State mismatch" error

**Cause**: Cookies not persisting between login and launch
**Fix**: Verify cookies are set with `SameSite=None; Secure`

### Learner progress not preserved

**Cause**: Different `learner_id` on each launch
**Fix**: Check `lti_user_mappings` table -- same `lti_sub` should map to same `learner_id`

### Grade not in gradebook

**Cause**: AGS endpoint URL incorrect or expired token
**Fix**: Check `auth_token_url` in `platform.json` and FastAPI AGS error logs

### "Launch data not found"

**Cause**: Redis TTL expired or Redis not running
**Fix**: Check Redis connectivity and increase `_DEFAULT_TTL` if sessions are too short

---

## Debugging Tools

### Inspect JWT Claims

Add temporary logging to the launch endpoint:

```python
# In routes.py, inside lti_launch():
import json, base64

form = await request.form()
id_token = dict(form).get("id_token", "")
if id_token:
    parts = id_token.split(".")
    payload = parts[1] + "=" * (4 - len(parts[1]) % 4)
    claims = json.loads(base64.urlsafe_b64decode(payload))
    print(json.dumps(claims, indent=2))
```

### Check Redis State

```bash
# List all LTI keys
docker-compose exec redis redis-cli KEYS "lti1p3:*"

# Get a specific launch
docker-compose exec redis redis-cli GET "lti1p3:<launch_id>"

# Check active launch mappings
docker-compose exec redis redis-cli KEYS "lti1p3:active:*"
```

### Monitor ngrok Traffic

ngrok provides a local web inspector:
- Open http://localhost:4040
- See all requests flowing through the tunnel
- Inspect request/response headers and bodies
- Replay requests for debugging
