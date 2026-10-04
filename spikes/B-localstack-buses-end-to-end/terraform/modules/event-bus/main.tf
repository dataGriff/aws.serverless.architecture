terraform {
  required_providers {
    aws = { source = "hashicorp/aws", version = ">= 5.0" }
  }
}

variable "name" {
  description = "Bus name, e.g. orders-bus or central-bus"
  type        = string
}

variable "put_events_principals" {
  description = "Account IDs (or role ARNs) allowed to PutEvents onto this bus. Empty = no cross-account policy."
  type        = list(string)
  default     = []
}

variable "tags" {
  type    = map(string)
  default = {}
}

resource "aws_cloudwatch_event_bus" "this" {
  name = var.name
  tags = var.tags
}

# Resource policy: who may put events on this bus.
# Central bus  -> each domain account
# Domain bus   -> the platform account
resource "aws_cloudwatch_event_bus_policy" "this" {
  count          = length(var.put_events_principals) > 0 ? 1 : 0
  event_bus_name = aws_cloudwatch_event_bus.this.name
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Sid       = "AllowPutEvents"
      Effect    = "Allow"
      Principal = { AWS = var.put_events_principals }
      Action    = "events:PutEvents"
      Resource  = aws_cloudwatch_event_bus.this.arn
    }]
  })
}

output "name" { value = aws_cloudwatch_event_bus.this.name }
output "arn"  { value = aws_cloudwatch_event_bus.this.arn }
