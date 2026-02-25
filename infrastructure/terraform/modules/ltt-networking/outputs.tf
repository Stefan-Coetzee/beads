output "private_subnet_ids" {
  description = "IDs of the LTT private subnets (for ECS tasks and ElastiCache)"
  value       = [for s in aws_subnet.private : s.id]
}

output "database_subnet_ids" {
  description = "IDs of the LTT database subnets (for RDS)"
  value       = [for s in aws_subnet.database : s.id]
}

output "alb_sg_id" {
  description = "Security group ID for the LTT ALB"
  value       = aws_security_group.alb.id
}

output "ecs_sg_id" {
  description = "Security group ID for LTT ECS tasks"
  value       = aws_security_group.ecs.id
}

output "rds_sg_id" {
  description = "Security group ID for the LTT RDS instance"
  value       = aws_security_group.rds.id
}

output "redis_sg_id" {
  description = "Security group ID for the LTT ElastiCache Redis node"
  value       = aws_security_group.redis.id
}
