terraform {
  required_version = ">= 1.6"
  required_providers {
    aws = { source = "hashicorp/aws", version = ">= 5.0" }
  }
}

# Real AWS sandbox. Same modules and the same hand-written patterns as envs/local, minus the LocalStack-only
# extras (archiver, Firehose probe, transformer). Exists to answer one question LocalStack cannot:
# does an event that reached central via a bus-to-bus rule get forwarded again to another domain bus?
# Apply:   task sandbox-apply    Test: task sandbox-test    Tear down: task sandbox-destroy

provider "aws" {
  region = var.region
}

variable "region" {
  type    = string
  default = "eu-west-2"
}

variable "fan_out_variant" {
  type    = string
  default = "anything-but"
}

data "aws_caller_identity" "me" {}

locals {
  tags       = { project = "spike-b", env = "sandbox" }
  patterns   = "${path.module}/../../../patterns" # SPIKE: replaced in spike C by generated/
  pattern    = { for f in fileset(local.patterns, "*.json") : trimsuffix(f, ".json") => jsondecode(file("${local.patterns}/${f}")) }
  domains    = ["orders", "payments"]
  account_id = data.aws_caller_identity.me.account_id
}

module "central_bus" {
  source                = "../../modules/event-bus"
  name                  = "central-bus"
  put_events_principals = ["arn:aws:iam::${local.account_id}:root"]
  tags                  = local.tags
}

module "domain_bus" {
  for_each              = toset(local.domains)
  source                = "../../modules/event-bus"
  name                  = "${each.key}-bus"
  put_events_principals = ["arn:aws:iam::${local.account_id}:root"]
  tags                  = local.tags
}

module "public_forward" {
  for_each        = toset(local.domains)
  source          = "../../modules/bus-forward-rule"
  name            = "${each.key}-public-forward"
  source_bus_name = module.domain_bus[each.key].name
  target_bus_arn  = module.central_bus.arn
  event_pattern   = local.pattern["${each.key}-public-forward"]
  tags            = local.tags
}

module "fan_out" {
  for_each        = toset(local.domains)
  source          = "../../modules/bus-forward-rule"
  name            = "${each.key}-fan-out"
  source_bus_name = module.central_bus.name
  target_bus_arn  = module.domain_bus[each.key].arn
  event_pattern   = local.pattern[var.fan_out_variant == "enumerated" ? "${each.key}-fan-out.enumerated" : "${each.key}-fan-out"]
  tags            = local.tags
}

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

module "probe" {
  for_each      = toset(concat(local.domains, ["central"]))
  source        = "../../modules/bus-sqs-rule"
  name          = "${each.key}-probe-all"
  bus_name      = each.key == "central" ? module.central_bus.name : module.domain_bus[each.key].name
  event_pattern = local.pattern["probe-all"]
  tags          = local.tags
}

module "broken_target" {
  source             = "../../modules/bus-sqs-rule"
  name               = "central-broken-target"
  bus_name           = module.central_bus.name
  event_pattern      = local.pattern["broken-target"]
  grant_queue_access = false
  tags               = local.tags
}

output "account_id" { value = local.account_id }
output "queues" {
  value = {
    orders_probe                     = module.probe["orders"].queue_url
    payments_probe                   = module.probe["payments"].queue_url
    central_probe                    = module.probe["central"].queue_url
    orders_consumer_payment_captured = module.consumer_orders_payment_captured.queue_url
    payments_consumer_order_placed   = module.consumer_payments_order_placed.queue_url
    broken_target_dlq                = module.broken_target.dlq_url
    orders_public_forward_dlq        = module.public_forward["orders"].dlq_url
    payments_public_forward_dlq      = module.public_forward["payments"].dlq_url
  }
}
output "dlqs" {
  value = {
    central-broken-target   = module.broken_target.dlq_url
    orders-public-forward   = module.public_forward["orders"].dlq_url
    payments-public-forward = module.public_forward["payments"].dlq_url
    orders-fan-out          = module.fan_out["orders"].dlq_url
    payments-fan-out        = module.fan_out["payments"].dlq_url
  }
}
output "broken_target_dlq_url" { value = module.broken_target.dlq_url }
output "fan_out_variant" { value = var.fan_out_variant }
