---
step: cross-cutting
when: >-
  Use when adding a new public event, a new version of one, or changing an event's schema or visibility: the catalog PR, the expected generated diff, the producer's outbox write, L0/L1 tests, consumers' receives[], dual-publishing until deprecated.date. Triggers on 'add an event', 'publish a new event', 'new event version', 'change the schema of', 'make an event public'.
title: "Operation · Add or change a public event"
read_first:
  - docs/architecture/conventions.md
  - docs/architecture/pii.md
  - docs/architecture/data-contracts.md
  - docs/architecture/generation-and-ci.md
---

# Operation · Add or change a public event

{{> before-you-start}}

{{> hard-rules}}

**Read first:** {{read_first}}

## Goal

Take an event from idea to produced, archived, contracted and consumed, touching only the catalog, the generator's output review, and the producing service.

## Steps

1. Catalog PR: `events/<Event>/` with schema (every field `x-pii`; `direct` fields with `encryption: subject-key` and `decryptors`), `x-visibility`, `x-audience`, `x-source`, two examples as full envelopes (`direct` fields as ciphertext when public), the `data-product.yaml` overlay; `sends[].to` the event's channel on the service's own bus; `schemas/` references by `$id`. If the change is breaking, it is a new version: move the old one to `events/<Event>/versioned/<v>/` with its `odcs.yaml`, set `deprecated: {date, message}` on it, and plan to dual-publish.
2. Run `catalog-gen build` for `test`; review the generated diff — it should be: forward pattern, Firehose routing and validation bundle, Parquet schema, ODCS, the event's channel pages, view DDL, one alarm, and nothing else. Anything else means the catalog entry is wrong.
3. Producer: build the event with the shared library (envelope, `correlationId` from the inbound `X-Correlation-Id`, `direct` fields encrypted); write it to the outbox in the same transaction as the state change.
4. Tests: L0 (event validates against the catalog schema and envelope); L1 (`assert_published`, quarantine on a deliberately broken payload, ciphertext check, silver row with the expected `d_*` columns, `datacontract test` green).
5. Consumers: they subscribe with their own PR adding `receives[]` from their own `{domain}-sub.<detail-type>` channel; if the event is `x-audience: restricted`, obtain the producer approval entry; consumers bump their pin to see the new version.
6. On version bump: dual-publish until the old version's `deprecated.date`; CI will fail any consumer still on the old version past that date.

## Done when

The generated diff is exactly the expected set; L0/L1 green; the event page shows its data product with a passing contract badge; no hand edits anywhere.

{{> report-back}}
