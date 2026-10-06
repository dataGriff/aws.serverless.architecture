---
description: "Step 2 · CI guardrails for catalog and domain PRs"
---

# Step 2 · CI guardrails for catalog and domain PRs

## Before you start

Read, in this order: `docs/architecture/README.md` (index and glossary), `docs/architecture/decisions.md`, then the files under **Read first** below. Load nothing else until a task needs it. Work from a task list and keep it updated.

## Hard rules

- Everything in an account is generated from the catalog. Never hand-edit a rule, bucket, route, role, alarm or contract; change the catalog or the generator.
- Do not introduce Athena, Glue, Iceberg, Kinesis, Temporal, Step Functions outside the saga module, a central gateway, CloudFront, a Schema Registry or a data platform account. If you believe an ADR trigger has fired, stop and run `prompts/10-evaluate-a-trigger.md` instead.
- PII: every schema field carries `x-pii`. `indirect` travels in clear, `direct` is encrypted per subject in public events through the subject-key service, `special` never enters an event.
- Facts are events. One synchronous hop between domains, through a generated client. Never another domain's database or bucket.
- Tests before infrastructure: L0 contract (no infra) → L1 domain-local (LocalStack + pinned `platform-local`) → L2 platform. Never depend on another domain's code or a shared environment.
- Small commits with the ADR or doc section they implement named in the message. If a decision cannot be undone and the docs do not settle it, stop and ask, giving the options and your recommendation.

**Read first:** `docs/architecture/generation-and-ci.md (CI section)` · `docs/architecture/conventions.md` · `docs/architecture/pii.md` · `docs/architecture/data-contracts.md` · `docs/architecture/adr/ADR-004-api-contracts.md` · `docs/architecture/adr/ADR-007-pii-in-events.md` · `docs/architecture/adr/ADR-012-data-contracts.md` · `docs/architecture/adr/ADR-016-lifecycle.md`

## Goal

Every rule in `generation-and-ci.md` becomes a check that fails with a message naming the convention and linking the doc. Reusable workflows, versioned, consumed by the catalog repo and every domain repo.

## Catalog PR checks

Schema diff vs main (breaking change on a public event needs `.v{n+1}`) · `oasdiff` (breaking API change needs `/v{n+1}`) · Spectral · `x-pii` on every field, `special` forbidden anywhere, `direct` on a public event requires `encryption: subject-key` and a `decryptors` list · `receives[]` targets are public or same-domain · `x-audience: restricted` subscriptions carry producer approval · `source` namespace matches owning domain · every `$ref` resolves into `schemas/`, no entity at the root · nothing depends on a version past its `deprecated.date` (EventCatalog's only lifecycle field) · ODCS lint and diff · sync-hop-depth lint over the catalog graph · generated output and deploy-order manifest up to date (`catalog-gen check`, covering the ODCS and channel pages written into the catalog) · pattern size · `eventcatalog build` leaves the source tree clean.

## Domain PR checks

L0 contract tests · L1 LocalStack tests with the pinned `platform-local` · Schemathesis through gateway validation · compactor output vs the ODCS contract · generated clients compile at pinned versions and honour `Sunset`.

## Nightly skeleton

Job definitions for everything step 5 will run (reconciliation, drift, `datacontract test`, freshness, access review, ROPA), wired but allowed to no-op until step 5.

## Done when

- `fixtures/pr-cases/` holds one failing fixture per rule; a matrix job proves each fails for its own reason and a clean fixture passes.
- A clean catalog PR completes in under eight minutes; a clean domain PR in under twelve.
- Workflows are tagged and the catalog and orders repos consume them by tag.

## Report back

Finish with: what was built (paths); each exit criterion with its evidence (test names and output, plan summaries, screenshots of the catalog where relevant); what you deliberately did not do and why; any ADR trigger you think is close to firing.
