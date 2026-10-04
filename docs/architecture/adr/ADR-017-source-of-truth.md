---
id: ADR-017
title: "Source of truth"
status: accepted
date: 2026-10-04
reviewed: unchanged
revisit_when:
  - "The monorepo becomes the bottleneck → federated catalogs, same model"
---

# ADR-017 · Source of truth

## Decision

EventCatalog repo; generator emits rules, policies, streams, bucket defs, Parquet and validation schemas, gateway bodies, authorizers, clients, mocks, alarms, reader roles, env pins; CI guards. CODEOWNERS per domain path; additive changes auto-merge; generator semver-pinned per account; applies canary in order (platform → one domain → rest). **No EventBridge Schema Registry** — drift is caught by the Firehose validation and the nightly checks.

## Revisit only when

The monorepo becomes the bottleneck → federated catalogs, same model.

## How to change this

Open a PR that supersedes this ADR with the trigger named in `revisit_when` and the evidence that it fired. Update `decisions.md` in the same PR. Generated IaC follows the catalog, never the other way round.
