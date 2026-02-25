# LTT Terraform Infrastructure

Deploys LTT into the existing ALX-AI VPC using ECS Fargate.

## Structure

```
terraform/
├── modules/
│   ├── ltt-networking/     New subnets + security groups in the existing VPC
│   ├── ltt-ecr/            ECR repositories (shared across all environments)
│   ├── ltt-secrets/        Secrets Manager shells (per environment)
│   ├── ltt-rds/            LTT's own RDS PostgreSQL instance
│   ├── ltt-elasticache/    LTT's own Redis node
│   ├── ltt-alb/            Internal ALB with target groups and routing rules
│   ├── ltt-ecs/            ECS cluster, task definitions, services, IAM
│   └── ltt-monitoring/     CloudWatch log groups and alarms
│
└── environments/
    ├── shared/             ECR repos + GitHub OIDC (apply once)
    ├── dev-staging/        Shared dev+staging infrastructure
    └── prod/               Dedicated production infrastructure
```

## Prerequisites

- Terraform 
- AWS CLI configured with appropriate permissions
- `jq` installed (used in CI/CD deploy scripts)
- Existing ALX-AI VPC and monitoring stack running

## Deployment Order

### 1. Shared (once only)

```bash
cd environments/shared
terraform init
terraform apply
```

Note the outputs:
- `ecr_backend_url` → set in dev-staging and prod `terraform.tfvars`
- `ecr_frontend_url` → same
- `github_actions_role_arn` → add as `AWS_ROLE_ARN` GitHub repository secret

### 2. Dev/Staging

```bash
cd environments/dev-staging

# Edit terraform.tfvars with ECR URLs from shared output
vim terraform.tfvars

# Set sensitive values via environment variables
export TF_VAR_db_master_password='<strong-password>'
export TF_VAR_redis_auth_token='<alphanumeric-token-min-16-chars>'

terraform init
terraform apply
```

After apply, populate Secrets Manager (use RDS/Redis endpoints from outputs):
```bash
aws secretsmanager put-secret-value \
  --secret-id ltt/dev/database_url \
  --secret-string "postgresql+asyncpg://ltt_user:<pass>@<rds-endpoint>:5432/ltt_dev"

# Repeat for: checkpoint_db_url, redis_url, anthropic_api_key,
#             lti_private_key, lti_public_key, lti_platform_config
# Do the same for ltt/staging/* secrets
```

Create additional databases (the RDS module only creates `ltt_dev`):
```bash
psql -h <rds-endpoint> -U ltt_user -d postgres <<EOF
CREATE DATABASE ltt_dev_checkpoints;
CREATE DATABASE ltt_staging;
CREATE DATABASE ltt_staging_checkpoints;
EOF
```

### 3. Production

```bash
cd environments/prod

vim terraform.tfvars  # ECR URLs + alarm_email

export TF_VAR_db_master_password='<prod-password>'
export TF_VAR_redis_auth_token='<prod-token>'

terraform init
terraform apply
```

Populate `ltt/prod/*` secrets in Secrets Manager (same pattern as above).

## GitHub Repository Setup

After applying `shared/`, configure these in the GitHub repository:

**Secrets** (`Settings → Secrets and variables → Actions → Secrets`):
- `AWS_ROLE_ARN` — from `shared` output `github_actions_role_arn`

**Variables** (`Settings → Secrets and variables → Actions → Variables`):
- `DEV_PRIVATE_SUBNETS` — comma-separated subnet IDs (from `dev-staging` networking module)
- `DEV_ECS_SG_ID` — ECS security group ID for dev
- `STAGING_PRIVATE_SUBNETS` — same subnets (dev and staging share)
- `STAGING_ECS_SG_ID` — same SG (dev and staging share)
- `PROD_PRIVATE_SUBNETS` — same subnets (prod reuses via data sources)
- `PROD_ECS_SG_ID` — same SG

All subnet/SG IDs are emitted as Terraform outputs from `dev-staging`.

## Nginx Configuration (reverse proxy)

Add to the existing nginx config on the bastion (`52.30.100.225`):

```nginx
upstream ltt_nonprod_alb {
    server <dev-staging ALB DNS from TF output>:80;
}

upstream ltt_prod_alb {
    server <prod ALB DNS from TF output>:80;
}

server {
    listen 443 ssl;
    server_name dev-mwongozo.alx-ai-tools.com staging-mwongozo.alx-ai-tools.com;
    # ssl_certificate / ssl_certificate_key — from Certbot
    location / {
        proxy_pass http://ltt_nonprod_alb;
        proxy_set_header Host $host;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_http_version 1.1;
        proxy_buffering off;    # critical for SSE chat streaming
        proxy_read_timeout 300s;
    }
}

server {
    listen 443 ssl;
    server_name mwongozo.alx-ai-tools.com;
    # ssl_certificate / ssl_certificate_key — from Certbot
    location / {
        proxy_pass http://ltt_prod_alb;
        proxy_set_header Host $host;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_http_version 1.1;
        proxy_buffering off;
        proxy_read_timeout 300s;
    }
}
```

Then:
```bash
sudo nginx -t && sudo systemctl reload nginx
```

## Debugging ECS Tasks

```bash
# Shell into a running Fargate task (no SSH needed)
aws ecs execute-command \
  --cluster ltt-dev \
  --task <task-id> \
  --container backend \
  --interactive \
  --command "/bin/sh"

# Tail logs
aws logs tail /ecs/ltt-dev-backend --follow
```

## State

All state is stored in the existing S3 + DynamoDB lock table:
- Bucket: `alx-monitoring-terraform-state-411683670812`
- DynamoDB: `terraform-state-locks`
- Keys: `ltt/shared/`, `ltt/dev-staging/`, `ltt/prod/`
