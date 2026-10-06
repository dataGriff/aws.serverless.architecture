---
id: ADR-015
title: "Observability"
concern: "Observability"
decision: >-
  Generated with the IaC, from the same catalog entry: alarms on `FailedInvocations` per rule, DLQ depth, consumer queue age, Firehose delivery/processing failures, compactor errors, API 5xx and p99; OpenTelemetry tracing with `correlationId` propagated API → outbox → bus → consumer; one dashboard per domain. Nightly **reconciliation**: outbox counts vs bronze counts per domain per hour.
status: accepted
date: 2026-10-04
reviewed: changed-after-review
revisit_when:
  - "Error budgets and SLO tooling once there are SLAs to defend"
---

# ADR-015 · Observability

## Decision

Generated with the IaC, from the same catalog entry: alarms on `FailedInvocations` per rule, DLQ depth, consumer queue age, Firehose delivery/processing failures, compactor errors, API 5xx and p99; OpenTelemetry tracing with `correlationId` propagated API → outbox → bus → consumer; one dashboard per domain. Nightly **reconciliation**: outbox counts vs bronze counts per domain per hour.

## Revisit only when

Error budgets and SLO tooling once there are SLAs to defend.

## How to change this

Open a PR that supersedes this ADR with the trigger named in `revisit_when` and the evidence that it fired. Set its `concern:`, `decision:` and `revisit_when` and run `task adr:build` in the same PR. Generated IaC follows the catalog, never the other way round.
