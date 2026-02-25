##############################################################################
# ltt-elasticache — LTT's own Redis node for LTI session storage
#
# Uses aws_elasticache_replication_group (not aws_elasticache_cluster)
# because auth_token and transit_encryption_enabled require the replication
# group resource type even for single-node deployments.
##############################################################################

resource "aws_elasticache_subnet_group" "this" {
  name       = "${var.name_prefix}-redis"
  subnet_ids = var.subnet_ids

  tags = { Name = "${var.name_prefix}-redis" }
}

resource "aws_elasticache_replication_group" "this" {
  replication_group_id = "${var.name_prefix}-redis"
  description          = "Redis for ${var.name_prefix} (LTI session storage)"

  engine               = "redis"
  engine_version       = "7.1"
  node_type            = var.node_type
  num_cache_clusters   = 1
  parameter_group_name = "default.redis7"
  port                 = 6379

  subnet_group_name  = aws_elasticache_subnet_group.this.name
  security_group_ids = [var.security_group_id]

  transit_encryption_enabled = true
  auth_token                 = var.auth_token

  # Single node — no failover
  automatic_failover_enabled = false
  multi_az_enabled           = false

  snapshot_retention_limit = 1
  snapshot_window          = "04:00-05:00"

  tags = {
    Name        = "${var.name_prefix}-redis"
    Environment = var.environment
    Service     = "ltt"
  }
}
