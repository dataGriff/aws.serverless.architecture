# PII in events — classified, not banned

PII will enter events; the platform classifies and controls it rather than pretending otherwise. The classification lives on every schema field as `x-pii` and drives generated encryption, quarantine, silver columns, log scrubbing, retention and the ROPA.

| Class | Examples | In a public event | In an internal event | Bronze / silver | Erasure |
| --- | --- | --- | --- | --- | --- |
| `none` | order total, status, timestamps | clear | clear | as published / typed `d_*` column | n/a |
| `indirect` | `customerId`, `accountRef`, device id, postcode district | clear; needed for correlation and routing | clear | as published / typed column, retention cap per class | unlinkable once the owning domain deletes the subject record; silver keeps the orphaned id |
| `direct` | name, email, phone, address, date of birth, account number, IBAN | ciphertext only — producer encrypts with the subject's data key; `audience: restricted` by default; consumers listed as `decryptors` fetch the key | clear permitted; every copy capped at 30 days, logs scrubbed | ciphertext inside `detail`, never a `d_*` column; clear text in a `direct` field is quarantined by Firehose | delete the subject key → every copy anywhere is unreadable, including Object-Locked bronze and replays |
| `special` | health, biometrics, ethnicity, religion, sexual orientation, criminal data, PCI PAN/CVV | never — reference by id, fetch via the owning API under its own controls | never | never present | handled by the system of record, not the event platform |

## Subject-key service (platform module)

- DynamoDB table of per-subject data keys, each wrapped by the owning domain's KMS CMK; `get-or-create(subjectId)` for producers, `get(subjectId)` for granted decryptors, `delete(subjectId)` for erasure with an approval step and grace period
- Access is IAM: the generator grants producers and the catalog's `decryptors`; nobody else, including the platform's own reader roles, can fetch keys
- Encryption context binds subject id and event type, so a key fetched for one purpose cannot decrypt another; data keys are cached per subject with a short TTL and invalidated by `SubjectErased`
- Deleting a key emits `platform.SubjectErased.v1`; consumers that persisted decrypted data run their own erasure on it

## Shared library (producers and consumers)

- One function to encrypt the `direct` fields of an event from its catalog classification, one to decrypt for a granted role; built on Lambda Powertools data masking / the AWS Encryption SDK
- Log scrubbing uses the same classification: `direct` and `special` field names are redacted in structured logs and trace attributes by middleware, not by developer discipline
- Decrypt failure for a shredded key is a first-class result ("erased"), not an exception, so replays and late consumers behave

## Why this shape

- Encrypting at the producer is the only control that follows the data into every copy EventBridge makes: buses, subscriber deliveries, DLQs, logs, the retained bus, replays, laptops
- Crypto-shredding reconciles the two things fintech needs at once: an immutable, Object-Locked audit trail and erasure on request
- Classification lives in the catalog, so the policy is generated and tested like everything else, and the ROPA is a report, not a spreadsheet
