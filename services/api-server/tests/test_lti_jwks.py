"""Tests for GET /lti/jwks (public key set endpoint)."""


class TestLtiJwks:
    async def test_jwks_returns_key_set(self, client):
        """JWKS endpoint returns JSON with 'keys' array."""
        resp = await client.get("/lti/jwks")
        assert resp.status_code == 200
        data = resp.json()
        assert "keys" in data
        assert len(data["keys"]) > 0

    async def test_jwks_key_has_required_fields(self, client):
        """Each JWK has kty, n, e fields."""
        resp = await client.get("/lti/jwks")
        key = resp.json()["keys"][0]
        assert key["kty"] == "RSA"
        assert "n" in key
        assert "e" in key

    async def test_jwks_no_auth_required(self, client_auth):
        """JWKS is public — works even with auth_enabled=True."""
        resp = await client_auth.get("/lti/jwks")
        assert resp.status_code == 200
        assert "keys" in resp.json()
