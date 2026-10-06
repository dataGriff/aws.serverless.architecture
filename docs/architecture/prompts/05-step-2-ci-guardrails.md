---
step: 2
when: >-
  Use for roadmap step 2 when turning the rules in generation-and-ci.md into CI checks: catalog PR checks, domain PR checks, the nightly skeleton, reusable versioned workflows with one failing fixture per rule. Triggers on 'CI guardrails', 'catalog CI', 'PR checks', 'reusable workflow'.
title: "Step 2 · CI guardrails for catalog and domain PRs"
read_first:
  - docs/architecture/generation-and-ci.md (CI section)
  - docs/architecture/conventions.md
  - docs/architecture/pii.md
  - docs/architecture/data-contracts.md
  - docs/architecture/adr/ADR-004-api-contracts.md
  - docs/architecture/adr/ADR-007-pii-in-events.md
  - docs/architecture/adr/ADR-012-data-contracts.md
  - docs/architecture/adr/ADR-016-lifecycle.md
---

# Step 2 · CI guardrails for catalog and domain PRs

{{> before-you-start}}

{{> hard-rules}}

**Read first:** {{read_first}}

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

{{> report-back}}
