---
name: arch-step-2-generator
description: Use for roadmap step 2 when extending the catalog generator (platform/catalog-gen): new emitters for API bodies, clients, alarms, roles, ROPA, env pins, deploy order, or when the generated output must replace a hand-written artefact byte for byte. Triggers on 'generator', 'catalog-gen', 'emit from the catalog', 'golden snapshot'.
---

# Step 2 · The catalog generator

## Before you start

Read, in this order: `docs/architecture/README.md` (index and glossary), `docs/architecture/decisions.md`, then the files under **Read first** below. Load nothing else until a task needs it. When a task needs what the catalog says (which services send or receive an event, which fields are `direct`, who owns what, what a change would break), ask the catalog rather than grepping it: through its MCP server when one is configured (`AGENTS.md`, *Querying the catalog*), otherwise through the published `llms.txt` and `schemas.txt`; open catalog files only to edit them. Work from a task list and keep it updated.

## Hard rules

- Everything in an account is generated from the catalog. Never hand-edit a rule, bucket, route, role, alarm or contract; change the catalog or the generator.
- Do not introduce Athena, Glue, Iceberg, Kinesis, Temporal, Step Functions outside the saga module, a central gateway, CloudFront, a Schema Registry or a data platform account. If you believe an ADR trigger has fired, stop and run `prompts/10-evaluate-a-trigger.md` instead.
- PII: every schema field carries `x-pii`. `indirect` travels in clear, `direct` is encrypted per subject in public events through the subject-key service, `special` never enters an event.
- Facts are events. One synchronous hop between domains, through a generated client. Never another domain's database or bucket.
- Tests before infrastructure: L0 contract (no infra) → L1 domain-local (LocalStack + pinned `platform-local`) → L2 platform. Never depend on another domain's code or a shared environment.
- Small commits with the ADR or doc section they implement named in the message. If a decision cannot be undone and the docs do not settle it, stop and ask, giving the options and your recommendation.

**Read first:** `docs/architecture/generation-and-ci.md` · `docs/architecture/data-contracts.md` · `docs/architecture/conventions.md` · `docs/architecture/adr/ADR-021-transport-routing-custom-bus.md` · `docs/architecture/adr/ADR-024-archive-firehose-subscriber.md` · `docs/architecture/adr/ADR-012-data-contracts.md` · `docs/architecture/adr/ADR-015-observability.md` · `docs/architecture/adr/ADR-017-source-of-truth.md`

## Goal

A deterministic generator — a pure function of (catalog release, environment config) — whose output under `generated/<env>/<account>/` is the only input Terraform reads for rules, streams, buckets, APIs, roles, alarms and contracts. Replace every hand-written artefact from step 1 with a generated one that is byte-identical.

## Emitters (one module each, unit-tested, golden-snapshot-tested against `fixtures/catalog-two-domains/`)

Forward rule patterns (split above 4 KB) · one subscriber per `receives[]` in the consumer's account (DATA filter = the pattern, delivery role, DLQ, retry 185/24h, `MaxBatchSize=1` for Lambda targets, a consumer-owned target reference `{service}-inbox`) — one file that Terraform renders as an eventsv2 subscriber in real accounts and as a Classic rule on the stub central in `platform-local`, never a separate twin · consumer rules on the domain bus for same-domain `receives[]` · Firehose subscribers with validation schema bundles (envelope flattened into each payload, `direct` fields schema-typed as the ciphertext envelope) and the archive routing map, packaged into the transform · Parquet schemas · ODCS contracts (event schema + `x-pii` + owners, merged with `data-product.yaml` under the overlay ownership rule), written into the catalog beside the event · the per-event logical channel pages written into the catalog · `commands/` and `queries/` pages from each OpenAPI (`operationId` → page id) · DuckDB view DDL · bucket definitions with lifecycle, CMK, Object Lock, replication flags · bus and bucket policy principal lists · per-domain reader roles and decryptor grants · REST API bodies with `x-amazon-apigateway-integration` per environment, request validators, authorizer config, WAF flags · typed clients, Prism config, Schemathesis job · alarms and dashboards · log-scrubbing config · subject-key encryption config · the deploy-order manifest (schemas → producer rules → central bus share → subscribers, one at a time per bus → clients) · environment pins · ROPA export.

## Design constraints

Python with uv; no network access; stable ordering and formatting so diffs are reviewable; `catalog-gen build --env test --out generated/` and `catalog-gen check` (fails on drift); semver, pinned with mise in every consuming repo; a `--explain <path>` that prints which catalog entry produced a given output file.

## Done when

- The step-1 hand-written outputs are byte-identical to the generated ones; the hand-written files are deleted.
- A test flips `x-visibility` on a fixture event and asserts the exact set of changed files: forward pattern, Firehose routing and validation bundle, silver schema, ODCS, channel pages, one alarm, nothing else — and the event's examples had to change too, because `direct` fields are ciphertext once public.
- A test adds a query to the fixture OpenAPI and asserts: one route, one validator, one integration, one client method, Prism serves it.
- `catalog-gen check` fails when any generated file is edited by hand.
- The generator has an owner pair and a release process documented in its README.

## Report back

Finish with: what was built (paths); each exit criterion with its evidence (test names and output, plan summaries, screenshots of the catalog where relevant); what you deliberately did not do and why; any ADR trigger you think is close to firing.
