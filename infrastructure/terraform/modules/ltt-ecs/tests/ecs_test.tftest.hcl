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

# Validation rejects memory values below 512 MB.
run "memory_below_minimum_rejected" {
  command = plan

  variables {
    memory = 256
  }

  expect_failures = [var.memory]
}

# Validation rejects memory values not aligned to 512 MB.
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

# Dev environment: autoscaling should be off by default.
run "dev_has_no_autoscaling_by_default" {
  command = plan

  assert {
    condition     = var.enable_autoscaling == false
    error_message = "enable_autoscaling should default to false."
  }
}
