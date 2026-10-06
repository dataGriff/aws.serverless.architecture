---
step: 5
when: >-
  Use for roadmap step 5: reader roles, DuckDB views across domain silvers, the nightly checks Lambda (reconciliation, drift, undocumented events, contract tests, freshness, ROPA, access review) and the first cross-domain question answered from silver. Triggers on 'reconciliation', 'nightly checks', 'read across domains', 'step 5', 'drift report'.
title: "Step 5 · Reading across domains, reconciliation and the nightly guardrails"
read_first:
  - docs/architecture/roadmap.md (Step 5)
  - docs/architecture/data-layer.md
  - docs/architecture/data-contracts.md
  - docs/architecture/generation-and-ci.md (nightly)
  - docs/architecture/adr/ADR-013-query-engine.md
  - docs/architecture/adr/ADR-015-observability.md
---

# Step 5 · Reading across domains, reconciliation and the nightly guardrails

{{> before-you-start}}

{{> hard-rules}}

**Read first:** {{read_first}}

## Goal

The first cross-domain answer from silver, and a nightly report that would have caught every fault we have so far imagined.

## Build

- Per-domain reader roles for people; DuckDB views that `UNION` deduped silver across the domain buckets, generated from the ODCS contracts; a Lambda runner for scheduled queries and a `task query` for laptops.
- Nightly checks Lambda: reconciliation (outbox counts vs bronze per domain per hour, tolerance from the contract); undocumented events (bronze vs catalog); quarantine volume split by schema failure vs clear-text `direct` PII; rule drift (account rules vs `generated/`); API drift (`get-export` vs catalog); partition completeness; bucket settings vs declarations; `datacontract test` per silver table and bronze envelope; freshness SLA; ROPA export; decryptor access review; erasure SLA.
- Results to alarms, a per-domain dashboard and catalog badges.
- Optional API access logs archived under `api/` in the domain's bronze bucket.

## Done when

- The nightly report exists, is clean, and each injected fault appears the next night: a hand-made rule, a hand-made route, a dropped event, a stale partition, a broken contract, a role with an unlisted decrypt grant.
- The first cross-domain question (orders × payments) is answered from silver by someone reading only the contracts.
- Adding a domain is demonstrably a catalog PR plus an account: do it for a fixture domain and time it.

{{> report-back}}
