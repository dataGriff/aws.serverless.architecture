terraform {
  required_providers {
    aws = { source = "hashicorp/aws", version = ">= 5.0" }
  }
}

# A rule on `source_bus_name` that forwards matching events to `target_bus_arn`.
# Used for both directions:
#   domain -> central : "public-forward" (pattern = domain's own public events)
#   central -> domain : "subscribe"      (pattern = what the domain's services receive)
# Every target has a DLQ so delivery failures (policy, throttling) are visible.

variable "name" {
  type = string
}

variable "source_bus_name" {
  type = string
}

variable "target_bus_arn" {
  type = string
}

variable "event_pattern" {
  description = "EventBridge event pattern as a map; the module JSON-encodes it."
  type        = any
}

variable "input_transformer" {
  description = "Optional { input_paths = {...}, input_template = \"...\" } to reshape into the published language."
  type = object({
    input_paths    = map(string)
    input_template = string
  })
  default = null
}

variable "tags" {
  type    = map(string)
  default = {}
}

resource "aws_sqs_queue" "dlq" {
  name                      = "${var.name}-dlq"
  message_retention_seconds = 1209600 # 14 days
  tags                      = var.tags
}

resource "aws_iam_role" "rule" {
  name = "${var.name}-role"
  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect    = "Allow"
      Principal = { Service = "events.amazonaws.com" }
      Action    = "sts:AssumeRole"
    }]
  })
  tags = var.tags
}

resource "aws_iam_role_policy" "rule" {
  name = "${var.name}-put-events"
  role = aws_iam_role.rule.id
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect   = "Allow"
      Action   = "events:PutEvents"
      Resource = var.target_bus_arn
    }]
  })
}

resource "aws_cloudwatch_event_rule" "this" {
  name           = var.name
  event_bus_name = var.source_bus_name
  event_pattern  = jsonencode(var.event_pattern)
  tags           = var.tags
}

resource "aws_cloudwatch_event_target" "bus" {
  rule           = aws_cloudwatch_event_rule.this.name
  event_bus_name = var.source_bus_name
  target_id      = "forward-to-bus"
  arn            = var.target_bus_arn
  role_arn       = aws_iam_role.rule.arn

  dead_letter_config {
    arn = aws_sqs_queue.dlq.arn
  }

  dynamic "input_transformer" {
    for_each = var.input_transformer == null ? [] : [var.input_transformer]
    content {
      input_paths    = input_transformer.value.input_paths
      input_template = input_transformer.value.input_template
    }
  }
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
      Condition = { ArnEquals = { "aws:SourceArn" = aws_cloudwatch_event_rule.this.arn } }
    }]
  })
}

output "rule_arn" { value = aws_cloudwatch_event_rule.this.arn }
output "dlq_url"  { value = aws_sqs_queue.dlq.id }
