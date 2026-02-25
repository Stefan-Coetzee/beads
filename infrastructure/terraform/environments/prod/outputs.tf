output "alb_dns" {
  description = "Prod ALB DNS name — add to nginx upstream block for mwongozo.alx-ai-tools.com"
  value       = module.alb.alb_dns
}

output "rds_endpoint" {
  description = "Prod RDS endpoint — use to build ltt/prod/database_url secret"
  value       = module.rds.endpoint
}

output "redis_endpoint" {
  description = "Prod Redis endpoint — use to build ltt/prod/redis_url secret"
  value       = module.redis.endpoint
}

output "cluster_name" {
  description = "ECS cluster name for prod"
  value       = module.ecs.cluster_name
}

output "backend_service_name" {
  description = "ECS backend service name (for CI/CD)"
  value       = module.ecs.backend_service_name
}

output "frontend_service_name" {
  description = "ECS frontend service name (for CI/CD)"
  value       = module.ecs.frontend_service_name
}

output "migrate_task_family" {
  description = "Migration task definition family for prod"
  value       = module.ecs.migrate_task_definition_family
}
