# Conventions

Constant across every bus, bucket and API; the Spectral ruleset and catalog CI enforce them.

## Event routing fields

- `source` = `{domain}.{service}` — the public-forward rule, every subscriber filter and the Firehose routing depend on it
- `detail-type` = `{EventName}.v{n}` — version in the name; breaking change = new name = new silver directory; dual-publish until `sunset`
- Rules match on `source` + `detail-type` only, never on payload; the generator splits a rule before it reaches the 4KB pattern limit

## Inside `detail`

- `eventId` (dedupe key everywhere), `occurredAt` (business time), `replay` (true on re-driven events; side-effecting consumers skip them)
- `correlationId` (from the API's `X-Correlation-Id` when a command started it), `causationId`
- `aggregateId` + `aggregateVersion` for ordering and FIFO grouping
- Every field classified in the catalog: `indirect` in clear; `direct` as the ciphertext envelope `{"enc":"v1","kid":"<subject-key-id>","ct":"<base64>"}`; `special` never. Payloads < 256 KB; claim-check to S3 otherwise

## API conventions Spectral-enforced

- OpenAPI 3.1 in the catalog; `/v{n}` path version; additive = minor, anything else is `/v{n+1}` with `Sunset`/`Deprecation` headers on the old one
- Every operation tagged `x-eventcatalog-message-type: command | query`; commands are POST with a required `Idempotency-Key`; queries are GET, cursor-paginated
- Errors are RFC 9457 `application/problem+json`; `X-Correlation-Id` accepted and echoed; gateway validates bodies against the catalog schemas
- Security scheme declared in the spec (JWT or IAM); `x-external: true` marks routes that get WAF

## Consumer discipline

- Events: at-least-once ⇒ idempotent on `eventId`; tolerant reader; honours `replay`; projection schema on the `receives[]` entry
- APIs: generated client only, pinned to a catalog version; timeouts, retries with jitter, circuit breaker; anti-corruption projection; one hop
- Never another domain's database or bucket; never a hand-rolled HTTP call; decrypted `direct` fields are used in flight and never persisted without the consumer's own erasure path
