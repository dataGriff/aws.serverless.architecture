# Spike D — EventBridge Custom Event Bus (eventsv2) as the platform's central bus.
# One account plays platform and both domains; RAM sharing to other accounts is therefore NOT exercised here.

data "aws_caller_identity" "me" {}

locals {
  prefix   = "spike-d"
  patterns = "${path.module}/../patterns" # SPIKE: hand-written; the generator would emit these as DATA filters
  pattern  = { for f in fileset(local.patterns, "*.json") : trimsuffix(f, ".json") => jsondecode(file("${local.patterns}/${f}")) }
  account  = data.aws_caller_identity.me.account_id
  tags     = { project = "spike-d" }

  # Classic defaults are 185 attempts / 24 h; the Custom bus defaults to 5 / 300 s. Set explicitly, as the generator would.
  retry = { max_retry_attempts = 185, max_event_age_in_seconds = 86400 }
}

# ---- the bus ----------------------------------------------------------------------------------------
resource "awscc_eventsv2_event_bus" "central" {
  name        = "${local.prefix}-central"
  description = "Spike D: central bus, retention on, subscribers owned by consumers"
  storage_configuration = {
    retention_period_in_days = 7
  }
}

# ---- queues: consumers, probes, one deliberately unreachable target --------------------------------------
locals {
  standard_queues = [
    "payments-consumer-order-placed", # what receives[] would generate in the payments account
    "orders-consumer-payment-captured",
    "probe-all",      # everything, WITH_METADATA
    "probe-replay",   # target for the test-created POINT_IN_TIME subscriber
    "probe-classic",  # everything that lands on the Classic orders-bus
    "broken-target",  # the delivery role has no sqs:SendMessage on this one
  ]
  subscribers = [
    "payments-consumer-order-placed", "orders-consumer-payment-captured", "probe-all", "fifo-orders",
    "broken-target", "loop-back-to-classic", "test-owned",
  ]
}

resource "aws_sqs_queue" "q" {
  for_each                   = toset(local.standard_queues)
  name                       = "${local.prefix}-${each.key}"
  visibility_timeout_seconds = 5
  message_retention_seconds  = 3600
  tags                       = local.tags
}

resource "aws_sqs_queue" "fifo" {
  name                        = "${local.prefix}-probe-fifo.fifo"
  fifo_queue                  = true
  content_based_deduplication = false
  visibility_timeout_seconds  = 5
  message_retention_seconds   = 3600
  tags                        = local.tags
}

resource "aws_sqs_queue" "dlq" {
  for_each                  = toset(local.subscribers)
  name                      = "${local.prefix}-${each.key}-dlq"
  message_retention_seconds = 3600
  tags                      = local.tags
}

# probe-classic is a Classic rule target, so it needs a resource policy for events.amazonaws.com
resource "aws_sqs_queue_policy" "probe_classic" {
  queue_url = aws_sqs_queue.q["probe-classic"].id
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect = "Allow", Principal = { Service = "events.amazonaws.com" }, Action = "sqs:SendMessage"
      Resource = aws_sqs_queue.q["probe-classic"].arn
      Condition = { ArnEquals = { "aws:SourceArn" = aws_cloudwatch_event_rule.classic_probe.arn } }
    }]
  })
}

# ---- the delivery role every subscriber uses (one per consuming account in the real design) -----------------
resource "aws_iam_role" "delivery" {
  name = "${local.prefix}-delivery-role"
  assume_role_policy = jsonencode({
    Version   = "2012-10-17"
    Statement = [{ Effect = "Allow", Principal = { Service = "events.amazonaws.com" }, Action = "sts:AssumeRole" }]
  })
  tags = local.tags
}

resource "aws_iam_role_policy" "delivery" {
  name = "${local.prefix}-deliver"
  role = aws_iam_role.delivery.id
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid    = "QueuesAndDlqs"
        Effect = "Allow"
        Action = "sqs:SendMessage"
        Resource = concat(
          [for k, q in aws_sqs_queue.q : q.arn if k != "broken-target"], # broken-target deliberately missing
          [aws_sqs_queue.fifo.arn],
          [for q in aws_sqs_queue.dlq : q.arn],
        )
      },
      { Sid = "LoopBackToClassic", Effect = "Allow", Action = "events:PutEvents", Resource = aws_cloudwatch_event_bus.orders.arn },
    ]
  })
}

