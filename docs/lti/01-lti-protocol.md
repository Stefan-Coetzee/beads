# LTI 1.3 Protocol Reference

> How the OIDC launch flow works, what claims are in the JWT, and the security model.

---

## Overview

LTI 1.3 is built on OpenID Connect (OIDC) and OAuth 2.0. The key actors:

- **Platform** (LMS): Open edX at `imbizo.alx-ai-tools.com` -- initiates launches, issues JWTs
- **Tool** (our app): LTT -- validates JWTs, renders the learning experience, sends grades back

The platform embeds the tool in an iframe. Authentication happens via signed JWTs, not shared cookies or session tokens.

---

## OIDC Launch Flow (4 Steps)

```
┌──────────┐                              ┌──────────┐
│ Open edX │                              │   LTT    │
│(Platform)│                              │  (Tool)  │
└────┬─────┘                              └────┬─────┘
     │                                         │
     │  1. Third-Party Login Request           │
     │  POST /lti/login                        │
     │  {iss, login_hint, target_link_uri,     │
     │   lti_message_hint, client_id}          │
     ├────────────────────────────────────────→│
     │                                         │
     │  2. Tool validates, generates nonce/    │
     │     state, redirects to platform auth   │
     │←────────────────────────────────────────┤
     │  302 → platform auth_login_url          │
     │  {scope=openid, response_type=id_token, │
     │   response_mode=form_post, client_id,   │
     │   redirect_uri, login_hint, state,      │
     │   nonce, prompt=none}                   │
     │                                         │
     │  3. Platform creates signed JWT,        │
     │     POSTs to tool launch URL            │
     │  POST /lti/launch                       │
     │  {id_token=<signed_jwt>, state}         │
     ├────────────────────────────────────────→│
     │                                         │
     │  4. Tool validates JWT:                 │
     │     - Verify state matches cookie       │
     │     - Fetch platform JWKS               │
     │     - Verify JWT signature (RS256)      │
     │     - Check iss, aud, exp, nonce        │
     │     - Extract user claims               │
     │     - Redirect to app                   │
     │                                         │
     │  ← HTML/redirect (app renders in        │
     │     iframe)                              │
     │←────────────────────────────────────────┤
```

### Step 1: Platform Initiates Login

Open edX sends a GET or POST to our `/lti/login` endpoint with:

| Parameter | Description | Example |
|---|---|---|
| `iss` | Platform issuer URL | `https://imbizo.alx-ai-tools.com` |
| `login_hint` | Opaque user identifier | `abc123` |
| `target_link_uri` | Our launch URL (must match registration) | `https://our-tool.ngrok.io/lti/launch` |
| `lti_message_hint` | Opaque resource context | `xyz789` |
| `client_id` | Our tool's client_id on the platform | `f93e96e8-8504-...` |

### Step 2: Tool Redirects to Platform Auth

Our tool:
1. Validates `iss` is a known platform
2. Validates `target_link_uri` matches our domain (prevents open redirect)
3. Generates cryptographic **nonce** (stored in Redis for replay prevention)
4. Generates **state** parameter (stored in cookie for CSRF prevention)
5. Redirects to the platform's `auth_login_url` with OIDC parameters

### Step 3: Platform Signs JWT and POSTs Back

The platform:
1. Validates `redirect_uri` matches registered URIs for this `client_id`
2. Constructs a JWT with all LTI claims
3. Signs it with the platform's private RSA key (RS256)
4. Auto-submits a hidden FORM POST to our `/lti/launch`

### Step 4: Tool Validates JWT and Launches

Our tool:
1. Verifies `state` matches the cookie (CSRF check)
2. Fetches the platform's public JWKS from `key_set_url`
3. Validates JWT signature using the matching public key
4. Validates standard claims: `iss`, `aud`, `exp`, `iat`
5. Validates `nonce` hasn't been used before (replay prevention)
6. Validates `deployment_id` is registered
7. Extracts LTI claims, maps user, redirects to app

