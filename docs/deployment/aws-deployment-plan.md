# AWS Deployment Plan — LTT on ECS Fargate

> Deploy into the existing ALX-AI VPC and infrastructure. LTT gets its own
> database, Redis, and ECS services but reuses networking, the reverse proxy,
> Route53, and Prometheus/Grafana monitoring.

---

## Table of Contents

1. [Architecture Overview](#architecture-overview)
2. [Existing Infrastructure (What We Reuse)](#existing-infrastructure-what-we-reuse)
3. [New Infrastructure (What We Add)](#new-infrastructure-what-we-add)
4. [Design Decisions](#design-decisions)
5. [Environment Strategy](#environment-strategy)
6. [Networking](#networking)
7. [Compute (ECS Fargate)](#compute-ecs-fargate)
8. [Data (RDS + ElastiCache)](#data-rds--elasticache)
9. [Secrets Management](#secrets-management)
10. [Load Balancing & Routing](#load-balancing--routing)
11. [Container Registry (ECR)](#container-registry-ecr)
12. [Dockerfiles](#dockerfiles)
13. [CI/CD Pipeline](#cicd-pipeline)
14. [Monitoring & Logging](#monitoring--logging)
15. [Terraform Structure](#terraform-structure)
16. [Cost Estimate](#cost-estimate)
17. [Implementation Order](#implementation-order)

---

## Architecture Overview

```
                          ┌──────────────────────────────┐
                          │      Open edX (Imbizo)       │
                          │  LTI 1.3 launch + grades     │
                          └──────────┬───────────────────┘
                                     │
                                     ▼
              ┌──────────────────────────────────────────────┐
              │  EXISTING: Reverse Proxy / Bastion (nginx)   │
              │  52.30.100.225 — *.alx-ai-tools.com          │
              │  Certbot SSL, rate limiting, SSE support      │
              │                                              │
              │  mwongozo.alx-ai-tools.com → LTT ALB             │
              │  grafana.alx-ai-tools.com → 10.0.11.4:3000  │
              │  langfuse.alx-ai-tools.com → 10.0.11.6:3000 │
              │  ...                                         │
              └──────────────────┬───────────────────────────┘
                                 │
                   EXISTING VPC: 10.0.0.0/16
                   ┌─────────────┴─────────────┐
                   │                           │
          ┌────────▼────────┐                  │
          │   NEW: LTT ALB  │                  │
          │  Path routing   │                  │
          └──┬──────────┬───┘                  │
             │          │                      │
    /api/* /lti/*    /* (other)                │
             │          │                      │
             ▼          ▼                      │
     ┌────────────┐ ┌────────────┐             │
     │  Backend   │ │  Frontend  │    EXISTING │
     │  FastAPI   │ │  Next.js   │    services │
     │ (Fargate)  │ │ (Fargate)  │    on EC2   │
     └──────┬──┬──┘ └────────────┘             │
            │  │                               │
     ┌──────┘  └──────┐                        │
     ▼                ▼                        │
┌──────────┐   ┌──────────┐     ┌──────────────┤
│ NEW: RDS │   │NEW: Redis│     │EXISTING: RDS │
│PostgreSQL│   │ElastiCach│     │(langfuse,n8n)│
│  (LTT)   │   │  (LTT)   │     │              │
└──────────┘   └──────────┘     └──────────────┘
```

**Key principle: LTT's database is independent.** The existing RDS instance serves
Langfuse and n8n. LTT gets its own RDS instance — different lifecycle, different
backup schedule, different scaling needs. If the monitoring stack's DB has issues,
LTT is unaffected, and vice versa.

---

## Existing Infrastructure (What We Reuse)

All of this lives in the `ALX-AI-monitoring-stack` repo and is already running.

### VPC (`10.0.0.0/16`, eu-west-1)

| Subnet | CIDR | AZ | Contains |
|--------|------|----|----------|
| Public A | `10.0.1.0/24` | eu-west-1a | Reverse proxy, NAT Gateway |
| Public B | `10.0.2.0/24` | eu-west-1b | (available) |
| Private | `10.0.11.0/24` | eu-west-1a | Monitoring, n8n, Langfuse, ClickHouse |
| Database A | `10.0.21.0/24` | eu-west-1a | Existing RDS |
| Database B | `10.0.22.0/24` | eu-west-1b | Existing RDS failover |

**We reuse:** VPC, public subnets, NAT Gateway, internet gateway, route tables.

**We add:** New private subnets for ECS tasks (to avoid IP conflicts with existing
EC2 instances in `10.0.11.0/24`). See [Networking](#networking).

### Reverse Proxy / Bastion (`52.30.100.225`)

- `t3.micro` running **nginx** with **Certbot** (Let's Encrypt auto-renewal)
- Already routes `*.alx-ai-tools.com` subdomains to internal services
- **Already has SSE streaming support**: `proxy_buffering off`, 24h timeouts
- Already has rate limiting, WebSocket support, HTTP→HTTPS redirects
- UFW firewall (ports 22, 80, 443)

**We reuse:** The proxy itself, SSL infrastructure, domain pattern.

**We add:** New `server` block for `mwongozo.alx-ai-tools.com` pointing to the LTT ALB.

### Route53

- Hosted zone for `alx-ai-tools.com`
- Existing A records point subdomains to the reverse proxy EIP

**We add:** `mwongozo.alx-ai-tools.com`, `dev-mwongozo.alx-ai-tools.com`,
`staging-mwongozo.alx-ai-tools.com`. All route through the same proxy and
the ALB differentiates by `Host` header.

### NAT Gateway

- Already provisioned in public subnet A
- Provides outbound internet for private instances

**We reuse as-is.** ECS Fargate tasks in private subnets use the same NAT Gateway
to pull images from ECR and call the Anthropic API. This saves ~$33/mo vs.
creating a second one.

### Monitoring (Grafana + Prometheus)

- Grafana at `10.0.11.4:3000`, Prometheus at `10.0.11.4:9090`
- Prometheus already scrapes cAdvisor from other services

**We add:** Prometheus scrape targets for ECS tasks (via CloudWatch Container
Insights export or a Prometheus ECS service discovery sidecar). CloudWatch Logs
as the primary logging backend, with optional Grafana dashboards on top.

### SSH Access Pattern

```bash
# Bastion hop to any private instance:
ssh -i key.pem \
  -o ProxyCommand='ssh -i key.pem -W %h:%p ubuntu@52.30.100.225' \
  ubuntu@10.0.11.x
```

ECS Fargate tasks don't need SSH — we use `aws ecs execute-command` for debugging.

---

## New Infrastructure (What We Add)

Everything below is **LTT-specific** and deployed via Terraform in this repo.

| Resource | Dev/Staging | Prod | Why independent |
|----------|-------------|------|-----------------|
| **Private subnets** | `10.0.12.0/24`, `10.0.13.0/24` | Same VPC, same subnets | Isolated from EC2 instances in `10.0.11.0/24` |
| **RDS PostgreSQL** | 1 instance (4 DBs) | 1 instance (2 DBs, Multi-AZ) | Own lifecycle, own backups, own scaling |
| **ElastiCache Redis** | 1 node (shared) | 1 node (dedicated) | LTI session storage, independent of per-instance Redis |
| **ALB** | 1 (host routing) | 1 (dedicated) | Path-based routing to ECS |
| **ECS Cluster** | 1 (4 services) | 1 (2 services) | Fargate, no EC2 nodes |
| **ECR** | 2 repos (shared) | Same repos | `ltt-backend`, `ltt-frontend` |
| **Secrets Manager** | Per-env secrets | Per-env secrets | DB passwords, API keys, LTI keys |
| **CloudWatch** | Log groups | Log groups + alarms | Per-service logging |

**Not created:**
- No new VPC (reuse existing)
- No new NAT Gateway (reuse existing)
- No CloudFront
- No MySQL RDS (sql.js runs in-browser)

---

## Design Decisions

### Why deploy into the existing VPC (not a new one)

| Factor | New VPC | Existing VPC |
|--------|---------|-------------|
| **NAT Gateway** | +$33/mo | Already paid for |
| **Reverse proxy** | Need new proxy or peering | Just add an nginx block |
| **Route53** | Same either way | Same |
| **Isolation** | Full network isolation | Separate subnets + security groups |
| **Blast radius** | Zero cross-contamination | A VPC-level outage affects both |
| **Operational cost** | Two VPCs to manage | One |

**Verdict:** Deploy into the existing VPC. At this scale, the NAT Gateway savings
alone ($33/mo) justifies it. We isolate LTT via dedicated subnets and security
groups — ECS tasks can't reach the monitoring EC2 instances, and vice versa.

The only risk is a VPC-level issue (e.g., NAT Gateway failure). This would also
affect the monitoring stack, which we want running during an LTT outage. If this
becomes a concern, we can move prod to its own VPC later.

### Why LTT gets its own RDS (not sharing the monitoring stack's RDS)

The existing RDS (`db.t3.micro`) runs Langfuse and n8n databases.

| Factor | Shared RDS | Independent RDS |
|--------|-----------|-----------------|
| **Cost** | $0 extra | +$12/mo (t4g.micro) |
| **Blast radius** | Langfuse slow query → LTT latency | Fully isolated |
| **Scaling** | Must coordinate with monitoring team | Scale independently |
| **Backups** | Shared schedule, restore affects all | Independent retention/restore |
| **Maintenance windows** | Must align | Own schedule |
| **Connection limits** | Shared pool (micro = 87 max) | Dedicated pool |
| **PostgreSQL version** | Must match (currently 17.5) | Can choose independently |

**Verdict:** Independent RDS. $12/mo is cheap insurance against the monitoring
stack's DB workload interfering with learner experience. Langfuse in particular
can generate heavy write loads during LLM observability bursts.

### Why ECS Fargate over EC2 + Docker Compose (monitoring stack pattern)

The monitoring stack runs each service on a dedicated EC2 instance with Docker
Compose. This works for long-lived internal tools but isn't ideal for LTT:

| Factor | EC2 + Docker Compose | ECS Fargate |
|--------|---------------------|-------------|
| **Zero-downtime deploys** | Manual (stop old, start new) | Built-in rolling update |
| **Health checks + restarts** | Manual (or systemd) | Automatic |
| **Scaling** | Launch new EC2, configure, deploy | `desired_count += 1` |
| **Cost (2 services)** | 2× t3.micro = $18/mo | 2× 0.25 vCPU = $18/mo |
| **Operational burden** | Patch OS, manage Docker, SSH | Near-zero |
| **CI/CD integration** | SSH deploy scripts | `aws ecs update-service` |

**Verdict:** ECS Fargate. Same cost as EC2 but with rolling deploys, auto-restart,
and no server management. The monitoring stack pattern is fine for tools where
downtime during deploys is acceptable — LTT needs better than that.

### Why no CloudFront

- **200 concurrent users** — ALB alone handles this
- **LTI iframe embedding** — CloudFront complicates CSP `frame-ancestors`
- **SSE streaming** — CloudFront can buffer/break Server-Sent Events
- **Existing proxy** — SSL termination already handled by nginx + Certbot

### Why no MySQL RDS

The MySQL database (`md_water_services`) exists for learner SQL exercises. Since
sql.js (SQLite compiled to WASM) is already a dependency and runs entirely
in-browser:

- **Zero server cost** — no RDS instance
- **Perfect isolation** — each learner gets their own in-memory database
- **No connection pooling headaches** — 200 concurrent users ≠ 200 DB connections
- **Trade-off**: SQLite syntax only (acceptable for educational exercises)

### Why ALB path-based routing instead of Next.js proxy

Currently, Next.js proxies `/api/*` and `/lti/*` to the backend via `rewrites()`.
In production, the ALB handles routing directly:

- **Eliminates double-hop** — ALB → backend, not ALB → Next.js → backend
- **Better for SSE** — no intermediate proxy buffering chat streams
- **Independent health checks** — ALB checks each service separately

The Next.js rewrites remain for local development (where there's no ALB).

---

## Environment Strategy

### Domain Scheme

Using subdomains of the existing `alx-ai-tools.com`:

| Environment | URL | Notes |
|-------------|-----|-------|
| Dev | `dev-mwongozo.alx-ai-tools.com` | Auto-deploy on push to `main` |
| Staging | `staging-mwongozo.alx-ai-tools.com` | Manual deploy, mirrors prod config |
| Prod | `mwongozo.alx-ai-tools.com` | Manual deploy with approval |

All three resolve to the reverse proxy EIP (`52.30.100.225`). Nginx routes by
`Host` header to the appropriate ALB.

### Environment Configuration

| Setting | Dev | Staging | Prod |
|---------|-----|---------|------|
| `LTT_ENV` | `dev` | `dev` | `prod` |
| `LTT_AUTH_ENABLED` | `false` | `true` | `true` |
| `LTT_DEBUG` | `true` | `false` | `false` |
| `LTT_CORS_ORIGINS` | `["https://dev-mwongozo..."]` | `["https://staging-mwongozo..."]` | `["https://mwongozo..."]` |
| RDS instance | Shared `db.t4g.micro` | Shared `db.t4g.micro` | Dedicated `db.t4g.small` Multi-AZ |
| Redis node | Shared `cache.t4g.micro` db0 | Shared `cache.t4g.micro` db1 | Dedicated `cache.t4g.micro` |
| Fargate CPU/Memory | 0.25 vCPU / 512 MB | 0.25 vCPU / 512 MB | 0.5 vCPU / 1 GB |
| Desired count | 1 | 1 | 2 |

**Staging mirrors prod security** (`auth_enabled=true`, `debug=false`) — it's the
"prod dress rehearsal".

### What's shared vs. separate

| Resource | Dev + Staging | Prod |
|----------|--------------|------|
| VPC | Existing (shared with monitoring stack) | Same VPC |
| NAT Gateway | Existing (shared) | Same |
| Reverse proxy | Existing (shared) | Same |
| RDS instance | Shared (separate DBs) | Dedicated, Multi-AZ |
| ElastiCache | Shared (db0 vs db1) | Dedicated |
| ALB | Shared (host routing) | Dedicated |
| ECS cluster | Shared (separate services) | Dedicated |
| ECR | Global (shared images) | Same |
| Secrets | Per-environment | Per-environment |

---

## Networking

### New subnets in the existing VPC

We add two private subnets for ECS tasks, separate from the existing `10.0.11.0/24`
where EC2 instances live:

```
EXISTING VPC: 10.0.0.0/16
│
├── EXISTING: Public Subnets
│   ├── 10.0.1.0/24  (eu-west-1a) — Reverse proxy, NAT GW
│   └── 10.0.2.0/24  (eu-west-1b)
│
├── EXISTING: Private Subnet
│   └── 10.0.11.0/24 (eu-west-1a) — Monitoring, n8n, Langfuse, ClickHouse
│
├── NEW: LTT Private Subnets (ECS Fargate + ElastiCache)
│   ├── 10.0.12.0/24 (eu-west-1a)
│   └── 10.0.13.0/24 (eu-west-1b)
│
├── EXISTING: Database Subnets
│   ├── 10.0.21.0/24 (eu-west-1a) — Existing RDS (langfuse, n8n)
│   └── 10.0.22.0/24 (eu-west-1b)
│
└── NEW: LTT Database Subnets (LTT RDS only)
    ├── 10.0.23.0/24 (eu-west-1a)
    └── 10.0.24.0/24 (eu-west-1b)
```

### Route Table

The new private subnets use the **existing** route table that sends `0.0.0.0/0`
through the existing NAT Gateway. No new route tables needed.

### Security Groups

| Security Group | Inbound | Outbound |
|---------------|---------|----------|
| `ltt-alb` | 80/443 from reverse proxy SG (`52.30.100.225`) | All to VPC |
| `ltt-ecs` | Dynamic ports from `ltt-alb` only | All (ECR pull, Anthropic API) |
| `ltt-rds` | 5432 from `ltt-ecs` only | None |
| `ltt-redis` | 6379 from `ltt-ecs` only | None |

**Key isolation:** `ltt-ecs` cannot reach `10.0.11.0/24` (monitoring instances),
and monitoring instances cannot reach `ltt-rds` or `ltt-redis`. Security groups
are the boundary, not subnets alone.

---

## Compute (ECS Fargate)

### Task Definitions

**Backend (FastAPI):**

```json
{
  "family": "ltt-backend",
  "cpu": "256",
  "memory": "512",
  "networkMode": "awsvpc",
  "containerDefinitions": [
    {
      "name": "backend",
      "image": "{account_id}.dkr.ecr.eu-west-1.amazonaws.com/ltt-backend:{tag}",
      "portMappings": [{ "containerPort": 8000, "protocol": "tcp" }],
      "environment": [
        { "name": "LTT_ENV", "value": "{env}" },
        { "name": "LTT_FRONTEND_URL", "value": "https://mwongozo.alx-ai-tools.com" },
        { "name": "LTT_CORS_ORIGINS", "value": "[\"https://mwongozo.alx-ai-tools.com\"]" },
        { "name": "LTT_CSP_FRAME_ANCESTORS", "value": "'self' https://imbizo.alx-ai-tools.com" },
        { "name": "LTT_LTI_PLATFORM_URL", "value": "https://imbizo.alx-ai-tools.com" }
      ],
      "secrets": [
        { "name": "LTT_DATABASE_URL", "valueFrom": "arn:aws:secretsmanager:..." },
        { "name": "LTT_CHECKPOINT_DATABASE_URL", "valueFrom": "arn:aws:secretsmanager:..." },
        { "name": "LTT_REDIS_URL", "valueFrom": "arn:aws:secretsmanager:..." },
        { "name": "LTT_ANTHROPIC_API_KEY", "valueFrom": "arn:aws:secretsmanager:..." },
        { "name": "LTT_LTI_PRIVATE_KEY", "valueFrom": "arn:aws:secretsmanager:..." },
        { "name": "LTT_LTI_PUBLIC_KEY", "valueFrom": "arn:aws:secretsmanager:..." },
        { "name": "LTT_LTI_PLATFORM_CONFIG", "valueFrom": "arn:aws:secretsmanager:..." }
      ],
      "healthCheck": {
        "command": ["CMD-SHELL", "curl -f http://localhost:8000/health || exit 1"],
        "interval": 30,
        "timeout": 5,
        "retries": 3
      },
      "logConfiguration": {
        "logDriver": "awslogs",
        "options": {
          "awslogs-group": "/ecs/ltt-{env}-backend",
          "awslogs-region": "eu-west-1",
          "awslogs-stream-prefix": "ecs"
        }
      }
    }
  ]
}
```

**Frontend (Next.js):**

```json
{
  "family": "ltt-frontend",
  "cpu": "256",
  "memory": "512",
  "networkMode": "awsvpc",
  "containerDefinitions": [
    {
      "name": "frontend",
      "image": "{account_id}.dkr.ecr.eu-west-1.amazonaws.com/ltt-frontend:{tag}",
      "portMappings": [{ "containerPort": 3000, "protocol": "tcp" }],
      "environment": [
        { "name": "LTI_PLATFORM_URL", "value": "https://imbizo.alx-ai-tools.com" },
        { "name": "NEXT_PUBLIC_API_URL", "value": "" }
      ],
      "healthCheck": {
        "command": ["CMD-SHELL", "wget -q --spider http://localhost:3000/ || exit 1"],
        "interval": 30,
        "timeout": 5,
        "retries": 3
      },
      "logConfiguration": {
        "logDriver": "awslogs",
        "options": {
          "awslogs-group": "/ecs/ltt-{env}-frontend",
          "awslogs-region": "eu-west-1",
          "awslogs-stream-prefix": "ecs"
        }
      }
    }
  ]
}
```

### Auto-Scaling (prod only)

```hcl
resource "aws_appautoscaling_target" "backend" {
  max_capacity       = 4
  min_capacity       = 2
  resource_id        = "service/${cluster_name}/${service_name}"
  scalable_dimension = "ecs:service:DesiredCount"
  service_namespace  = "ecs"
}

resource "aws_appautoscaling_policy" "backend_cpu" {
  name               = "cpu-tracking"
  policy_type        = "TargetTrackingScaling"
  resource_id        = aws_appautoscaling_target.backend.resource_id
  scalable_dimension = aws_appautoscaling_target.backend.scalable_dimension
  service_namespace  = aws_appautoscaling_target.backend.service_namespace

  target_tracking_scaling_policy_configuration {
    predefined_metric_specification {
      predefined_metric_type = "ECSServiceAverageCPUUtilization"
    }
    target_value = 70.0
  }
}
```

Scale on CPU: 2 baseline, up to 4 at 70%. At 200 concurrent users with 0.5 vCPU
per task, 2 tasks is sufficient. Scaling to 4 handles unexpected spikes.

### ECS Exec (for debugging)

```bash
# Shell into a running Fargate task (replaces SSH)
aws ecs execute-command \
  --cluster ltt-dev \
  --task <task-id> \
  --container backend \
  --interactive \
  --command "/bin/sh"
```

Requires `enableExecuteCommand: true` on the ECS service and an SSM VPC endpoint
or NAT Gateway (we have NAT).

---

## Data (RDS + ElastiCache)

### RDS PostgreSQL — LTT-specific (independent from monitoring stack RDS)

**Dev/Staging (shared instance, separate databases):**

| Parameter | Value |
|-----------|-------|
| Engine | PostgreSQL 17 |
| Instance class | `db.t4g.micro` (2 vCPU, 1 GB RAM) |
| Storage | 20 GB gp3 |
| Multi-AZ | No |
| Backup retention | 7 days |
| Encryption | Yes (AWS-managed KMS key) |
| Public access | No (database subnet only) |
| Subnet group | `10.0.23.0/24`, `10.0.24.0/24` (new LTT DB subnets) |

Databases on this instance:
- `ltt_dev` + `ltt_dev_checkpoints`
- `ltt_staging` + `ltt_staging_checkpoints`

**Production (dedicated instance):**

| Parameter | Value |
|-----------|-------|
| Engine | PostgreSQL 17 |
| Instance class | `db.t4g.small` (2 vCPU, 2 GB RAM) |
| Storage | 20 GB gp3 (auto-scaling to 100 GB) |
| Multi-AZ | **Yes** |
| Backup retention | 14 days |
| Encryption | Yes (customer-managed KMS key) |
| Public access | No |
| Performance Insights | Enabled |
| Subnet group | Same `10.0.23.0/24`, `10.0.24.0/24` |

**Why `t4g.small` for prod:** 5000 users, ~200 concurrent. Each chat message = 1-3
queries. At peak: ~200 queries/second. `t4g.micro` handles this but has no
headroom. `t4g.small` gives 2x RAM for connection pooling and query caching.

### ElastiCache Redis — LTT-specific

**Dev/Staging (shared node):**

| Parameter | Value |
|-----------|-------|
| Engine | Redis 7 |
| Node type | `cache.t4g.micro` |
| Replicas | 0 |
| Encryption in-transit | Yes |
| Auth token | Yes (from Secrets Manager) |
| Subnet group | `10.0.12.0/24`, `10.0.13.0/24` (LTT private subnets) |

Dev uses DB 0, staging uses DB 1.

**Production (dedicated node):**

Same spec as above, but a separate instance. If Redis goes down, learners
re-launch from Open edX — inconvenient, not catastrophic. No replicas needed.

### Database Initialization

Alembic migrations run as an ECS one-off task before each deployment:

```bash
aws ecs run-task \
  --cluster ltt-{env} \
  --task-definition ltt-{env}-migrate \
  --launch-type FARGATE \
  --network-configuration "awsvpcConfiguration={subnets=[...],securityGroups=[...]}" \
  --overrides '{"containerOverrides":[{"name":"migrate","command":["alembic","upgrade","head"]}]}'
```

A `ltt-migrate` task definition uses the same backend image but runs the migration
command instead of uvicorn.

---

## Secrets Management

### AWS Secrets Manager

Each environment gets its own secrets:

```
ltt/{env}/database_url          → postgresql+asyncpg://ltt_user:...@ltt-{env}.xxx.rds.amazonaws.com:5432/ltt_{env}
ltt/{env}/checkpoint_db_url     → postgresql://ltt_user:...@ltt-{env}.xxx.rds.amazonaws.com:5432/ltt_{env}_checkpoints
ltt/{env}/redis_url             → rediss://...@ltt-{env}.xxx.cache.amazonaws.com:6379/0
ltt/{env}/anthropic_api_key     → sk-ant-...
ltt/{env}/lti_private_key       → -----BEGIN RSA PRIVATE KEY-----...
ltt/{env}/lti_public_key        → -----BEGIN PUBLIC KEY-----...
ltt/{env}/lti_platform_config   → {"https://imbizo...": [...]}
```

ECS injects these as environment variables at container start via the `secrets`
block in the task definition. No secrets in Terraform state or Docker images.

### Rotation

- **Database passwords:** Secrets Manager automatic rotation (Lambda)
- **Redis auth token:** Manual (recreate node + update secret)
- **LTI RSA keys:** Manual (generate keypair, update JWKS, update Open edX)
- **Anthropic API key:** Manual (Anthropic console)

---

## Load Balancing & Routing

### ALB Configuration

**Dev/Staging ALB (shared, host + path routing):**

```
Listener: HTTP:80 (ALB terminates at HTTP — nginx handles SSL)
  ├── Rule: Host = dev-mwongozo.alx-ai-tools.com, Path = /api/* OR /lti/* OR /health
  │   → Target Group: dev-backend (port 8000)
  ├── Rule: Host = dev-mwongozo.alx-ai-tools.com, Path = /*
  │   → Target Group: dev-frontend (port 3000)
  ├── Rule: Host = staging-mwongozo.alx-ai-tools.com, Path = /api/* OR /lti/* OR /health
  │   → Target Group: staging-backend (port 8000)
  └── Rule: Host = staging-mwongozo.alx-ai-tools.com, Path = /*
      → Target Group: staging-frontend (port 3000)
```

**Prod ALB (dedicated, path routing only):**

```
Listener: HTTP:80
  ├── Rule: Path = /api/* OR /lti/* OR /health
  │   → Target Group: prod-backend (port 8000)
  └── Default
      → Target Group: prod-frontend (port 3000)
```

**Note:** ALBs listen on HTTP:80, not HTTPS. SSL termination happens at the nginx
reverse proxy (Certbot). The ALB sits in the private subnet — traffic between
nginx and ALB is VPC-internal. This avoids needing ACM certificates for internal
traffic.

### Health Checks

| Target Group | Path | Interval | Healthy threshold |
|-------------|------|----------|-------------------|
| Backend | `/health` | 30s | 2 |
| Frontend | `/` | 30s | 2 |

### Nginx Configuration (added to existing reverse proxy)

```nginx
# LTT — production
upstream ltt_prod_alb {
    server ltt-prod-alb-xxxx.eu-west-1.elb.amazonaws.com:80;
}

server {
    listen 443 ssl;
    server_name mwongozo.alx-ai-tools.com;

    ssl_certificate /etc/letsencrypt/live/mwongozo.alx-ai-tools.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/mwongozo.alx-ai-tools.com/privkey.pem;

    # Rate limiting
    limit_req zone=general burst=20 nodelay;

    location / {
        proxy_pass http://ltt_prod_alb;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;

        # SSE support (critical for chat streaming)
        proxy_http_version 1.1;
        proxy_buffering off;
        proxy_cache off;
        proxy_read_timeout 300s;
    }
}

# LTT — dev + staging (same pattern, different upstream + server_name)
upstream ltt_nonprod_alb {
    server ltt-nonprod-alb-xxxx.eu-west-1.elb.amazonaws.com:80;
}

server {
    listen 443 ssl;
    server_name dev-mwongozo.alx-ai-tools.com staging-mwongozo.alx-ai-tools.com;
    # ... same proxy config ...
}
```

---

## Container Registry (ECR)

Two repositories, shared across all environments:

```
{account_id}.dkr.ecr.eu-west-1.amazonaws.com/ltt-backend
{account_id}.dkr.ecr.eu-west-1.amazonaws.com/ltt-frontend
```

### Image Tagging

```
ltt-backend:dev-abc1234       ← git short SHA
ltt-backend:staging-abc1234
ltt-backend:prod-abc1234
ltt-backend:latest            ← latest build from main
```

### Lifecycle Policy

- Keep last 10 images per tag prefix
- Delete untagged images after 7 days

---

## Dockerfiles

### Backend (`Dockerfile` at repo root, context = repo root)

```dockerfile
FROM python:3.12-slim AS base

RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

WORKDIR /app

# Copy workspace root files for uv
COPY pyproject.toml uv.lock ./

# Copy services
COPY services/ltt-core/ services/ltt-core/
COPY services/api-server/ services/api-server/
COPY services/agent-tutor/ services/agent-tutor/

# Copy content (project ingestion) and Alembic
COPY content/ content/
COPY alembic.ini ./

# Install deps
RUN uv sync --frozen --no-dev

# LTI public key (private key injected via Secrets Manager at runtime)
COPY configs/lti/public.key configs/lti/public.key

ENV PYTHONPATH=/app/services/ltt-core/src
ENV PATH="/app/.venv/bin:$PATH"

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

CMD ["uvicorn", "api.app:app", "--host", "0.0.0.0", "--port", "8000", \
     "--app-dir", "services/api-server/src", "--workers", "2"]
```

### Frontend (`apps/web/Dockerfile`, context = `apps/web/`)

```dockerfile
FROM node:20-alpine AS deps
WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci --omit=dev

FROM node:20-alpine AS builder
WORKDIR /app
COPY . .
COPY --from=deps /app/node_modules ./node_modules
ENV NEXT_TELEMETRY_DISABLED=1
RUN npm run build

FROM node:20-alpine AS runner
WORKDIR /app
ENV NODE_ENV=production
ENV NEXT_TELEMETRY_DISABLED=1

COPY --from=builder /app/.next/standalone ./
COPY --from=builder /app/.next/static ./.next/static
COPY --from=builder /app/public ./public

EXPOSE 3000

HEALTHCHECK --interval=30s --timeout=5s --retries=3 \
    CMD wget -q --spider http://localhost:3000/ || exit 1

CMD ["node", "server.js"]
```

**Required change:** Add `output: "standalone"` to `next.config.ts` for the
standalone Node.js server output.

### Migration Task

Same backend image, different command:

```hcl
command = ["alembic", "upgrade", "head"]
```

---

## CI/CD Pipeline

### Build & Deploy Flow

```
Push to main ──→ Tests pass ──→ Build images ──→ Push to ECR ──→ Deploy dev
                                                                      │
Manual trigger (staging) ─────────────────────────────── Deploy staging │
Manual trigger (prod, with approval) ──────────────────── Deploy prod  │
```

### deploy.yml (new GitHub Actions workflow)

```yaml
name: Deploy

on:
  push:
    branches: [main]
  workflow_dispatch:
    inputs:
      environment:
        description: 'Target environment'
        required: true
        type: choice
        options: [staging, prod]

jobs:
  build:
    runs-on: ubuntu-latest
    permissions:
      id-token: write
      contents: read
    outputs:
      image_tag: ${{ steps.meta.outputs.tag }}
    steps:
      - uses: actions/checkout@v4

      - uses: aws-actions/configure-aws-credentials@v4
        with:
          role-to-arn: arn:aws:iam::{account}:role/github-actions-deploy
          aws-region: eu-west-1

      - uses: aws-actions/amazon-ecr-login@v2

      - id: meta
        run: echo "tag=${GITHUB_SHA::7}" >> "$GITHUB_OUTPUT"

      - name: Build and push backend
        run: |
          docker build -f Dockerfile.backend -t $ECR_BACKEND:${{ steps.meta.outputs.tag }} .
          docker push $ECR_BACKEND:${{ steps.meta.outputs.tag }}

      - name: Build and push frontend
        run: |
          docker build -f apps/web/Dockerfile -t $ECR_FRONTEND:${{ steps.meta.outputs.tag }} apps/web/
          docker push $ECR_FRONTEND:${{ steps.meta.outputs.tag }}

  deploy-dev:
    if: github.event_name == 'push'
    needs: build
    uses: ./.github/workflows/deploy-env.yml
    with:
      environment: dev
      image_tag: ${{ needs.build.outputs.image_tag }}

  deploy-target:
    if: github.event_name == 'workflow_dispatch'
    needs: build
    uses: ./.github/workflows/deploy-env.yml
    with:
      environment: ${{ inputs.environment }}
      image_tag: ${{ needs.build.outputs.image_tag }}
```

### Deployment Strategy

| Environment | Trigger | Strategy |
|-------------|---------|----------|
| Dev | Auto on push to `main` | Rolling (1 task) |
| Staging | Manual | Rolling |
| Prod | Manual with approval | Rolling (min 1 healthy, max 200%) |

---

## Monitoring & Logging

### CloudWatch Logs

| Log Group | Retention |
|-----------|-----------|
| `/ecs/ltt-dev-backend` | 30 days |
| `/ecs/ltt-dev-frontend` | 30 days |
| `/ecs/ltt-staging-backend` | 30 days |
| `/ecs/ltt-staging-frontend` | 30 days |
| `/ecs/ltt-prod-backend` | 90 days |
| `/ecs/ltt-prod-frontend` | 90 days |

### CloudWatch Alarms (prod only)

| Alarm | Metric | Threshold | Action |
|-------|--------|-----------|--------|
| High CPU | ECS CPU utilization | >80% for 5 min | SNS → email |
| High Memory | ECS memory utilization | >85% for 5 min | SNS → email |
| 5xx errors | ALB HTTP 5xx count | >10 in 5 min | SNS → email |
| Unhealthy targets | ALB unhealthy hosts | >0 for 5 min | SNS → email |
| RDS connections | DatabaseConnections | >80% of max | SNS → email |
| RDS CPU | CPUUtilization | >80% for 10 min | SNS → email |

### Prometheus/Grafana Integration (existing stack)

The existing Prometheus at `10.0.11.4:9090` can scrape ECS task metrics via
CloudWatch Container Insights or a Prometheus ECS service discovery config.
Add a Grafana dashboard for LTT alongside the existing service dashboards.

---

## Terraform Structure

```
infrastructure/terraform/
├── modules/
│   ├── ltt-networking/        # New subnets, security groups (in existing VPC)
│   │   ├── main.tf
│   │   ├── variables.tf       # vpc_id, existing route_table_id
│   │   └── outputs.tf         # subnet_ids, sg_ids
│   │
│   ├── ltt-rds/               # LTT's own RDS instance
│   │   ├── main.tf
│   │   ├── variables.tf       # instance_class, multi_az, db_names
│   │   └── outputs.tf         # endpoint, port
│   │
│   ├── ltt-elasticache/       # LTT's own Redis
│   │   ├── main.tf
│   │   ├── variables.tf
│   │   └── outputs.tf         # endpoint, port
│   │
│   ├── ltt-alb/               # ALB, listeners, target groups, routing rules
│   │   ├── main.tf
│   │   ├── variables.tf
│   │   └── outputs.tf         # alb_dns, target_group_arns
│   │
│   ├── ltt-ecs/               # Cluster, services, task definitions, IAM
│   │   ├── main.tf
│   │   ├── variables.tf
│   │   └── outputs.tf         # service_names, cluster_arn, sg_id
│   │
│   ├── ltt-ecr/               # Container repositories
│   │   ├── main.tf
│   │   ├── variables.tf
│   │   └── outputs.tf         # repository_urls
│   │
│   ├── ltt-secrets/           # Secrets Manager (shells — values set manually)
│   │   ├── main.tf
│   │   ├── variables.tf
│   │   └── outputs.tf         # secret_arns
│   │
│   └── ltt-monitoring/        # CloudWatch log groups, alarms, SNS
│       ├── main.tf
│       ├── variables.tf
│       └── outputs.tf
│
├── environments/
│   ├── shared/                # ECR repos (used by all envs)
│   │   ├── main.tf
│   │   ├── backend.tf         # S3 state backend
│   │   ├── providers.tf
│   │   └── terraform.tfvars
│   │
│   ├── dev-staging/           # Subnets + RDS + Redis + ALB + ECS (×2 envs)
│   │   ├── main.tf
│   │   ├── backend.tf
│   │   ├── providers.tf
│   │   ├── variables.tf
│   │   └── terraform.tfvars
│   │
│   └── prod/                  # Subnets + RDS + Redis + ALB + ECS
│       ├── main.tf
│       ├── backend.tf
│       ├── providers.tf
│       ├── variables.tf
│       └── terraform.tfvars
│
└── README.md
```

### Key: referencing existing infrastructure

The `dev-staging/main.tf` references the existing VPC by ID (from Terraform remote
state or data source), not by creating a new one:

```hcl
# Look up existing VPC from the monitoring stack
data "aws_vpc" "existing" {
  filter {
    name   = "tag:Name"
    values = ["monitoring-stack-prod-vpc"]  # or by VPC ID
  }
}

data "aws_route_table" "private" {
  filter {
    name   = "tag:Name"
    values = ["monitoring-stack-prod-private-rt"]
  }
}

# Create LTT-specific subnets in the existing VPC
module "networking" {
  source = "../../modules/ltt-networking"

  vpc_id              = data.aws_vpc.existing.id
  private_route_table = data.aws_route_table.private.id
  private_cidrs       = ["10.0.12.0/24", "10.0.13.0/24"]
  database_cidrs      = ["10.0.23.0/24", "10.0.24.0/24"]
  azs                 = ["eu-west-1a", "eu-west-1b"]
  reverse_proxy_sg_id = data.aws_security_group.reverse_proxy.id
}

# LTT's own RDS (independent from monitoring stack RDS)
module "rds" {
  source = "../../modules/ltt-rds"

  name_prefix       = "ltt-nonprod"
  vpc_id            = data.aws_vpc.existing.id
  subnet_ids        = module.networking.database_subnet_ids
  allowed_sg_ids    = [module.ecs_dev.sg_id, module.ecs_staging.sg_id]
  instance_class    = "db.t4g.micro"
  allocated_storage = 20
  multi_az          = false
}

# LTT's own Redis
module "redis" {
  source = "../../modules/ltt-elasticache"

  name_prefix    = "ltt-nonprod"
  vpc_id         = data.aws_vpc.existing.id
  subnet_ids     = module.networking.private_subnet_ids
  allowed_sg_ids = [module.ecs_dev.sg_id, module.ecs_staging.sg_id]
  node_type      = "cache.t4g.micro"
}

# ALB in public subnets (existing)
data "aws_subnets" "public" {
  filter {
    name   = "tag:Name"
    values = ["monitoring-stack-prod-public-*"]
  }
}

module "alb" {
  source = "../../modules/ltt-alb"

  name_prefix    = "ltt-nonprod"
  vpc_id         = data.aws_vpc.existing.id
  public_subnets = data.aws_subnets.public.ids
  proxy_sg_id    = data.aws_security_group.reverse_proxy.id

  routing_rules = {
    dev = {
      host     = "dev-mwongozo.alx-ai-tools.com"
      backends = { api = module.ecs_dev.backend_tg_arn, web = module.ecs_dev.frontend_tg_arn }
    }
    staging = {
      host     = "staging-mwongozo.alx-ai-tools.com"
      backends = { api = module.ecs_staging.backend_tg_arn, web = module.ecs_staging.frontend_tg_arn }
    }
  }
}

# ECS services
module "ecs_dev" {
  source = "../../modules/ltt-ecs"

  name_prefix     = "ltt-dev"
  vpc_id          = data.aws_vpc.existing.id
  private_subnets = module.networking.private_subnet_ids
  alb_sg_id       = module.alb.sg_id
  backend_image   = "${var.ecr_backend_url}:dev-latest"
  frontend_image  = "${var.ecr_frontend_url}:dev-latest"
  cpu             = 256
  memory          = 512
  desired_count   = 1
  secret_arns     = module.secrets_dev.arns

  env_vars = {
    LTT_ENV          = "dev"
    LTT_AUTH_ENABLED = "false"
    LTT_DEBUG        = "true"
    # ...
  }
}
```

### State Management

```hcl
terraform {
  backend "s3" {
    bucket         = "alx-monitoring-terraform-state-411683670812"
    key            = "ltt/dev-staging/terraform.tfstate"
    region         = "eu-west-1"
    dynamodb_table = "terraform-state-locks"
    encrypt        = true
  }
}
```

State bucket and DynamoDB lock table are created once manually (or in the `shared`
workspace).

---

## Cost Estimate

### Monthly (USD, eu-west-1)

| Resource | Dev/Staging | Prod | Notes |
|----------|-------------|------|-------|
| **ECS Fargate** | | | |
| 4 tasks × 0.25 vCPU | $29.20 | — | 2 services × 2 envs |
| 2 tasks × 0.5 vCPU | — | $29.20 | Backend + frontend |
| 4 tasks × 512 MB | $12.85 | — | |
| 2 tasks × 1 GB | — | $12.85 | |
| **RDS PostgreSQL** | | | |
| `db.t4g.micro` single-AZ | $12.41 | — | LTT's own instance |
| `db.t4g.small` Multi-AZ | — | $49.06 | LTT's own instance |
| Storage (20 GB gp3) | $2.30 | $2.30 | |
| **ElastiCache Redis** | | | |
| `cache.t4g.micro` | $11.52 | $11.52 | |
| **ALB** | | | |
| Fixed hourly | $16.43 | $16.43 | |
| LCU (low traffic) | ~$3.00 | ~$5.00 | |
| **NAT Gateway** | — | — | **Already paid for** |
| **Secrets Manager** | $3.20 | $3.20 | ~8 secrets × $0.40 |
| **CloudWatch** | $2.50 | $2.50 | ~5 GB logs |
| **ECR** | $0.50 | — | Shared |
| | | | |
| **Subtotal** | **~$94** | **~$132** | |
| **Total** | | **~$226/mo** | |

**Savings vs. greenfield:** ~$66/mo saved by reusing VPC + NAT Gateway.

### Cost Optimization

1. **Fargate Savings Plans** (1-year commit): ~50% savings on compute → saves ~$35/mo
2. **RDS Reserved Instance** (1-year, no upfront): ~35% savings on prod RDS → saves ~$17/mo
3. **With reservations: ~$175/mo total**

---

## Implementation Order

```
Phase 1: Foundation (Week 1)
  1.1  Set up GitHub Actions OIDC in AWS (IAM provider + deploy role)
  1.2  Write Terraform modules: ltt-networking, ltt-ecr, ltt-secrets
       (State bucket + DynamoDB lock table already exist)
  1.3  Apply shared workspace (ECR repos)
  1.4  Write Dockerfiles for backend and frontend
  1.5  Add output: "standalone" to next.config.ts
  1.6  Test Docker builds locally

Phase 2: Dev Environment (Week 2)
  2.1  Write Terraform modules: ltt-rds, ltt-elasticache, ltt-alb, ltt-ecs, ltt-monitoring
  2.2  Apply dev-staging workspace
  2.3  Push images to ECR manually
  2.4  Run migrations via ECS run-task
  2.5  Add nginx server block to reverse proxy (dev-mwongozo.alx-ai-tools.com)
  2.6  Add Route53 record for dev-mwongozo.alx-ai-tools.com
  2.7  Certbot: generate SSL cert for dev-mwongozo.alx-ai-tools.com
  2.8  Verify: Open edX → LTI launch → LTT workspace

Phase 3: CI/CD (Week 2-3)
  3.1  Create IAM role for GitHub Actions (OIDC federation)
  3.2  Write deploy.yml + deploy-env.yml workflows
  3.3  Test auto-deploy to dev on push to main
  3.4  Test manual deploy to staging

Phase 4: Production (Week 3)
  4.1  Apply prod workspace (dedicated RDS Multi-AZ, dedicated Redis)
  4.2  Generate production RSA keys for LTI
  4.3  Populate prod secrets in Secrets Manager
  4.4  Add nginx server block for mwongozo.alx-ai-tools.com
  4.5  Register LTI tool in prod Open edX
  4.6  Deploy and smoke test
  4.7  Set up CloudWatch alarms + SNS email notifications

Phase 5: Hardening (Week 4)
  5.1  Complete production hardening phases 2-5 (auth middleware, stateless agents)
  5.2  Enable auth_enabled=true in staging, test full LTI flow
  5.3  Deploy hardened code to prod
  5.4  Test LTI flow end-to-end with real Open edX
```

---

## Pre-Deployment Checklist

- [ ] `output: "standalone"` added to `next.config.ts`
- [ ] Next.js rewrites conditionally disabled when `NEXT_PUBLIC_API_URL` is empty
- [ ] `/health` endpoint returns DB + Redis connectivity status
- [ ] Alembic migrations run cleanly on empty database
- [ ] Docker images build and run locally
- [ ] LTI RSA keypair generated for production (separate from dev keys)
- [ ] LTI tool registered in Open edX with production URLs
- [ ] Secrets populated in AWS Secrets Manager
- [ ] Nginx reverse proxy configured with `proxy_buffering off` for SSE
- [ ] Certbot SSL certs generated for all LTT subdomains
- [ ] Route53 records created
- [ ] CORS origins restricted to production domain
- [ ] CSP `frame-ancestors` restricted to Open edX domain
- [ ] `LTT_AUTH_ENABLED=true` enforced in prod
- [ ] CloudWatch alarms configured and tested
- [ ] RDS backup/restore tested

---

## Resolved Questions

1. **Domain**: `mwongozo.alx-ai-tools.com` — "guide" / "the one who shows the path" in Swahili.
   - Dev: `dev-mwongozo.alx-ai-tools.com`
   - Staging: `staging-mwongozo.alx-ai-tools.com`
   - Prod: `mwongozo.alx-ai-tools.com`

2. **GitHub OIDC**: **Does not exist.** The monitoring stack has no GitHub Actions
   workflows or OIDC provider. We create this from scratch in LTT's `shared`
   Terraform workspace: `aws_iam_openid_connect_provider` for
   `token.actions.githubusercontent.com` + an IAM role that GitHub Actions assumes
   for ECR push and ECS deploy.

3. **Terraform state**: Reuse the existing bucket and lock table:
   - **Bucket:** `alx-monitoring-terraform-state-411683670812`
   - **DynamoDB:** `terraform-state-locks`
   - **Region:** `eu-west-1`
   - LTT uses a different key prefix: `ltt/shared/`, `ltt/dev-staging/`, `ltt/prod/`

4. **Reverse proxy**: Managed by the monitoring stack's Terraform (template file
   rendered during `terraform apply`). May be out of sync with what's actually on
   the box. **LTT Terraform does NOT touch the reverse proxy.** Adding the
   `mwongozo.alx-ai-tools.com` server block is done either:
   - **(a) Safe**: SSH to bastion, manually add the nginx block, `nginx -t && systemctl reload nginx`
   - **(b) Proper**: Add the block to the monitoring stack's nginx template,
     verify state is in sync (`terraform plan`), then apply
   - Either way, this is a monitoring stack concern, documented here for reference.

5. **Open edX VPC**: Not blocking. All traffic routes through the reverse proxy,
   so the ALB only needs to accept traffic from the proxy's security group
   (`52.30.100.225`). No VPC peering with Open edX needed.
