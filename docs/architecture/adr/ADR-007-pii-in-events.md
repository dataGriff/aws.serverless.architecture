---
id: ADR-007
title: "PII in events"
status: accepted
date: 2026-10-04
reviewed: changed-after-review
revisit_when:
  - "Analytics needs a `direct` field in silver → reversible tokenisation for that field, a masked column, and a DPIA entry"
  - "Key fetch on the publish path costs latency → cached data keys per subject with a short TTL"
  - "A consumer must persist decrypted data → it owns an erasure path triggered by the `SubjectErased` event"
---

# ADR-007 · PII in events

## Decision

**PII is expected, so it is classified rather than banned.** Every field in a catalog schema carries `x-pii`: `none` · `indirect` (pseudonymous identifiers such as `customerId`) · `direct` (name, email, address, date of birth, account number, IBAN) · `special` (health, biometrics, ethnicity, PCI PAN/CVV). Public events may carry `indirect` in clear. `direct` fields are **encrypted by the producer** with a per-subject data key from the platform's **subject-key service** (envelope encryption under the domain CMK, applied by a shared library), so every copy — bus, archive, DLQ, logs, replay, laptop — holds ciphertext; only consumer roles the catalog lists as `decryptors` can fetch the key; **erasure is deleting the subject key** (crypto-shredding), which also empties Object-Locked bronze. `special` never enters any event, public or internal — reference by id only. Internal events may carry `direct` in clear inside the account because every copy there has a 30-day cap and scrubbed logs. The Firehose validator **quarantines a `direct` field that arrives in clear**.

## Revisit only when

Analytics needs a `direct` field in silver → reversible tokenisation for that field, a masked column, and a DPIA entry. Key fetch on the publish path costs latency → cached data keys per subject with a short TTL. A consumer must persist decrypted data → it owns an erasure path triggered by the `SubjectErased` event.

## How to change this

Open a PR that supersedes this ADR with the trigger named in `revisit_when` and the evidence that it fired. Update `decisions.md` in the same PR. Generated IaC follows the catalog, never the other way round.
