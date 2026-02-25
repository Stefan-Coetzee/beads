variable "name_prefix" {
  description = "Prefix for all resource names"
  type        = string
  nullable    = false
}

variable "environment" {
  description = "Environment name (dev, staging, prod)"
  type        = string
  nullable    = false

  validation {
    condition     = contains(["dev", "staging", "prod"], var.environment)
    error_message = "environment must be one of: dev, staging, prod."
  }
}

variable "log_retention_days" {
  description = "CloudWatch log retention in days (30 for dev/staging, 90 for prod)"
  type        = number
  default     = 30

  validation {
    condition = contains(
      [1, 3, 5, 7, 14, 30, 60, 90, 120, 150, 180, 365, 400, 545, 731, 1096, 1827, 2192, 2557, 2922, 3288, 3653],
      var.log_retention_days
    )
    error_message = "log_retention_days must be a valid CloudWatch Logs retention value (e.g. 1, 3, 5, 7, 14, 30, 60, 90, 120, 150, 180, 365)."
  }
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
