---
id: ADR-008
title: "Replay"
status: superseded
superseded_by: "ADR-023 — central becomes a Custom Event Bus with retention; replay is a point-in-time subscriber"
date: 2026-10-04
reviewed: changed-after-review
revisit_when:
  - "Replay older than the archive window → an S3 → bus replayer that sets the same flag"
---

# ADR-008 · Replay

## Decision

Native EventBridge archive on central (30 days) is the **operational** replay tool: replayed events carry `replay-name` and are re-emitted with `replay: true`; side-effecting consumers (notifications, payouts) ignore them. S3 bronze is for analytics and audit, not for re-driving consumers.

## Revisit only when

Replay older than the archive window → an S3 → bus replayer that sets the same flag.

## How to change this

Open a PR that supersedes this ADR with the trigger named in `revisit_when` and the evidence that it fired. Update `decisions.md` in the same PR. Generated IaC follows the catalog, never the other way round.
