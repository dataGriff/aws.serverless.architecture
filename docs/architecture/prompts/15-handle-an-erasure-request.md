---
step: cross-cutting
title: "Operation · Handle a subject erasure request"
read_first:
  - docs/architecture/pii.md
  - docs/architecture/adr/ADR-007-pii-in-events.md
  - docs/architecture/data-layer.md
---

# Operation · Handle a subject erasure request

{{> before-you-start}}

{{> hard-rules}}

**Read first:** {{read_first}}

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

{{> report-back}}
