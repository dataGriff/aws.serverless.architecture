---
id: ADR-010
title: "Bucket location & protection"
concern: "Bucket location & protection"
decision: >-
  Platform account, one bronze + one silver per domain. Retention, lifecycle and cost tags declared by the domain in the catalog, applied by the platform. **KMS CMK per domain** on buckets and buses, **Object Lock** on bronze (it is the audit trail), **versioning + cross-region replication in prod**, CloudTrail data events on. Readers: the domain's own account for its pair; **per-domain reader roles** (`orders-reader`) for people; one composite role for the platform's checks only.
status: accepted
date: 2026-10-04
reviewed: changed-after-review
revisit_when:
  - "Data residency or a domain running its own pipeline → move that domain's pair into its account; same layout, same grants"
---

# ADR-010 · Bucket location & protection

## Decision

Platform account, one bronze + one silver per domain. Retention, lifecycle and cost tags declared by the domain in the catalog, applied by the platform. **KMS CMK per domain** on buckets and buses, **Object Lock** on bronze (it is the audit trail), **versioning + cross-region replication in prod**, CloudTrail data events on. Readers: the domain's own account for its pair; **per-domain reader roles** (`orders-reader`) for people; one composite role for the platform's checks only.

## Revisit only when

Data residency or a domain running its own pipeline → move that domain's pair into its account; same layout, same grants.

## How to change this

Open a PR that supersedes this ADR with the trigger named in `revisit_when` and the evidence that it fired. Set its `concern:`, `decision:` and `revisit_when` and run `task adr:build` in the same PR. Generated IaC follows the catalog, never the other way round.
