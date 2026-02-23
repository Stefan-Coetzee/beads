# Infrastructure

> Docker services, database setup, and deployment configuration.

---

## Docker Services

Defined in [docker/docker-compose.yml](docker/docker-compose.yml):

| Service | Image | Port | Purpose |
|---------|-------|------|---------|
| **PostgreSQL** | `postgres:17-alpine` | 5432 | Primary database (tasks, learners, progress, LTI mappings) |
| **MySQL** | `mysql:8.0` | 3306 | Learner-facing SQL database (Maji Ndogo water data) |
| **Redis** | `redis:7-alpine` | 6379 | LTI launch state cache (nonces, sessions) |

### Default credentials

| Service | User | Password | Database |
|---------|------|----------|----------|
| PostgreSQL | `ltt_user` | `ltt_password` | `ltt_dev` |
| MySQL | `learner` | `learner_password` | `md_water_services` |
| Redis | — | — | — |

---

## Quick Start

```bash
# Start all services
docker compose up -d

# Start specific services
docker compose up -d postgres redis    # LTI dev (no MySQL needed)
docker compose up -d postgres          # Core dev only

# Check status
docker compose ps

# View logs
docker compose logs -f postgres

# Stop
docker compose down

# Reset (destroy volumes)
docker compose down -v
```

---

## Volumes

Data persists across restarts via named volumes:

- `postgres_data` — PostgreSQL data directory
- `mysql_data` — MySQL data directory
- `redis_data` — Redis persistence (RDB snapshots)

---

## Production Notes

See [docs/lti/10-production-checklist.md](../docs/lti/10-production-checklist.md) for:

- Redis persistence (AOF/RDB) and password configuration
- PostgreSQL production credentials
- Tunnel replacement with static domain
- Health check hardening
