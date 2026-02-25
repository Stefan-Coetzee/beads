##############################################################################
# prod — dedicated production infrastructure
#
# Dedicated RDS (Multi-AZ, db.t4g.small), dedicated Redis,
# dedicated ALB, and a single ECS cluster with 2 desired tasks + auto-scaling.
#
# NOTE: The networking subnets (10.0.12-13.0/24, 10.0.23-24.0/24) are shared
# with dev-staging and were created in that workspace. We reference them here
# via data sources rather than recreating them.
#
# Usage:
#   cd infrastructure/terraform/environments/prod
#   terraform init && terraform apply
# Credentials are read automatically from ltt/infra/credentials in Secrets Manager.
##############################################################################

##############################################################################
# Infrastructure credentials — read from Secrets Manager (single KV secret)
# Keys: prod_db_password, prod_redis_token
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

data "aws_security_group" "reverse_proxy" {
  filter {
    name   = "tag:Name"
    values = [var.reverse_proxy_sg_name_tag]
  }
}

# Reference subnets created by dev-staging workspace
data "aws_subnets" "ltt_private" {
  filter {
    name   = "vpc-id"
    values = [data.aws_vpc.existing.id]
  }
  filter {
    name   = "tag:Name"
    values = ["ltt-private-*"]
  }
}

data "aws_subnets" "ltt_database" {
  filter {
    name   = "vpc-id"
    values = [data.aws_vpc.existing.id]
  }
  filter {
    name   = "tag:Name"
    values = ["ltt-database-*"]
  }
}

# Reference security groups created by dev-staging networking module
data "aws_security_group" "ltt_alb" {
  filter {
    name   = "tag:Name"
    values = ["ltt-alb"]
  }
}

data "aws_security_group" "ltt_ecs" {
  filter {
    name   = "tag:Name"
    values = ["ltt-ecs"]
  }
}

data "aws_security_group" "ltt_rds" {
  filter {
    name   = "tag:Name"
    values = ["ltt-rds"]
  }
}

data "aws_security_group" "ltt_redis" {
  filter {
    name   = "tag:Name"
    values = ["ltt-redis"]
  }
}

##############################################################################
# RDS — dedicated prod instance (Multi-AZ, db.t4g.small)
##############################################################################

module "rds" {
  source = "../../modules/ltt-rds"

  name_prefix           = "ltt-prod"
  environment           = "prod"
  vpc_id                = data.aws_vpc.existing.id
  subnet_ids            = data.aws_subnets.ltt_database.ids
  security_group_id     = data.aws_security_group.ltt_rds.id
  instance_class        = "db.t4g.small"
  allocated_storage     = 20
  max_allocated_storage = 100
  initial_db_name       = "ltt_prod"
  master_username       = "ltt_user"
  master_password       = local.infra.prod_db_password
  multi_az              = true
  backup_retention_days = 14
}

##############################################################################
# ElastiCache Redis — dedicated prod node
##############################################################################

module "redis" {
  source = "../../modules/ltt-elasticache"

  name_prefix       = "ltt-prod"
  environment       = "prod"
  subnet_ids        = data.aws_subnets.ltt_private.ids
  security_group_id = data.aws_security_group.ltt_redis.id
  node_type         = "cache.t4g.micro"
  auth_token        = local.infra.prod_redis_token
}

##############################################################################
# ALB — dedicated prod ALB (path routing only, no host header check)
##############################################################################

module "alb" {
  source = "../../modules/ltt-alb"

  name_prefix  = "ltt-prod"
  environment  = "prod"
  vpc_id       = data.aws_vpc.existing.id
  subnet_ids   = data.aws_subnets.ltt_private.ids
  alb_sg_id    = data.aws_security_group.ltt_alb.id

  routing_rules = {
    prod = {
      # No host header check — prod ALB handles only mwongozo.alx-ai-tools.com
      host = ""
    }
  }
}

##############################################################################
# Secrets Manager — placeholder shells for prod
##############################################################################

module "secrets_prod" {
  source      = "../../modules/ltt-secrets"
  environment = "prod"
}

##############################################################################
# Monitoring — CloudWatch log groups + alarms with email notifications
##############################################################################

module "monitoring" {
  source = "../../modules/ltt-monitoring"

  name_prefix        = "ltt-prod"
  environment        = "prod"
  log_retention_days = 90
  alarm_email        = var.alarm_email

  ecs_cluster_name     = module.ecs.cluster_name
  backend_service_name = module.ecs.backend_service_name
  alb_arn_suffix   = module.alb.alb_arn_suffix
  rds_instance_id  = module.rds.instance_id
}

##############################################################################
# ECS — prod (2 tasks, auto-scaling up to 4)
##############################################################################

module "ecs" {
  source = "../../modules/ltt-ecs"

  name_prefix     = "ltt-prod"
  environment     = "prod"
  vpc_id          = data.aws_vpc.existing.id
  private_subnets = data.aws_subnets.ltt_private.ids
  ecs_sg_id       = data.aws_security_group.ltt_ecs.id
  backend_tg_arn  = module.alb.backend_tg_arns["prod"]
  frontend_tg_arn = module.alb.frontend_tg_arns["prod"]

  backend_image  = "${var.ecr_backend_url}:prod-latest"
  frontend_image = "${var.ecr_frontend_url}:prod-latest"

  cpu           = 512
  memory        = 1024
  desired_count = 2

  secret_arns = module.secrets_prod.arns

  env_vars = {
    LTT_ENV                 = "prod"
    LTT_AUTH_ENABLED        = "true"
    LTT_DEBUG               = "false"
    LTT_FRONTEND_URL        = "https://mwongozo.alx-ai-tools.com"
    LTT_CORS_ORIGINS        = "[\"https://mwongozo.alx-ai-tools.com\"]"
    LTT_CSP_FRAME_ANCESTORS = "https://imbizo.alx-ai-tools.com"
  }

  enable_autoscaling = true
  autoscaling_max    = 4

  depends_on = [module.monitoring]
}
