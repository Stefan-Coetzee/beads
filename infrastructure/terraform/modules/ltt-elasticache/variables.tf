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

variable "subnet_ids" {
  description = "Subnet IDs for the ElastiCache subnet group (use ltt private subnets)"
  type        = list(string)
}

variable "security_group_id" {
  description = "Security group ID (ltt-redis SG from ltt-networking)"
  type        = string
  nullable    = false
}

variable "node_type" {
  description = "ElastiCache node type"
  type        = string
  default     = "cache.t4g.micro"
  nullable    = false
}

variable "auth_token" {
  description = "Redis AUTH token (16–128 chars, alphanumeric only). Store in Secrets Manager."
  type        = string
  sensitive   = true
  nullable    = false

  validation {
    condition     = length(var.auth_token) >= 16 && length(var.auth_token) <= 128
    error_message = "auth_token must be between 16 and 128 characters (ElastiCache requirement)."
  }
}