# ---- subscribers ------------------------------------------------------------------------------------------
resource "awscc_eventsv2_subscriber" "payments_consumer_order_placed" {
  name          = "${local.prefix}-payments-consumer-order-placed"
  event_bus_arn = awscc_eventsv2_event_bus.central.event_bus_arn
  filter_configuration = {
    filters = [{ scope = "DATA", pattern = jsonencode(local.pattern["payments-consumer-order-placed"]) }]
  }
  invoke_configuration     = { target_arn = aws_sqs_queue.q["payments-consumer-order-placed"].arn, role_arn = aws_iam_role.delivery.arn }
  retry_policy             = local.retry
  on_failure_configuration = { arn = aws_sqs_queue.dlq["payments-consumer-order-placed"].arn }
  depends_on               = [aws_iam_role_policy.delivery]
}

resource "awscc_eventsv2_subscriber" "orders_consumer_payment_captured" {
  name          = "${local.prefix}-orders-consumer-payment-captured"
  event_bus_arn = awscc_eventsv2_event_bus.central.event_bus_arn
  filter_configuration = {
    filters = [{ scope = "DATA", pattern = jsonencode(local.pattern["orders-consumer-payment-captured"]) }]
  }
  invoke_configuration     = { target_arn = aws_sqs_queue.q["orders-consumer-payment-captured"].arn, role_arn = aws_iam_role.delivery.arn }
  retry_policy             = local.retry
  on_failure_configuration = { arn = aws_sqs_queue.dlq["orders-consumer-payment-captured"].arn }
  depends_on               = [aws_iam_role_policy.delivery]
}

# everything, with SystemMetadata, so tests can see aws:DeliveryType, aws:SequenceNumber, EventGroupId
resource "awscc_eventsv2_subscriber" "probe_all" {
  name                     = "${local.prefix}-probe-all"
  event_bus_arn            = awscc_eventsv2_event_bus.central.event_bus_arn
  transformer              = { type = "WITH_METADATA" }
  invoke_configuration     = { target_arn = aws_sqs_queue.q["probe-all"].arn, role_arn = aws_iam_role.delivery.arn }
  retry_policy             = local.retry
  on_failure_configuration = { arn = aws_sqs_queue.dlq["probe-all"].arn }
  depends_on               = [aws_iam_role_policy.delivery]
}

# FIFO: ordered within EventGroupId, delivered to a FIFO queue keyed by the same group
resource "awscc_eventsv2_subscriber" "fifo_orders" {
  name          = "${local.prefix}-fifo-orders"
  event_bus_arn = awscc_eventsv2_event_bus.central.event_bus_arn
  type          = "FIFO"
  filter_configuration = {
    filters = [{ scope = "DATA", pattern = jsonencode({ source = [{ prefix = "orders." }] }) }]
  }
  transformer = { type = "WITH_METADATA" }
  invoke_configuration = {
    target_arn = aws_sqs_queue.fifo.arn
    role_arn   = aws_iam_role.delivery.arn
    sqs_parameters = {
      message_group_id         = "{% $events.SystemMetadata.EventGroupId %}"
      message_deduplication_id = "{% $events.SystemMetadata.`aws:EventId` %}"
    }
  }
  retry_policy             = local.retry
  on_failure_configuration = { arn = aws_sqs_queue.dlq["fifo-orders"].arn }
  depends_on               = [aws_iam_role_policy.delivery]
}

# the delivery role cannot write to this queue -> DLQ path, fast
resource "awscc_eventsv2_subscriber" "broken_target" {
  name          = "${local.prefix}-broken-target"
  event_bus_arn = awscc_eventsv2_event_bus.central.event_bus_arn
  filter_configuration = {
    filters = [{ scope = "DATA", pattern = jsonencode({ "detail-type" = ["BrokenTargetProbe.v1"] }) }]
  }
  invoke_configuration     = { target_arn = aws_sqs_queue.q["broken-target"].arn, role_arn = aws_iam_role.delivery.arn }
  retry_policy             = { max_retry_attempts = 1, max_event_age_in_seconds = 60 }
  on_failure_configuration = { arn = aws_sqs_queue.dlq["broken-target"].arn }
  depends_on               = [aws_iam_role_policy.delivery]
}

# bus-to-bus back to the Classic domain bus: is an event that came FROM that bus delivered again, dropped, or LOOP_DETECTED?
resource "awscc_eventsv2_subscriber" "loop_back_to_classic" {
  name          = "${local.prefix}-loop-back-to-classic"
  event_bus_arn = awscc_eventsv2_event_bus.central.event_bus_arn
  filter_configuration = {
    filters = [{ scope = "DATA", pattern = jsonencode({ source = [{ prefix = "orders." }], "detail-type" = ["OrderPlaced.v1"] }) }]
  }
  invoke_configuration     = { target_arn = aws_cloudwatch_event_bus.orders.arn, role_arn = aws_iam_role.delivery.arn }
  retry_policy             = { max_retry_attempts = 1, max_event_age_in_seconds = 60 }
  on_failure_configuration = { arn = aws_sqs_queue.dlq["loop-back-to-classic"].arn }
  depends_on               = [aws_iam_role_policy.delivery]
}

