terraform {
  required_providers {
    aws     = { source = "hashicorp/aws", version = ">= 5.0" }
    archive = { source = "hashicorp/archive", version = ">= 2.4" }
  }
}

# Stretch from the Spike B prompt: a Lambda on a bus that writes every matching event raw to one S3 bucket,
# so "what flowed" can be inspected with DuckDB. Stands in for the Firehose archive LocalStack Community lacks.

variable "name" { type = string }
variable "bus_name" { type = string }
variable "event_pattern" { type = any }
variable "tags" {
  type    = map(string)
  default = {}
}

resource "aws_s3_bucket" "archive" {
  bucket        = var.name
  force_destroy = true
  tags          = var.tags
}

data "archive_file" "fn" {
  type        = "zip"
  source_file = "${path.module}/src/handler.py"
  output_path = "${path.module}/.build/${var.name}.zip"
}

resource "aws_iam_role" "fn" {
  name = "${var.name}-lambda-role"
  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect    = "Allow"
      Principal = { Service = "lambda.amazonaws.com" }
      Action    = "sts:AssumeRole"
    }]
  })
  tags = var.tags
}

resource "aws_iam_role_policy" "fn" {
  name = "${var.name}-put-object"
  role = aws_iam_role.fn.id
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      { Effect = "Allow", Action = "s3:PutObject", Resource = "${aws_s3_bucket.archive.arn}/*" },
      { Effect = "Allow", Action = ["logs:CreateLogGroup", "logs:CreateLogStream", "logs:PutLogEvents"], Resource = "*" },
    ]
  })
}

resource "aws_lambda_function" "fn" {
  function_name    = var.name
  role             = aws_iam_role.fn.arn
  runtime          = "python3.12"
  handler          = "handler.handler"
  filename         = data.archive_file.fn.output_path
  source_code_hash = data.archive_file.fn.output_base64sha256
  timeout          = 10
  environment {
    variables = { BUCKET = aws_s3_bucket.archive.bucket }
  }
  tags = var.tags
}

resource "aws_sqs_queue" "dlq" {
  name                      = "${var.name}-dlq"
  message_retention_seconds = 3600
  tags                      = var.tags
}

resource "aws_cloudwatch_event_rule" "this" {
  name           = var.name
  event_bus_name = var.bus_name
  event_pattern  = jsonencode(var.event_pattern)
  tags           = var.tags
}

resource "aws_cloudwatch_event_target" "fn" {
  rule           = aws_cloudwatch_event_rule.this.name
  event_bus_name = var.bus_name
  target_id      = "archiver"
  arn            = aws_lambda_function.fn.arn
  dead_letter_config {
    arn = aws_sqs_queue.dlq.arn
  }
}

resource "aws_lambda_permission" "events" {
  statement_id  = "AllowEventBridge"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.fn.function_name
  principal     = "events.amazonaws.com"
  source_arn    = aws_cloudwatch_event_rule.this.arn
}

output "bucket" { value = aws_s3_bucket.archive.bucket }
output "dlq_url" { value = aws_sqs_queue.dlq.id }
output "function_name" { value = aws_lambda_function.fn.function_name }
