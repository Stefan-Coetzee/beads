variable "name_prefix" {
  description = "Prefix for all resource names (e.g. 'ltt-dev', 'ltt-prod')"
  type        = string
}

variable "environment" {
  description = "Environment name (dev, staging, prod)"
  type        = string
}

variable "aws_region" {
  description = "AWS region for CloudWatch Logs"
  type        = string
  default     = "eu-west-1"
}

variable "vpc_id" {
  description = "VPC ID"
  type        = string
}

variable "private_subnets" {
  description = "Subnet IDs for ECS tasks (ltt private subnets from ltt-networking)"
  type        = list(string)
}

variable "ecs_sg_id" {
  description = "Security group ID for ECS tasks (from ltt-networking)"
  type        = string
}

variable "backend_tg_arn" {
  description = "Backend target group ARN (from ltt-alb)"
  type        = string
}

variable "frontend_tg_arn" {
  description = "Frontend target group ARN (from ltt-alb)"
  type        = string
}

variable "backend_image" {
  description = "Full ECR image URI for the backend (e.g. 123456789.dkr.ecr.eu-west-1.amazonaws.com/ltt-backend:dev-abc1234)"
  type        = string
}

variable "frontend_image" {
  description = "Full ECR image URI for the frontend"
  type        = string
}

variable "cpu" {
  description = "Fargate task CPU units (256 = 0.25 vCPU)"
  type        = number
  default     = 256
}

variable "memory" {
  description = "Fargate task memory in MB"
  type        = number
  default     = 512
}

variable "desired_count" {
  description = "Desired number of running tasks per service"
  type        = number
  default     = 1
}

variable "secret_arns" {
  description = "Map of secret key → ARN from ltt-secrets module"
  type        = map(string)
  sensitive   = true
}

variable "env_vars" {
  description = "Non-secret environment variables injected into the backend container"
  type        = map(string)
  default     = {}
}

variable "lti_platform_url" {
  description = "Open edX LTI platform URL (for CSP frame-ancestors in the frontend)"
  type        = string
  default     = "https://imbizo.alx-ai-tools.com"
}

variable "enable_autoscaling" {
  description = "Enable CPU-based auto-scaling for the backend service (prod only)"
  type        = bool
  default     = false
}

variable "autoscaling_max" {
  description = "Maximum task count when auto-scaling is enabled"
  type        = number
  default     = 4
}
