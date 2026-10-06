---
description: "Operation · Add or change a public event"
---

# Operation · Add or change a public event

## Before you start

Read, in this order: `docs/architecture/README.md` (index and glossary), `docs/architecture/decisions.md`, then the files under **Read first** below. Load nothing else until a task needs it. Work from a task list and keep it updated.

## Hard rules

- Everything in an account is generated from the catalog. Never hand-edit a rule, bucket, route, role, alarm or contract; change the catalog or the generator.
- Do not introduce Athena, Glue, Iceberg, Kinesis, Temporal, Step Functions outside the saga module, a central gateway, CloudFront, a Schema Registry or a data platform account. If you believe an ADR trigger has fired, stop and run `prompts/10-evaluate-a-trigger.md` instead.
- PII: every schema field carries `x-pii`. `indirect` travels in clear, `direct` is encrypted per subject in public events through the subject-key service, `special` never enters an event.
- Facts are events. One synchronous hop between domains, through a generated client. Never another domain's database or bucket.
- Tests before infrastructure: L0 contract (no infra) → L1 domain-local (LocalStack + pinned `platform-local`) → L2 platform. Never depend on another domain's code or a shared environment.
- Small commits with the ADR or doc section they implement named in the message. If a decision cannot be undone and the docs do not settle it, stop and ask, giving the options and your recommendation.

**Read first:** `docs/architecture/conventions.md` · `docs/architecture/pii.md` · `docs/architecture/data-contracts.md` · `docs/architecture/generation-and-ci.md`

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

## Report back

Finish with: what was built (paths); each exit criterion with its evidence (test names and output, plan summaries, screenshots of the catalog where relevant); what you deliberately did not do and why; any ADR trigger you think is close to firing.
