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

{{> before-you-start}}

{{> hard-rules}}

**Read first:** {{read_first}}

## Goal

A minimal catalog that already exercises every concept the platform relies on, so the generator in step 2 has a real input and every later PR has a shape to copy.

## Build

Start from `templates/catalog-repo/` (one starter domain, `sample`, already passing `task all` against `platform/`): copy it to the catalog repository, pin `PLATFORM`, then rename `sample` to `orders` and shape it as below. The two-domain worked example with cross-domain subscriptions is `spikes/A-catalog-source-of-truth/catalog/`.

- Domain `orders` with owners; `CODEOWNERS` scoped to `domains/orders/**`, `services/order-service/**`, `events/Order*/**`.
- Service `order-service` with `sends[]`, `receives[]` (empty for now) and `specifications: [{type: openapi, path: openapi.yaml, name: …}]` (the list form; the older object form is legacy and does not render the spec page).
- Events: `OrderPlaced.v1` — `x-visibility: public`, `x-audience: all`, `x-source: orders.order-service`, fields `orderId`/`customerId` (`x-pii: indirect`), `total` (Money, `none`), `customerEmail` (`x-pii: direct`, `encryption: subject-key`, `decryptors: []`); `order.aggregate.updated` — `x-visibility: internal`, with an obviously internal field so the "never leaves" test has something to catch. Platform keys in frontmatter are `x-` prefixed: EventCatalog fails the build on unknown bare keys. JSON Schema per event describing the business fields only (`x-pii` on every property; the generator flattens `conventions/envelope.schema.json` into it for validation) and two example payloads each, written as full EventBridge envelopes.
- OpenAPI 3.1 for `order-service`: `POST /v1/orders` (`x-eventcatalog-message-type: command`, `Idempotency-Key` header, `problem+json` errors) and `GET /v1/orders/{id}` (`query`, cursor-less). Request/response bodies `$ref` `schemas/orders/Order` and `schemas/Money` relatively. Hand-write `commands/PlaceOrder` and `queries/GetOrder` pages (`id` = `operationId`, received by the service): core EventCatalog does not derive them from the spec; the step-2 generator takes them over.
- `schemas/` with value objects only at the root (`Money`, `Address`, `Identifier`) and `schemas/orders/Order`; every file declares `x-kind: value-object|entity` and an `$id` URL, and event schemas reference them by `$id` (relative refs break once an event moves under `versioned/`).
- Channels: hand-write only `orders-api`. Buses are names (`x-bus` on the domain), not channel pages; the per-event logical channels (`orders-bus.OrderPlaced.v1` → `central-bus.OrderPlaced.v1` → `{domain}-sub.OrderPlaced.v1`) are generated in step 2. Until then `order-service` `sends[].to` names `orders-bus.OrderPlaced.v1` and the page is a hand-written placeholder marked `x-generated: catalog-gen`.
- `events/OrderPlaced/data-product.yaml` overlay (SLAs, quality thresholds, terms, intended consumers; only the overlay-owned keys in `data-contracts.md`) and a placeholder `events/OrderPlaced/odcs.yaml` marked "hand-written until step 2". The current version lives at `events/<Event>/`; `versioned/<v>/` is for previous versions only.
- A JSON Schema for the overlay itself under `conventions/`.
- CI: the template's `.github/workflows/catalog-pr.yml`, made live: catalog build with a dirty-tree gate (`eventcatalog build` migrates frontmatter in place; fail if it rewrote a source file), Spectral, meta-schema check, ODCS lint, `$ref` resolution, "no entity in `schemas/` root".
- A README whose first line is "A PR here is how you publish an event, subscribe to one, or expose an API."

## Done when

- `npm run build` renders the catalog with the event page showing its schema and ODCS and the service page listing the command and query; the build leaves the tree clean.
- CI fails, with a message naming the convention, when: a field lacks `x-pii`; an operation lacks a message type; a public event carries a `special` field; a `direct` field on a public event has no `encryption`; an entity is placed in `schemas/` root.
- The OpenAPI passes Spectral; both example payloads validate against their schemas and the envelope.

## Notes

Use the installed EventCatalog version's folder conventions (`node_modules/@eventcatalog/core/dist/docs/`) and check how specifications and attachments render before modelling anything it cannot show. Render the ODCS with `<Schema file="odcs.yaml" lang="yaml" />` beside the event; do not claim a feature the version lacks. Spike A's `findings.md` lists what 4.12 renders and what it rejects.

{{> report-back}}
