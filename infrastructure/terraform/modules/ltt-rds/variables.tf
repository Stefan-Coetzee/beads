variable "name_prefix" {
  description = "Identifier prefix for the RDS instance and related resources"
  type        = string
}

variable "environment" {
  description = "Environment name (dev, staging, prod) — controls deletion protection and snapshots"
  type        = string
}

variable "vpc_id" {
  description = "VPC ID"
  type        = string
}

variable "subnet_ids" {
  description = "Subnet IDs for the DB subnet group (use ltt database subnets)"
  type        = list(string)
}

variable "security_group_id" {
  description = "Security group ID that grants access (ltt-rds SG from ltt-networking)"
  type        = string
}

variable "instance_class" {
  description = "RDS instance class"
  type        = string
  default     = "db.t4g.micro"
}

variable "allocated_storage" {
  description = "Initial storage in GB"
  type        = number
  default     = 20
}

variable "max_allocated_storage" {
  description = "Maximum autoscaling storage in GB (set equal to allocated_storage to disable)"
  type        = number
  default     = 100
}

variable "initial_db_name" {
  description = "Name of the initial database created on the instance"
  type        = string
}

variable "master_username" {
  description = "Master DB username"
  type        = string
  default     = "ltt_user"
}

variable "master_password" {
  description = "Master DB password (store in Secrets Manager, pass here via TF_VAR_)"
  type        = string
  sensitive   = true
}

variable "multi_az" {
  description = "Enable Multi-AZ for high availability (prod only)"
  type        = bool
  default     = false
}

variable "backup_retention_days" {
  description = "Number of days to retain automated backups"
  type        = number
  default     = 7
}
