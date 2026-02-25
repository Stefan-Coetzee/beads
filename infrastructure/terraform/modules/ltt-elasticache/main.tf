##############################################################################
# ltt-elasticache — LTT's own Redis node for LTI session storage
##############################################################################

resource "aws_elasticache_subnet_group" "this" {
  name       = "${var.name_prefix}-redis"
  subnet_ids = var.subnet_ids

  tags = { Name = "${var.name_prefix}-redis" }
}

resource "aws_elasticache_cluster" "this" {
  cluster_id           = "${var.name_prefix}-redis"
  engine               = "redis"
  engine_version       = "7.1"
  node_type            = var.node_type
  num_cache_nodes      = 1
  parameter_group_name = "default.redis7"
  port                 = 6379

  subnet_group_name  = aws_elasticache_subnet_group.this.name
  security_group_ids = [var.security_group_id]

  # Auth token enables Redis AUTH (required with TLS)
  transit_encryption_enabled = true
  auth_token                 = var.auth_token

  snapshot_retention_limit = 1
  snapshot_window          = "04:00-05:00"

  tags = {
    Name        = "${var.name_prefix}-redis"
    Environment = var.environment
    Service     = "ltt"
  }
}
