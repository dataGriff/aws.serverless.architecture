---
id: ADR-001
title: "Transport & routing"
status: accepted
date: 2026-10-04
reviewed: changed-after-review
revisit_when:
  - "Events with `audience: restricted` (the default for any event carrying `direct` PII) → per-subscription rules on central, applied by the platform pipeline with producer approval recorded in the catalog"
  - "Ordering per aggregate → FIFO SQS target keyed by `aggregateId`"
  - "Proven stream volume → Kinesis for that stream only"
---

# ADR-001 · Transport & routing

## Decision

EventBridge: domain buses + one central bus. **Fan-out-all**: for each domain the platform generates one rule on central that forwards every public event *except the domain's own* to that domain's bus; the domain then filters with **consumer rules on its own bus**, generated from `receives[]`. No cross-account rule management, loop guard built into the pattern, one hop, DLQ + alarm on every target.

## Revisit only when

Events with `audience: restricted` (the default for any event carrying `direct` PII) → per-subscription rules on central, applied by the platform pipeline with producer approval recorded in the catalog. Ordering per aggregate → FIFO SQS target keyed by `aggregateId`. Proven stream volume → Kinesis for that stream only.

## How to change this

Open a PR that supersedes this ADR with the trigger named in `revisit_when` and the evidence that it fired. Update `decisions.md` in the same PR. Generated IaC follows the catalog, never the other way round.
