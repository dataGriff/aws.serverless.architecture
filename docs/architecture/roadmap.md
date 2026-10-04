# Roadmap

Each step proves one mechanism; nothing is built ahead of a trigger. Every part below has a ready-to-run prompt under [prompts/](prompts/README.md): `00`–`02` for day one, `03` for step 1, `04`–`05` for step 2, `06`–`07` for step 3, `08` for step 4, `09` for step 5, `10` for anything trigger-gated. To prove the two load-bearing ideas before committing to day one, run the isolated spikes under [prompts/spikes/](prompts/spikes/README.md) first.

## Day one · Foundations — needed before the first event or endpoint has any value
### Decide & write down (ADRs)

- EventBridge-first, fan-out-all routing, domain-owned buses, services and APIs; central keeps only a native archive for replay
- Firehose archive with schema validation; buckets in the platform account, one pair per domain, CMK per domain, Object Lock on bronze; internal archive per domain by default
- REST API Gateway with validation; WAF on anything externally reachable from day one; no central gateway; no Schema Registry
- **PII is classified, not banned**: `indirect` in clear, `direct` encrypted per subject via the platform's subject-key service, `special` never; erasure = key deletion
- Parquet + DuckDB with read-time dedupe; no Athena/Glue/Iceberg; no data platform account; no orchestrator platform — the saga module instead
- ODCS v3 is the data-contract standard; every dataset served outside its domain has one, generated from the catalog and tested nightly
- Environments: nonprod (dev, test) and prod per domain and platform; catalog tag pinned per env
- Ownership: domain → consumer rules, API contract, handlers, SLOs, retention/sunset declarations; platform → central, Firehose, compactor, buckets, auth issuer, catalog CI, reader roles, alarms
- Each trade-off above recorded as accepted, with its trigger

### Fix the conventions

- Events: `source = {domain}.{service}`; `detail-type = {Name}.v{n}`; envelope `eventId`, `occurredAt`, `correlationId`, `causationId`, `aggregateId`, `aggregateVersion`, `replay`; catalog fields `visibility`, `audience`, `pii`, `deprecated`, `sunset`
- APIs: OpenAPI 3.1; `/v{n}`; additive = minor; RFC 9457 `problem+json`; `Idempotency-Key` on every command; cursor pagination; `X-Correlation-Id`; `Sunset`/`Deprecation` headers; a Spectral ruleset that encodes all of it
- `schemas/` = value objects only; entities under `schemas/{domain}/`; every field carries `x-pii`; the 4KB pattern limit means the generator splits forward rules when the public list grows
- Names: `{domain}-bus`, `{domain}-events-bronze|silver`, `{domain}.api.example.com`, `{domain}-reader`

### Stand up the tooling

- EventCatalog repo: one domain, one service, one public + one internal event, one OpenAPI with one command and one query, channels, example payloads, CODEOWNERS per domain path
- Terraform module library, tagged: `event-bus`, `bus-forward-rule`, `firehose-archive` (with validation transform), `compactor`, `domain-buckets`, `rest-api` (from OpenAPI), `outbox-relay` (DynamoDB Streams → Pipes → PutEvents), `idempotency-store`, `saga`, `subject-keys` (per-subject data keys + the encrypt/decrypt library), `alarms`, `platform-local` stub
- mise (terraform, task, uv, awscli, node), Taskfile, LocalStack compose, pytest + DuckDB, Spectral, oasdiff, Prism, Schemathesis, datacontract-cli — identical locally and in CI; a real AWS sandbox account for the nightly L2 run
- Pilot domain (orders) with an outbox in its service and one real endpoint; platform + first domain accounts (nonprod/prod); platform-owned JWT issuer; London EventBridge quotas checked and raise requests filed

**Exit:** a new engineer clones two repos, runs `task up && task apply && task test`, calls the mock of an API that isn't built yet, and reads every convention and every accepted trade-off in under an hour.

## Step 1 · Walking skeleton — single account, LocalStack

### Build

