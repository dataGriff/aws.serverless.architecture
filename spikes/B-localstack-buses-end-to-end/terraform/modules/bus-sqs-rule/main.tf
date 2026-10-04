terraform {
  required_providers {
    aws = { source = "hashicorp/aws", version = ">= 5.0" }
  }
}

# A rule on a bus whose target is an SQS queue (consumer or probe), with a DLQ.
# `grant_queue_access = false` produces the deliberately broken target for the DLQ test.

variable "name" { type = string }
variable "bus_name" { type = string }
variable "event_pattern" { type = any }
variable "grant_queue_access" {
  type    = bool
  default = true
}
variable "tags" {
  type    = map(string)
  default = {}
}

resource "aws_sqs_queue" "target" {
  name                       = var.name
  visibility_timeout_seconds = 5
  message_retention_seconds  = 3600
  tags                       = var.tags
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

resource "aws_cloudwatch_event_target" "sqs" {
  rule           = aws_cloudwatch_event_rule.this.name
  event_bus_name = var.bus_name
  target_id      = "sqs"
  arn            = aws_sqs_queue.target.arn
  dead_letter_config {
    arn = aws_sqs_queue.dlq.arn
  }
}

resource "aws_sqs_queue_policy" "target" {
  count     = var.grant_queue_access ? 1 : 0
  queue_url = aws_sqs_queue.target.id
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect    = "Allow"
      Principal = { Service = "events.amazonaws.com" }
      Action    = "sqs:SendMessage"
      Resource  = aws_sqs_queue.target.arn
      Condition = { ArnEquals = { "aws:SourceArn" = aws_cloudwatch_event_rule.this.arn } }
    }]
  })
}

resource "aws_sqs_queue_policy" "dlq" {
  queue_url = aws_sqs_queue.dlq.id
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect    = "Allow"
      Principal = { Service = "events.amazonaws.com" }
      Action    = "sqs:SendMessage"
      Resource  = aws_sqs_queue.dlq.arn
    }]
  })
}

output "queue_url" { value = aws_sqs_queue.target.id }
output "dlq_url" { value = aws_sqs_queue.dlq.id }
output "rule_arn" { value = aws_cloudwatch_event_rule.this.arn }
