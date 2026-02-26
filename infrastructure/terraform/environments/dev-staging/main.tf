##############################################################################
# dev-staging — shared infrastructure for dev and staging environments
#
# One RDS instance (4 databases), one Redis node, one ALB (host routing),
# two ECS clusters (ltt-dev + ltt-staging).
#
# Usage:
#   cd infrastructure/terraform/environments/dev-staging
#   terraform init && terraform apply
# Credentials are read automatically from ltt/infra/credentials in Secrets Manager.
##############################################################################

##############################################################################
# Infrastructure credentials — read from Secrets Manager (single KV secret)
# Keys: nonprod_db_password, nonprod_redis_token
##############################################################################

data "aws_secretsmanager_secret_version" "infra" {
  secret_id = "ltt/infra/credentials"
}

locals {
  infra = jsondecode(data.aws_secretsmanager_secret_version.infra.secret_string)
}

##############################################################################
# Reference existing ALX-AI infrastructure (read-only)
##############################################################################

data "aws_vpc" "existing" {
  filter {
    name   = "tag:Name"
    values = [var.vpc_name_tag]
  }
}

data "aws_route_table" "private" {
  filter {
    name   = "tag:Name"
    values = [var.private_route_table_name_tag]
  }
}

data "aws_security_group" "reverse_proxy" {
  filter {
    name   = "tag:Name"
    values = [var.reverse_proxy_sg_name_tag]
  }
}

data "aws_subnets" "existing_public" {
  filter {
    name   = "vpc-id"
    values = [data.aws_vpc.existing.id]
  }
  filter {
    name   = "tag:Name"
    values = ["monitoring-stack-prod-public-*"]
  }
}

##############################################################################
# Networking — new subnets and security groups in the existing VPC
##############################################################################

module "networking" {
  source = "../../modules/ltt-networking"

  name_prefix            = "ltt"
  vpc_id                 = data.aws_vpc.existing.id
  private_route_table_id = data.aws_route_table.private.id
  reverse_proxy_sg_id    = data.aws_security_group.reverse_proxy.id

  private_cidrs  = ["10.0.12.0/24", "10.0.13.0/24"]
  database_cidrs = ["10.0.23.0/24", "10.0.24.0/24"]
  azs            = ["eu-west-1a", "eu-west-1b"]
}

##############################################################################
# RDS — shared dev/staging instance (separate databases per environment)
#
# Terraform creates the initial ltt_dev database. All other databases
# (ltt_dev_checkpoints, ltt_staging, ltt_staging_checkpoints) are created
# automatically by the migrate ECS task via `db ensure-databases` before
# Alembic runs. No manual psql steps required.
##############################################################################

module "rds" {
  source = "../../modules/ltt-rds"

  name_prefix           = "ltt-nonprod"
  environment           = "dev"
  vpc_id                = data.aws_vpc.existing.id
  subnet_ids            = module.networking.database_subnet_ids
  security_group_id     = module.networking.rds_sg_id
  instance_class        = "db.t4g.micro"
  allocated_storage     = 20
  max_allocated_storage = 50
  initial_db_name       = "ltt_dev"
  master_username       = "ltt_user"
  master_password       = local.infra.nonprod_db_password
  multi_az              = false
  backup_retention_days = 7
}

##############################################################################
# ElastiCache Redis — shared dev/staging node (db0=dev, db1=staging)
##############################################################################

module "redis" {
  source = "../../modules/ltt-elasticache"

  name_prefix       = "ltt-nonprod"
  environment       = "dev"
  subnet_ids        = module.networking.private_subnet_ids
  security_group_id = module.networking.redis_sg_id
  node_type         = "cache.t4g.micro"
  auth_token        = local.infra.nonprod_redis_token
}

##############################################################################
# ALB — shared dev/staging, host-based routing
##############################################################################

module "alb" {
  source = "../../modules/ltt-alb"

  name_prefix  = "ltt-nonprod"
  environment  = "dev-staging"
  vpc_id       = data.aws_vpc.existing.id
  subnet_ids   = module.networking.private_subnet_ids
  alb_sg_id    = module.networking.alb_sg_id

