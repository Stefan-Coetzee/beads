variable "name_prefix" {
  description = "Prefix for all resource names"
  type        = string
}

variable "environment" {
  description = "Environment name (dev, staging, prod)"
  type        = string
}

variable "subnet_ids" {
  description = "Subnet IDs for the ElastiCache subnet group (use ltt private subnets)"
  type        = list(string)
}

variable "security_group_id" {
  description = "Security group ID (ltt-redis SG from ltt-networking)"
  type        = string
}

variable "node_type" {
  description = "ElastiCache node type"
  type        = string
  default     = "cache.t4g.micro"
}

variable "auth_token" {
  description = "Redis AUTH token (16–128 chars, alphanumeric only). Store in Secrets Manager."
  type        = string
  sensitive   = true
}
