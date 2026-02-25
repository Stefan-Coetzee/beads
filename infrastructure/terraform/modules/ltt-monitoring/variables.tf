variable "name_prefix" {
  description = "Prefix for all resource names"
  type        = string
}

variable "environment" {
  description = "Environment name (dev, staging, prod)"
  type        = string
}

variable "log_retention_days" {
  description = "CloudWatch log retention in days (30 for dev/staging, 90 for prod)"
  type        = number
  default     = 30
}

variable "alarm_email" {
  description = "Email address for CloudWatch alarm notifications. Leave empty to skip alarm creation (dev/staging)."
  type        = string
  default     = ""
}

variable "ecs_cluster_name" {
  description = "ECS cluster name (for alarm dimensions)"
  type        = string
  default     = ""
}

variable "backend_service_name" {
  description = "ECS backend service name (for alarm dimensions)"
  type        = string
  default     = ""
}

variable "alb_arn_suffix" {
  description = "ALB ARN suffix for ALB alarm dimensions (e.g. app/ltt-prod/abc123). Leave empty to skip ALB alarms."
  type        = string
  default     = ""
}

variable "rds_instance_id" {
  description = "RDS instance identifier for RDS alarm dimensions. Leave empty to skip RDS alarms."
  type        = string
  default     = ""
}
