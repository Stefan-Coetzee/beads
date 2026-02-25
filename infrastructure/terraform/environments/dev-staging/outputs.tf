output "alb_dns" {
  description = "ALB DNS name — add to nginx upstream block for dev-mwongozo and staging-mwongozo"
  value       = module.alb.alb_dns
}

output "rds_endpoint" {
  description = "RDS endpoint — use to build ltt/dev/database_url and ltt/staging/database_url secrets"
  value       = module.rds.endpoint
}

output "redis_endpoint" {
  description = "Redis endpoint — use to build ltt/dev/redis_url and ltt/staging/redis_url secrets"
  value       = module.redis.endpoint
}

output "dev_cluster_name" {
  description = "ECS cluster name for the dev environment"
  value       = module.ecs_dev.cluster_name
}

output "staging_cluster_name" {
  description = "ECS cluster name for the staging environment"
  value       = module.ecs_staging.cluster_name
}

output "dev_backend_service" {
  description = "ECS backend service name for dev (for CI/CD)"
  value       = module.ecs_dev.backend_service_name
}

output "dev_frontend_service" {
  description = "ECS frontend service name for dev (for CI/CD)"
  value       = module.ecs_dev.frontend_service_name
}

output "dev_migrate_task_family" {
  description = "Migration task definition family for dev"
  value       = module.ecs_dev.migrate_task_definition_family
}
