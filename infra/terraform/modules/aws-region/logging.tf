resource "aws_cloudwatch_log_group" "main" {
  name              = "/ecs/${var.project_name}/${var.environment}"
  retention_in_days = 30
  tags              = var.tags
}
