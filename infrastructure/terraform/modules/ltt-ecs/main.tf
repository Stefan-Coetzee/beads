##############################################################################
# ltt-ecs — ECS Fargate cluster, IAM roles, task definitions, and services
##############################################################################

##############################################################################
# ECS Cluster
##############################################################################

resource "aws_ecs_cluster" "this" {
  name = var.name_prefix

  setting {
    name  = "containerInsights"
    value = "enabled"
  }

  tags = {
    Name        = var.name_prefix
    Environment = var.environment
    Service     = "ltt"
  }
}

##############################################################################
# IAM — Execution Role
# ECS uses this role to pull ECR images and inject Secrets Manager values.
##############################################################################

resource "aws_iam_role" "execution" {
  name = "${var.name_prefix}-ecs-execution"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect    = "Allow"
      Principal = { Service = "ecs-tasks.amazonaws.com" }
      Action    = "sts:AssumeRole"
    }]
  })
}

resource "aws_iam_role_policy_attachment" "execution_managed" {
  role       = aws_iam_role.execution.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AmazonECSTaskExecutionRolePolicy"
}

resource "aws_iam_role_policy" "execution_secrets" {
  name = "${var.name_prefix}-secrets-read"
  role = aws_iam_role.execution.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect   = "Allow"
      Action   = ["secretsmanager:GetSecretValue"]
      Resource = values(var.secret_arns)
    }]
  })
}

##############################################################################
# IAM — Task Role
# The application container runs with this role. Needed for ECS Exec (SSM).
##############################################################################

resource "aws_iam_role" "task" {
  name = "${var.name_prefix}-ecs-task"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect    = "Allow"
      Principal = { Service = "ecs-tasks.amazonaws.com" }
      Action    = "sts:AssumeRole"
    }]
  })
}

resource "aws_iam_role_policy" "task_exec" {
  name = "${var.name_prefix}-ecs-exec"
  role = aws_iam_role.task.id

  # SSM permissions required for `aws ecs execute-command` (ECS Exec)
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect = "Allow"
      Action = [
        "ssmmessages:CreateControlChannel",
        "ssmmessages:CreateDataChannel",
        "ssmmessages:OpenControlChannel",
        "ssmmessages:OpenDataChannel"
      ]
      Resource = "*"
    }]
  })
}

##############################################################################
# Locals — secret → env var name mapping
##############################################################################

locals {
  # Map secret key → container env var name.
  # All names must match pydantic-settings env_prefix="LTT_" in settings.py.
  secret_env_vars = {
    database_url        = "LTT_DATABASE_URL"
    checkpoint_db_url   = "LTT_CHECKPOINT_DATABASE_URL"
    redis_url           = "LTT_REDIS_URL"
    anthropic_api_key   = "LTT_ANTHROPIC_API_KEY"
    lti_private_key     = "LTT_LTI_PRIVATE_KEY"
    lti_public_key      = "LTT_LTI_PUBLIC_KEY"
    lti_platform_config = "LTT_LTI_PLATFORM_CONFIG"
  }

  # Only inject secrets that are provided (allows partial secret sets in dev)
  active_secrets = {
    for k, arn in var.secret_arns : k => arn if contains(keys(local.secret_env_vars), k)
  }
}

##############################################################################
# Task Definition — Backend (FastAPI)
##############################################################################

resource "aws_ecs_task_definition" "backend" {
  family                   = "${var.name_prefix}-backend"
  network_mode             = "awsvpc"
  requires_compatibilities = ["FARGATE"]
  cpu                      = var.cpu
  memory                   = var.memory
  execution_role_arn       = aws_iam_role.execution.arn
  task_role_arn            = aws_iam_role.task.arn

  container_definitions = jsonencode([
    {
      name  = "backend"
      image = var.backend_image

      portMappings = [{ containerPort = 8000, protocol = "tcp" }]

      environment = [
        for k, v in var.env_vars : { name = k, value = tostring(v) }
      ]

      secrets = [
        for k, arn in local.active_secrets : {
          name      = local.secret_env_vars[k]
          valueFrom = arn
        }
      ]

      healthCheck = {
        command     = ["CMD-SHELL", "curl -f http://localhost:8000/health || exit 1"]
        interval    = 30
        timeout     = 5
        retries     = 3
        startPeriod = 60
      }

      logConfiguration = {
        logDriver = "awslogs"
        options = {
          "awslogs-group"         = "/ecs/${var.name_prefix}-backend"
          "awslogs-region"        = var.aws_region
          "awslogs-stream-prefix" = "ecs"
        }
      }
    }
  ])

  tags = { Name = "${var.name_prefix}-backend", Environment = var.environment }
}

##############################################################################
# Task Definition — Frontend (Next.js)
##############################################################################

