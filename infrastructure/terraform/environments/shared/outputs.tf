output "ecr_backend_url" {
  description = "ECR URL for the backend image"
  value       = module.ecr.backend_url
}

output "ecr_frontend_url" {
  description = "ECR URL for the frontend image"
  value       = module.ecr.frontend_url
}

output "github_actions_role_arn" {
  description = "IAM role ARN — add this to GitHub repository secrets as AWS_ROLE_ARN"
  value       = aws_iam_role.github_actions_deploy.arn
}

output "oidc_provider_arn" {
  description = "GitHub OIDC provider ARN"
  value       = aws_iam_openid_connect_provider.github.arn
}
