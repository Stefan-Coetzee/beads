output "backend_log_group_name" {
  description = "CloudWatch log group name for the backend service"
  value       = aws_cloudwatch_log_group.backend.name
}

output "frontend_log_group_name" {
  description = "CloudWatch log group name for the frontend service"
  value       = aws_cloudwatch_log_group.frontend.name
}

output "alarm_topic_arn" {
  description = "SNS topic ARN for alarm notifications (empty string if not created)"
  value       = length(aws_sns_topic.alarms) > 0 ? aws_sns_topic.alarms[0].arn : ""
}
