---
id: ADR-003
title: "Orchestration"
status: accepted
date: 2026-10-04
reviewed: changed-after-review
revisit_when:
  - "Several sagas + portability → Temporal, per domain or as a process-manager context; never a cross-domain workflow by default"
---

# ADR-003 · Orchestration

## Decision

No orchestrator platform. Choreography via events; a stateful process is a saga *inside the owning domain*, built from the platform's **saga module** (state table + Scheduler, or a Step Functions template) that ships on day one because payments needs it on day one. It speaks only contracts.

## Revisit only when

Several sagas + portability → Temporal, per domain or as a process-manager context; never a cross-domain workflow by default.

## How to change this

Open a PR that supersedes this ADR with the trigger named in `revisit_when` and the evidence that it fired. Update `decisions.md` in the same PR. Generated IaC follows the catalog, never the other way round.
