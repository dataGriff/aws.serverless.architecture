---
id: ADR-009
title: "Archive"
status: superseded
superseded_by: "ADR-024 — Firehose becomes a subscriber on central; LocalStack cannot test its partitioning, quarantine or transform contract"
date: 2026-10-04
reviewed: changed-after-review
revisit_when:
  - "Sub-minute analytics → a second Firehose target straight to Parquet"
---

# ADR-009 · Archive

## Decision

**Firehose, one stream per domain**, fed by a central rule on the domain's source prefix: dynamic partitioning on `source`/`detail-type`, NDJSON, 60s buffers, no per-event Lambda, no small files. The Firehose transform **validates every record against the catalog schema**; failures land under `processing-failed/` and raise an alarm, and a `direct`-classified field that arrives in clear is quarantined the same way, so the archive doubles as a live contract and PII monitor. Each domain also runs the same module on its own bus for **internal events** into a bucket in its own account (30-day retention) — the default, not optional.

## Revisit only when

Sub-minute analytics → a second Firehose target straight to Parquet.

## How to change this

Open a PR that supersedes this ADR with the trigger named in `revisit_when` and the evidence that it fired. Update `decisions.md` in the same PR. Generated IaC follows the catalog, never the other way round.
