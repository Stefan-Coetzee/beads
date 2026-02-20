# User Identity Mapping

> How LTI user identities map to LTT learner records.

---

## Current State

Today, LTT has no authentication. The frontend generates a random `learner_id` (`learner-<hex>`), stores it in a browser cookie, and passes it with every API call. The backend creates a `LearnerModel` record on first contact.

```
Frontend cookie: learner_id = "learner-a1b2c3d4"
                        ↓
API request body: { "learner_id": "learner-a1b2c3d4", ... }
                        ↓
Backend: ensure_learner_exists(session, "learner-a1b2c3d4")
```

This works for development but provides no identity assurance. With LTI, Open edX handles authentication and gives us a verified user identity.

---

## LTI Identity Claims

From the LTI launch JWT, we receive:

| Claim | Description | Example |
|---|---|---|
| `sub` | Platform-specific user ID (pseudonymous) | `user-12345` |
| `iss` | Platform issuer URL | `https://imbizo.alx-ai-tools.com` |
| `name` | Full name (if platform shares PII) | `Alice Smith` |
| `email` | Email address (if shared) | `alice@example.com` |
| `given_name` | First name | `Alice` |
| `family_name` | Last name | `Smith` |

The `sub` + `iss` pair uniquely identifies a user across platforms.

---

## Database Changes

### Option A: Mapping Table (Recommended)

Add a new table that maps LTI identities to LTT learner IDs:

```sql
CREATE TABLE lti_user_mappings (
    id TEXT PRIMARY KEY,              -- UUID
    lti_sub TEXT NOT NULL,            -- LTI sub claim
    lti_iss TEXT NOT NULL,            -- LTI issuer URL
    learner_id TEXT NOT NULL REFERENCES learners(id),
    name TEXT,                        -- Cached from LTI claims
    email TEXT,                       -- Cached from LTI claims
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),

    UNIQUE(lti_sub, lti_iss)          -- One mapping per platform user
);

CREATE INDEX idx_lti_mapping_sub_iss ON lti_user_mappings(lti_sub, lti_iss);
CREATE INDEX idx_lti_mapping_learner ON lti_user_mappings(learner_id);
```

This keeps the existing `learners` table untouched and supports:
- Multiple LTI platforms pointing to the same learner
- Standalone (non-LTI) learners continuing to work
- Clean separation of concerns

### SQLAlchemy Model

```python
# services/ltt-core/src/ltt/models/lti_mapping.py

from sqlalchemy import String, Text, DateTime, UniqueConstraint, Index
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from .base import Base


class LTIUserMapping(Base):
    __tablename__ = "lti_user_mappings"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    lti_sub: Mapped[str] = mapped_column(String, nullable=False)
    lti_iss: Mapped[str] = mapped_column(String, nullable=False)
    learner_id: Mapped[str] = mapped_column(
        String, ForeignKey("learners.id"), nullable=False
    )
    name: Mapped[str | None] = mapped_column(Text)
    email: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )

    __table_args__ = (
        UniqueConstraint("lti_sub", "lti_iss", name="uq_lti_sub_iss"),
        Index("idx_lti_mapping_sub_iss", "lti_sub", "lti_iss"),
        Index("idx_lti_mapping_learner", "learner_id"),
    )
```

### Alembic Migration

```bash
PYTHONPATH=services/ltt-core/src uv run alembic revision --autogenerate -m "Add LTI user mappings table"
PYTHONPATH=services/ltt-core/src uv run alembic upgrade head
```

---

## User Mapping Service

### `users.py`

