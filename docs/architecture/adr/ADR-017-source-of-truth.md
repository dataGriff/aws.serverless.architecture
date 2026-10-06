---
id: ADR-017
title: "Source of truth"
concern: "Source of truth"
decision: >-
  EventCatalog repo; generator emits rules, policies, streams, bucket defs, Parquet and validation schemas, gateway bodies, authorizers, clients, mocks, alarms, reader roles, env pins; CI guards. CODEOWNERS per domain path; additive changes auto-merge; generator semver-pinned per account; applies canary in order (platform → one domain → rest). **No EventBridge Schema Registry** — drift is caught by the Firehose validation and the nightly checks.
status: accepted
date: 2026-10-04
reviewed: unchanged
revisit_when:
  - "The monorepo becomes the bottleneck → federated catalogs, same model"
---

# ADR-017 · Source of truth

## Decision

EventCatalog repo; generator emits rules, policies, streams, bucket defs, Parquet and validation schemas, gateway bodies, authorizers, clients, mocks, alarms, reader roles, env pins; CI guards. CODEOWNERS per domain path; additive changes auto-merge; generator semver-pinned per account; applies canary in order (platform → one domain → rest). **No EventBridge Schema Registry** — drift is caught by the Firehose validation and the nightly checks.

Two clarifications from Spikes A and C (2026-10-04): the catalog build must be idempotent on its sources — CI fails when `eventcatalog build` rewrites a file — and `CODEOWNERS` is generated to the repo root from the catalog's per-domain file whenever the catalog shares a repo. Generated artefacts that the site must render (ODCS contracts, per-event channel pages) are written into the catalog and committed; `catalog-gen check` covers them like any file under `generated/`.

## Revisit only when

The monorepo becomes the bottleneck → federated catalogs, same model.

## How to change this

Open a PR that supersedes this ADR with the trigger named in `revisit_when` and the evidence that it fired. Set its `concern:`, `decision:` and `revisit_when` and run `task adr:build` in the same PR. Generated IaC follows the catalog, never the other way round.
