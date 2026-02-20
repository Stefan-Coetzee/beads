# Open edX Studio Configuration

> Step-by-step guide to configuring the LTI tool on `imbizo.alx-ai-tools.com`.

---

## Prerequisites

- Admin or course staff access to `https://imbizo.alx-ai-tools.com`
- LTT running locally with ngrok tunnel (see [06-ngrok-setup.md](06-ngrok-setup.md))
- RSA keys generated (see [02-implementation.md](02-implementation.md))

---

## Step 1: Enable LTI Consumer in Course

1. Open Studio: `https://studio.imbizo.alx-ai-tools.com` (or wherever Studio is hosted)
2. Navigate to your course
3. Go to **Settings → Advanced Settings**
4. Find **Advanced Module List**
5. Add `"lti_consumer"` to the list (if not already present):
   ```json
   ["lti_consumer"]
   ```
6. Click **Save Changes**

> On most Open edX installations, `lti_consumer` is already enabled by default.

---

## Step 2: Add LTI Component to a Course Unit

1. Navigate to the course unit where you want the LTT workspace
2. Click **+ Add New Component**
3. Click **Advanced**
4. Select **LTI Consumer**

This creates an LTI component that you'll configure in the next steps.

---

## Step 3: Configure LTI 1.3 Settings

Click **Edit** on the LTI component and configure:

### Basic Settings

| Setting | Value |
|---|---|
| **LTI Version** | `LTI 1.3` |
| **LTI 1.3 Tool Launch URL** | `https://ltt-dev.ngrok-free.app/lti/launch` |
| **LTI 1.3 OIDC URL** | `https://ltt-dev.ngrok-free.app/lti/login` |
| **LTI 1.3 Tool Public Key** | Paste contents of `configs/lti/public.key` |

Alternatively, use JWKS URL instead of pasting the public key:

| Setting | Value |
|---|---|
| **LTI 1.3 Tool Keyset URL** | `https://ltt-dev.ngrok-free.app/lti/jwks` |

> Use either the public key OR the keyset URL, not both. The keyset URL is preferred as it supports key rotation.

### Custom Parameters

Add custom parameters to pass the project ID and workspace type:

```
project_id=proj-9b46
workspace_type=sql
```

These arrive in the JWT under `https://purl.imsglobal.org/spec/lti/claim/custom`.

### LTI Advantage Settings

| Setting | Value |
|---|---|
| **LTI Assignment and Grades Service** | `Allow tools to submit grades only` (declarative) |
| **LTI Names and Roles Provisioning Service** | `Enabled` (optional, for roster access) |

### Display Settings

| Setting | Value |
|---|---|
| **Inline Height** | `900` (pixels, or adjust to fit your workspace) |
| **Modal** | Unchecked (we want inline, not modal) |
| **Scored** | Checked |
| **Weight** | Set as needed (e.g., `1.0` for equal weight, or percentage of total grade) |
| **Display Name** | `Maji Ndogo Water Analysis` (or your project title) |

### Deep Linking (Optional)

If you want instructors to be able to select projects from a catalog:

| Setting | Value |
|---|---|
| **LTI 1.3 Tool Deep Linking URL** | `https://ltt-dev.ngrok-free.app/lti/launch` |

---

## Step 4: Save and Get Platform Configuration

After saving the LTI component, Open edX generates platform-side configuration values. You need these for your tool config.

### Where to Find Platform Values

1. After saving, look for the **LTI 1.3 Settings** section (shown after save)
2. Open edX displays:

| Platform Value | Description | Example |
|---|---|---|
| **Client ID** | Unique identifier for this tool registration | `f93e96e8-8504-4bb0-8553-ee147920ee42` |
| **Deployment ID** | Usually `1` | `1` |
| **Keyset URL** | Platform's public key endpoint | `https://imbizo.alx-ai-tools.com/api/lti_consumer/v1/public_keysets/<uuid>` |
| **Access Token URL** | For OAuth2 service calls (AGS/NRPS) | `https://imbizo.alx-ai-tools.com/api/lti_consumer/v1/token/<uuid>` |
| **OIDC Callback URL** | Platform's auth endpoint | `https://imbizo.alx-ai-tools.com/api/lti_consumer/v1/launch/` |

> These values may also be labeled as "Platform Issuer Details" or similar depending on the Open edX version.

---

## Step 5: Update Tool Configuration

Take the platform values from Step 4 and update `configs/lti/platform.json`:

