output "arns" {
  description = "Map of secret key → ARN (pass to ltt-ecs module as secret_arns)"
  value       = { for k, v in aws_secretsmanager_secret.ltt : k => v.arn }
}