resource "aws_ecs_task_definition" "frontend" {
  family                   = "${var.name_prefix}-frontend"
  network_mode             = "awsvpc"
  requires_compatibilities = ["FARGATE"]
  cpu                      = var.cpu
  memory                   = var.memory
  execution_role_arn       = aws_iam_role.execution.arn
  task_role_arn            = aws_iam_role.task.arn

  container_definitions = jsonencode([
    {
      name  = "frontend"
      image = var.frontend_image

      portMappings = [{ containerPort = 3000, protocol = "tcp" }]

      environment = [
        # NEXT_PUBLIC_API_URL intentionally empty — ALB handles routing
        { name = "NEXT_PUBLIC_API_URL", value = "" },
        { name = "LTI_PLATFORM_URL", value = var.lti_platform_url },
        { name = "NODE_ENV", value = "production" }
      ]

      healthCheck = {
        command     = ["CMD-SHELL", "wget -q --spider http://localhost:3000/ || exit 1"]
        interval    = 30
        timeout     = 5
        retries     = 3
        startPeriod = 30
      }

      logConfiguration = {
        logDriver = "awslogs"
        options = {
          "awslogs-group"         = "/ecs/${var.name_prefix}-frontend"
          "awslogs-region"        = var.aws_region
          "awslogs-stream-prefix" = "ecs"
        }
      }
    }
  ])

  tags = { Name = "${var.name_prefix}-frontend", Environment = var.environment }
}

##############################################################################
# Task Definition — Migration (same image as backend, different command)
# Run via: aws ecs run-task --overrides '{"containerOverrides":[...]}'
##############################################################################

resource "aws_ecs_task_definition" "migrate" {
  family                   = "${var.name_prefix}-migrate"
  network_mode             = "awsvpc"
  requires_compatibilities = ["FARGATE"]
  cpu                      = 256
  memory                   = 512
  execution_role_arn       = aws_iam_role.execution.arn
  task_role_arn            = aws_iam_role.task.arn

  container_definitions = jsonencode([
    {
      name  = "migrate"
      image = var.backend_image
      # Ensure all required databases exist (primary + checkpoints sibling),
      # then run Alembic migrations. Uses /bin/sh so both commands run in one
      # container without needing a separate entrypoint script.
      command = ["/bin/sh", "-c", "python -m ltt.cli.main db ensure-databases && alembic upgrade head"]

      environment = [
        for k, v in var.env_vars : { name = k, value = tostring(v) }
      ]

      secrets = [
        for k, arn in local.active_secrets : {
          name      = local.secret_env_vars[k]
          valueFrom = arn
        }
      ]

      logConfiguration = {
        logDriver = "awslogs"
        options = {
          "awslogs-group"         = "/ecs/${var.name_prefix}-backend"
          "awslogs-region"        = var.aws_region
          "awslogs-stream-prefix" = "migrate"
        }
      }
    }
  ])

  tags = { Name = "${var.name_prefix}-migrate", Environment = var.environment }
}

##############################################################################
# ECS Services
##############################################################################

resource "aws_ecs_service" "backend" {
  name            = "${var.name_prefix}-backend"
  cluster         = aws_ecs_cluster.this.id
  task_definition = aws_ecs_task_definition.backend.arn
  launch_type     = "FARGATE"
  desired_count   = var.desired_count

  # ECS Exec for debugging (replaces SSH)
  enable_execute_command = true

  network_configuration {
    subnets          = var.private_subnets
    security_groups  = [var.ecs_sg_id]
    assign_public_ip = false
  }

  load_balancer {
    target_group_arn = var.backend_tg_arn
    container_name   = "backend"
    container_port   = 8000
  }

  deployment_minimum_healthy_percent = 50
  deployment_maximum_percent         = 200

  # CI/CD updates the task definition; ignore drift here
  lifecycle {
    ignore_changes = [task_definition, desired_count]
  }

  tags = { Name = "${var.name_prefix}-backend", Environment = var.environment }
}

resource "aws_ecs_service" "frontend" {
  name            = "${var.name_prefix}-frontend"
  cluster         = aws_ecs_cluster.this.id
  task_definition = aws_ecs_task_definition.frontend.arn
  launch_type     = "FARGATE"
  desired_count   = var.desired_count

  enable_execute_command = true

  network_configuration {
    subnets          = var.private_subnets
    security_groups  = [var.ecs_sg_id]
    assign_public_ip = false
  }

  load_balancer {
    target_group_arn = var.frontend_tg_arn
    container_name   = "frontend"
    container_port   = 3000
  }

  deployment_minimum_healthy_percent = 50
  deployment_maximum_percent         = 200

  lifecycle {
    ignore_changes = [task_definition, desired_count]
  }

  tags = { Name = "${var.name_prefix}-frontend", Environment = var.environment }
}

##############################################################################
# Auto-scaling (prod only — controlled by var.enable_autoscaling)
##############################################################################

resource "aws_appautoscaling_target" "backend" {
  count = var.enable_autoscaling ? 1 : 0

  max_capacity       = var.autoscaling_max
  min_capacity       = var.desired_count
  resource_id        = "service/${aws_ecs_cluster.this.name}/${aws_ecs_service.backend.name}"
  scalable_dimension = "ecs:service:DesiredCount"
  service_namespace  = "ecs"
}

resource "aws_appautoscaling_policy" "backend_cpu" {
  count = var.enable_autoscaling ? 1 : 0

  name               = "${var.name_prefix}-cpu-tracking"
  policy_type        = "TargetTrackingScaling"
  resource_id        = aws_appautoscaling_target.backend[0].resource_id
  scalable_dimension = aws_appautoscaling_target.backend[0].scalable_dimension
  service_namespace  = aws_appautoscaling_target.backend[0].service_namespace

  target_tracking_scaling_policy_configuration {
    predefined_metric_specification {
      predefined_metric_type = "ECSServiceAverageCPUUtilization"
    }
    target_value       = 70.0
    scale_in_cooldown  = 300
    scale_out_cooldown = 60
  }
}