# ---- Classic side: a domain keeps its Classic bus and forwards public events to the Custom central bus ------
resource "aws_cloudwatch_event_bus" "orders" {
  name = "${local.prefix}-orders-bus"
  tags = local.tags
}

resource "aws_iam_role" "classic_forward" {
  name = "${local.prefix}-orders-forward-role"
  assume_role_policy = jsonencode({
    Version   = "2012-10-17"
    Statement = [{ Effect = "Allow", Principal = { Service = "events.amazonaws.com" }, Action = "sts:AssumeRole" }]
  })
  tags = local.tags
}

resource "aws_iam_role_policy" "classic_forward" {
  name = "${local.prefix}-put-events-v2"
  role = aws_iam_role.classic_forward.id
  policy = jsonencode({
    Version   = "2012-10-17"
    Statement = [{ Effect = "Allow", Action = ["events:PutEvents", "events:PutRawEvents"], Resource = awscc_eventsv2_event_bus.central.event_bus_arn }]
  })
}

resource "aws_cloudwatch_event_rule" "classic_forward" {
  name           = "${local.prefix}-orders-public-forward"
  event_bus_name = aws_cloudwatch_event_bus.orders.name
  event_pattern  = jsonencode(local.pattern["orders-public-forward"])
  tags           = local.tags
}

resource "aws_sqs_queue" "classic_forward_dlq" {
  name                      = "${local.prefix}-orders-public-forward-dlq"
  message_retention_seconds = 3600
  tags                      = local.tags
}

resource "aws_sqs_queue_policy" "classic_forward_dlq" {
  queue_url = aws_sqs_queue.classic_forward_dlq.id
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect = "Allow", Principal = { Service = "events.amazonaws.com" }, Action = "sqs:SendMessage"
      Resource = aws_sqs_queue.classic_forward_dlq.arn
      Condition = { ArnEquals = { "aws:SourceArn" = aws_cloudwatch_event_rule.classic_forward.arn } }
    }]
  })
}

resource "aws_cloudwatch_event_target" "classic_forward" {
  rule           = aws_cloudwatch_event_rule.classic_forward.name
  event_bus_name = aws_cloudwatch_event_bus.orders.name
  target_id      = "to-custom-central"
  arn            = awscc_eventsv2_event_bus.central.event_bus_arn
  role_arn       = aws_iam_role.classic_forward.arn
  dead_letter_config {
    arn = aws_sqs_queue.classic_forward_dlq.arn
  }
}

resource "aws_cloudwatch_event_rule" "classic_probe" {
  name           = "${local.prefix}-orders-probe-all"
  event_bus_name = aws_cloudwatch_event_bus.orders.name
  event_pattern  = jsonencode({ source = [{ prefix = "" }] })
  tags           = local.tags
}

resource "aws_cloudwatch_event_target" "classic_probe" {
  rule           = aws_cloudwatch_event_rule.classic_probe.name
  event_bus_name = aws_cloudwatch_event_bus.orders.name
  target_id      = "sqs"
  arn            = aws_sqs_queue.q["probe-classic"].arn
}

# ---- outputs for tests/harness.py -------------------------------------------------------------------------
output "bus_arn" { value = awscc_eventsv2_event_bus.central.event_bus_arn }
output "bus_name" { value = awscc_eventsv2_event_bus.central.name }
output "classic_bus_name" { value = aws_cloudwatch_event_bus.orders.name }
output "delivery_role_arn" { value = aws_iam_role.delivery.arn }
output "queues" {
  value = merge({ for k, q in aws_sqs_queue.q : k => q.id }, { "probe-fifo" = aws_sqs_queue.fifo.id })
}
output "dlqs" {
  value = merge({ for k, q in aws_sqs_queue.dlq : k => q.id }, { "classic-forward" = aws_sqs_queue.classic_forward_dlq.id })
}
output "dlq_arns" {
  value = { for k, q in aws_sqs_queue.dlq : k => q.arn }
}
output "subscriber_arns" {
  value = {
    payments-consumer-order-placed   = awscc_eventsv2_subscriber.payments_consumer_order_placed.subscriber_arn
    orders-consumer-payment-captured = awscc_eventsv2_subscriber.orders_consumer_payment_captured.subscriber_arn
    probe-all                        = awscc_eventsv2_subscriber.probe_all.subscriber_arn
    fifo-orders                      = awscc_eventsv2_subscriber.fifo_orders.subscriber_arn
    broken-target                    = awscc_eventsv2_subscriber.broken_target.subscriber_arn
    loop-back-to-classic             = awscc_eventsv2_subscriber.loop_back_to_classic.subscriber_arn
  }
}
