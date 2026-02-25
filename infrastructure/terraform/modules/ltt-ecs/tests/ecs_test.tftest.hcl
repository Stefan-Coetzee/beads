# Unit tests for ltt-ecs module.
# Uses mock_provider — no AWS credentials or real resources required.
# Run: terraform test  (from the module directory)

mock_provider "aws" {}

variables {
  name_prefix     = "test"
  environment     = "dev"
  aws_region      = "eu-west-1"
  vpc_id          = "vpc-00000000000000001"
  private_subnets = ["subnet-00000000000000001", "subnet-00000000000000002"]
  ecs_sg_id       = "sg-00000000000000001"
  backend_tg_arn  = "arn:aws:elasticloadbalancing:eu-west-1:123456789012:targetgroup/test-backend/abc123"
  frontend_tg_arn = "arn:aws:elasticloadbalancing:eu-west-1:123456789012:targetgroup/test-frontend/abc123"
  backend_image   = "123456789012.dkr.ecr.eu-west-1.amazonaws.com/ltt-backend:test"
  frontend_image  = "123456789012.dkr.ecr.eu-west-1.amazonaws.com/ltt-frontend:test"
  secret_arns     = {}
}

# Container Insights enabled on the cluster.
run "cluster_has_container_insights" {
  command = plan

  assert {
    condition     = one([for s in aws_ecs_cluster.this.setting : s if s.name == "containerInsights"]).value == "enabled"
    error_message = "ECS cluster must have Container Insights enabled."
  }
}

# ECS Exec enabled on both services (needed for `aws ecs execute-command`).
run "ecs_exec_enabled_on_backend" {
  command = plan

  assert {
    condition     = aws_ecs_service.backend.enable_execute_command == true
    error_message = "ECS Exec must be enabled on the backend service."
  }
}

run "ecs_exec_enabled_on_frontend" {
  command = plan

  assert {
    condition     = aws_ecs_service.frontend.enable_execute_command == true
    error_message = "ECS Exec must be enabled on the frontend service."
  }
}

# Tasks must not get public IPs (private subnets, internal ALB).
run "backend_has_no_public_ip" {
  command = plan

  assert {
    condition     = aws_ecs_service.backend.network_configuration[0].assign_public_ip == false
    error_message = "Backend ECS tasks must not receive public IP addresses."
  }
}

run "frontend_has_no_public_ip" {
  command = plan

  assert {
    condition     = aws_ecs_service.frontend.network_configuration[0].assign_public_ip == false
    error_message = "Frontend ECS tasks must not receive public IP addresses."
  }
}

# Autoscaling resources must NOT be created when enable_autoscaling = false.
run "no_autoscaling_resources_when_disabled" {
  command = plan

  assert {
    condition     = length(aws_appautoscaling_target.backend) == 0
    error_message = "No autoscaling target should be created when enable_autoscaling is false."
  }

  assert {
    condition     = length(aws_appautoscaling_policy.backend_cpu) == 0
    error_message = "No autoscaling policy should be created when enable_autoscaling is false."
  }
}

# Autoscaling resources ARE created when enable_autoscaling = true.
run "autoscaling_resources_created_when_enabled" {
  command = plan

  variables {
    enable_autoscaling = true
  }

  assert {
    condition     = length(aws_appautoscaling_target.backend) == 1
    error_message = "Autoscaling target must be created when enable_autoscaling is true."
  }
}

##############################################################################
# active_secrets filtering — the critical local that gates what gets injected
# into the container. Tested via jsondecode() on container_definitions JSON.
##############################################################################

# Empty secret_arns → no secrets injected into the container.
run "empty_secret_arns_injects_nothing" {
  command = plan

  variables {
    secret_arns = {}
  }

  assert {
    condition     = length(jsondecode(aws_ecs_task_definition.backend.container_definitions)[0].secrets) == 0
    error_message = "Empty secret_arns must produce zero injected secrets."
  }
}

# Unknown keys in secret_arns are silently dropped — only recognised keys pass.
run "active_secrets_filters_unknown_keys" {
  command = plan

  variables {
    secret_arns = {
      database_url = "arn:aws:secretsmanager:eu-west-1:123456789012:secret:ltt/dev/database_url"
      redis_url    = "arn:aws:secretsmanager:eu-west-1:123456789012:secret:ltt/dev/redis_url"
      rogue_key    = "arn:aws:secretsmanager:eu-west-1:123456789012:secret:something/else"
    }
  }

  assert {
    condition     = length(jsondecode(aws_ecs_task_definition.backend.container_definitions)[0].secrets) == 2
    error_message = "rogue_key must be filtered out; only 2 known secrets should be injected."
  }
}

# Known keys are mapped to the correct LTT_ environment variable names.
run "active_secrets_uses_correct_env_var_names" {
  command = plan

  variables {
    secret_arns = {
      database_url      = "arn:aws:secretsmanager:eu-west-1:123456789012:secret:ltt/dev/database_url"
      anthropic_api_key = "arn:aws:secretsmanager:eu-west-1:123456789012:secret:ltt/dev/anthropic_api_key"
    }
  }

  assert {
    condition = contains(
      [for s in jsondecode(aws_ecs_task_definition.backend.container_definitions)[0].secrets : s.name],
      "LTT_DATABASE_URL"
    )
    error_message = "database_url must be injected as LTT_DATABASE_URL."
  }

  assert {
    condition = contains(
      [for s in jsondecode(aws_ecs_task_definition.backend.container_definitions)[0].secrets : s.name],
      "LTT_ANTHROPIC_API_KEY"
    )
    error_message = "anthropic_api_key must be injected as LTT_ANTHROPIC_API_KEY."
  }
}

# The migration task gets the same secret injection as the backend.
run "migrate_task_gets_same_secrets" {
  command = plan

  variables {
    secret_arns = {
      database_url = "arn:aws:secretsmanager:eu-west-1:123456789012:secret:ltt/dev/database_url"
    }
  }

  assert {
    condition     = length(jsondecode(aws_ecs_task_definition.migrate.container_definitions)[0].secrets) == 1
    error_message = "Migration task must receive the same secret injection as the backend."
  }
}

##############################################################################
# Validation rejection tests
##############################################################################

# Validation rejects unknown environment values.
run "invalid_environment_rejected" {
  command = plan

  variables {
    environment = "qa"
  }

  expect_failures = [var.environment]
}

# Validation rejects CPU values not in the Fargate allowed set.
run "invalid_cpu_rejected" {
  command = plan

  variables {
    cpu = 128
  }

  expect_failures = [var.cpu]
}

# Validation rejects memory below 512 MB.
run "memory_below_minimum_rejected" {
  command = plan

  variables {
    memory = 256
  }

  expect_failures = [var.memory]
}

# Validation rejects memory not aligned to 512 MB.
run "memory_not_multiple_of_512_rejected" {
  command = plan

  variables {
    memory = 768
  }

  expect_failures = [var.memory]
}

# Validation rejects desired_count = 0.
run "zero_desired_count_rejected" {
  command = plan

  variables {
    desired_count = 0
  }

  expect_failures = [var.desired_count]
}
