---
id: ADR-024
title: "Archive — Firehose as a subscriber on central; a Lambda shim locally"
status: accepted
supersedes: ADR-009
date: 2026-10-04
accepted: 2026-10-04
evidence:
  - spikes/B-localstack-buses-end-to-end/findings.md
revisit_when:
  - "Sub-minute analytics → a second Firehose subscriber straight to Parquet"
  - "LocalStack's Firehose honours dynamic partitioning, `ProcessingConfiguration` and `ErrorOutputPrefix` → retire the local shim and run the real module locally"
---

# ADR-024 · Archive — Firehose as a subscriber on central; a Lambda shim locally

## Why ADR-009 is reopened

Two reasons. With central as a Custom Event Bus (ADR-021) the archive is fed by a **subscriber** per domain, not by a Classic rule. And Spike B's Firehose probe (`task probe-firehose`, both LocalStack editions) showed that the three ADR-009 mechanisms the design makes load-bearing cannot be tested locally:

| ADR-009 mechanism | LocalStack 4.14 / 2026.9 |
| --- | --- |
| 60 s buffering | ignored; one object per record, written in ~3 s |
| validation Lambda | invoked with a non-AWS payload (`{"records":[{"data":…}]}`, no `recordId`); a contract-conformant Lambda crashes; on crash Firehose writes **empty objects** |
| `ProcessingFailed` → `processing-failed/` | not quarantined; written raw under the normal prefix |
| dynamic partitioning `!{partitionKeyFromLambda:…}` | not evaluated; the placeholder text is the S3 key |

The archive *shape* the data layer reads — one object per event, Hive prefixes `source=/detail_type=`, DuckDB over S3 — was proven end to end with a 10-line Lambda (`test_archiver_writes_every_central_event_to_s3`, `test_duckdb_reads_archive_with_hive_partitions`, `task query`).

## Decision

**On AWS: Firehose, one stream per domain, as a subscriber on central** with a `DATA` filter on the domain's source prefix. Dynamic partitioning on `source`/`detail-type`, NDJSON, 60 s buffers, the validation transform against the catalog schema with `processing-failed/` and the PII-in-clear quarantine — all as ADR-009 wrote them. Each domain still runs the archive module on its own Classic bus for internal events into its own bucket.

**Locally (`platform-local`, domain-local): the Lambda shim** from Spike B writes `raw/source=…/detail_type=…/<id>.json` and **imports the same validation function** Firehose invokes on AWS, so the contract check and quarantine logic is one piece of code tested in both places. Firehose behaviour itself — buffering, partition evaluation, `processing-failed/`, the transform payload contract — is **sandbox-only** (ADR-025).

Spike C fixed the shape of the shared validation step: `validate.classify(event, bundles)` returns `None` or `(reason, message)` with reasons `schema`, `pii-in-clear`, `unknown-event`; the validator is `fastjsonschema` (pure Python, no compiled dependency — the generated bundle uses only draft-07-level keywords); the generated bundles and the routing map are **packaged into the function** (Firehose transform and shim alike), never passed as environment variables, so a catalog change is a code change of the function. Quarantine keys are `processing-failed/reason=<reason>/source=…/detail_type=…/`, which DuckDB reads as Hive columns. Events whose source matches no routing-map prefix go to the platform's own bronze bucket.

## What does not change

Bucket layout, CMKs, Object Lock, retention (ADR-010); the compactor reads the same prefixes (ADR-011); ODCS contracts (ADR-012); the validation rules themselves.

## New trade-offs

- Two renderers for one catalog entry (Firehose subscriber on AWS, Lambda shim locally). The shim is deliberately dumb: no buffering, no small-file control; it exists for tests, not for cost.
- DuckDB infers `detail.eventId` as `UUID`; the compactor must pin column types from the catalog schema rather than trust inference (Spike B).
- Firehose as a *subscriber* target is documented but was not exercised in Spike D; it is the first thing Step 1's sandbox run proves.

## How to change this

Open a PR that supersedes this ADR with the trigger named in `revisit_when` and the evidence that it fired. Update `decisions.md` in the same PR. Generated IaC follows the catalog, never the other way round.
