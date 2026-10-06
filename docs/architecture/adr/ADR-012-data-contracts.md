---
id: ADR-012
title: "Data contracts"
concern: "Data contracts"
decision: >-
  **ODCS v3** (Bitol Open Data Contract Standard) is the contract format for every dataset the platform serves. One contract per public event version's silver table, **generated** from the event's JSON Schema, `x-pii` classes and catalog ownership, plus a small hand-written overlay for SLAs, quality thresholds and terms of use. One envelope contract per domain's bronze. The contract is stored in the catalog beside the event version, rendered on a data-product page linked to the event, and is the input the generator uses for Parquet schemas, DuckDB view DDL, quality checks, reader grants and retention. `datacontract test` runs against real silver nightly; a failing check is an alarm and a badge on the catalog page. Nothing may be consumed outside its domain without a contract.
status: accepted
date: 2026-10-04
reviewed: changed-after-review
revisit_when:
  - "A dataset not derived from events (an external feed, a gold aggregate) → hand-authored ODCS, same tooling and tests"
  - "A data marketplace or mesh platform arrives → ODCS is what you publish to it; nothing else changes"
---

# ADR-012 · Data contracts

## Decision

**ODCS v3** (Bitol Open Data Contract Standard) is the contract format for every dataset the platform serves. One contract per public event version's silver table, **generated** from the event's JSON Schema, `x-pii` classes and catalog ownership, plus a small hand-written overlay for SLAs, quality thresholds and terms of use. One envelope contract per domain's bronze. The contract is stored in the catalog beside the event version, rendered on a data-product page linked to the event, and is the input the generator uses for Parquet schemas, DuckDB view DDL, quality checks, reader grants and retention. `datacontract test` runs against real silver nightly; a failing check is an alarm and a badge on the catalog page. Nothing may be consumed outside its domain without a contract.

## Revisit only when

A dataset not derived from events (an external feed, a gold aggregate) → hand-authored ODCS, same tooling and tests. A data marketplace or mesh platform arrives → ODCS is what you publish to it; nothing else changes.

## How to change this

Open a PR that supersedes this ADR with the trigger named in `revisit_when` and the evidence that it fired. Set its `concern:`, `decision:` and `revisit_when` and run `task adr:build` in the same PR. Generated IaC follows the catalog, never the other way round.
