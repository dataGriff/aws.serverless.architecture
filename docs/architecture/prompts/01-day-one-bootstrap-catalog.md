---
step: day-one
title: "Day one · Bootstrap the EventCatalog repo"
read_first:
  - docs/architecture/data-contracts.md
  - docs/architecture/generation-and-ci.md
  - docs/architecture/conventions.md
  - docs/architecture/pii.md
  - conventions/ (from prompt 00)
---

# Day one · Bootstrap the EventCatalog repo

## Before you start

Read, in this order: `docs/architecture/README.md` (index and glossary), `docs/architecture/decisions.md`, then the files under **Read first** below. Load nothing else until a task needs it. Work from a task list and keep it updated.

## Hard rules

- Everything in an account is generated from the catalog. Never hand-edit a rule, bucket, route, role, alarm or contract; change the catalog or the generator.
- Do not introduce Athena, Glue, Iceberg, Kinesis, Temporal, Step Functions outside the saga module, a central gateway, CloudFront, a Schema Registry or a data platform account. If you believe an ADR trigger has fired, stop and run `prompts/10-evaluate-a-trigger.md` instead.
- PII: every schema field carries `x-pii`. `indirect` travels in clear, `direct` is encrypted per subject in public events through the subject-key service, `special` never enters an event.
- Facts are events. One synchronous hop between domains, through a generated client. Never another domain's database or bucket.
- Tests before infrastructure: L0 contract (no infra) → L1 domain-local (LocalStack + pinned `platform-local`) → L2 platform. Never depend on another domain's code or a shared environment.
- Small commits with the ADR or doc section they implement named in the message. If a decision cannot be undone and the docs do not settle it, stop and ask, giving the options and your recommendation.

**Read first:** `docs/architecture/data-contracts.md` · `docs/architecture/generation-and-ci.md` · `docs/architecture/conventions.md` · `docs/architecture/pii.md` · `conventions/ (from prompt 00)`

## Goal

A minimal catalog that already exercises every concept the platform relies on, so the generator in step 2 has a real input and every later PR has a shape to copy.

## Build

- Domain `orders` with owners; `CODEOWNERS` scoped to `domains/orders/**`, `services/order-service/**`, `events/Order*/**`.
- Service `order-service` with `sends[]`, `receives[]` (empty for now) and `specifications.openapiPath`.
- Events: `OrderPlaced.v1` — `visibility: public`, `audience: all`, fields `orderId`/`customerId` (`x-pii: indirect`), `total` (Money, `none`), `customerEmail` (`x-pii: direct`, `encryption: subject-key`, `decryptors: []`); `order.aggregate.updated` — internal, with an obviously internal field so the "never leaves" test has something to catch. JSON Schema and two example payloads each; both reference `conventions/envelope.schema.json`.
- OpenAPI 3.1 for `order-service`: `POST /v1/orders` (`x-eventcatalog-message-type: command`, `Idempotency-Key` header, `problem+json` errors) and `GET /v1/orders/{id}` (`query`, cursor-less). Request/response bodies `$ref` `schemas/orders/Order` and `schemas/Money`.
- `schemas/` with value objects only at the root (`Money`, `Address`, `Identifier`) and `schemas/orders/Order`.
- Channels: `central-bus`, `orders-bus`, `orders-api`.
- `events/OrderPlaced/versioned/1/data-product.yaml` overlay (SLAs, quality thresholds, terms, intended consumers) and a placeholder `odcs.yaml` marked "hand-written until step 2".
- A JSON Schema for the overlay itself under `conventions/`.
- CI: catalog build, Spectral, meta-schema check, ODCS lint, `$ref` resolution, "no entity in `schemas/` root".
- A README whose first line is "A PR here is how you publish an event, subscribe to one, or expose an API."

## Done when

- `npm run build` renders the catalog with the event page linking to the API operations and the data-product overlay.
- CI fails, with a message naming the convention, when: a field lacks `x-pii`; an operation lacks a message type; a public event carries a `special` field; a `direct` field on a public event has no `encryption`; an entity is placed in `schemas/` root.
- The OpenAPI passes Spectral; both example payloads validate against their schemas and the envelope.

## Notes

Use the installed EventCatalog version's folder conventions and check its docs for how specifications and attachments render before modelling anything it cannot show. Put the ODCS beside the event version and link it; do not claim a feature the version lacks.

## Report back

Finish with: what was built (paths); each exit criterion with its evidence (test names and output, plan summaries, screenshots of the catalog where relevant); what you deliberately did not do and why; any ADR trigger you think is close to firing.