---

## JWT Claims (id_token)

The `id_token` JWT from Open edX contains these claims:

### Standard OIDC Claims

```json
{
  "iss": "https://imbizo.alx-ai-tools.com",
  "sub": "user-id-12345",
  "aud": "tool-client-id",
  "exp": 1640000000,
  "iat": 1639999000,
  "nonce": "random-nonce-from-step-2"
}
```

### User Identity Claims

```json
{
  "name": "Alice Smith",
  "given_name": "Alice",
  "family_name": "Smith",
  "email": "alice@example.com"
}
```

### LTI Core Claims

```json
{
  "https://purl.imsglobal.org/spec/lti/claim/message_type": "LtiResourceLinkRequest",
  "https://purl.imsglobal.org/spec/lti/claim/version": "1.3.0",
  "https://purl.imsglobal.org/spec/lti/claim/deployment_id": "1",
  "https://purl.imsglobal.org/spec/lti/claim/target_link_uri": "https://tool.example.com/lti/launch",

  "https://purl.imsglobal.org/spec/lti/claim/resource_link": {
    "id": "resource-link-id-123",
    "title": "Maji Ndogo Water Analysis",
    "description": "AI-tutored SQL project"
  },

  "https://purl.imsglobal.org/spec/lti/claim/roles": [
    "http://purl.imsglobal.org/vocab/lis/v2/membership#Learner",
    "http://purl.imsglobal.org/vocab/lis/v2/institution/person#Student"
  ],

  "https://purl.imsglobal.org/spec/lti/claim/context": {
    "id": "course-id-456",
    "label": "DA101",
    "title": "Introduction to Data Analysis",
    "type": ["http://purl.imsglobal.org/vocab/lis/v2/course#CourseOffering"]
  },

  "https://purl.imsglobal.org/spec/lti/claim/custom": {
    "project_id": "proj-9b46",
    "workspace_type": "sql"
  }
}
```

### LTI Advantage Claims

#### AGS (Assignments and Grades Service)

```json
{
  "https://purl.imsglobal.org/spec/lti-ags/claim/endpoint": {
    "scope": [
      "https://purl.imsglobal.org/spec/lti-ags/scope/lineitem",
      "https://purl.imsglobal.org/spec/lti-ags/scope/lineitem.readonly",
      "https://purl.imsglobal.org/spec/lti-ags/scope/result.readonly",
      "https://purl.imsglobal.org/spec/lti-ags/scope/score"
    ],
    "lineitems": "https://imbizo.alx-ai-tools.com/api/lti_consumer/v1/courses/123/lineitems",
    "lineitem": "https://imbizo.alx-ai-tools.com/api/lti_consumer/v1/courses/123/lineitems/456"
  }
}
```

#### NRPS (Names and Roles Provisioning Service)

```json
{
  "https://purl.imsglobal.org/spec/lti-nrps/claim/namesroleservice": {
    "context_memberships_url": "https://imbizo.alx-ai-tools.com/api/lti_consumer/v1/courses/123/memberships",
    "service_versions": ["2.0"]
  }
}
```

### Deep Linking Claims

When `message_type` is `LtiDeepLinkingRequest`:

```json
{
  "https://purl.imsglobal.org/spec/lti-dl/claim/deep_linking_settings": {
    "deep_link_return_url": "https://imbizo.alx-ai-tools.com/api/lti_consumer/v1/deep_link_return/",
    "accept_types": ["link", "ltiResourceLink"],
    "accept_presentation_document_targets": ["iframe", "window"],
    "accept_multiple": true
  }
}
```

---

## Custom Parameters

Open edX allows course authors to pass custom parameters to the tool. We use these to map LTI launches to specific LTT projects:

```
project_id=proj-9b46
workspace_type=sql
```

These arrive in the JWT under `https://purl.imsglobal.org/spec/lti/claim/custom`.

---

## Security Model

### What Prevents Attacks

