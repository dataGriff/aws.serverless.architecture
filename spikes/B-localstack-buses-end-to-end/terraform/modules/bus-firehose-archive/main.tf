terraform {
  required_providers {
    aws     = { source = "hashicorp/aws", version = ">= 5.0" }
    archive = { source = "hashicorp/archive", version = ">= 2.4" }
  }
}

# Firehose probe (outside Spike B's boundary; ADR-009's shape): a rule on a bus -> Firehose -> S3 with
# a validation Lambda, dynamic partitioning on source / detail-type, and a processing-failed/ prefix.

variable "name" { type = string }
variable "bus_name" { type = string }
variable "event_pattern" { type = any }
variable "tags" {
  type    = map(string)
  default = {}
}

resource "aws_s3_bucket" "bronze" {
  bucket        = var.name
  force_destroy = true
  tags          = var.tags
}

data "archive_file" "validator" {
  type        = "zip"
  source_file = "${path.module}/src/validator.py"
  output_path = "${path.module}/.build/${var.name}-validator.zip"
}

resource "aws_iam_role" "validator" {
  name = "${var.name}-validator-role"
  assume_role_policy = jsonencode({
    Version   = "2012-10-17"
    Statement = [{ Effect = "Allow", Principal = { Service = "lambda.amazonaws.com" }, Action = "sts:AssumeRole" }]
  })
  tags = var.tags
}

resource "aws_lambda_function" "validator" {
  function_name    = "${var.name}-validator"
  role             = aws_iam_role.validator.arn
  runtime          = "python3.12"
  handler          = "validator.handler"
  filename         = data.archive_file.validator.output_path
  source_code_hash = data.archive_file.validator.output_base64sha256
  timeout          = 60
  tags             = var.tags
}

resource "aws_iam_role" "firehose" {
  name = "${var.name}-firehose-role"
  assume_role_policy = jsonencode({
    Version   = "2012-10-17"
    Statement = [{ Effect = "Allow", Principal = { Service = "firehose.amazonaws.com" }, Action = "sts:AssumeRole" }]
  })
  tags = var.tags
}

resource "aws_iam_role_policy" "firehose" {
  name = "${var.name}-firehose"
  role = aws_iam_role.firehose.id
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      { Effect = "Allow", Action = ["s3:PutObject", "s3:GetBucketLocation", "s3:ListBucket"], Resource = [aws_s3_bucket.bronze.arn, "${aws_s3_bucket.bronze.arn}/*"] },
      { Effect = "Allow", Action = ["lambda:InvokeFunction", "lambda:GetFunctionConfiguration"], Resource = "${aws_lambda_function.validator.arn}:*" },
      { Effect = "Allow", Action = ["lambda:InvokeFunction", "lambda:GetFunctionConfiguration"], Resource = aws_lambda_function.validator.arn },
    ]
  })
}

resource "aws_kinesis_firehose_delivery_stream" "this" {
  name        = var.name
  destination = "extended_s3"

  extended_s3_configuration {
    role_arn            = aws_iam_role.firehose.arn
    bucket_arn          = aws_s3_bucket.bronze.arn
    prefix              = "bronze/source=!{partitionKeyFromLambda:source}/detail_type=!{partitionKeyFromLambda:detail_type}/"
    error_output_prefix = "processing-failed/!{firehose:error-output-type}/"
    buffering_interval  = 60
    buffering_size      = 64 # dynamic partitioning requires >= 64 MiB on AWS

    dynamic_partitioning_configuration {
      enabled = true
    }

    processing_configuration {
      enabled = true
      processors {
        type = "Lambda"
        parameters {
          parameter_name  = "LambdaArn"
          parameter_value = "${aws_lambda_function.validator.arn}:$LATEST"
        }
      }
    }
  }
  tags = var.tags
}

resource "aws_iam_role" "rule" {
  name = "${var.name}-rule-role"
  assume_role_policy = jsonencode({
    Version   = "2012-10-17"
    Statement = [{ Effect = "Allow", Principal = { Service = "events.amazonaws.com" }, Action = "sts:AssumeRole" }]
  })
  tags = var.tags
}

resource "aws_iam_role_policy" "rule" {
  name = "${var.name}-put-record"
  role = aws_iam_role.rule.id
  policy = jsonencode({
    Version   = "2012-10-17"
    Statement = [{ Effect = "Allow", Action = ["firehose:PutRecord", "firehose:PutRecordBatch"], Resource = aws_kinesis_firehose_delivery_stream.this.arn }]
  })
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

resource "aws_cloudwatch_event_target" "firehose" {
  rule           = aws_cloudwatch_event_rule.this.name
  event_bus_name = var.bus_name
  target_id      = "firehose"
  arn            = aws_kinesis_firehose_delivery_stream.this.arn
  role_arn       = aws_iam_role.rule.arn
  dead_letter_config {
    arn = aws_sqs_queue.dlq.arn
  }
}

output "bucket" { value = aws_s3_bucket.bronze.bucket }
output "stream" { value = aws_kinesis_firehose_delivery_stream.this.name }
output "dlq_url" { value = aws_sqs_queue.dlq.id }