- `orders-bus` and `central-bus`; public-forward rule; the fan-out rule back (everything except `orders.`); a consumer rule on `orders-bus` from `receives[]`
- Archive: Firehose (or a Lambda shim where LocalStack lacks the feature) with the validation transform into `orders-events-bronze`; compactor at T−2h with daily re-compaction → `orders-events-silver`; DuckDB views with read-time dedupe
- Orders REST API from the catalog OpenAPI with gateway validation; one command (`POST /orders` → outbox relay module) and one query; Prism serving the same spec; idempotency-store module behind the command
- One `direct` field (customer email on `OrderPlaced.v1`) encrypted end to end through the subject-keys module; a consumer role with a decrypt grant and one without
- A hand-written ODCS contract for the `OrderPlaced.v1` silver table — to learn the shape before the generator owns it — with `datacontract test` in `task test`

### Prove

- Public event reaches central and lands in the orders bucket with shape intact; internal event stays on the domain bus; the fan-out never echoes a domain's own event back
- A non-conformant payload, or a `direct` field sent in clear, lands under `processing-failed/` and raises the alarm; a duplicate delivered across an hour boundary yields one silver row; the email is ciphertext in bronze and absent from silver's `d_*` columns
- Schemathesis passes; the gateway rejects an invalid body; a command produces the event; Prism answers the query from spec examples

**Exit:** `task test` green for events, archive validation, dedupe and API; `task query` shows the event the API call produced, by `correlationId`.

## Step 2 · Catalog drives the IaC — including alarms, roles and lifecycle

### Build

- Generator emits, per account and per environment: forward/fan-out/consumer rule patterns, Firehose streams with their validation schema bundles, `schemas/*.json` for the compactor, bucket definitions with lifecycle and CMKs, per-domain reader roles, **alarms and dashboards** for every rule, DLQ, stream, compactor and API
- From each `openapi.yaml`: command/query pages, the REST API body with integrations and request validators, authorizer config, typed clients per version, Prism config, Schemathesis job, Sunset headers
- From each public event version + its overlay: the ODCS contract, and from the contract the Parquet schema, view DDL, quality checks and reader grants; the hand-written step-1 contract is replaced by the generated one and must be byte-identical
- Output under `generated/`, read via `jsondecode(file(...))`; generator semver pinned per account; a **deploy-order manifest** per catalog change (schemas → producer rules → central rules → consumer rules → clients)
- Catalog CI: schema diff, `oasdiff`, Spectral, `receives[]` → public/audience check with producer approval for restricted events, namespace lint, `$ref` resolution into `schemas/`, **PII block on public events**, **sunset enforcement**, pattern-size split, sync-hop-depth lint

### Prove

- Flip an event to public → the plan shows the forward rule, Firehose routing, silver schema and an alarm, nothing else
- Add a query to the OpenAPI → one route + validator + integration; the client gains one method; Prism serves it before any handler exists
- Mark `pii: true` on a public event, or leave a consumer on a sunset version → CI fails with the reason

**Exit:** no hand-written rule, bucket, route, authorizer, client, alarm or role anywhere; `git blame` on any of them points at the generator.

## Step 3 · Second domain, the saga, and testing in isolation

### Build

- `payments`: own bus, bucket pair in the platform env, fan-out both ways, loop test across three buses; its API with one command; **the saga module driving authorise → capture → settle** inside payments, speaking only contracts; WAF on the webhook route
- Extract `platform-local` as a versioned module: stub central-bus + fan-out + archive + compactor + per-domain buckets
- `platform_testing` package: `assert_published`, `assert_not_published`, `assert_quarantined`, `duck()`, `prism(service, version)`, `replay(event)`, fixtures for LocalStack / Terraform / outbox drain
- Payments calls the orders API through the generated client; its L1 tests run against the Prism mock of orders pinned to a catalog version; the nightly L2 run moves onto the real sandbox account

### Prove

- Orders repo CI is green with the payments repo absent, and vice versa
- Bumping the orders API pin in payments' repo is the only way payments sees a new orders field — and it fails loudly if orders broke compatibility
- A replay-flagged `PaymentCaptured` produces no notification; a saga step that times out compensates via its own events only
- Erasure drill: delete a subject key → the ungranted consumer never could read the field, the granted consumer now decodes it as erased, and the `SubjectErased` event reaches both