  routing_rules = {
    dev = {
      host = "dev-mwongozo.alx-ai-tools.com"
    }
    staging = {
      host = "staging-mwongozo.alx-ai-tools.com"
    }
  }
}

##############################################################################
# Secrets Manager — placeholder shells for dev and staging
# Populate before first ECS deployment:
#   aws secretsmanager put-secret-value --secret-id ltt/dev/database_url --secret-string "postgresql+asyncpg://..."
##############################################################################

module "secrets_dev" {
  source      = "../../modules/ltt-secrets"
  environment = "dev"
}

module "secrets_staging" {
  source      = "../../modules/ltt-secrets"
  environment = "staging"
}

##############################################################################
# Monitoring — CloudWatch log groups (no alarms for dev/staging)
##############################################################################

module "monitoring_dev" {
  source = "../../modules/ltt-monitoring"

  name_prefix        = "ltt-dev"
  environment        = "dev"
  log_retention_days = 30
}

module "monitoring_staging" {
  source = "../../modules/ltt-monitoring"

  name_prefix        = "ltt-staging"
  environment        = "staging"
  log_retention_days = 30
}

##############################################################################
# ECS — dev environment
##############################################################################

module "ecs_dev" {
  source = "../../modules/ltt-ecs"

  name_prefix     = "ltt-dev"
  environment     = "dev"
  vpc_id          = data.aws_vpc.existing.id
  private_subnets = module.networking.private_subnet_ids
  ecs_sg_id       = module.networking.ecs_sg_id
  backend_tg_arn  = module.alb.backend_tg_arns["dev"]
  frontend_tg_arn = module.alb.frontend_tg_arns["dev"]

  backend_image  = "${var.ecr_backend_url}:dev-latest"
  frontend_image = "${var.ecr_frontend_url}:dev-latest"

  cpu           = 256
  memory        = 512
  desired_count = 1

  secret_arns = module.secrets_dev.arns

  env_vars = {
    LTT_ENV                 = "dev"
    LTT_AUTH_ENABLED        = "true"
    LTT_DEBUG               = "false"
    LTT_FRONTEND_URL        = "https://dev-mwongozo.alx-ai-tools.com"
    LTT_CORS_ORIGINS        = "[\"https://dev-mwongozo.alx-ai-tools.com\"]"
    LTT_CSP_FRAME_ANCESTORS = "https://imbizo.alx-ai-tools.com"
  }

  enable_autoscaling = false

  depends_on = [module.monitoring_dev]
}

##############################################################################
# ECS — staging environment
##############################################################################

module "ecs_staging" {
  source = "../../modules/ltt-ecs"

  name_prefix     = "ltt-staging"
  environment     = "staging"
  vpc_id          = data.aws_vpc.existing.id
  private_subnets = module.networking.private_subnet_ids
  ecs_sg_id       = module.networking.ecs_sg_id
  backend_tg_arn  = module.alb.backend_tg_arns["staging"]
  frontend_tg_arn = module.alb.frontend_tg_arns["staging"]

  backend_image  = "${var.ecr_backend_url}:staging-latest"
  frontend_image = "${var.ecr_frontend_url}:staging-latest"

  cpu           = 256
  memory        = 512
  desired_count = 1

  secret_arns = module.secrets_staging.arns

  env_vars = {
    # LTT_ENV="dev" because settings.py only accepts "local"|"dev"|"prod";
    # staging auth is enforced via LTT_AUTH_ENABLED, not the env literal.
    LTT_ENV                 = "dev"
    LTT_AUTH_ENABLED        = "true"
    LTT_DEBUG               = "false"
    LTT_FRONTEND_URL        = "https://staging-mwongozo.alx-ai-tools.com"
    LTT_CORS_ORIGINS        = "[\"https://staging-mwongozo.alx-ai-tools.com\"]"
    LTT_CSP_FRAME_ANCESTORS = "https://imbizo.alx-ai-tools.com"
  }

  enable_autoscaling = false

  depends_on = [module.monitoring_staging]
}
