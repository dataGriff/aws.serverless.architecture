---
id: ADR-004
title: "API contracts"
concern: "API contracts"
decision: >-
  Design-first. OpenAPI 3.1 in the catalog under the owning service; each operation is a **command** (POST) or **query** (GET) via `x-eventcatalog-message-type`, so `sends[]`/`receives[]` cover APIs like events. `schemas/` holds **value objects only** (Money, Address, ids); entities live under `schemas/{domain}/` and are owned.
status: accepted
date: 2026-10-04
reviewed: unchanged
revisit_when:
  - "Many consumers of one API with divergent needs → add Pact consumer-driven contracts beside the spec"
---

# ADR-004 · API contracts

## Decision

Design-first. OpenAPI 3.1 in the catalog under the owning service; each operation is a **command** (POST) or **query** (GET) via `x-eventcatalog-message-type`, so `sends[]`/`receives[]` cover APIs like events. `schemas/` holds **value objects only** (Money, Address, ids); entities live under `schemas/{domain}/` and are owned.

## Revisit only when

Many consumers of one API with divergent needs → add Pact consumer-driven contracts beside the spec.

## How to change this

Open a PR that supersedes this ADR with the trigger named in `revisit_when` and the evidence that it fired. Set its `concern:`, `decision:` and `revisit_when` and run `task adr:build` in the same PR. Generated IaC follows the catalog, never the other way round.
