---
description: "Step 3 · Payments domain, with a saga and an external webhook"
---

# Step 3 · Payments domain, with a saga and an external webhook

## Before you start

Read, in this order: `docs/architecture/README.md` (index and glossary), `docs/architecture/decisions.md`, then the files under **Read first** below. Load nothing else until a task needs it. Work from a task list and keep it updated.

## Hard rules

- Everything in an account is generated from the catalog. Never hand-edit a rule, bucket, route, role, alarm or contract; change the catalog or the generator.
- Do not introduce Athena, Glue, Iceberg, Kinesis, Temporal, Step Functions outside the saga module, a central gateway, CloudFront, a Schema Registry or a data platform account. If you believe an ADR trigger has fired, stop and run `prompts/10-evaluate-a-trigger.md` instead.
- PII: every schema field carries `x-pii`. `indirect` travels in clear, `direct` is encrypted per subject in public events through the subject-key service, `special` never enters an event.
- Facts are events. One synchronous hop between domains, through a generated client. Never another domain's database or bucket.
- Tests before infrastructure: L0 contract (no infra) → L1 domain-local (LocalStack + pinned `platform-local`) → L2 platform. Never depend on another domain's code or a shared environment.
- Small commits with the ADR or doc section they implement named in the message. If a decision cannot be undone and the docs do not settle it, stop and ask, giving the options and your recommendation.

**Read first:** `docs/architecture/roadmap.md (Step 3)` · `docs/architecture/adr/ADR-003-orchestration.md` · `docs/architecture/adr/ADR-005-api-hosting.md` · `docs/architecture/adr/ADR-007-pii-in-events.md` · `docs/architecture/conventions.md`

## Goal

The second domain, added entirely through catalog PRs and the generator, exercising the parts orders did not: an externally reachable route, a stateful process, and PII arriving from outside.

## Build

- Catalog: domain `payments`, service `payment-service` (sends `PaymentCaptured.v1` public; receives `OrderPlaced.v1`), service `psp-webhook-ingest` (inbound webhook as OpenAPI with `x-external: true`; receives nothing, sends internal `payments.psp.webhook.received`), API `POST /v1/payments` (command) and `GET /v1/payments/{id}` (query).
- Generated: `payments-bus`, bucket pair, payments' and orders' subscribers on the stub central (subscriber-shaped rules targeting each domain's own queues), internal consumer rules on each domain bus, Firehose/shim, compactor, alarms, REST API with WAF on the webhook route.
- `psp-webhook-ingest`: signature verification, inbox table with idempotency, anti-corruption mapping to the internal event; any PSP-supplied PII classified `direct` before it leaves the inbox.
- The saga module driving authorise → capture → settle inside payments: state table, Scheduler-driven timeouts, compensation via payments' own events only, idempotent steps.
- A routing test across orders, payments and central: every public event takes exactly one bus-to-bus hop (domain bus → central), nothing is ever delivered from central to a domain bus, and each consumer queue receives one copy.

## Done when

- Payments' L0 and L1 suites are green with the orders repository absent; orders' suites are green with payments absent.
- A saga step that times out compensates through `payments.*` events and nothing else; a replayed `PaymentCaptured.v1` triggers no second settlement.
- A webhook with a bad signature is rejected before the handler; the WAF association exists on the external route in the generated API body.
- The routing test passes and no generated subscriber or stub rule targets a domain bus.

## Report back

Finish with: what was built (paths); each exit criterion with its evidence (test names and output, plan summaries, screenshots of the catalog where relevant); what you deliberately did not do and why; any ADR trigger you think is close to firing.
