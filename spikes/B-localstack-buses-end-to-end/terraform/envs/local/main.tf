terraform {
  required_version = ">= 1.6"
  required_providers {
    aws = { source = "hashicorp/aws", version = ">= 5.0" }
  }
}

provider "aws" {
  region                      = "eu-west-1" # ADR-021: the platform region (the Custom Event Bus has no London endpoint)
  access_key                  = "test"
  secret_key                  = "test"
  skip_credentials_validation = true
  skip_metadata_api_check     = true
  skip_requesting_account_id  = true
  s3_use_path_style           = true
  endpoints {
    events   = var.localstack_endpoint
    sqs      = var.localstack_endpoint
    iam      = var.localstack_endpoint
    sts      = var.localstack_endpoint
    s3       = var.localstack_endpoint
    lambda   = var.localstack_endpoint
    logs     = var.localstack_endpoint
    firehose = var.localstack_endpoint
  }
}

# Spike C: every routing pattern, subscriber, bus-policy principal, validation bundle and the archive routing map
# come from catalog-gen's output. Nothing routing-shaped is written by hand in this file.
# Override to plan/apply a different generator output (the behaviour-through-the-catalog tests do this).
variable "generated_dir" {
  type    = string
  default = null
}

variable "localstack_endpoint" {
  type    = string
  default = "http://localhost:4566"
}

# Firehose is outside Spike B's boundary. This flag exists only for `task probe-firehose`, which checks whether
# LocalStack honours the three ADR-009 features: validation Lambda, dynamic partitioning, processing-failed/.
variable "enable_firehose_probe" {
  type    = bool
  default = false
}

# ADR-022: input transformers are not available on bus targets. Kept so the xfail test can keep proving it.
variable "enable_transformer_rule" {
  type    = bool
  default = false
}

locals {
  tags      = { project = "spike-c", env = "local" }
  generated = coalesce(var.generated_dir, "${path.module}/../../../../A-catalog-source-of-truth/generated/local")

  routing_map = jsondecode(file("${local.generated}/archive/routing-map.json"))
  domains     = sort([for prefix, _ in local.routing_map : trimsuffix(prefix, ".")])

  # rules/{domain}-public-forward[.part-N].json : domain bus -> central (the one bus-to-bus hop AWS allows)
  forward_rules = {
    for f in fileset(local.generated, "rules/*-public-forward*.json") :
    trimsuffix(basename(f), ".json") => {
      domain  = [for d in local.domains : d if startswith(basename(f), "${d}-public-forward")][0]
      pattern = jsondecode(file("${local.generated}/${f}"))
    }
  }
  # rules/{domain}-consumer-{event}.json : same-domain receives[], a rule on the domain's own bus
  consumer_rules = {
    for f in fileset(local.generated, "rules/*-consumer-*.json") :
    trimsuffix(basename(f), ".json") => {
      domain  = [for d in local.domains : d if startswith(basename(f), "${d}-consumer-")][0]
      pattern = jsondecode(file("${local.generated}/${f}"))
    }
  }
  # subscribers/{domain}-{event}.json : cross-domain receives[]. On AWS this is an eventsv2 subscriber on the
  # Custom central bus; in platform-local it is rendered as a Classic rule on the stub central with the same
  # filter, the same retry policy, its own DLQ and the consumer's queue as the single target (ADR-025, L1).
  subscribers = {
    for f in fileset(local.generated, "subscribers/*.json") :
    trimsuffix(basename(f), ".json") => jsondecode(file("${local.generated}/${f}"))
  }
  forwarding_domains = distinct([for k, v in local.forward_rules : v.domain])

  # Test scaffolding, not routing: a probe that sees everything on a bus, and an event type nobody publishes.
  probe_all     = { source = [{ prefix = "" }] }
  broken_target = { source = [{ prefix = "" }], detail-type = ["BrokenTargetProbe.v1"] }

  # One LocalStack account plays every role. The policies are still written cross-account style
  # (principal = account id) so the policy shape is exercised even though the boundary is not.
  account_id      = "000000000000"
  domain_accounts = { for d in local.domains : d => local.account_id }
}

# ---- Buses -------------------------------------------------------------------
# central: every domain with a forward rule may PutEvents (its public-forward rule's role).
module "central_bus" {
  source                = "../../modules/event-bus"
  name                  = "central-bus"
  put_events_principals = distinct([for d in local.forwarding_domains : "arn:aws:iam::${local.domain_accounts[d]}:root"])
  tags                  = local.tags
}

# domain: nobody outside the account puts events here (ADR-021: no fan-out from central), so no cross-account policy.
module "domain_bus" {
  for_each = toset(local.domains)
  source   = "../../modules/event-bus"
  name     = "${each.key}-bus"
  tags     = local.tags
}

# ---- Domain -> central: public-forward ----------------------------------------
module "public_forward" {
  for_each        = local.forward_rules
  source          = "../../modules/bus-forward-rule"
  name            = each.key
  source_bus_name = module.domain_bus[each.value.domain].name
  target_bus_arn  = module.central_bus.arn
  event_pattern   = each.value.pattern
  tags            = local.tags
}

