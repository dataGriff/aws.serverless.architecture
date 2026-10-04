---
description: "Step 1 · Walking skeleton (single account, LocalStack)"
---

# Step 1 · Walking skeleton (single account, LocalStack)

## Before you start

Read, in this order: `docs/architecture/README.md` (index and glossary), `docs/architecture/decisions.md`, then the files under **Read first** below. Load nothing else until a task needs it. Work from a task list and keep it updated.

## Hard rules

- Everything in an account is generated from the catalog. Never hand-edit a rule, bucket, route, role, alarm or contract; change the catalog or the generator.
- Do not introduce Athena, Glue, Iceberg, Kinesis, Temporal, Step Functions outside the saga module, a central gateway, CloudFront, a Schema Registry or a data platform account. If you believe an ADR trigger has fired, stop and run `prompts/10-evaluate-a-trigger.md` instead.
- PII: every schema field carries `x-pii`. `indirect` travels in clear, `direct` is encrypted per subject in public events through the subject-key service, `special` never enters an event.
- Facts are events. One synchronous hop between domains, through a generated client. Never another domain's database or bucket.
- Tests before infrastructure: L0 contract (no infra) → L1 domain-local (LocalStack + pinned `platform-local`) → L2 platform. Never depend on another domain's code or a shared environment.
- Small commits with the ADR or doc section they implement named in the message. If a decision cannot be undone and the docs do not settle it, stop and ask, giving the options and your recommendation.

**Read first:** `docs/architecture/roadmap.md (Step 1)` · `docs/architecture/data-layer.md` · `docs/architecture/pii.md` · `docs/architecture/testing.md` · `docs/architecture/data-contracts.md`

## Goal

Prove every mechanism once, in one account, with real tests, before any generator exists. Patterns and schemas are hand-written here, but written exactly as the generator will emit them, and sourced from the catalog checkout — the catalog remains the only place an event name or field is defined.

## Build (use the modules from prompt 02)

- `platform/envs/local`: a Classic stub `central` (stand-in for the Custom Event Bus, which LocalStack does not emulate), orders' `receives[]` rendered as rules on the stub targeting orders' consumer queues (the subscriber's shape; never a rule targeting `orders-bus`), the archive shim → `orders-events-bronze` running the same validation code as the Firehose transform (ADR-024), the compactor → `orders-events-silver`, the `subject-keys` service, alarms.
- `domains/orders`: `orders-bus`, public-forward rule, one consumer rule from `receives[]`, `order-service` with an outbox, the relay module, the idempotency store, the REST API from the catalog OpenAPI with gateway validation, handlers for `POST /v1/orders` (writes the outbox) and `GET /v1/orders/{id}`, Prism serving the same spec.
- `customerEmail` encrypted end to end through the subject-keys client; one consumer role with a decrypt grant and one without.
- A hand-written ODCS contract for the `OrderPlaced.v1` silver table, following `data-contracts.md`, and `datacontract test` wired into `task test`.
- `tests/query.py` DuckDB views for bronze and silver with read-time dedupe.

## Tests (names are the contract)

`test_public_event_reaches_central_and_bronze_with_shape_intact` · `test_internal_event_never_leaves_domain_bus` · `test_fan_out_excludes_own_events` · `test_dlq_catches_broken_target` · `test_bad_payload_is_quarantined_with_alarm` · `test_direct_field_in_clear_is_quarantined` · `test_cross_hour_duplicate_yields_one_silver_row` · `test_rerun_window_is_idempotent` · `test_replay_flag_causes_no_side_effect` · `test_api_conforms_to_spec` (Schemathesis) · `test_gateway_rejects_invalid_body` · `test_command_produces_event_with_correlation_id` · `test_direct_field_ciphertext_in_bronze_and_absent_from_silver_columns` · `test_granted_role_decrypts_ungranted_cannot` · `test_silver_passes_odcs_contract`.

## Done when

- `task test` is green for all of the above; `task query -- "select … from silver"` shows the event the API call produced, found by `correlationId`.
- No event name, field or type is defined anywhere except the catalog checkout.
- The README states which LocalStack gaps are shimmed and which tests are `sandbox-only`.

## Report back

Finish with: what was built (paths); each exit criterion with its evidence (test names and output, plan summaries, screenshots of the catalog where relevant); what you deliberately did not do and why; any ADR trigger you think is close to firing.