```json
{
  "https://imbizo.alx-ai-tools.com": [
    {
      "default": true,
      "client_id": "f93e96e8-8504-4bb0-8553-ee147920ee42",
      "auth_login_url": "https://imbizo.alx-ai-tools.com/api/lti_consumer/v1/launch/",
      "auth_token_url": "https://imbizo.alx-ai-tools.com/api/lti_consumer/v1/token/<uuid>",
      "auth_audience": null,
      "key_set_url": "https://imbizo.alx-ai-tools.com/api/lti_consumer/v1/public_keysets/<uuid>",
      "key_set": null,
      "deployment_ids": ["1"]
    }
  ]
}
```

Replace `<uuid>` with the actual UUIDs from the Open edX platform values.

**Important**: The top-level key (`https://imbizo.alx-ai-tools.com`) must match the `iss` claim that Open edX sends in the JWT. This is typically the LMS domain.

---

## Step 6: Restart and Test

1. Restart the FastAPI server (to pick up the new config):
   ```bash
   PYTHONPATH=services/ltt-core/src:services/api-server/src \
     uv run uvicorn api.app:app --host 0.0.0.0 --port 8000
   ```

2. Ensure ngrok is running:
   ```bash
   ngrok http 3000 --domain ltt-dev.ngrok-free.app
   ```

3. In Open edX, navigate to the course unit with the LTI component
4. Click **Preview** or view as a student
5. You should see the LTT workspace load inside the iframe

---

## Determining the Platform Issuer URL

The `iss` (issuer) claim in the JWT must match the key in your `platform.json`. For Open edX, the issuer is typically:

- **Tutor-based**: `https://imbizo.alx-ai-tools.com` (the LMS domain)
- **Native Open edX**: Same as above

If the launch fails with "Unknown platform issuer", check the actual `iss` value in the JWT:

1. In your `/lti/launch` endpoint, temporarily log the raw JWT:
   ```python
   import base64, json
   form = await request.form()
   id_token = form.get("id_token")
   payload = id_token.split(".")[1]
   # Add padding
   payload += "=" * (4 - len(payload) % 4)
   claims = json.loads(base64.urlsafe_b64decode(payload))
   print(f"ISS: {claims.get('iss')}")
   ```

2. Use that exact `iss` value as the key in `platform.json`.

---

## Multiple Projects in One Course

To offer multiple LTT projects in a single course:

### Option A: Multiple LTI Components

Add one LTI component per project, each with different custom parameters:

**Component 1**:
```
project_id=proj-9b46
workspace_type=sql
```

**Component 2**:
```
project_id=proj-abc1
workspace_type=python
```

Each component appears as a separate graded item in the course.

### Option B: Deep Linking

Configure Deep Linking so instructors can select from available projects:

1. Enable Deep Linking URL in the LTI component
2. When the instructor configures content, they see a project selection UI
3. The selected project is stored as a custom parameter in the LTI link

---

## Grading Configuration

### Setting Grade Weight

1. In Studio, click on the LTI component
2. Check **Scored**
3. Set **Weight** (e.g., `1.0`)
4. The grade from LTT will contribute to the subsection grade

### Grade Passback Behavior

| LTT Event | Grade Sent | Open edX Behavior |
|---|---|---|
| Learner starts project | 0/N tasks | 0% in gradebook |
| Learner completes tasks | K/N tasks | K/N * 100% in gradebook |
| All tasks complete | N/N tasks | 100% in gradebook |

### Grading Policy Integration

Open edX grading policies (drop lowest, weighted categories) work normally. The LTI grade is treated like any other graded component.

---

## Security Checklist

Before going live:

- [ ] RSA keys are generated and not committed to git
- [ ] `platform.json` has the correct issuer URL and client_id
- [ ] LTI Launch URL is HTTPS
- [ ] Content-Security-Policy allows framing by `imbizo.alx-ai-tools.com`
- [ ] AGS is enabled in the LTI component settings
- [ ] Custom parameters include `project_id`
- [ ] Test launch works with a student account

---

## Troubleshooting

### "There was an error loading this tool"

Open edX could not reach the tool's login endpoint.

**Check**: Is ngrok running? Is the URL in Studio correct?

### "LTI configuration error"

Mismatch between platform and tool configuration.

**Check**: Does `client_id` in `platform.json` match what Open edX generated?

### "Invalid state" error

The CSRF state cookie was lost between login and launch.

**Check**: Are cookies being set with `SameSite=None; Secure`? Is the redirect going through the same domain?

### Grade not showing in gradebook

AGS is not configured or grade passback failed.

**Check**:
1. Is "LTI Assignment and Grades Service" enabled in the LTI component?
2. Is the component marked as "Scored"?
3. Check FastAPI logs for AGS errors

### iframe is too small

The default iframe height may be too small for the workspace.

**Check**: Set "Inline Height" to `900` or higher in the LTI component settings. Also ensure the iframe auto-resize JavaScript is working (see [05-frontend-iframe.md](05-frontend-iframe.md)).
