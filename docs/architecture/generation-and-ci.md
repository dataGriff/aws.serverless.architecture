# What the catalog generates, and what CI enforces

## Generated from the catalog

### From `events/` + `visibility` + `audience` + `pii`

- Per-domain **public-forward** pattern (split at 4KB); per-`receives[]` **subscriber** on central in the consumer's account (and its Classic-rule twin for `platform-local`); per-domain **Firehose subscriber** on central
- Firehose validation schema bundles and per-event Parquet schemas (`schemas/<type>.json`) → typed `d_*` columns
- Input-transformer templates where `derivedFrom` is set; `sunset` enforcement data
- From `x-pii`: per-event encryption config (which fields, which subject-key policy), decrypt grants for the listed `decryptors`, Firehose ciphertext checks, silver column policy, log-scrubbing config, retention per class, and a records-of-processing (ROPA) export

### From the generated ODCS contract (+ overlay)

- Parquet schema for the compactor; DuckDB view DDL (and Athena DDL when that trigger fires); the `servers` block per environment from the env pin
- Quality checks the nightly Lambda executes with DuckDB: unique `event_id`, not-null envelope, partition completeness, reconciliation tolerance, freshness SLA
- Reader-role grants, retention lifecycle per class, ROPA columns, and the data-product page in the catalog

### From `services/*/openapi.yaml`

- Command/query message pages via `x-eventcatalog-message-type`, so API dependencies show in the same graph as events
- REST API body with integrations and request validators per environment; authorizer config from the security scheme; WAF association for `x-external` routes
- Typed clients per API version; Prism mock config; Schemathesis job; Sunset headers; the subdomain's DNS record

### From `services/*.receives[]`

- Per-domain **consumer rules on the domain's own bus**, each with DLQ and alarm
- Consumer code bindings and contract-test fixtures (events) · client pins and mock configs (APIs)
- Subscriber and caller lists on each event and operation page; the sync-hop-depth lint input

### From `domains/` + `channels/`

- Central and domain bus policies; DLQs for every target; the deploy-order manifest
- Per-domain bronze + silver definitions with lifecycle, CMKs, Object Lock, replication and cost tags; grants to the domain account and its reader role
- Firehose streams, compactor schedules, **alarms and dashboards**, `platform-local` and environment pins

## CI guardrails

### On every catalog PR

- Schema diff — breaking change on a public event fails unless `.v{n+1}` is declared; `oasdiff` and Spectral for APIs
- Every field has an `x-pii` class; `special` fails on any event; `direct` on a public event requires `encryption: subject-key` and an approved `decryptors` list; every operation has a message type; every `$ref` resolves into `schemas/` and entities are not in the shared root
- Every `receives[]` references something public or same-domain; restricted-audience subscriptions carry producer approval; `source` namespace matches the owning domain; no sync chain deeper than one hop
- Every public event version has an ODCS contract that lints, carries the envelope quality checks, and diffs against main — a breaking contract change needs a new event version
- Nothing depends on a version past its `sunset`; generated output and the deploy-order manifest are up to date

### On every domain PR

- L0 contract tests; L1 LocalStack tests with the pinned `platform-local` stub and Prism mocks, including quarantine, dedupe and replay cases
- Schemathesis against the domain's own API through gateway validation; compactor output matches the catalog schema for every event the domain publishes
- The generated clients the domain depends on compile at their pinned versions and honour Sunset

### Nightly, from the platform account

- Reconciliation: outbox counts vs bronze counts per domain per hour; quarantine volume per event type, split by schema failure vs clear-text `direct` PII
- Decryptor access review: roles holding subject-key access vs the catalog's `decryptors` lists; erasure SLA: time from `SubjectErased` to key deletion
- Every EventBridge rule in every account exists in `generated/`; every deployed API export matches its catalog spec — flags hand-made rules and routes
- Per domain bucket: distinct `source`/`detail-type` in bronze vs catalog — undocumented events; silver partition completeness; lifecycle, CMK and Object Lock settings match the declarations
- `datacontract test` for every silver table and bronze envelope against the real buckets; freshness SLA (silver no older than 3 h behind bus time); results to alarms and catalog badges
- L2 platform suite against the real sandbox account
