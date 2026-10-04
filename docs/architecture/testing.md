# Testing

A domain proves its own events and its own API end to end with nobody else present. The layers below are cumulative.

## Domain-local run

```mermaid
flowchart LR
  subgraph DOM[orders repo · LocalStack · owned and run by the domain]
    SVC[order-service · real code] --> OBX[outbox table] --> REL[relay · fixture drains in-process] --> BUS[(orders-bus)]
    ST[Schemathesis · requests from catalog OpenAPI] --> H[order-api handlers · real code] --> OBX
    H --> CL[generated client · payments API]
  end
  subgraph STUB[platform-local · licensed LocalStack · pinned]
    BUS --> FWD[public-forward rule · generated] --> CB[("stub central · Classic stand-in for the Custom Event Bus")]
    CB --> SUB["consumer rules in subscriber shape · from receives · → orders' own queues"]
    CB --> AR["archive shim → orders-events-bronze (same validation code as the Firehose transform)"] --> CP[compactor → silver · T-2h · dedupe]
    CL --> PR[Prism mock of payments API · same catalog pin]
  end
  subgraph AS[assertions · platform_testing + DuckDB + jsonschema]
    A1[events: schema valid · in bronze · internal never reached stub · bad payload quarantined · cross-hour dup = 1 row · replay flag = no side effect]
    A2[APIs: conforms to OpenAPI · gateway rejects invalid body · Idempotency-Key enforced · client↔mock round-trips · command → outbox → bronze]
  end
  CP --> A1
  PR --> A2
```

## Layers

### L0 · Contract (no infra · every commit)

- Events: an event built by domain code validates against the catalog JSON Schema; each `receives[]` handler is unit-tested against the catalog example payload
- APIs: Spectral ruleset + `oasdiff` in catalog CI; the generated client compiles against the pinned spec; handler unit tests use request/response examples from the spec
- Lifecycle: nothing may depend on a version past its sunset; breaking change needs a new version — CI, not a meeting

### L1 · Domain-local (licensed LocalStack, `ENFORCE_IAM=1` · every PR)

- Real service + outbox drained in-process → own bus → forward rule → Classic stub central → subscriber-shaped rules to own queues + archive shim → own bronze; compactor → own silver. The Custom Event Bus itself is not emulated; anything on the sandbox-only list below is not asserted here
- Schemathesis drives the domain's own API from its catalog spec (gateway validation included); upstream APIs are Prism mocks of their catalog specs
- Asserts via DuckDB + jsonschema, including bad-payload quarantine, cross-hour duplicates, ciphertext checks and replay-flag handling; the local silver passes its ODCS contract test; seconds per test; no other domain present

### L2 · Platform (real AWS sandbox · nightly and per platform PR)

- Synthetic events generated *from catalog schemas*, never a domain's code; an ephemeral stack per branch in the sandbox account, torn down after
- **Sandbox-only — never trusted from LocalStack** (ADR-025): the Custom Event Bus and RAM sharing, subscriber delivery, FIFO per `EventGroupId`, dedup, point-in-time replay with `aws:DeliveryType`, DLQ records and latency, resource-policy and IAM evaluation, bus-to-bus hop limits and loop detection, Firehose buffering/partitioning/`processing-failed/`/transform contract. Tests for these carry the `sandbox` marker; a LocalStack divergence is `xfail(strict=True)` with the reason
- Compactor dedupe/idempotency/late-event re-compaction; generator output snapshot-tested from one catalog input in both renderings (subscribers for AWS, Classic rules for `platform-local`): patterns, gateway bodies, authorizers, alarms, roles, ODCS contracts

### L3 · Smoke (real AWS · post-deploy)

- One `{domain}.SmokeTest.v1` event per domain → appears in its bronze bucket within the Firehose buffer; proves the forward rule, RAM share, the Firehose subscriber, cross-account
- One `GET /v1/health` per API through the real authorizer; proves DNS, gateway deploy, JWT/IAM, WAF where present
- Both marked public in the catalog, both excluded from silver; a quarterly replay drill with a point-in-time subscriber into `test`

## Querying what a domain published, locally

```
-- bronze: NDJSON from Firehose, readable within the buffer window
CREATE VIEW bronze AS SELECT * FROM read_ndjson_auto('s3://orders-events-bronze/**/*', union_by_name=true);
SELECT source, "detail-type", count(*) FROM bronze GROUP BY 1,2;                      -- what did we publish
SELECT count(*) FROM read_ndjson_auto('s3://orders-events-bronze/processing-failed/**/*');  -- contract violations
SELECT time, source, "detail-type" FROM bronze WHERE detail.correlationId = 'c-1' ORDER BY time;  -- one flow, API call included

-- silver: deduped at read time, so cross-hour duplicates never reach a query
CREATE VIEW silver AS
  SELECT * FROM read_parquet('s3://orders-events-silver/silver/**/*.parquet', hive_partitioning=true, union_by_name=true)
  QUALIFY row_number() OVER (PARTITION BY event_id ORDER BY bus_time) = 1;
SELECT dt, hour, detail_type, count(*) FROM silver GROUP BY ALL ORDER BY 1,2;         -- partition completeness
```
