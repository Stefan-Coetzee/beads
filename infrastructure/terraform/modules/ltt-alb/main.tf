##############################################################################
# ltt-alb — internal Application Load Balancer with target groups per service
#
# The ALB is internal (VPC-only). SSL termination is handled by the nginx
# reverse proxy. The nginx proxy forwards HTTP to the ALB on port 80.
#
# Target groups are created here (one backend + one frontend per env entry).
# ECS services reference these target group ARNs.
##############################################################################

resource "aws_lb" "this" {
  name               = var.name_prefix
  internal           = true
  load_balancer_type = "application"
  security_groups    = [var.alb_sg_id]
  subnets            = var.subnet_ids

  tags = {
    Name        = var.name_prefix
    Environment = var.environment
    Service     = "ltt"
  }
}

resource "aws_lb_listener" "http" {
  load_balancer_arn = aws_lb.this.arn
  port              = 80
  protocol          = "HTTP"

  # Default: 404 — all traffic must match a routing rule
  default_action {
    type = "fixed-response"
    fixed_response {
      content_type = "text/plain"
      message_body = "Not Found"
      status_code  = "404"
    }
  }
}

##############################################################################
# Target groups — one pair (backend + frontend) per environment entry
##############################################################################

resource "aws_lb_target_group" "backend" {
  for_each = var.routing_rules

  name        = "${each.key}-backend"
  port        = 8000
  protocol    = "HTTP"
  vpc_id      = var.vpc_id
  target_type = "ip"

  health_check {
    path                = "/health"
    interval            = 30
    timeout             = 5
    healthy_threshold   = 2
    unhealthy_threshold = 3
    matcher             = "200"
  }

  deregistration_delay = 30

  tags = { Name = "${each.key}-backend", Environment = each.key }
}

resource "aws_lb_target_group" "frontend" {
  for_each = var.routing_rules

  name        = "${each.key}-frontend"
  port        = 3000
  protocol    = "HTTP"
  vpc_id      = var.vpc_id
  target_type = "ip"

  health_check {
    path                = "/"
    interval            = 30
    timeout             = 5
    healthy_threshold   = 2
    unhealthy_threshold = 3
    matcher             = "200"
  }

  deregistration_delay = 30

  tags = { Name = "${each.key}-frontend", Environment = each.key }
}

##############################################################################
# Listener rules — API/LTI paths → backend, everything else → frontend
# Priority: (index * 10) so rules don't collide across environments
##############################################################################

resource "aws_lb_listener_rule" "backend" {
  for_each = var.routing_rules

  listener_arn = aws_lb_listener.http.arn
  priority     = 100 + index(sort(keys(var.routing_rules)), each.key) * 10

  action {
    type             = "forward"
    target_group_arn = aws_lb_target_group.backend[each.key].arn
  }

  # Match host header when running multiple envs on one ALB (dev-staging)
  dynamic "condition" {
    for_each = each.value.host != "" ? [each.value.host] : []
    content {
      host_header {
        values = [condition.value]
      }
    }
  }

  condition {
    path_pattern {
      values = ["/api/*", "/lti/*", "/health"]
    }
  }
}

resource "aws_lb_listener_rule" "frontend" {
  for_each = var.routing_rules

  listener_arn = aws_lb_listener.http.arn
  priority     = 200 + index(sort(keys(var.routing_rules)), each.key) * 10

  action {
    type             = "forward"
    target_group_arn = aws_lb_target_group.frontend[each.key].arn
  }

  # Match host header when running multiple envs on one ALB
  dynamic "condition" {
    for_each = each.value.host != "" ? [each.value.host] : []
    content {
      host_header {
        values = [condition.value]
      }
    }
  }

  condition {
    path_pattern {
      values = ["/*"]
    }
  }
}
