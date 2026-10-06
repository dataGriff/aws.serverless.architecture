---
id: ADR-020
title: "DR"
concern: "DR"
decision: >-
  Single region: **eu-west-1** (Ireland; London has no Custom Event Bus endpoint). Bronze is versioned and replicated cross-region in prod; archive RPO is the Firehose buffer (≤ 60 s); the bus itself is rebuilt from IaC. Stated RTO: region recovery.
status: accepted
date: 2026-10-04
reviewed: changed-after-review
revisit_when:
  - "RTO shorter than a region incident → EventBridge global endpoints with replication, and active-passive gateways"
---

# ADR-020 · DR

## Decision

Single region: **eu-west-1 (Ireland)**, chosen 2026-10-04 because the EventBridge Custom Event Bus (ADR-021) has no eu-west-2 endpoint; previously London. Bronze is versioned and replicated cross-region in prod; archive RPO is the Firehose buffer (≤ 60 s); the bus itself is rebuilt from IaC. Stated RTO: region recovery.

## Revisit only when

RTO shorter than a region incident → EventBridge global endpoints with replication, and active-passive gateways.

## How to change this

Open a PR that supersedes this ADR with the trigger named in `revisit_when` and the evidence that it fired. Set its `concern:`, `decision:` and `revisit_when` and run `task adr:build` in the same PR. Generated IaC follows the catalog, never the other way round.
