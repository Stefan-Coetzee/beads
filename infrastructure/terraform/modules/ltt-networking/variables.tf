variable "name_prefix" {
  description = "Prefix applied to all resource names (e.g. 'ltt')"
  type        = string
}

variable "vpc_id" {
  description = "ID of the existing ALX-AI VPC (10.0.0.0/16)"
  type        = string
}

variable "private_route_table_id" {
  description = "ID of the existing private route table (has 0.0.0.0/0 → NAT Gateway)"
  type        = string
}

variable "private_cidrs" {
  description = "CIDR blocks for LTT private subnets (ECS tasks + ElastiCache)"
  type        = list(string)
  default     = ["10.0.12.0/24", "10.0.13.0/24"]
}

variable "database_cidrs" {
  description = "CIDR blocks for LTT database subnets (RDS)"
  type        = list(string)
  default     = ["10.0.23.0/24", "10.0.24.0/24"]
}

variable "azs" {
  description = "Availability zones (must match length of private_cidrs and database_cidrs)"
  type        = list(string)
  default     = ["eu-west-1a", "eu-west-1b"]
}

variable "reverse_proxy_sg_id" {
  description = "Security group ID of the nginx reverse proxy (bastion at 52.30.100.225)"
  type        = string
}
