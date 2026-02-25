variable "vpc_name_tag" {
  description = "Name tag of the existing ALX-AI VPC"
  type        = string
  default     = "monitoring-stack-prod-vpc"
}

variable "private_route_table_name_tag" {
  description = "Name tag of the existing private route table"
  type        = string
  default     = "monitoring-stack-prod-private-rt"
}

variable "reverse_proxy_sg_name_tag" {
  description = "Name tag of the reverse proxy security group"
  type        = string
  default     = "monitoring-stack-prod-bastion-sg"
}

variable "ecr_backend_url" {
  description = "ECR backend image URL (from shared workspace output)"
  type        = string
}

variable "ecr_frontend_url" {
  description = "ECR frontend image URL (from shared workspace output)"
  type        = string
}

# Sensitive — pass via TF_VAR_ environment variables, never in tfvars
variable "db_master_password" {
  description = "RDS master password for ltt-nonprod instance"
  type        = string
  sensitive   = true
}

variable "redis_auth_token" {
  description = "Redis AUTH token for dev/staging ElastiCache node"
  type        = string
  sensitive   = true
}
