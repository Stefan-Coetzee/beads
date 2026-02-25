output "endpoint" {
  description = "Redis cluster endpoint address"
  value       = aws_elasticache_cluster.this.cache_nodes[0].address
}

output "port" {
  description = "Redis port"
  value       = aws_elasticache_cluster.this.cache_nodes[0].port
}

output "redis_url_template" {
  description = "Redis URL template (auth_token must be filled in manually in Secrets Manager)"
  value       = "rediss://:<AUTH_TOKEN>@${aws_elasticache_cluster.this.cache_nodes[0].address}:${aws_elasticache_cluster.this.cache_nodes[0].port}/0"
  sensitive   = true
}
