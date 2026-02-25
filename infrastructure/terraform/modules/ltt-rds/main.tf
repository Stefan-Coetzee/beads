##############################################################################
# ltt-rds — LTT's own RDS PostgreSQL instance (independent from monitoring stack)
##############################################################################

resource "aws_db_subnet_group" "this" {
  name       = "${var.name_prefix}-db"
  subnet_ids = var.subnet_ids

  tags = { Name = "${var.name_prefix}-db" }
}

resource "aws_db_parameter_group" "this" {
  name   = "${var.name_prefix}-pg17"
  family = "postgres17"

  tags = { Name = "${var.name_prefix}-pg17" }
}

resource "aws_db_instance" "this" {
  identifier = var.name_prefix

  engine         = "postgres"
  engine_version = "17"
  instance_class = var.instance_class

  allocated_storage     = var.allocated_storage
  max_allocated_storage = var.max_allocated_storage
  storage_type          = "gp3"
  storage_encrypted     = true

  # Initial database. Additional databases (dev, staging checkpoints) are
  # created via psql after the instance is live.
  db_name  = var.initial_db_name
  username = var.master_username
  password = var.master_password

  db_subnet_group_name   = aws_db_subnet_group.this.name
  parameter_group_name   = aws_db_parameter_group.this.name
  vpc_security_group_ids = [var.security_group_id]

  multi_az            = var.multi_az
  publicly_accessible = false

  # Protect prod from accidental deletion
  deletion_protection       = var.environment == "prod"
  skip_final_snapshot       = var.environment != "prod"
  final_snapshot_identifier = var.environment == "prod" ? "${var.name_prefix}-final-snapshot" : null

  backup_retention_period = var.backup_retention_days
  backup_window           = "03:00-04:00"
  maintenance_window      = "Mon:04:00-Mon:05:00"

  # Performance Insights on prod (Multi-AZ instance)
  performance_insights_enabled = var.multi_az

  tags = {
    Name        = var.name_prefix
    Environment = var.environment
    Service     = "ltt"
  }
}
