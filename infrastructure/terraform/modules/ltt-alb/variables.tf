variable "name_prefix" {
  description = "Name for the ALB (e.g. 'ltt-nonprod', 'ltt-prod')"
  type        = string
}

variable "environment" {
  description = "Primary environment label for tagging"
  type        = string
}

variable "vpc_id" {
  description = "VPC ID (for target groups)"
  type        = string
}

variable "subnet_ids" {
  description = "Subnet IDs for the ALB (use ltt private subnets — ALB is internal)"
  type        = list(string)
}

variable "alb_sg_id" {
  description = "Security group ID for the ALB (from ltt-networking)"
  type        = string
}

variable "routing_rules" {
  description = <<-EOT
    Map of environment key → routing config. One pair of target groups is created per key.
    host: Host header value for routing (set to "" for single-env prod ALB with no host check).
    Example:
      routing_rules = {
        dev     = { host = "dev-mwongozo.alx-ai-tools.com" }
        staging = { host = "staging-mwongozo.alx-ai-tools.com" }
      }
  EOT
  type = map(object({
    host = string
  }))
}
