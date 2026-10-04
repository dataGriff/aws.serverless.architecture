terraform {
  required_version = ">= 1.6"
  required_providers {
    aws = { source = "hashicorp/aws", version = ">= 5.0" }
  }
}

provider "aws" {
  region                      = "eu-west-2"
  access_key                  = "test"
  secret_key                  = "test"
  skip_credentials_validation = true
  skip_metadata_api_check     = true
  skip_requesting_account_id  = true
  s3_use_path_style           = true
  endpoints {
    events = var.localstack_endpoint
    sqs    = var.localstack_endpoint
    iam    = var.localstack_endpoint
    sts    = var.localstack_endpoint
    s3     = var.localstack_endpoint
    lambda = var.localstack_endpoint
    logs   = var.localstack_endpoint
  }
}

variable "localstack_endpoint" {
  type    = string
  default = "http://localhost:4566"
}

# "anything-but" uses {"anything-but": {"prefix": ...}}; "enumerated" lists the other domains' prefixes.
# Spike B's job is to find out which LocalStack honours. Spike C makes this a generator flag.
variable "fan_out_variant" {
  type    = string
  default = "anything-but"
}

# ADR-006 assumes an input transformer can reshape a public event on the forward rule.
# That is UNVERIFIED for event-bus targets. Enable to test; record the answer in findings.md.
variable "enable_transformer_rule" {
  type    = bool
  default = false
}

locals {
  tags     = { project = "spike-b", env = "local" }
  patterns = "${path.module}/../../../patterns" # SPIKE: replaced in spike C by generated/local/
  pattern  = { for f in fileset(local.patterns, "*.json") : trimsuffix(f, ".json") => jsondecode(file("${local.patterns}/${f}")) }
  domains  = ["orders", "payments"]

  # One LocalStack account plays every role. The policies are still written cross-account style
  # (principal = account id) so the policy shape is exercised even though the boundary is not.
  account_id       = "000000000000"
  platform_account = local.account_id
  domain_accounts  = { for d in local.domains : d => local.account_id }
}

# ---- Buses -------------------------------------------------------------------
# central: every domain account may PutEvents (their public-forward rules).
module "central_bus" {
  source                = "../../modules/event-bus"
  name                  = "central-bus"
  put_events_principals = distinct([for d in local.domains : "arn:aws:iam::${local.domain_accounts[d]}:root"])
  tags                  = local.tags
}

# domain: only the platform account may PutEvents (its fan-out rule).
module "domain_bus" {
  for_each              = toset(local.domains)
  source                = "../../modules/event-bus"
  name                  = "${each.key}-bus"
  put_events_principals = ["arn:aws:iam::${local.platform_account}:root"]
  tags                  = local.tags
}

# ---- Domain -> central: public-forward --------------------------------------
module "public_forward" {
  for_each        = toset(local.domains)
  source          = "../../modules/bus-forward-rule"
  name            = "${each.key}-public-forward"
  source_bus_name = module.domain_bus[each.key].name
  target_bus_arn  = module.central_bus.arn
  event_pattern   = local.pattern["${each.key}-public-forward"]
  tags            = local.tags
}

# ---- Central -> domain: fan-out-all (everything public except the domain's own)
module "fan_out" {
  for_each        = toset(local.domains)
  source          = "../../modules/bus-forward-rule"
  name            = "${each.key}-fan-out"
  source_bus_name = module.central_bus.name
  target_bus_arn  = module.domain_bus[each.key].arn
  event_pattern   = local.pattern[var.fan_out_variant == "enumerated" ? "${each.key}-fan-out.enumerated" : "${each.key}-fan-out"]
  tags            = local.tags
}

# ---- Consumer rules on each domain's own bus (what the generator emits from receives[])
module "consumer_orders_payment_captured" {
  source        = "../../modules/bus-sqs-rule"
  name          = "orders-consumer-payment-captured"
  bus_name      = module.domain_bus["orders"].name
  event_pattern = local.pattern["orders-consumer-payment-captured"]
  tags          = local.tags
}

module "consumer_payments_order_placed" {
  source        = "../../modules/bus-sqs-rule"
  name          = "payments-consumer-order-placed"
  bus_name      = module.domain_bus["payments"].name
  event_pattern = local.pattern["payments-consumer-order-placed"]
  tags          = local.tags
}

# ---- Probes: everything on each domain bus, and everything on central ---------
module "probe" {
  for_each      = toset(concat(local.domains, ["central"]))
  source        = "../../modules/bus-sqs-rule"
  name          = "${each.key}-probe-all"
  bus_name      = each.key == "central" ? module.central_bus.name : module.domain_bus[each.key].name
  event_pattern = local.pattern["probe-all"]
  tags          = local.tags
}

# ---- Deliberately broken target: queue without an access policy -> DLQ -------
module "broken_target" {
  source             = "../../modules/bus-sqs-rule"
  name               = "central-broken-target"
  bus_name           = module.central_bus.name
  event_pattern      = local.pattern["broken-target"]
  grant_queue_access = false
  tags               = local.tags
}

# ---- Stretch: raw archiver on central -> S3, inspected with DuckDB (stands in for Firehose) ----
module "central_archive" {
  source        = "../../modules/bus-s3-archiver"
  name          = "central-archive"
  bus_name      = module.central_bus.name
  event_pattern = local.pattern["probe-all"]
  tags          = local.tags
}

# ---- Optional: input transformer on a forward rule (verify support for bus targets)
module "transformer_forward" {
  count           = var.enable_transformer_rule ? 1 : 0
  source          = "../../modules/bus-forward-rule"
  name            = "orders-transformer-forward"
  source_bus_name = module.domain_bus["orders"].name
  target_bus_arn  = module.central_bus.arn
  event_pattern   = local.pattern["orders-transformer-forward"]
  input_transformer = {
    input_paths = {
      eventId      = "$.detail.eventId"
      occurredAt   = "$.detail.occurredAt"
      aggregateId  = "$.detail.aggregateId"
      total        = "$.detail.total"
    }
    input_template = "{\"eventId\": <eventId>, \"occurredAt\": <occurredAt>, \"aggregateId\": <aggregateId>, \"total\": <total>}"
  }
  tags = local.tags
}

# ---- Outputs consumed by tests/harness.py -----------------------------------
output "queues" {
  value = {
    orders_probe                    = module.probe["orders"].queue_url
    payments_probe                  = module.probe["payments"].queue_url
    central_probe                   = module.probe["central"].queue_url
    orders_consumer_payment_captured = module.consumer_orders_payment_captured.queue_url
    payments_consumer_order_placed  = module.consumer_payments_order_placed.queue_url
    broken_target_dlq               = module.broken_target.dlq_url
    orders_public_forward_dlq       = module.public_forward["orders"].dlq_url
    payments_public_forward_dlq     = module.public_forward["payments"].dlq_url
  }
}
output "archive_bucket" { value = module.central_archive.bucket }
output "dlqs" {
  value = {
    central-archive         = module.central_archive.dlq_url
    central-broken-target   = module.broken_target.dlq_url
    orders-public-forward   = module.public_forward["orders"].dlq_url
    payments-public-forward = module.public_forward["payments"].dlq_url
    orders-fan-out          = module.fan_out["orders"].dlq_url
    payments-fan-out        = module.fan_out["payments"].dlq_url
  }
}
output "broken_target_dlq_url" { value = module.broken_target.dlq_url }
output "fan_out_variant" { value = var.fan_out_variant }
output "pattern_sizes" { value = { for k, v in local.pattern : k => length(jsonencode(v)) } }
