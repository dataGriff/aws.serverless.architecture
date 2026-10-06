---
id: ADR-011
title: "Analytical layer"
concern: "Analytical layer"
decision: >-
  Compactor Lambda per domain, running at **T−2h** with a **daily re-compaction of yesterday** (late deliveries, retries up to 24h). One Parquet file per (type, hour), Hive partitions, catalog-typed `d_*` columns for `none`/`indirect` fields only — `direct` PII never becomes a column and stays ciphertext inside `detail`. Dedupe happens twice: in the compactor *and* in the views (`QUALIFY row_number() OVER (PARTITION BY event_id)`) because duplicates cross hour boundaries. A `.v2` event is a new directory.
status: accepted
date: 2026-10-04
reviewed: changed-after-review
revisit_when:
  - "Row-level updates, time travel or evolution beyond additive → PyIceberg in the compactor, same files"
  - "Humans need SQL/BI → Athena external tables over the existing silver"
---

# ADR-011 · Analytical layer

## Decision

Compactor Lambda per domain, running at **T−2h** with a **daily re-compaction of yesterday** (late deliveries, retries up to 24h). One Parquet file per (type, hour), Hive partitions, catalog-typed `d_*` columns for `none`/`indirect` fields only — `direct` PII never becomes a column and stays ciphertext inside `detail`. Dedupe happens twice: in the compactor *and* in the views (`QUALIFY row_number() OVER (PARTITION BY event_id)`) because duplicates cross hour boundaries. A `.v2` event is a new directory.

## Revisit only when

Row-level updates, time travel or evolution beyond additive → PyIceberg in the compactor, same files. Humans need SQL/BI → Athena external tables over the existing silver.

## How to change this

Open a PR that supersedes this ADR with the trigger named in `revisit_when` and the evidence that it fired. Set its `concern:`, `decision:` and `revisit_when` and run `task adr:build` in the same PR. Generated IaC follows the catalog, never the other way round.
