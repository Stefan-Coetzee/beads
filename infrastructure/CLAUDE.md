# Infrastructure — Agent Reference

Quick reference for any agent working with this infrastructure.

---

## AWS Account

| | |
|---|---|
| **Account ID** | `411683670812` |
| **Region** | `eu-west-1` |
| **VPC** | `monitoring-stack-prod-vpc` — `vpc-0aad56dd2ddd64608` — `10.0.0.0/16` |

---

## Key Resources

### Bastion / Reverse Proxy
| | |
|---|---|
| **IP** | `52.30.100.225` |
| **Role** | nginx reverse proxy + SSL termination for all apps |
| **Nginx config** | `/etc/nginx/conf.d/ltt.conf` |
| **Instance ID** | `i-0c5d6100078600c18` (t3.micro) |
| **Security group** | `monitoring-stack-prod-reverse-proxy-sg` (`sg-0af12595896ca60cc`) |
| **Not Terraform-managed** | Must be updated manually — see `tools/scripts/gen-nginx-config.sh` |

### Domains
| Environment | URL | ALB |
|---|---|---|
| dev | `dev-mwongozo.alx-ai-tools.com` | `ltt-nonprod` |
| staging | `staging-mwongozo.alx-ai-tools.com` | `ltt-nonprod` |
| prod | `mwongozo.alx-ai-tools.com` | `ltt-prod` |
| LTI platform (Open edX) | `imbizo.alx-ai-tools.com` | not LTT |

### Terraform State
| | |
|---|---|
| **S3 bucket** | `alx-monitoring-terraform-state-411683670812` |
| **DynamoDB lock table** | `terraform-state-locks` |
| **State keys** | `ltt/shared/`, `ltt/dev-staging/`, `ltt/prod/` |

### ECR Repositories
Created by `environments/shared`. Names: `ltt-backend`, `ltt-frontend`.
Get URLs: `terraform -chdir=infrastructure/terraform/environments/shared output`

### Secrets Manager — Known Gaps
| Secret | Status |
|---|---|
| `ltt/prod/anthropic_api_key` | **PLACEHOLDER** — must be set with a real key before prod deploy |
| All `ltt/dev/*` and `ltt/staging/*` | Populated ✓ |
| All `ltt/prod/*` (except anthropic) | Not yet — prod Terraform not applied |

---

## Architecture

```
Internet
  └─▶ nginx on 52.30.100.225  (SSL termination, host-header routing)
        ├─▶ ltt-nonprod ALB   (internal, VPC-only)
        │     ├─▶ ltt-dev ECS cluster    (backend :8000, frontend :3000)
        │     └─▶ ltt-staging ECS cluster
        └─▶ ltt-prod ALB      (internal, VPC-only)
              └─▶ ltt-prod ECS cluster   (2 tasks, autoscaling to 4)
```

**Traffic routing**: nginx forwards the `Host` header intact. The ALB uses
host-header listener rules to distinguish dev from staging. Paths `/api/*`,
`/lti/*`, `/health` go to the backend container; everything else to frontend.

**dev-staging share**: one RDS instance (4 databases), one Redis node, one ALB,
two ECS clusters. prod has dedicated RDS (Multi-AZ), Redis, and ALB.

---

## Deployment

### First-time infrastructure bring-up (in order)

```bash
# 1. Shared — ECR repos + GitHub OIDC role (run once ever)
cd infrastructure/terraform/environments/shared
terraform init && terraform apply
# Note outputs: ecr_backend_url, ecr_frontend_url, github_actions_role_arn

# 2. Set GitHub Actions secret + variables (see terraform/README.md)

# 3. Dev/staging — networking, RDS, Redis, ALB, ECS
cd infrastructure/terraform/environments/dev-staging
terraform init && terraform apply
# Credentials read automatically from ltt/infra/credentials in Secrets Manager

# 4. Populate Secrets Manager (use RDS endpoint from TF output)
aws secretsmanager put-secret-value \
  --secret-id ltt/dev/database_url \
  --secret-string "postgresql+asyncpg://ltt_user:<pass>@<rds-endpoint>:5432/ltt_dev"
# Repeat for all ltt/dev/* and ltt/staging/* secrets

# 5. Update nginx on the bastion (generates exact commands with real DNS names)
./tools/scripts/gen-nginx-config.sh

# 6. Prod — when ready
cd infrastructure/terraform/environments/prod
terraform init && terraform apply
```

### Application deploys (after infra exists)

```bash
# Deploy to dev
git push origin main:env-dev

# Deploy to staging
git push origin main:env-staging

# Deploy to prod
git push origin main:env-prod
```

GitHub Actions builds images, runs Alembic migrations, rolling-updates ECS,
waits for stable. Runs on GitHub's servers — close your laptop after the push.

### Check a running deploy

```bash
gh run list                  # recent runs
gh run watch                 # stream live logs
```

---

## Key Commands

### ECS / Logs

```bash
# Tail backend logs
aws logs tail /ecs/ltt-dev-backend --follow

# Shell into a running task (no SSH needed)
aws ecs execute-command \
  --cluster ltt-dev \
  --task <task-id> \
  --container backend \
  --interactive \
  --command "/bin/sh"

# List running tasks
aws ecs list-tasks --cluster ltt-dev
```

### RDS

```bash
# Get RDS endpoint
aws rds describe-db-instances \
  --db-instance-identifier ltt-nonprod \
  --query 'DBInstances[0].Endpoint.Address' \
  --output text

# Connect (from within VPC or via ECS Exec)
psql -h <endpoint> -U ltt_user -d ltt_dev
```

### ALB DNS names (needed for nginx config)

```bash
aws elbv2 describe-load-balancers \
  --names ltt-nonprod ltt-prod \
  --query 'LoadBalancers[*].[LoadBalancerName,DNSName]' \
  --output table
```

### Secrets Manager

```bash
# List LTT secrets
aws secretsmanager list-secrets \
  --filters Key=name,Values=ltt/ \
  --query 'SecretList[*].Name' \
  --output table

# Update a secret value
aws secretsmanager put-secret-value \
  --secret-id ltt/dev/database_url \
  --secret-string "postgresql+asyncpg://..."
```

### Terraform

```bash
# Always run from the environment directory
cd infrastructure/terraform/environments/dev-staging

# Plan without applying
terraform plan

# Check outputs (ALB DNS, subnet IDs, etc.)
terraform output

# Validate modules without AWS credentials
terraform -chdir=infrastructure/terraform/environments/dev-staging \
  init -backend=false && validate

# Run module unit tests (no AWS credentials needed)
cd infrastructure/terraform/modules/ltt-rds && terraform test
cd infrastructure/terraform/modules/ltt-ecs && terraform test
cd infrastructure/terraform/modules/ltt-networking && terraform test
```

---

## What Is and Isn't Terraform-Managed

| Resource | Managed by |
|---|---|
| ECR repos, GitHub OIDC role | Terraform (`shared`) |
| VPC, NAT Gateway, public subnets | **Not LTT** — pre-existing ALX-AI stack |
| LTT subnets, security groups | Terraform (`dev-staging`) |
| RDS, ElastiCache, ALB, ECS | Terraform (`dev-staging` / `prod`) |
| Secrets Manager shells | Terraform (values set manually) |
| CloudWatch log groups + alarms | Terraform |
| nginx config on bastion | **Manual** — `tools/scripts/gen-nginx-config.sh` |
| SSL certificates (Certbot) | **Manual** — run once on bastion |
| DNS records (`*.alx-ai-tools.com`) | **Manual** — registrar/Route53 |
| GitHub Environments (`env-dev` etc.) | **Manual** — repo Settings |
