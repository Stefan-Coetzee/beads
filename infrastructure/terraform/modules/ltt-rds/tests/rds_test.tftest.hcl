# Unit tests for ltt-rds module.
# Uses mock_provider — no AWS credentials or real resources required.
# Run: terraform test  (from the module directory)

mock_provider "aws" {}

variables {
  name_prefix           = "test"
  environment           = "dev"
  vpc_id                = "vpc-00000000000000001"
  subnet_ids            = ["subnet-00000000000000001", "subnet-00000000000000002"]
  security_group_id     = "sg-00000000000000001"
  initial_db_name       = "ltt_dev"
  master_username       = "ltt_user"
  master_password       = "test-password-abc123"
  backup_retention_days = 7
}

# Dev: no deletion protection, skips final snapshot.
run "dev_has_no_deletion_protection" {
  command = plan

  assert {
    condition     = aws_db_instance.ltt.deletion_protection == false
    error_message = "Dev environment must not enable deletion protection."
  }

  assert {
    condition     = aws_db_instance.ltt.skip_final_snapshot == true
    error_message = "Dev environment must skip the final snapshot."
  }
}

# Prod: deletion protection on, final snapshot kept.
run "prod_enables_deletion_protection" {
  command = plan

  variables {
    environment = "prod"
  }

  assert {
    condition     = aws_db_instance.ltt.deletion_protection == true
    error_message = "Prod environment must enable deletion protection."
  }

  assert {
    condition     = aws_db_instance.ltt.skip_final_snapshot == false
    error_message = "Prod environment must not skip the final snapshot."
  }
}

# Storage is always encrypted.
run "storage_is_encrypted" {
  command = plan

  assert {
    condition     = aws_db_instance.ltt.storage_encrypted == true
    error_message = "RDS storage must always be encrypted at rest."
  }
}

# Validation rejects unknown environment values.
run "invalid_environment_rejected" {
  command = plan

  variables {
    environment = "qa"
  }

  expect_failures = [var.environment]
}

# Validation rejects backup_retention_days > 35 (AWS limit).
run "invalid_backup_retention_rejected" {
  command = plan

  variables {
    backup_retention_days = 40
  }

  expect_failures = [var.backup_retention_days]
}

# Validation rejects backup_retention_days = 0.
run "zero_backup_retention_rejected" {
  command = plan

  variables {
    backup_retention_days = 0
  }

  expect_failures = [var.backup_retention_days]
}