| Threat | Mitigation |
|---|---|
| CSRF (forged launch) | `state` parameter in cookie, verified on return |
| Replay attack | `nonce` stored in Redis with TTL, rejected if seen before |
| JWT forgery | RS256 signature verified against platform's public JWKS |
| Man-in-the-middle | All communication over TLS 1.2+ (HTTPS required) |
| Open redirect | `target_link_uri` validated against registered domains |
| Impersonation | `iss` + `aud` + `deployment_id` all validated against config |

### Key Material

| Key | Owner | Purpose | Storage |
|---|---|---|---|
| Platform private key | Open edX | Signs id_token JWTs | Platform's keystore |
| Platform public JWKS | Open edX | Tool verifies JWT signatures | Fetched from `key_set_url` |
| Tool private key | LTT | Signs outgoing JWTs (Deep Linking, service token requests) | `configs/lti/private.key` |
| Tool public key | LTT | Platform verifies tool's signatures | Served at `/lti/jwks` |

### Important Notes

- **No PKCE**: LTI 1.3 uses implicit flow with `response_mode=form_post`, not authorization code + PKCE
- **No shared secrets**: Unlike LTI 1.1, there are no shared OAuth secrets. All auth is asymmetric (RSA)
- **Nonce TTL**: Store nonces for at least 1 hour, discard after
- **JWKS caching**: Cache platform JWKS for ~2 hours. Some platforms rotate keys hourly
- **Clock skew**: Allow ~5 minutes of clock skew when validating `exp` and `iat`

---

## LTI Advantage Services

These are server-to-server API calls that the tool makes back to the platform after the initial launch.

### Authentication for Service Calls

Service calls use OAuth 2.0 client_credentials grant:

```
1. Tool creates a JWT signed with its private key:
   {iss: client_id, sub: client_id, aud: auth_token_url, jti: unique_id}

2. Tool POSTs to platform's auth_token_url:
   grant_type=client_credentials
   client_assertion_type=urn:ietf:params:oauth:client-assertion-type:jwt-bearer
   client_assertion=<signed_jwt>
   scope=<requested_scopes>

3. Platform returns access token:
   {access_token: "...", token_type: "Bearer", expires_in: 3600}

4. Tool uses Bearer token for AGS/NRPS API calls
```

PyLTI1p3 handles this automatically when you call `ags.put_grade()` or `nrps.get_members()`.

### AGS (Grades)

- **PUT score**: Send a grade for a specific user to a line item
- **GET results**: Read grades from the gradebook
- **Manage line items**: Create, update, delete gradebook columns

### NRPS (Roster)

- **GET members**: Retrieve course roster with user details and roles

### Deep Linking

- **Receive request**: Platform asks tool to select/configure content
- **Return response**: Tool sends signed JWT with selected resources back to platform
- **Result**: Platform creates an LTI link in the course pointing to the selected resource

---

## Message Types

| Type | Trigger | Purpose |
|---|---|---|
| `LtiResourceLinkRequest` | Learner clicks LTI link | Normal launch -- render the tool |
| `LtiDeepLinkingRequest` | Instructor configures content in Studio | Content selection -- pick which project to link |

---

## Role Checking

PyLTI1p3 provides convenience methods:

```python
message_launch.check_student_access()     # Learner
message_launch.check_teacher_access()     # Instructor
message_launch.check_staff_access()       # Admin/Staff
message_launch.check_teaching_assistant_access()  # TA
```

We use this to determine whether to show the learner workspace or an instructor dashboard.

---

## References

- [LTI 1.3 Core Specification](https://www.imsglobal.org/spec/lti/v1p3/)
- [LTI AGS v2.0 Specification](https://www.imsglobal.org/spec/lti-ags/v2p0)
- [IMS Security Framework 1.0](https://www.imsglobal.org/spec/security/v1p0)
- [PyLTI1p3 GitHub](https://github.com/dmitry-viskov/pylti1.3)
- [Open edX xblock-lti-consumer](https://github.com/openedx/xblock-lti-consumer)
