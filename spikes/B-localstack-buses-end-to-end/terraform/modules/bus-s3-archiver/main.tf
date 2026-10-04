terraform {
  required_providers {
    aws     = { source = "hashicorp/aws", version = ">= 5.0" }
    archive = { source = "hashicorp/archive", version = ">= 2.4" }
  }
}

# ADR-024's local shim: a Lambda on a bus that validates every matching event against the catalog-generated
# validation bundle, routes it to the domain's bronze bucket by the generated routing map, and quarantines
# failures under processing-failed/. The validation function (src/validate.py) is the one Firehose would call
# on AWS; the bundles and routing map are generator output, packaged into the zip so a catalog change is a
# code change here (source_code_hash) and a config change (ROUTING_MAP).

variable "name" { type = string }
variable "bus_name" { type = string }
variable "event_pattern" { type = any }
variable "routing_map" {
  description = "generated/archive/routing-map.json: source prefix -> { bucket, detailTypes }"
  type        = map(object({ bucket = string, detailTypes = list(string) }))
}
variable "fallback_bucket" {
  description = "Where events whose source matches no routing-map prefix are quarantined"
  type        = string
}
variable "validation_files" {
  description = "generated/validation/*.json, packaged into the function as validation/<domain>.json"
  type        = list(string)
}
variable "tags" {
  type    = map(string)
  default = {}
}

locals {
  buckets = distinct(concat([for _, r in var.routing_map : r.bucket], [var.fallback_bucket]))
  deps    = "${path.module}/.build/deps" # task deps: fastjsonschema (pure Python) installed here
}

resource "aws_s3_bucket" "bronze" {
  for_each      = toset(local.buckets)
  bucket        = each.key
  force_destroy = true
  tags          = var.tags
}

data "archive_file" "fn" {
  type        = "zip"
  output_path = "${path.module}/.build/${var.name}.zip"

  dynamic "source" {
    for_each = fileset("${path.module}/src", "*.py")
    content {
      filename = source.value
      content  = file("${path.module}/src/${source.value}")
    }
  }
  dynamic "source" {
    for_each = fileset(local.deps, "**/*.py")
    content {
      filename = source.value
      content  = file("${local.deps}/${source.value}")
    }
  }
  dynamic "source" {
    for_each = toset(var.validation_files)
    content {
      filename = "validation/${basename(source.value)}"
      content  = file(source.value)
    }
  }
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
      { Effect = "Allow", Action = "s3:PutObject", Resource = [for b in aws_s3_bucket.bronze : "${b.arn}/*"] },
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
    variables = {
      ROUTING_MAP     = jsonencode(var.routing_map)
      FALLBACK_BUCKET = var.fallback_bucket
    }
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

output "buckets" {
  description = "source prefix -> bucket, plus '' -> the fallback bucket"
  value       = merge({ for p, r in var.routing_map : p => r.bucket }, { "" = var.fallback_bucket })
}
output "dlq_url" { value = aws_sqs_queue.dlq.id }
output "function_name" { value = aws_lambda_function.fn.function_name }
