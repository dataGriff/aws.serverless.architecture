---
step: day-one
title: "Day one · Terraform module library and toolchain"
read_first:
  - docs/architecture/data-layer.md
  - docs/architecture/testing.md
  - docs/architecture/roadmap.md (Day one)
  - docs/architecture/adr/ADR-024-archive-firehose-subscriber.md
  - docs/architecture/adr/ADR-010-bucket-location-protection.md
  - docs/architecture/adr/ADR-011-analytical-layer.md
  - docs/architecture/adr/ADR-015-observability.md
---

# Day one · Terraform module library and toolchain

{{> before-you-start}}

{{> hard-rules}}

**Read first:** {{read_first}}

## Goal

The module library every repo will consume, each module validated and smoke-tested against LocalStack where LocalStack can, with the gaps named rather than papered over.

## Modules (one directory each, README, example, test)

Five already exist under `platform/terraform/modules` (`event-bus`, `bus-forward-rule`, `bus-sqs-rule`, `bus-s3-archiver`, `bus-firehose-archive`), proven by Spike B and C; `platform_testing` is seeded under `platform/platform_testing`. Extend the library there; do not start a second one. Spike D's `terraform/main.tf` has the proven `awscc_eventsv2_*` resource shapes for `custom-event-bus` and `subscriber`.

`event-bus` (Classic, domain) · `custom-event-bus` (eventsv2 central via `awscc`: retention, RAM share, resource policy) · `subscriber` (awscc; DATA filter, delivery role, DLQ, retry 185/24h, optional FIFO and JSONata transform; applied serially) · `bus-forward-rule` (no input transformer — rejected on bus targets; splits patterns above 4 KB) · `firehose-archive` (as a subscriber on central; dynamic partitioning on source/detail-type, GZIP NDJSON, validation transform Lambda loading a schema bundle, ciphertext check for `direct` fields, `processing-failed/`) · `compactor` (T−2h window, daily re-compaction, dedupe, Parquet types exactly as `data-layer.md`, file metadata) · `domain-buckets` (bronze + silver, CMK, Object Lock, versioning, lifecycle from inputs, read grants) · `rest-api` (REST API from an OpenAPI body with integrations, request validators, authorizer, WAF association when `x-external`) · `outbox-relay` (DynamoDB Streams → Pipes → PutEvents) · `idempotency-store` · `saga` (DynamoDB state + Scheduler, and a Step Functions template variant) · `subject-keys` (table, KMS, get-or-create/get/delete API with approval + grace on delete, `SubjectErased` emission, client library with encrypt/decrypt and log scrubbing) · `alarms` (per rule, DLQ, stream, compactor, API) · `platform-local` (Classic stub central + subscriber-shaped consumer rules + archive shim + compactor + a domain's bucket pair; pinned licensed LocalStack with `ENFORCE_IAM=1`).

## Toolchain

`.mise.toml` (terraform, task, uv, awscli, node), a root `Taskfile.yml` (`up`, `apply`, `test`, `query`, `compact`, `reset`, `lint`), LocalStack compose, pytest + DuckDB, Spectral, oasdiff, Prism, Schemathesis, datacontract-cli. Document the sandbox AWS account used for the nightly L2 run and how CI assumes a role in it with OIDC.

## Done when

- `terraform validate` and tflint pass for every module; each has an `examples/basic` that applies in LocalStack.
- Each module has at least one behavioural test (a LocalStack smoke, or for features LocalStack Community lacks — Firehose dynamic partitioning, WAF, REST validators — a documented shim and a test marked `sandbox-only`).
- The `subject-keys` client round-trips encrypt → decrypt, refuses decrypt for an ungranted role, and returns "erased" after a key deletion.
- Modules are tagged `v0.1.0`; a fresh clone runs `mise install && task up && task apply && task test` in `examples/` green in under ten minutes.

{{> report-back}}
