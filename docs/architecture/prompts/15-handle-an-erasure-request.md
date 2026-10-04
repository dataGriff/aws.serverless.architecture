---
step: cross-cutting
title: "Operation · Handle a subject erasure request"
read_first:
  - docs/architecture/pii.md
  - docs/architecture/adr/ADR-007-pii-in-events.md
  - docs/architecture/data-layer.md
---

# Operation · Handle a subject erasure request

## Before you start

Read, in this order: `docs/architecture/README.md` (index and glossary), `docs/architecture/decisions.md`, then the files under **Read first** below. Load nothing else until a task needs it. Work from a task list and keep it updated.

## Hard rules

- Everything in an account is generated from the catalog. Never hand-edit a rule, bucket, route, role, alarm or contract; change the catalog or the generator.
- Do not introduce Athena, Glue, Iceberg, Kinesis, Temporal, Step Functions outside the saga module, a central gateway, CloudFront, a Schema Registry or a data platform account. If you believe an ADR trigger has fired, stop and run `prompts/10-evaluate-a-trigger.md` instead.
- PII: every schema field carries `x-pii`. `indirect` travels in clear, `direct` is encrypted per subject in public events through the subject-key service, `special` never enters an event.
- Facts are events. One synchronous hop between domains, through a generated client. Never another domain's database or bucket.
- Tests before infrastructure: L0 contract (no infra) → L1 domain-local (LocalStack + pinned `platform-local`) → L2 platform. Never depend on another domain's code or a shared environment.
- Small commits with the ADR or doc section they implement named in the message. If a decision cannot be undone and the docs do not settle it, stop and ask, giving the options and your recommendation.

**Read first:** `docs/architecture/pii.md` · `docs/architecture/adr/ADR-007-pii-in-events.md` · `docs/architecture/data-layer.md`

## Goal

Erase a subject's `direct` personal data from everything the platform holds — buses, archives, replays, silver, laptops — by deleting one key, while respecting the records the business is legally obliged to keep.

## Steps

1. Identify the subject identifiers across domains (the owning domain's API resolves aliases). Record the request with its date and the deadline.
2. Check retention obligations with the owning domain and data protection: some records (financial-crime, transaction history) must be retained in a form that identifies the subject for a statutory period; those are held by the system of record, not by events. Decide and record: full erasure, or erasure of event copies with the system of record retained under its lawful basis.
3. Request key deletion through the subject-key service: approval step, grace period, then delete. The service emits `platform.SubjectErased.v1`.
4. Consumers that persisted decrypted `direct` data run their purge on `SubjectErased` and report completion; chase any that have not within the SLA.
5. Verify: a granted role decrypting any historical event for the subject receives "erased"; a replay of those events is harmless; `indirect` identifiers remain but are unlinkable once the owning domain deletes the subject record.
6. Record completion in the erasure log the nightly checks read; the ROPA export shows the subject's classes and decryptors as of the request.

## Done when

Key deleted, `SubjectErased` consumed by every decryptor, verification query shows no decryptable `direct` field for the subject, the log entry exists, and the request closed inside the SLA.

## Report back

Finish with: what was built (paths); each exit criterion with its evidence (test names and output, plan summaries, screenshots of the catalog where relevant); what you deliberately did not do and why; any ADR trigger you think is close to firing.
