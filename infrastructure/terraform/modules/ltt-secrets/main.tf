##############################################################################
# ltt-secrets — Secrets Manager shells for one LTT environment
#
# Creates placeholder secrets. Actual values MUST be populated manually
# before the first ECS deployment (aws secretsmanager put-secret-value).
# Terraform uses ignore_changes on the secret string so manual updates
# are never overwritten by a subsequent apply.
##############################################################################

locals {
  secret_definitions = {
    database_url        = "PostgreSQL asyncpg URL: postgresql+asyncpg://ltt_user:<pass>@<host>:5432/ltt_${var.environment}"
    checkpoint_db_url   = "PostgreSQL psycopg2 URL for checkpoint DB: postgresql://ltt_user:<pass>@<host>:5432/ltt_${var.environment}_checkpoints"
    redis_url           = "Redis TLS URL: rediss://:<token>@<host>:6379/0"
    anthropic_api_key   = "Anthropic API key (sk-ant-...)"
    lti_private_key     = "RSA private key PEM for LTI 1.3 JWT signing"
    lti_public_key      = "RSA public key PEM for LTI 1.3 JWKS"
    lti_platform_config = "JSON: LTI platform registration (issuer, client_id, endpoints)"
  }
}

resource "aws_secretsmanager_secret" "ltt" {
  for_each = local.secret_definitions

  name        = "ltt/${var.environment}/${each.key}"
  description = each.value

  tags = {
    Environment = var.environment
    Service     = "ltt"
    ManagedBy   = "terraform"
  }
}

# Placeholder values — replace these manually before deploying ECS tasks.
# ignore_changes ensures terraform apply never clobbers values set outside TF.
resource "aws_secretsmanager_secret_version" "ltt" {
  for_each = local.secret_definitions

  secret_id     = aws_secretsmanager_secret.ltt[each.key].id
  secret_string = "PLACEHOLDER — set before deploying (see ltt/${var.environment}/${each.key})"

  lifecycle {
    ignore_changes = [secret_string]
  }
}