**Exit:** a domain proves its events, its API and its saga end to end — service → bus → bronze → silver, and spec → handler → outbox — with no other domain and no shared environment.

## Step 4 · Real accounts — nonprod then prod

### Build

- Platform + one account per domain, nonprod and prod tiers; bus policies from the catalog; central rules applied by the platform pipeline in the manifest's order
- Bucket pairs with CMKs, Object Lock on bronze, versioning + CRR in prod; grants to each domain's own account and to its reader role; CloudTrail data events on
- DNS delegated per domain; REST APIs deployed from generated bodies with the platform issuer; WAF attached where the catalog marks an API external
- Native archive enabled on central; a replay runbook; post-deploy smokes (`SmokeTest.v1` event, `GET /v1/health`); catalog tag pins per environment with promotion by PR

### Prove

- Both smokes green in every account on every deploy; a new event version reaches dev, then test, then prod only by pin bumps
- A domain cannot read another domain's bucket pair; a reader role cannot write; an unauthenticated call is rejected at the gateway; a malformed webhook is dropped by WAF before the handler
- A replay from the native archive into `test` re-drives a consumer without side effects

**Exit:** the things LocalStack couldn't prove — IAM, resource policies, DNS, encryption, cross-account delivery, real auth, replay — are proven continuously by smokes and drills.

## Step 5 · Reading across domains, reconciliation, and the guardrails

### Build

- Per-domain reader roles for people; DuckDB views that `UNION` deduped silver across domain buckets (Lambda for scheduled runs, laptop for ad hoc)
- Nightly Lambda: **reconciliation** (outbox counts vs bronze counts per domain per hour), undocumented events (bronze vs catalog), quarantine volume, rule drift (account rules vs `generated/`), API drift (`get-export` vs catalog), partition completeness, bucket lifecycle/tags vs declarations
- Retention and cost per domain visible from bucket tags; optional API access logs archived to the domain's bronze bucket under `api/`
- Nightly ROPA export from the catalog (which events and fields carry which PII class, who may decrypt) and the decryptor access review
- Nightly `datacontract test` for every silver table and bronze envelope; freshness SLA; results to alarms and catalog badges

### Prove

- First cross-domain question (orders × payments) answered from silver only, by someone reading the contracts rather than asking the teams
- A hand-made rule or route in any account, or a lost event, shows up in the next nightly report

**Exit:** a nightly report exists and is clean; adding a domain is a catalog PR plus an account, not a platform-team project.

## Only when · Trigger-driven additions — each is additive and reads the same files and contracts

### Events & processes

- **Restricted-audience event** → per-subscription rules on central, platform-applied, producer approval in the catalog
- **Internal vocab in a public event** → input transformer or publish-twice; catalog `derivedFrom`
- **Ordering per aggregate** → FIFO SQS target, group by `aggregateId`
- **Several sagas + portability** → Temporal, per domain or as a process-manager context
- **Stream volume / replay beyond 30 days** → Kinesis for that stream; S3 → bus replayer with the flag

### APIs

- **One hostname, edge caching** → CloudFront edge in the platform account, `/{domain}/*` → domain gateways
- **Many consumers of one API** → Pact consumer-driven contracts alongside the spec
- **Private-only APIs** → VPC link; **internal throughput** → gRPC/ALB; **BFF need** → GraphQL in the consuming domain
- **Cross-domain query fan-out** → read model from events in the asking domain, not a chain

### Data & platform

- **Analytics needs a `direct` field** → reversible tokenisation for that field with a masked silver column and a DPIA entry
- **Humans need SQL / BI** → Athena external tables over the existing silver; **time travel / non-additive evolution** → PyIceberg in the compactor
- **Analyst IAM boundary / gold storage / ownership** → data platform account; **residency** → that domain's pair moves into its account
- **A dataset not derived from events, or a gold aggregate** → hand-authored ODCS, same tests; **a marketplace or mesh platform** → publish the existing contracts
- **RTO shorter than a region incident** → EventBridge global endpoints; **monorepo blocks** → catalog federation

**Rule:** write the trigger in an ADR before building the thing. If you can't name the trigger, it isn't time.
