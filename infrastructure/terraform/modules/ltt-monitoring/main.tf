##############################################################################
# ltt-monitoring — CloudWatch log groups, alarms, and SNS notifications
##############################################################################

##############################################################################
# CloudWatch Log Groups
##############################################################################

resource "aws_cloudwatch_log_group" "backend" {
  name              = "/ecs/${var.name_prefix}-backend"
  retention_in_days = var.log_retention_days

  tags = { Service = "ltt", Environment = var.environment }
}

resource "aws_cloudwatch_log_group" "frontend" {
  name              = "/ecs/${var.name_prefix}-frontend"
  retention_in_days = var.log_retention_days

  tags = { Service = "ltt", Environment = var.environment }
}

##############################################################################
# SNS Topic for alarms (prod only — alarm_email must be set)
##############################################################################

resource "aws_sns_topic" "alarms" {
  count = var.alarm_email != "" ? 1 : 0
  name  = "${var.name_prefix}-alarms"

  tags = { Service = "ltt", Environment = var.environment }
}

resource "aws_sns_topic_subscription" "email" {
  count = var.alarm_email != "" ? 1 : 0

  topic_arn = aws_sns_topic.alarms[0].arn
  protocol  = "email"
  endpoint  = var.alarm_email
}

##############################################################################
# CloudWatch Alarms (only created when alarm_email is set — prod)
##############################################################################

locals {
  alarm_actions = var.alarm_email != "" ? [aws_sns_topic.alarms[0].arn] : []
}

resource "aws_cloudwatch_metric_alarm" "ecs_cpu_high" {
  count = var.alarm_email != "" ? 1 : 0

  alarm_name          = "${var.name_prefix}-backend-cpu-high"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 2
  metric_name         = "CPUUtilization"
  namespace           = "AWS/ECS"
  period              = 300
  statistic           = "Average"
  threshold           = 80
  alarm_description   = "Backend ECS CPU > 80% for 10 minutes"
  alarm_actions       = local.alarm_actions

  dimensions = {
    ClusterName = var.ecs_cluster_name
    ServiceName = var.backend_service_name
  }
}

resource "aws_cloudwatch_metric_alarm" "ecs_memory_high" {
  count = var.alarm_email != "" ? 1 : 0

  alarm_name          = "${var.name_prefix}-backend-memory-high"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 2
  metric_name         = "MemoryUtilization"
  namespace           = "AWS/ECS"
  period              = 300
  statistic           = "Average"
  threshold           = 85
  alarm_description   = "Backend ECS memory > 85% for 10 minutes"
  alarm_actions       = local.alarm_actions

  dimensions = {
    ClusterName = var.ecs_cluster_name
    ServiceName = var.backend_service_name
  }
}

resource "aws_cloudwatch_metric_alarm" "alb_5xx" {
  count = var.alarm_email != "" && var.alb_arn_suffix != "" ? 1 : 0

  alarm_name          = "${var.name_prefix}-alb-5xx"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 1
  metric_name         = "HTTPCode_Target_5XX_Count"
  namespace           = "AWS/ApplicationELB"
  period              = 300
  statistic           = "Sum"
  threshold           = 10
  alarm_description   = "ALB 5xx errors > 10 in 5 minutes"
  alarm_actions       = local.alarm_actions
  treat_missing_data  = "notBreaching"

  dimensions = {
    LoadBalancer = var.alb_arn_suffix
  }
}

resource "aws_cloudwatch_metric_alarm" "alb_unhealthy_hosts" {
  count = var.alarm_email != "" && var.alb_arn_suffix != "" ? 1 : 0

  alarm_name          = "${var.name_prefix}-alb-unhealthy-hosts"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 1
  metric_name         = "UnHealthyHostCount"
  namespace           = "AWS/ApplicationELB"
  period              = 300
  statistic           = "Average"
  threshold           = 0
  alarm_description   = "ALB unhealthy targets > 0 for 5 minutes"
  alarm_actions       = local.alarm_actions

  dimensions = {
    LoadBalancer = var.alb_arn_suffix
  }
}

resource "aws_cloudwatch_metric_alarm" "rds_cpu_high" {
  count = var.alarm_email != "" && var.rds_instance_id != "" ? 1 : 0

  alarm_name          = "${var.name_prefix}-rds-cpu-high"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 2
  metric_name         = "CPUUtilization"
  namespace           = "AWS/RDS"
  period              = 600
  statistic           = "Average"
  threshold           = 80
  alarm_description   = "RDS CPU > 80% for 20 minutes"
  alarm_actions       = local.alarm_actions

  dimensions = {
    DBInstanceIdentifier = var.rds_instance_id
  }
}
