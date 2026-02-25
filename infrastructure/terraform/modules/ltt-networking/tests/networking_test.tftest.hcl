# Unit tests for ltt-networking module.
# Uses mock_provider — no AWS credentials or real resources required.
# Run: terraform test  (from the module directory)

mock_provider "aws" {}

variables {
  name_prefix            = "test"
  vpc_id                 = "vpc-00000000000000001"
  private_route_table_id = "rtb-00000000000000001"
  reverse_proxy_sg_id    = "sg-00000000000000001"
  # azs and *_cidrs use defaults: 2 AZs, 2 CIDRs each
}

# Creates one private subnet per AZ (for_each keyed by AZ).
run "creates_two_private_subnets" {
  command = plan

  assert {
    condition     = length(aws_subnet.private) == 2
    error_message = "Expected 2 private subnets — one per default AZ."
  }
}

# Creates one database subnet per AZ.
run "creates_two_database_subnets" {
  command = plan

  assert {
    condition     = length(aws_subnet.database) == 2
    error_message = "Expected 2 database subnets — one per default AZ."
  }
}

# Route table associations match subnet count.
run "route_table_associations_match_subnet_count" {
  command = plan

  assert {
    condition     = length(aws_route_table_association.private) == length(aws_subnet.private)
    error_message = "Each private subnet must have a route table association."
  }

  assert {
    condition     = length(aws_route_table_association.database) == length(aws_subnet.database)
    error_message = "Each database subnet must have a route table association."
  }
}

# Mismatched private_cidrs / azs lengths must be rejected by validation.
run "mismatched_private_cidrs_rejected" {
  command = plan

  variables {
    private_cidrs = ["10.0.12.0/24"] # 1 CIDR but azs defaults to 2 — should fail
  }

  expect_failures = [var.private_cidrs]
}

# Mismatched database_cidrs / azs lengths must be rejected by validation.
run "mismatched_database_cidrs_rejected" {
  command = plan

  variables {
    database_cidrs = ["10.0.23.0/24"] # 1 CIDR but azs defaults to 2 — should fail
  }

  expect_failures = [var.database_cidrs]
}
