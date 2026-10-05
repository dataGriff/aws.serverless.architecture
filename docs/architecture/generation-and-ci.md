# What the catalog generates, and what CI enforces

## Generated from the catalog

### From `events/` + `x-visibility` + `x-audience` + `x-pii`

Platform keys in EventCatalog frontmatter are `x-` prefixed (unknown top-level keys fail the build); `x-pii` lives on every JSON Schema property, including shared `schemas/`, never in frontmatter.

- Per-domain **public-forward** pattern (split at 4KB); per cross-domain `receives[]` one **subscriber** file on central (filter = the Classic pattern, retry 185/24 h, DLQ, a consumer-owned target reference `{service}-inbox`); per same-domain `receives[]` a consumer rule on the domain bus; per-domain **Firehose subscriber** on central. `platform-local` renders the *same* subscriber file as a Classic rule on the stub central — one source, two renderings, no separate twin file. No fan-out artefact exists (ADR-021).
- Validation schema bundles (envelope flattened into each payload — `allOf` cannot compose a closed payload — with `direct` fields schema-typed as the ciphertext envelope) and the archive routing map; both are packaged into the Firehose transform on AWS and into the Lambda shim locally (never an environment variable: 4 KB ceiling). Per-event Parquet schemas (`schemas/<type>.json`) → typed `d_*` columns
- Input-transformer templates where `derivedFrom` is set; sunset enforcement data from `deprecated.date` (EventCatalog has no `sunset` key)
- From `x-pii`: per-event encryption config (which fields, which subject-key policy), decrypt grants for the listed `decryptors`, Firehose ciphertext checks, silver column policy, log-scrubbing config, retention per class, and a records-of-processing (ROPA) export

### From the generated ODCS contract (+ overlay)

- Parquet schema for the compactor; DuckDB view DDL (and Athena DDL when that trigger fires); the `servers` block per environment from the env pin
- Quality checks the nightly Lambda executes with DuckDB: unique `event_id`, not-null envelope, partition completeness, reconciliation tolerance, freshness SLA
- Reader-role grants, retention lifecycle per class, ROPA columns, and the data-product page in the catalog

### From `services/*/openapi.yaml`

- Command/query message pages (`operationId` → page id, `x-eventcatalog-message-type` → `commands/` or `queries/`), emitted by the generator because core EventCatalog does not derive them, so API dependencies show in the same graph as events
- REST API body with integrations and request validators per environment; authorizer config from the security scheme; WAF association for `x-external` routes
- Typed clients per API version; Prism mock config; Schemathesis job; Sunset headers; the subdomain's DNS record

### From `services/*.receives[]`

- Per-domain **consumer rules on the domain's own bus** for same-domain events, each with DLQ and alarm; the subscriber on central for cross-domain events (above)
- Consumer code bindings and contract-test fixtures (events) · client pins and mock configs (APIs)
- Subscriber and caller lists on each event and operation page; the sync-hop-depth lint input

### From `domains/` + `channels/`

- The central bus policy (RAM share plus the forward roles' principals); domain buses carry **no** cross-account policy — nothing outside the account publishes to them (ADR-021); DLQs for every target; the deploy-order manifest; the per-event logical channel pages and the ODCS contracts, written into the catalog and committed
- Per-domain bronze + silver definitions with lifecycle, CMKs, Object Lock, replication and cost tags; grants to the domain account and its reader role
- Firehose streams, compactor schedules, **alarms and dashboards**, `platform-local` and environment pins

## CI guardrails

### On every catalog PR

- Schema diff — breaking change on a public event fails unless `.v{n+1}` is declared; `oasdiff` and Spectral for APIs
- Every field has an `x-pii` class; `special` fails on any event; `direct` on a public event requires `encryption: subject-key` and an approved `decryptors` list; every operation has a message type; every `$ref` resolves into `schemas/` (shared schemas by `$id` URL, so an event moving under `versioned/` keeps resolving) and entities (`x-kind: entity`, or a `<Name>Id` identity field) are not in the shared root; every example validates against the *generated* schema — so flipping an event to public also means rewriting its examples with ciphertext in the `direct` fields
- Every `receives[]` references something public or same-domain; restricted-audience subscriptions carry producer approval; `source` namespace matches the owning domain; no sync chain deeper than one hop
- Every public event version has an ODCS contract that lints, carries the envelope quality checks, and diffs against main — a breaking contract change needs a new event version
- Nothing depends on a version past its `deprecated.date`; generated output and the deploy-order manifest are up to date (`catalog-gen check`), and the schema diff runs against a checkout of the base ref
- `eventcatalog build` must not rewrite the source tree (it migrates old frontmatter in place): fail on a dirty tree after build

### On every domain PR

- Drift has two halves and both gate `task test`: catalog → generated (`catalog-gen check`) and generated → applied (`terraform plan -detailed-exitcode` is empty); every deployed rule on every local bus equals a generated file (the nightly scan below, run locally)
- L0 contract tests; L1 LocalStack tests with the pinned `platform-local` stub and Prism mocks, including quarantine, dedupe and replay cases
- Schemathesis against the domain's own API through gateway validation; compactor output matches the catalog schema for every event the domain publishes
- The generated clients the domain depends on compile at their pinned versions and honour Sunset

### Nightly, from the platform account

- Reconciliation: outbox counts vs bronze counts per domain per hour; quarantine volume per event type, split by schema failure vs clear-text `direct` PII
- Decryptor access review: roles holding subject-key access vs the catalog's `decryptors` lists; erasure SLA: time from `SubjectErased` to key deletion
- Every EventBridge rule and subscriber in every account exists in `generated/` with an identical pattern (the same scan L1 runs locally); every deployed API export matches its catalog spec — flags hand-made rules and routes
- Per domain bucket: distinct `source`/`detail-type` in bronze vs catalog — undocumented events; silver partition completeness; lifecycle, CMK and Object Lock settings match the declarations
- `datacontract test` for every silver table and bronze envelope against the real buckets; freshness SLA (silver no older than 3 h behind bus time); results to alarms and catalog badges
- L2 platform suite against the real sandbox account
