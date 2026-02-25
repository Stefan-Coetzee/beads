output "endpoint" {
  description = "Redis primary endpoint address"
  value       = aws_elasticache_replication_group.this.primary_endpoint_address
}

output "port" {
  description = "Redis port"
  value       = aws_elasticache_replication_group.this.port
}

output "redis_url_template" {
  description = "Redis URL template (auth_token must be filled in Secrets Manager)"
  value       = "rediss://:<AUTH_TOKEN>@${aws_elasticache_replication_group.this.primary_endpoint_address}:${aws_elasticache_replication_group.this.port}/0"
  sensitive   = true
}
