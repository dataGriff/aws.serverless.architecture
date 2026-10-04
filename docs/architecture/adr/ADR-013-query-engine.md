---
id: ADR-013
title: "Query engine"
status: accepted
date: 2026-10-04
reviewed: unchanged
revisit_when:
  - "Multi-GB single queries or many concurrent BI users → Athena on the same tables"
---

# ADR-013 · Query engine

## Decision

DuckDB — laptop, CI, Lambda. Views `UNION` across domain silvers with read-time dedupe.

## Revisit only when

Multi-GB single queries or many concurrent BI users → Athena on the same tables.

## How to change this

Open a PR that supersedes this ADR with the trigger named in `revisit_when` and the evidence that it fired. Update `decisions.md` in the same PR. Generated IaC follows the catalog, never the other way round.