# ---- Subscribers on central (Classic rendering of the eventsv2 subscriber) ----
module "subscriber" {
  for_each      = local.subscribers
  source        = "../../modules/bus-sqs-rule"
  name          = each.value.name
  bus_name      = module.central_bus.name
  event_pattern = each.value.filter
  retry_policy  = each.value.retryPolicy
  tags          = merge(local.tags, { account = each.value.account, targets = join(",", each.value.targets) })
}

# ---- Same-domain consumer rules on the domain's own bus ------------------------
module "consumer_rule" {
  for_each      = local.consumer_rules
  source        = "../../modules/bus-sqs-rule"
  name          = each.key
  bus_name      = module.domain_bus[each.value.domain].name
  event_pattern = each.value.pattern
  tags          = local.tags
}

# ---- Probes: everything on each domain bus, and everything on central ---------
module "probe" {
  for_each      = toset(concat(local.domains, ["central"]))
  source        = "../../modules/bus-sqs-rule"
  name          = "${each.key}-probe-all"
  bus_name      = each.key == "central" ? module.central_bus.name : module.domain_bus[each.key].name
  event_pattern = local.probe_all
  tags          = local.tags
}

# ---- Deliberately broken target: queue without an access policy -> DLQ -------
module "broken_target" {
  source             = "../../modules/bus-sqs-rule"
  name               = "central-broken-target"
  bus_name           = module.central_bus.name
  event_pattern      = local.broken_target
  grant_queue_access = false
  tags               = local.tags
}

# ---- Archive shim on central (ADR-024): validate against the generated bundle, route by the routing map ----
module "central_archive" {
  source           = "../../modules/bus-s3-archiver"
  name             = "central-archive"
  bus_name         = module.central_bus.name
  event_pattern    = local.probe_all
  routing_map      = local.routing_map
  fallback_bucket  = "platform-events-bronze"
  validation_files = [for f in fileset(local.generated, "validation/*.json") : "${local.generated}/${f}"]
  tags             = local.tags
}

module "firehose_probe" {
  count         = var.enable_firehose_probe ? 1 : 0
  source        = "../../modules/bus-firehose-archive"
  name          = "central-bronze"
  bus_name      = module.central_bus.name
  event_pattern = local.probe_all
  tags          = local.tags
}

output "firehose_bucket" { value = var.enable_firehose_probe ? module.firehose_probe[0].bucket : "" }

# ---- Optional: input transformer on a forward rule (ADR-022: rejected on AWS and on licensed LocalStack)
module "transformer_forward" {
  count           = var.enable_transformer_rule ? 1 : 0
  source          = "../../modules/bus-forward-rule"
  name            = "orders-transformer-forward"
  source_bus_name = module.domain_bus["orders"].name
  target_bus_arn  = module.central_bus.arn
  event_pattern   = { source = [{ prefix = "orders." }], detail-type = ["OrderPlacedTransformed.v1"] }
  input_transformer = {
    input_paths = {
      eventId     = "$.detail.eventId"
      occurredAt  = "$.detail.occurredAt"
      aggregateId = "$.detail.aggregateId"
      total       = "$.detail.total"
    }
    input_template = "{\"eventId\": <eventId>, \"occurredAt\": <occurredAt>, \"aggregateId\": <aggregateId>, \"total\": <total>}"
  }
  tags = local.tags
}

# ---- Outputs consumed by tests/harness.py -----------------------------------
output "queues" {
  value = merge(
    { for d in concat(local.domains, ["central"]) : "${d}_probe" => module.probe[d].queue_url },
    { for k, m in module.subscriber : "subscriber:${k}" => m.queue_url },
    { for k, m in module.consumer_rule : "consumer:${k}" => m.queue_url },
    { broken_target_dlq = module.broken_target.dlq_url },
  )
}
output "archive_buckets" { value = module.central_archive.buckets }
output "dlqs" {
  value = merge(
    { central-archive = module.central_archive.dlq_url, central-broken-target = module.broken_target.dlq_url },
    { for k, m in module.public_forward : k => m.dlq_url },
    { for k, m in module.subscriber : k => m.dlq_url },
    { for k, m in module.consumer_rule : k => m.dlq_url },
  )
}
output "broken_target_dlq_url" { value = module.broken_target.dlq_url }
output "generated_dir" { value = abspath(local.generated) }
output "rules" {
  description = "Every catalog-driven rule: name -> { bus, file } so a test can compare deployed patterns with generated/"
  value = merge(
    { for k, v in local.forward_rules : k => { bus = "${v.domain}-bus", file = "rules/${k}.json" } },
    { for k, v in local.consumer_rules : k => { bus = "${v.domain}-bus", file = "rules/${k}.json" } },
    { for k, v in local.subscribers : v.name => { bus = "central-bus", file = "subscribers/${k}.json" } },
  )
}
output "pattern_sizes" {
  value = merge(
    { for k, v in local.forward_rules : k => length(jsonencode(v.pattern)) },
    { for k, v in local.consumer_rules : k => length(jsonencode(v.pattern)) },
    { for k, v in local.subscribers : k => length(jsonencode(v.filter)) },
  )
}
