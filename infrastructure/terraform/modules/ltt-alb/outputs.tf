output "alb_dns" {
  description = "ALB DNS name (configure in nginx upstream block)"
  value       = aws_lb.this.dns_name
}

output "alb_arn" {
  description = "ALB ARN"
  value       = aws_lb.this.arn
}

output "alb_arn_suffix" {
  description = "ALB ARN suffix for CloudWatch alarm dimensions (e.g. app/ltt-prod/abc123)"
  value       = aws_lb.this.arn_suffix
}

output "listener_arn" {
  description = "HTTP listener ARN"
  value       = aws_lb_listener.http.arn
}

output "backend_tg_arns" {
  description = "Map of env key → backend target group ARN"
  value       = { for k, tg in aws_lb_target_group.backend : k => tg.arn }
}

output "frontend_tg_arns" {
  description = "Map of env key → frontend target group ARN"
  value       = { for k, tg in aws_lb_target_group.frontend : k => tg.arn }
}
