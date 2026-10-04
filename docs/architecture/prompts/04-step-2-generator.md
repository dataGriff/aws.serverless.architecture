---
step: 2
title: "Step 2 · The catalog generator"
read_first:
  - docs/architecture/generation-and-ci.md
  - docs/architecture/data-contracts.md
  - docs/architecture/conventions.md
  - docs/architecture/adr/ADR-001-transport-routing.md
  - docs/architecture/adr/ADR-009-archive.md
  - docs/architecture/adr/ADR-012-data-contracts.md
  - docs/architecture/adr/ADR-015-observability.md
  - docs/architecture/adr/ADR-017-source-of-truth.md
---

# Step 2 · The catalog generator

## Before you start

Read, in this order: `docs/architecture/README.md` (index and glossary), `docs/architecture/decisions.md`, then the files under **Read first** below. Load nothing else until a task needs it. Work from a task list and keep it updated.

## Hard rules

- Everything in an account is generated from the catalog. Never hand-edit a rule, bucket, route, role, alarm or contract; change the catalog or the generator.
- Do not introduce Athena, Glue, Iceberg, Kinesis, Temporal, Step Functions outside the saga module, a central gateway, CloudFront, a Schema Registry or a data platform account. If you believe an ADR trigger has fired, stop and run `prompts/10-evaluate-a-trigger.md` instead.
- PII: every schema field carries `x-pii`. `indirect` travels in clear, `direct` is encrypted per subject in public events through the subject-key service, `special` never enters an event.
- Facts are events. One synchronous hop between domains, through a generated client. Never another domain's database or bucket.
- Tests before infrastructure: L0 contract (no infra) → L1 domain-local (LocalStack + pinned `platform-local`) → L2 platform. Never depend on another domain's code or a shared environment.
- Small commits with the ADR or doc section they implement named in the message. If a decision cannot be undone and the docs do not settle it, stop and ask, giving the options and your recommendation.

**Read first:** `docs/architecture/generation-and-ci.md` · `docs/architecture/data-contracts.md` · `docs/architecture/conventions.md` · `docs/architecture/adr/ADR-001-transport-routing.md` · `docs/architecture/adr/ADR-009-archive.md` · `docs/architecture/adr/ADR-012-data-contracts.md` · `docs/architecture/adr/ADR-015-observability.md` · `docs/architecture/adr/ADR-017-source-of-truth.md`

## Goal

A deterministic generator — a pure function of (catalog release, environment config) — whose output under `generated/<env>/<account>/` is the only input Terraform reads for rules, streams, buckets, APIs, roles, alarms and contracts. Replace every hand-written artefact from step 1 with a generated one that is byte-identical.

## Emitters (one module each, unit-tested, golden-snapshot-tested against `fixtures/catalog-two-domains/`)

Forward rule patterns (split above 4 KB) · one subscriber per `receives[]` in the consumer's account (DATA filter = the pattern, delivery role, DLQ, retry 185/24h, `MaxBatchSize=1` for Lambda targets) and its Classic-rule twin for `platform-local` · Firehose subscribers with validation schema bundles and the `direct`-field ciphertext list · Parquet schemas · ODCS contracts (event schema + `x-pii` + owners, merged with `data-product.yaml`) · DuckDB view DDL · bucket definitions with lifecycle, CMK, Object Lock, replication flags · bus and bucket policy principal lists · per-domain reader roles and decryptor grants · REST API bodies with `x-amazon-apigateway-integration` per environment, request validators, authorizer config, WAF flags · typed clients, Prism config, Schemathesis job · alarms and dashboards · log-scrubbing config · subject-key encryption config · the deploy-order manifest (schemas → producer rules → central bus share → subscribers, one at a time per bus → clients) · environment pins · ROPA export.

## Design constraints

Python with uv; no network access; stable ordering and formatting so diffs are reviewable; `catalog-gen build --env test --out generated/` and `catalog-gen check` (fails on drift); semver, pinned with mise in every consuming repo; a `--explain <path>` that prints which catalog entry produced a given output file.

## Done when

- The step-1 hand-written outputs are byte-identical to the generated ones; the hand-written files are deleted.
- A test flips `visibility` on a fixture event and asserts the exact set of changed files: forward pattern, Firehose routing, silver schema, ODCS, one alarm, nothing else.
- A test adds a query to the fixture OpenAPI and asserts: one route, one validator, one integration, one client method, Prism serves it.
- `catalog-gen check` fails when any generated file is edited by hand.
- The generator has an owner pair and a release process documented in its README.

## Report back

Finish with: what was built (paths); each exit criterion with its evidence (test names and output, plan summaries, screenshots of the catalog where relevant); what you deliberately did not do and why; any ADR trigger you think is close to firing.
