locals {
  box_log_streams = ["kv-api", "kv-worker", "kv-fetcher", "kv-contributions", "nginx-access", "nginx-error"]
}

resource "aws_cloudwatch_log_group" "box" {
  for_each          = toset(local.box_log_streams)
  name              = "/${var.project}/${each.key}"
  retention_in_days = var.log_retention_days
}

resource "aws_iam_role_policy" "box_logs" {
  name = "${var.project}-box-logs"
  role = aws_iam_role.box.id
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid    = "ShipTheBoxLogs"
        Effect = "Allow"
        Action = [
          "logs:CreateLogStream",
          "logs:PutLogEvents",
          "logs:DescribeLogStreams",
        ]
        Resource = flatten([for group in aws_cloudwatch_log_group.box : [group.arn, "${group.arn}:*"]])
      },
    ]
  })
}
