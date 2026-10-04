# Event & API platform — architecture

EventBridge-first, domain-owned, catalog-driven. Each domain account owns its bus, its rules, its services and its API; the platform account owns the central bus (with a native archive for replay only), the Firehose archive and compaction into *one bronze and one silver bucket per domain*, API auth, generated alarms, and per-domain read-only roles. EventCatalog is the source of truth for events *and* APIs — design-first OpenAPI modelled as commands and queries — and generates every account's IaC, gateways, clients, mocks and alarms. The data layer is S3 + Firehose + one compactor Lambda + Parquet, queried with DuckDB. PII in events is expected and classified: pseudonymous identifiers travel in clear, direct identifiers are encrypted per subject so erasure is a key deletion, special categories never travel. Every dataset the platform serves — each silver table, each domain's bronze, any gold built later — has an ODCS data contract generated from the same catalog entry and tested nightly. Nothing else (Athena, Glue, Iceberg, an orchestrator platform, a central edge, a data platform account) is built until a named trigger says so, and the trade-offs that buys are written down below.

## End state

```mermaid
flowchart TB
  subgraph CAT[EventCatalog repo — source of truth]
    C[domains · services · events · commands/queries · schemas · channels]
    G[Generator + CI: rules, policies, streams, buckets, REST APIs, clients, mocks, alarms, roles, env pins]
  end
  subgraph PLAT[Platform account — routing, governance, data operations]
    CB[(central-bus · public events only · native archive 30d for replay)]
    FAN[fan-out rule per domain: all public except own → domain bus]
    FH[Firehose per domain: validate vs catalog schema → processing-failed/ + alarm]
    BR[(bronze bucket per domain · NDJSON · CMK · Object Lock · CRR in prod)]
    CMP[compactor per domain · T-2h · daily re-compact · dedupe]
    SV[(silver bucket per domain · Parquet · Hive partitions)]
    DUCK[DuckDB views · read-time dedupe · per-domain reader roles]
    AUTH[API auth: JWT issuer · IAM SigV4 · WAF for external routes]
    OBS[generated alarms · OTel traces · nightly checks + reconciliation]
  end
  subgraph ORD[Orders account]
    OB[(orders-bus)]
    OS[order-service · outbox → relay module]
    OF[public-forward rule · source prefix orders.]
    OC[consumer rules on own bus · from receives]
    OA[REST API from OpenAPI · orders.api.example.com]
    OI[(internal archive · 30d · own account)]
  end
  subgraph PAY[Payments account]
    PB[(payments-bus)]
    PS[payment-service + saga module]
    PA[REST API + PSP webhook behind WAF]
    PCL[generated client for orders API]
  end
  OS --> OB --> OF --> CB
  OB --> OI
  CB --> FAN --> PB --> PS
  CB --> FH --> BR --> CMP --> SV --> DUCK
  OB --> OC
  PCL -- "GET /v1/orders/{id} · one sync hop" --> OA
  G -. generates IaC for every account .-> PLAT
  G -.-> ORD
  G -.-> PAY
```

Three domains are shown; every domain account has the same shape. Everything inside the platform and domain accounts is generated from the catalog.

> **Proposed change (2026-10-04, Spikes B and D):** the `central-bus → domain bus` fan-out hop in this diagram is refused by EventBridge Classic (`THIRD_ACCOUNT_HOP_DETECTED`). [ADR-021](adr/ADR-021-transport-routing-custom-bus.md) proposes a Custom Event Bus as central with consumer-owned subscribers and carries the replacement diagram; ADR-022 to ADR-025 follow from it. This diagram is left as the accepted state until those ADRs are accepted.

## Glossary

- **central-bus** — the one EventBridge bus that routes public events between domains; it persists nothing except a native archive used only for replay.
- **fan-out-all** — one platform-owned rule per domain on central that forwards every public event except the domain's own to that domain's bus. Subscriptions are therefore consumer rules on the domain's own bus.
- **public / internal** — `visibility` in the catalog. Public events are forwarded to central and archived; internal events never leave the domain account.
- **audience** — `all` (default) or `restricted`; restricted events use per-subscription rules on central with producer approval.
- **bronze / silver** — per-domain S3 buckets in the platform account: bronze is raw NDJSON written by Firehose (audit, replay source for analytics); silver is Parquet written by the compactor (query layer).
- **platform-local** — the versioned Terraform module a domain applies in LocalStack to get a stub central bus, fan-out, archive, compactor and its own buckets, so it can test publication with no other domain present.
- **saga module** — the platform's in-domain stateful-process pattern (state table + Scheduler, or Step Functions template). Never a cross-domain workflow.
- **replay flag** — `replay: true` in the envelope on re-driven events; side-effecting consumers skip them.
- **x-pii** — the per-field classification in every catalog schema: `none` · `indirect` (pseudonymous ids, clear) · `direct` (encrypted per subject in public events) · `special` (never in any event).
- **subject-key service** — platform module holding a data key per subject under the owning domain's CMK; producers encrypt `direct` fields with it, listed `decryptors` fetch it, erasure deletes it (crypto-shredding).
- **ODCS** — Bitol's Open Data Contract Standard v3. Every dataset the platform serves (each silver table, each bronze, any gold) has one, generated from the event's catalog entry plus a small overlay, and tested nightly.
- **data product** — a silver table (or later a gold dataset) with its ODCS contract, consumers and freshness, rendered as its own catalog page linked to the event.

## Files

| File | Load it when |
| --- | --- |
| [decisions.md](decisions.md) | proposing or reviewing any infrastructure, routing, data or API design change; checking whether a service is permitted |
| [adr/](adr/) | challenging one decision — each ADR carries its `revisit_when` triggers in frontmatter |
| [trade-offs.md](trade-offs.md) | someone asks "why can't we…", or a symptom (duplicates, staleness, test gaps) needs explaining |
| [conventions.md](conventions.md) | writing or reviewing an event, an API operation, a consumer, or a catalog entry |
| [generation-and-ci.md](generation-and-ci.md) | changing the generator, adding a catalog field, or wondering why CI failed |
| [pii.md](pii.md) | any event or API that carries personal data; classification, encryption, erasure, the subject-key service |
| [data-layer.md](data-layer.md) | reading or writing bronze/silver; column types, layout, what is and isn't on disk |
| [data-contracts.md](data-contracts.md) | creating or consuming a dataset; the ODCS mapping, overlay, quality checks and catalog representation |
| [testing.md](testing.md) | writing tests for a domain, the platform, or a smoke; querying bronze/silver locally |
| [roadmap.md](roadmap.md) | planning work, deciding what is day-one vs trigger-gated, writing exit criteria |
| [prompts/](prompts/README.md) | running a roadmap step or a recurring operation with an agent — one self-contained prompt each, also installed as `/arch:*` commands |
| [prompts/spikes/](prompts/spikes/README.md) | proving the catalog-as-source-of-truth and the LocalStack bus mechanics in isolation, before day one |

## For AI agents

Read `decisions.md` before proposing infrastructure. Do not introduce Athena, Glue, Iceberg, Kinesis, Temporal, Step Functions outside the saga module, a central gateway, CloudFront, a Schema Registry or a data platform account unless the matching ADR's `revisit_when` trigger is cited with evidence. Every rule, bucket, route, client, alarm, role and data contract is generated from the catalog: change the catalog or the generator, never the account by hand. PII in events is classified per field (`x-pii`): `indirect` in clear, `direct` encrypted per subject, `special` never — see `pii.md` before touching a payload. Any dataset consumed outside its domain has an ODCS contract first. One synchronous hop between domains, through a generated client.
