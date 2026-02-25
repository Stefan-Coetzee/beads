output "backend_url" {
  description = "Full ECR repository URL for the backend image"
  value       = aws_ecr_repository.backend.repository_url
}

output "frontend_url" {
  description = "Full ECR repository URL for the frontend image"
  value       = aws_ecr_repository.frontend.repository_url
}

output "backend_name" {
  description = "ECR repository name for the backend"
  value       = aws_ecr_repository.backend.name
}

output "frontend_name" {
  description = "ECR repository name for the frontend"
  value       = aws_ecr_repository.frontend.name
}