```python
"""
LTI user identity mapping.

Maps LTI sub+iss to internal LTT learner IDs.
Creates new learner records on first LTI launch.
"""

from __future__ import annotations

import json
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ltt.models.learner import LearnerModel
from ltt.models.lti_mapping import LTIUserMapping
from ltt.utils.ids import generate_entity_id


async def get_or_create_lti_learner(
    session: AsyncSession,
    lti_sub: str,
    lti_iss: str,
    name: Optional[str] = None,
    email: Optional[str] = None,
) -> str:
    """
    Map an LTI user to an LTT learner_id.

    If the user has launched before, returns the existing learner_id.
    If this is their first launch, creates a new learner and mapping.

    Returns:
        The LTT learner_id (e.g., "learner-a1b2c3d4")
    """
    # Check for existing mapping
    result = await session.execute(
        select(LTIUserMapping).where(
            LTIUserMapping.lti_sub == lti_sub,
            LTIUserMapping.lti_iss == lti_iss,
        )
    )
    mapping = result.scalar_one_or_none()

    if mapping:
        # Update cached PII if changed
        if name and mapping.name != name:
            mapping.name = name
        if email and mapping.email != email:
            mapping.email = email
        await session.commit()
        return mapping.learner_id

    # First launch: create learner + mapping
    learner_id = generate_entity_id("learner")

    metadata = json.dumps({
        "name": name or "",
        "email": email or "",
        "lti_sub": lti_sub,
        "lti_iss": lti_iss,
        "source": "lti",
    })

    learner = LearnerModel(id=learner_id, learner_metadata=metadata)
    session.add(learner)

    mapping = LTIUserMapping(
        id=generate_entity_id("lti"),
        lti_sub=lti_sub,
        lti_iss=lti_iss,
        learner_id=learner_id,
        name=name,
        email=email,
    )
    session.add(mapping)

    await session.commit()
    return learner_id


async def get_learner_by_lti(
    session: AsyncSession,
    lti_sub: str,
    lti_iss: str,
) -> Optional[str]:
    """Look up learner_id by LTI identity. Returns None if not found."""
    result = await session.execute(
        select(LTIUserMapping.learner_id).where(
            LTIUserMapping.lti_sub == lti_sub,
            LTIUserMapping.lti_iss == lti_iss,
        )
    )
    row = result.scalar_one_or_none()
    return row
```

---

## Mapping Flow

### First LTI Launch

```
Open edX JWT: { sub: "edx-user-42", iss: "https://imbizo.alx-ai-tools.com" }
    │
    ▼
get_or_create_lti_learner()
    │
    ├── SELECT FROM lti_user_mappings WHERE sub='edx-user-42' AND iss=...
    │   → NULL (first time)
    │
    ├── CREATE learner: learner_id = "learner-f8a3b1c2"
    │   metadata = { name: "Alice Smith", source: "lti" }
    │
    ├── CREATE mapping: lti_sub="edx-user-42", learner_id="learner-f8a3b1c2"
    │
    └── return "learner-f8a3b1c2"
```

### Subsequent Launches

```
Open edX JWT: { sub: "edx-user-42", iss: "https://imbizo.alx-ai-tools.com" }
    │
    ▼
get_or_create_lti_learner()
    │
    ├── SELECT FROM lti_user_mappings WHERE sub='edx-user-42' AND iss=...
    │   → mapping.learner_id = "learner-f8a3b1c2"
    │
    └── return "learner-f8a3b1c2"  (same learner, preserved progress)
```

---

## API Changes

### Dual-Mode Authentication

The API supports both LTI-authenticated and standalone requests:

```python
async def resolve_learner_id(request: Request) -> str:
    """
    Resolve learner_id from either:
    1. X-LTI-Launch-Id header (LTI mode)
    2. learner_id in request body/query (standalone mode)
    """
    launch_id = request.headers.get("X-LTI-Launch-Id")

    if launch_id:
        # LTI mode: resolve from cached launch data
        context = resolve_launch(launch_id, get_launch_data_storage())
        if not context:
            raise HTTPException(401, "LTI session expired")

        # Map sub → learner_id
        async with get_session() as session:
            learner_id = await get_learner_by_lti(
                session, context.learner_sub, lti_iss=...
            )
        if not learner_id:
            raise HTTPException(401, "Learner not found")
        return learner_id

    # Standalone mode: use provided learner_id
    # (existing behavior, for dev/testing)
    return get_learner_id_from_request(request)
```

This means:
- **LTI launches** use the `X-LTI-Launch-Id` header -- authenticated and verified
- **Standalone use** continues to work with `learner_id` in request body -- for local dev
- Both paths converge on the same internal `learner_id`, so all services work identically

---

## Privacy Considerations

| Data | Storage | Access |
|---|---|---|
| `lti_sub` | `lti_user_mappings` table | Internal only, never exposed to frontend |
| `name`, `email` | `lti_user_mappings` + `learner_metadata` | Only if platform shares PII (configurable in Open edX) |
| `learner_id` | Frontend state, API calls | Opaque identifier, no PII |

Open edX can be configured to share or withhold PII. Our system works with just the `sub` claim (pseudonymous). Name and email are optional convenience fields.

---

## Multi-Platform Support

The `lti_iss` column ensures we can support multiple Open edX instances or other LMS platforms:

```
imbizo.alx-ai-tools.com  + edx-user-42  →  learner-f8a3b1c2
other-edx.example.com    + edx-user-42  →  learner-d9e7a3b1  (different learner!)
canvas.example.com       + canvas-789   →  learner-c4d5e6f7
```

Same `sub` from different platforms = different learners. This is correct because `sub` is platform-scoped.
