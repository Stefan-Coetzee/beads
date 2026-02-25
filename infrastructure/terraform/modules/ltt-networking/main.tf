##############################################################################
# ltt-networking — new subnets and security groups in the existing ALX-AI VPC
##############################################################################

# Private subnets for ECS Fargate tasks and ElastiCache Redis
resource "aws_subnet" "private" {
  count             = length(var.private_cidrs)
  vpc_id            = var.vpc_id
  cidr_block        = var.private_cidrs[count.index]
  availability_zone = var.azs[count.index]

  tags = {
    Name = "${var.name_prefix}-private-${count.index + 1}"
  }
}

# Database subnets for LTT's own RDS instance
resource "aws_subnet" "database" {
  count             = length(var.database_cidrs)
  vpc_id            = var.vpc_id
  cidr_block        = var.database_cidrs[count.index]
  availability_zone = var.azs[count.index]

  tags = {
    Name = "${var.name_prefix}-database-${count.index + 1}"
  }
}

# Associate new subnets with the existing private route table (has NAT Gateway)
resource "aws_route_table_association" "private" {
  count          = length(aws_subnet.private)
  subnet_id      = aws_subnet.private[count.index].id
  route_table_id = var.private_route_table_id
}

resource "aws_route_table_association" "database" {
  count          = length(aws_subnet.database)
  subnet_id      = aws_subnet.database[count.index].id
  route_table_id = var.private_route_table_id
}

##############################################################################
# Security Groups
##############################################################################

# LTT ALB — accepts HTTP from the nginx reverse proxy only
resource "aws_security_group" "alb" {
  name        = "${var.name_prefix}-alb"
  description = "LTT ALB: inbound HTTP from reverse proxy only"
  vpc_id      = var.vpc_id

  ingress {
    description     = "HTTP from nginx reverse proxy"
    from_port       = 80
    to_port         = 80
    protocol        = "tcp"
    security_groups = [var.reverse_proxy_sg_id]
  }

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = { Name = "${var.name_prefix}-alb" }
}

# LTT ECS tasks — inbound from ALB only, outbound everywhere (ECR, Anthropic API)
resource "aws_security_group" "ecs" {
  name        = "${var.name_prefix}-ecs"
  description = "LTT ECS tasks: inbound from ALB, outbound to internet"
  vpc_id      = var.vpc_id

  ingress {
    description     = "All TCP from ALB"
    from_port       = 0
    to_port         = 65535
    protocol        = "tcp"
    security_groups = [aws_security_group.alb.id]
  }

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = { Name = "${var.name_prefix}-ecs" }
}

# LTT RDS — inbound PostgreSQL from ECS tasks only
resource "aws_security_group" "rds" {
  name        = "${var.name_prefix}-rds"
  description = "LTT RDS: PostgreSQL from ECS tasks only"
  vpc_id      = var.vpc_id

  ingress {
    description     = "PostgreSQL from ECS tasks"
    from_port       = 5432
    to_port         = 5432
    protocol        = "tcp"
    security_groups = [aws_security_group.ecs.id]
  }

  tags = { Name = "${var.name_prefix}-rds" }
}

# LTT Redis — inbound Redis from ECS tasks only
resource "aws_security_group" "redis" {
  name        = "${var.name_prefix}-redis"
  description = "LTT Redis: 6379 from ECS tasks only"
  vpc_id      = var.vpc_id

  ingress {
    description     = "Redis from ECS tasks"
    from_port       = 6379
    to_port         = 6379
    protocol        = "tcp"
    security_groups = [aws_security_group.ecs.id]
  }

  tags = { Name = "${var.name_prefix}-redis" }
}
