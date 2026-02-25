variable "vpc_name_tag" {
  description = "Name tag of the existing ALX-AI VPC"
  type        = string
  default     = "monitoring-stack-prod-vpc"
}

variable "private_route_table_name_tag" {
  description = "Name tag of the existing private route table"
  type        = string
  default     = "monitoring-stack-prod-private-rt-1"
}

variable "reverse_proxy_sg_name_tag" {
  description = "Name tag of the reverse proxy security group"
  type        = string
  default     = "monitoring-stack-prod-reverse-proxy-sg"
}

variable "ecr_backend_url" {
  description = "ECR backend image URL (from shared workspace output)"
  type        = string
}

variable "ecr_frontend_url" {
  description = "ECR frontend image URL (from shared workspace output)"
  type        = string
}

variable "alarm_email" {
  description = "Email address for CloudWatch alarm notifications"
  type        = string
}
