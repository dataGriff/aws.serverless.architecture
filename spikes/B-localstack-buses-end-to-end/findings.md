# Spike B — findings

Run on 2026-10-04 against LocalStack Community **4.14.0** (`localstack/localstack:4.14.0`), then re-run on the licensed **2026.9.0** image (section "Second pass" below). Terraform 1.9.8, hashicorp/aws 6.67.0, Docker 29.5.3, Python 3.12 / boto3 1.43 / pytest 9.1. Every claim below names the test or command that proves it.

## Result

- [x] **go-with-changes** — the EventBridge mechanics behave as assumed *on LocalStack*, but two of the design's load-bearing assumptions are contradicted by the AWS documentation, and LocalStack does not model either gap, so the local suite is green for the wrong reasons on those points:
  1. **The two-hop path `domain-bus → central-bus → domain-bus` is not supported by EventBridge (Classic buses) — confirmed in a real account** (section "Confirmed on real AWS" below): the second hop is refused with `THIRD_ACCOUNT_HOP_DETECTED` and lands in the fan-out rule's DLQ. AWS docs: "EventBridge can't route events received from a sender event bus to a third event bus" ([eb-bus-to-bus](https://docs.aws.amazon.com/eventbridge/latest/userguide/eb-bus-to-bus.html)), ([eb-cross-account](https://docs.aws.amazon.com/eventbridge/latest/userguide/eb-cross-account.html)). That is exactly ADR-001's fan-out-all. LocalStack (both editions) delivers the second hop, so the local suite is a **false positive** on this point.
  2. **Input transformers are not available on cross-account bus targets** ("`Input`, `InputPath`, and `InputTransformer` are not available with `PutTarget` if the target is an event bus of a different AWS account", [PutTargets API](https://docs.aws.amazon.com/eventbridge/latest/APIReference/API_PutTargets.html)). ADR-006's only revisit path ("input transformer on the forward rule") therefore cannot be taken in the multi-account end state.
- Everything else the spike was asked to prove — bus-to-bus targets with roles, bus resource policies written cross-account style, `anything-but`+`prefix`, own-event exclusion, consumer rules on the domain bus, envelope preservation, at-least-once, pattern sizes — works on LocalStack and matches the docs. DLQ delivery, resource-policy enforcement and archive replay are **sandbox-only** (LocalStack Community does not implement them).

## Confirmed on real AWS (sandbox account, eu-west-2, 2026-10-04)

`task sandbox-apply && task sandbox-test` applies the same modules and the same `patterns/*.json` to a real account (`terraform/envs/sandbox`) and runs the suite with real credentials. Result: **6 failed, 6 passed, 3 skipped** (the archiver/DuckDB tests are LocalStack-only), and the failures are exactly the two-hop tests.

| Test | LocalStack | Real AWS | What AWS said |
| --- | --- | --- | --- |
| `test_public_event_reaches_central_in_one_hop` (domain → central) | pass | **pass** | — |
| `test_fan_out_from_central_reaches_domain_in_one_hop` (central → domain, event put straight on central) | pass | **pass** (see note on the first run) | — |
| `test_internal_event_never_reaches_central_or_payments` | pass | **pass** | — |
| `test_fan_out_does_not_echo_own_event` | pass | **pass** | — |
| `test_broken_target_lands_in_dlq` (SQS policy denies EventBridge) | xfail | **pass** — the DLQ record arrives within 20 s with `ERROR_CODE=NO_RESOURCE`, `ERROR_MESSAGE="The specified queue does not exist or you do not have access to it … AWS.SimpleQueueService.NonExistentQueue"` | DLQ delivery works on AWS and a policy denial is reported as `NO_RESOURCE`, not an access error — alarm wording should say so. LocalStack cannot show any of it |
| `test_pattern_sizes_under_4kb`, `test_anything_but_prefix_supported_or_fallback` | pass | **pass** | `anything-but` + `prefix` confirmed by `TestEventPattern` on AWS |
| `test_public_event_from_orders_reaches_payments_probe` | pass | **FAIL** | fan-out DLQ: `THIRD_ACCOUNT_HOP_DETECTED` |
| `test_public_event_reaches_payments_consumer_rule` | pass | **FAIL** | same |
| `test_three_bus_loop_terminates` | pass | **FAIL** (event never reaches orders' consumer) | same |
| `test_envelope_preserved_across_two_hops` | pass | **FAIL** | same |
| `test_duplicate_put_is_delivered_twice` | pass | **FAIL** (0 of 2 arrive) | same |

The DLQ record on both fan-out rules (`task sandbox-dlq-peek`):

```
ERROR_CODE    THIRD_ACCOUNT_HOP_DETECTED
ERROR_MESSAGE Event ingestion rejected for event 016356af-… because an event can be sent to an event bus target only once.
              This event was previously delivered to an event bus target.
```

So the answer to "can an event go domain → central → another domain through EventBridge rules alone" is **no**, demonstrated, not just cited. Each hop works on its own; the chain is refused at the second bus-to-bus target and the event lands in that rule's DLQ (which also means every fan-out DLQ alarm would fire on every public event under the design as written). Both LocalStack editions deliver the chain, so the local suite is a false positive on this point and the `sandbox` marker stays.

Note on the one-hop fan-out test: on the first AWS run it failed only on its DLQ-depth assertion because AWS `PurgeQueue` is rate-limited (once per 60 s) and asynchronous, so residue from earlier tests was still counted; the delivery itself succeeded. The assertion is now a before/after delta.

## Reproduce

```sh
mise install                                 # terraform, task, uv, awscli
task -d spikes/B-localstack-buses-end-to-end reset   # down → up → apply → test   (14 passed, 1 xfailed, ~2 min apply + ~2 min tests)
task -d spikes/B-localstack-buses-end-to-end query   # DuckDB over the S3 archive: what flowed through central
task -d spikes/B-localstack-buses-end-to-end probe   # pattern operators, archive/replay, ordering → markdown table
task -d spikes/B-localstack-buses-end-to-end apply FAN_OUT=enumerated && task -d spikes/B-localstack-buses-end-to-end test
task -d spikes/B-localstack-buses-end-to-end test-transformer                  # 1 xfailed (see below)
task -d spikes/B-localstack-buses-end-to-end send -- events/broken-target.json && task -d spikes/B-localstack-buses-end-to-end dlq
task -d spikes/B-localstack-buses-end-to-end depths  # every queue, including DLQs
# licensed image (needs LOCALSTACK_AUTH_TOKEN exported in your shell):
task -d spikes/B-localstack-buses-end-to-end down && task -d spikes/B-localstack-buses-end-to-end up LICENSED=true && task -d spikes/B-localstack-buses-end-to-end apply && task -d spikes/B-localstack-buses-end-to-end test
task -d spikes/B-localstack-buses-end-to-end up LICENSED=true ENFORCE_IAM=0   # needed for CreateArchive
# real AWS (aws sso login --profile admin first; PROFILE= to override):
task -d spikes/B-localstack-buses-end-to-end sandbox-apply && task -d spikes/B-localstack-buses-end-to-end sandbox-test
task -d spikes/B-localstack-buses-end-to-end sandbox-dlq-peek   # THIRD_ACCOUNT_HOP_DETECTED on the fan-out DLQs
task -d spikes/B-localstack-buses-end-to-end sandbox-destroy
```

`-m sandbox` selects the tests whose LocalStack result must not be trusted; run those in a real account before relying on them (`uv run --with boto3 --with pytest pytest -m sandbox` with real credentials and no `AWS_ENDPOINT_URL`).

## LocalStack fidelity (Community, version: 4.14.0)

| Mechanism | Works? | Evidence | Note for real AWS |
| --- | --- | --- | --- |
| bus-to-bus target with IAM role (`events.amazonaws.com` trust, `events:PutEvents` on the target bus) | yes | `test_public_event_reaches_central_in_one_hop`, `test_fan_out_from_central_reaches_domain_in_one_hop`; DLQs of both forward rules stay at 0 (`dlq_count`) | Role shape matches the docs; LocalStack does not evaluate the role, so a wrong policy would still deliver locally. **Sandbox.** |
| second bus-to-bus hop (`orders-bus → central → payments-bus`) | **delivers, but AWS says it must not** | `test_public_event_from_orders_reaches_payments_probe`, `test_envelope_preserved_across_two_hops`, `test_three_bus_loop_terminates` all pass locally; marked `@pytest.mark.sandbox` | Documented as unsupported for Classic buses in the same account and across accounts. **Sandbox, expected to fail there.** |
| bus resource policy, cross-account shape (`Principal.AWS = arn:aws:iam::<acct>:root`, `events:PutEvents`) | applies | `terraform apply` creates `aws_cloudwatch_event_bus_policy` on all three buses (`terraform state list \| grep bus_policy`) | Not enforced locally. **Sandbox.** |
| `prefix` | yes | `task probe` rows `prefix`, `prefix (miss)`; `test_anything_but_prefix_supported_or_fallback` | — |
| `anything-but` + `prefix` | yes | `test_anything_but_prefix_supported_or_fallback`; `task probe` rows `anything-but + prefix` (matches other domain) and `(own)` (excludes own) | Supported by AWS since 2023; verify once in the sandbox with `aws events test-event-pattern`. |
| `anything-but` list, `exists` (top-level and nested), `suffix`, `equals-ignore-case`, `wildcard`, `numeric`, `$or` | yes, all | `task probe` | — |
| enumerated fan-out fallback needed? | **no** | `task apply FAN_OUT=enumerated && task test` is also green (same 11 passed / 1 xfailed), so both forms work; `anything-but`+`prefix` stays the default | The enumerated form grows with every domain and needs a re-apply per onboarding; keep it only as a generator flag. |
| consumer rule on the domain's own bus (`receives[]` shape) | yes | `test_public_event_reaches_payments_consumer_rule`, `test_three_bus_loop_terminates` (orders' consumer of `PaymentCaptured.v1`) | — |
| own-event exclusion (no echo) | yes | `test_fan_out_does_not_echo_own_event`: exactly one delivery on `orders-probe-all`; `test_fan_out_from_central_reaches_domain_in_one_hop`: `expect_none` on orders' probe | Pattern-based, so it holds on AWS too; the AWS one-hop rule would additionally stop any echo. |
| loop terminates | yes | `test_three_bus_loop_terminates`: 1 copy per bus, then 0 further deliveries after 10 s | On AWS the loop cannot even start (one hop max). If the fan-out target becomes a re-publisher (see below) that guard is gone and this test becomes load-bearing. **Sandbox.** |
| DLQ on a target whose SQS policy denies EventBridge | **no** — the policy-less queue receives the event (`task depths` → `central-broken-target 3`, `central-broken-target-dlq 0` after three puts) | `test_broken_target_lands_in_dlq` is `xfail(strict=True)` with the reason string; `task send -- events/broken-target.json && task dlq` returns no messages | LocalStack Community does not enforce SQS resource policies. **Sandbox.** |
| DLQ on a target that does not exist | **no** — LocalStack logs `{"ErrorCode": "TargetDeliveryFailure", ...NonExistentQueue...}` ~210 ms after `PutEvents` (15:18:24.145 → 15:18:24.356 in `docker logs`) but writes nothing to the DLQ | ad hoc: `aws events put-targets ... Arn=arn:aws:sqs:…:does-not-exist,DeadLetterConfig={Arn=<dlq>}` then `task depths` → DLQ stays 0 | `DeadLetterConfig` is accepted and stored but never used. DLQ latency on AWS is therefore unmeasured. **Sandbox.** |
| input transformer on a bus target | **no** — LocalStack uses the transformed template as the whole `PutEvents` entry, logs `Parameter DetailType is not valid. Reason: DetailType is a required argument.` and drops the event (no DLQ) | `task test-transformer` → `test_input_transformer_on_bus_target` xfailed (strict) | **Not available at all for cross-account bus targets** (PutTargets API note). Same-account behaviour is undocumented. ADR-006 depends on this — see below. |
| archive: `CreateArchive`, `DescribeArchive` (`EventCount` increments) | yes | `task probe` row `CreateArchive`; `aws events describe-archive --archive-name probe-arch` shows `EventCount: 1` after a put | — |
| replay: `StartReplay` | **no** — returns HTTP 500 `InternalError` (`docker logs`: `exception during call chain: replace() takes at least 2 positional arguments (0 given)`); the replay is nevertheless registered and sits in `STARTING` forever; nothing is re-emitted; with boto's default retries the second attempt reports `ResourceAlreadyExistsException` | `task probe` row `StartReplay` (client with `max_attempts=0`); `aws events list-replays` | ADR-008's replay drill and the `replay: true` flag are **sandbox-only**. |
| ordering across two hops | **not preserved** even on LocalStack | `task probe` row `ordering`: 20 sequential puts, 20/20 delivered, order `[0, 1, 3, 2, 5, 4, …]` on one run, `[0, 2, 1, 5, 3, 4, …]` on the next | Matches EventBridge's no-ordering guarantee; confirms ADR-001's FIFO-SQS trigger is the right escape hatch. |
| at-least-once (duplicate put delivered twice) | yes | `test_duplicate_put_is_delivered_twice` | Same on AWS by design; consumers dedupe on `eventId` (documented, not fixed). |
| envelope preserved across hops (`source`, `detail-type`, `detail`, `time` equal; `id` differs) | yes | `test_envelope_preserved_across_two_hops` | AWS assigns a new `id` and ingestion time per bus for the new Custom Event Bus ([docs](https://docs.aws.amazon.com/eventbridge/latest/userguide/eb-custom-bus-target-bus.html)); Classic `time` behaviour unverified. **Sandbox.** |
| pattern sizes | all < 80 bytes | `test_pattern_sizes_under_4kb`, `task sizes` | Generated patterns will stay tiny: fan-out is one `anything-but`, forward is one prefix + a detail-type list. |
| Terraform (hashicorp/aws 6.67) against LocalStack | yes | `task apply` → 65 resources, ~2 min; `aws_sqs_queue_policy` creates take ~25 s each (LocalStack, not Terraform) | — |
| Lambda archiver stretch (S3 + DuckDB) | **yes** | `test_archiver_writes_every_central_event_to_s3`, `test_internal_event_is_never_archived`, `test_duckdb_reads_archive_with_hive_partitions`; `task query` | See "Stretch: archive" below. The starter's `LAMBDA_DOCKER_NETWORK=host` had to go: it makes every Lambda container fail with `Unable to detect IP address … in network host`. |

## Stretch: archive — Lambda on central → S3, read with DuckDB

A rule on `central-bus` matching everything (`patterns/probe-all.json`) invokes a 10-line Lambda (`terraform/modules/bus-s3-archiver/src/handler.py`) that writes each event as one JSON object to `s3://central-archive/raw/source=<source>/detail_type=<detail-type>/<id>.json`. It is the stretch the spike prompt names; Firehose is explicitly out of scope for Spike B. LocalStack does ship Firehose in every plan, but the "Firehose probe" section below shows it does not honour the ADR-009 features the design depends on, so this shim is what platform-local will need. This is what "what flowed" looks like after a `task test`:

```
$ task query
┌──────────────────────────┬──────────────────────┬────────┬─────────────────────┬─────────────────────┐
│          source          │     detail_type      │ events │     first_seen      │      last_seen      │
├──────────────────────────┼──────────────────────┼────────┼─────────────────────┼─────────────────────┤
│ orders.order-service     │ OrderPlaced.v1       │      9 │ 2026-10-04 16:14:02 │ 2026-10-04 16:15:49 │
│ payments.payment-service │ PaymentCaptured.v1   │      2 │ 2026-10-04 16:14:48 │ 2026-10-04 16:15:58 │
│ platform.spike           │ BrokenTargetProbe.v1 │      1 │ 2026-10-04 16:15:25 │ 2026-10-04 16:15:25 │
└──────────────────────────┴──────────────────────┴────────┴─────────────────────┴─────────────────────┘
```

| Claim | Evidence |
| --- | --- |
| every public event that reaches central is archived, raw, under Hive partitions, with the `central-archive` DLQ at 0 | `test_archiver_writes_every_central_event_to_s3` |
| internal events never reach the archive (they never reach central) | `test_internal_event_is_never_archived` |
| DuckDB reads the bucket straight from LocalStack's S3 via `httpfs` (path-style, test creds), `hive_partitioning=true` turns the prefixes into `source` / `detail_type` columns, and `detail.*` is queryable as a struct | `test_duckdb_reads_archive_with_hive_partitions`; `task query -- "SELECT detail.correlationId, time FROM archive ORDER BY time"` |
| `read_json_auto` infers `detail.eventId` as `UUID`, not `VARCHAR` | same test; the compactor must pin column types from the catalog schema (ADR-011's `d_*` columns) rather than trust inference |
| `order.aggregate.updated` (internal) is absent from the archive; `BrokenTargetProbe.v1` is present because it was put on central directly | `task query` after `task test` |
| Lambda cold start inside LocalStack is ~2 s; events land in S3 within ~3 s of `PutEvents` | `archived()` polls at 1 s and succeeds on the 2nd–3rd poll |
| the at-least-once duplicate from `test_duplicate_put_is_delivered_twice` is two objects in the archive with the same `correlationId` and `time` and different `id`s | `task query -- "SELECT detail.correlationId, time FROM archive ORDER BY time DESC LIMIT 5"` shows the pair; this is the row ADR-011's read-time `QUALIFY row_number() OVER (PARTITION BY event_id)` exists to collapse |

What this does not prove: anything about Firehose (buffering, dynamic partitioning, the validation transform, `processing-failed/`; ADR-009), Object Lock or CMKs (ADR-010), or compaction (ADR-011). It proves the *shape* the data layer reads — one object per event, Hive prefixes, DuckDB over S3 — works end to end on LocalStack, and gives Spike C and Step 1 a working `duck()` helper and `task query` to start from.

## Firehose probe (outside Spike B's boundary; answers the ADR-009 open question)

`task probe-firehose` applies a Firehose stream on `central-bus` in ADR-009's shape — EventBridge rule → Firehose (role) → S3 with a validation Lambda (`ProcessingConfiguration`), dynamic partitioning on `source` / `detail-type` from the Lambda's partition keys, `ErrorOutputPrefix = processing-failed/…`, 60 s / 64 MiB buffers — then puts one valid event and one carrying `customerEmail` in clear. Same result on Community 4.14.0 and licensed 2026.9.0.

| ADR-009 mechanism | LocalStack | Evidence |
| --- | --- | --- |
| EventBridge → Firehose target with a role | **works** | objects appear in `central-bronze` ~3 s after `PutEvents`; `central-bronze` DLQ empty |
| buffering (60 s interval) | **ignored** — one S3 object per record, written immediately | `objects written within 150 s: 2 (first seen after ~3 s)` |
| Lambda transform is invoked | yes, but **with a non-AWS payload**: `{"records": [{"data": "<b64>"}]}` — no `recordId`, `invocationId`, `deliveryStreamArn` or `approximateArrivalTimestamp` | `INVOCATION SHAPE:` line in `/aws/lambda/central-bronze-validator`; a contract-conformant Lambda dies with `KeyError: 'recordId'` |
| when the transform Lambda errors | Firehose **writes an empty object** per record under the normal prefix; nothing is retried, nothing goes to `processing-failed/` | first run: two 0-byte objects |
| `Ok` record with transformed `data` | **honoured** — the S3 body is the Lambda's output | body has `json.dumps` spacing, not the compact original |
| `ProcessingFailed` record | **not quarantined** — written raw under the normal `bronze/` prefix, not `processing-failed/` | second object is the untouched PII-in-clear event; `error_output_prefix` never used |
| dynamic partitioning (`!{partitionKeyFromLambda:…}`) | **not evaluated** — the placeholder text is the S3 key, with Firehose's `YYYY/MM/DD/HH/` appended | key: `bronze/source=!{partitionKeyFromLambda:source}/detail_type=!{partitionKeyFromLambda:detail_type}/2026/10/04/16/central-bronze-…` |
| DuckDB over the result | reads it, but `hive_partitioning=true` yields the literal placeholder as the partition value | `[('!{partitionKeyFromLambda:source}', '!{partitionKeyFromLambda:detail_type}', 2)]` |

**Consequence.** LocalStack's Firehose is a pass-through to S3: fine for "did the stream get the record", useless for the three things ADR-009 makes load-bearing — validation-driven quarantine, PII-in-clear detection and the bronze layout. For platform-local and domain-local tests, the bronze archive should be produced by the Lambda shim from the stretch (same layout, same `duck()` view) with the validation logic in it; real Firehose behaviour (buffering, partitioning, `processing-failed/`, the exact transform contract) is **sandbox-only** and belongs in the nightly L2 run. Write the validation Lambda once and use it in both: Firehose calls it in AWS, the shim imports it locally. Flag for LocalStack: the transform payload shape is a fidelity bug worth reporting.

## Second pass: licensed image (LocalStack 2026.9.0, `task up LICENSED=true`)

Re-run the same day with `localstack/localstack:2026.09.0` (`edition: pro`, licence activated) and `ENFORCE_IAM=1`, then once more with `ENFORCE_IAM=0`. The token comes from the shell environment; `docker-compose.licensed.yml` references it and never holds it.

| Mechanism | Community 4.14.0 | Licensed 2026.9.0 | What changed |
| --- | --- | --- | --- |
| suite (`task test`) | 11 passed, 1 xfailed | 11 passed, 1 xfailed | identical; **the second bus-to-bus hop still delivers**, so the one-hop limit is not modelled in either edition |
| pattern operators | all ok | all ok | — |
| ordering across hops | out of order | out of order | — |
| SQS resource policy on a target | not enforced (event lands on the policy-less queue) | **enforced** with `ENFORCE_IAM=1`: `Failed to deliver event to target sqs of rule central-broken-target: AccessDenied … sqs:sendmessage` and the queue stays at 0 | the broken target is now broken for the right reason |
| DLQ record for the failed delivery | none | **still none** (`central-broken-target-dlq 0` after the denied delivery; `task dlq` empty) | `DeadLetterConfig` is still inert; DLQ delivery and latency stay **sandbox-only** |
| input transformer on a bus target | accepted at `PutTargets`, event dropped at delivery | **rejected at `PutTargets`**: `ValidationException: Modifying the input for target forward-to-bus is not supported` (`task test-transformer` fails in `terraform apply`) | this is AWS's own error text; the licensed provider models the real restriction, same-account included. `task probe` row `InputTransformer on a bus target` reproduces it without Terraform |
| `CreateArchive` with `ENFORCE_IAM=1` | ok | **500 InternalError**: LocalStack creates the archive's internal rule as `events.amazonaws.com` and its own IAM engine denies `events:PutRule` on it | LocalStack bug; archives need `ENFORCE_IAM=0` |
| `CreateArchive` / `StartReplay` with `ENFORCE_IAM=0` | create ok, replay 500 | create ok, **replay still 500** with the same `replace() takes at least 2 positional arguments` traceback | the replay bug is in both editions; **replay is sandbox-only, full stop** |
| broken target with `ENFORCE_IAM=0` | delivered to the policy-less queue | delivered to the policy-less queue (`central-broken-target 1`) | without IAM enforcement the licensed image behaves like Community |

`ENFORCE_IAM=1` also warns `No IAM action found for given operation events:ListTagsForResource. Falling back to allow` on every Terraform read; harmless.

**Net effect of the licence:** one gap closes (resource policies and roles are enforced, so a misconfigured policy fails locally) and one claim hardens (the transformer restriction is rejected at the API with AWS's wording). The three findings that drive the recommendation — the one-hop limit, no DLQ records, broken replay — are unchanged. A licence is worth having for day one because of IAM enforcement alone; it does not remove the need for the sandbox run.

## Differences from docs/architecture assumptions

1. **ADR-001 (fan-out-all) assumes a second bus-to-bus hop.** EventBridge Classic buses deliver exactly one bus-to-bus hop; an event that arrived on `central-bus` via a rule is not forwarded again by central's rules. Both the same-account and cross-account pages say so. LocalStack hides this.
2. **ADR-006's revisit path (input transformer on the forward rule) is unavailable cross-account**, and LocalStack cannot test the same-account variant either. The remaining path, "a distinct public event with `derivedFrom`", is the only one that works end to end.
3. **testing.md L2 claims "DLQ behaviour … native archive replay" are testable on LocalStack.** They are not on Community 4.14: DLQ delivery, resource-policy enforcement, IAM role evaluation and `StartReplay` are all sandbox-only. The nightly real-AWS run is not a belt-and-braces step for these; it is the only test.
4. **roadmap.md / README assume a "LocalStack compose pinned to a version" is a free choice.** `localstack/localstack:latest` (2026.6.2) exits with `License activation failed` unless `LOCALSTACK_AUTH_TOKEN` is set; 4.14.0 is the last Community line. Either pin 4.14.0 everywhere (platform-local, domain repos, CI) and accept it will not receive fixes, or budget for a LocalStack licence.
5. **The starter Taskfile did not parse** (flow-style YAML in `dlq`); rewritten in block style. `test_three_bus_loop_terminates` as written asserted zero deliveries on the probes without first draining the one legitimate copy; fixed to assert exactly one copy per bus, then zero after 10 s.
6. **EventBridge now has a second product.** AWS relaunched the **Custom Event Bus** on 2026-09-24 (the rules-and-targets bus is now "Custom Event Bus - Classic"): one bus shared via AWS RAM, per-account *subscribers* (filter + optional transform + one target + retries + DLQ), retention 1–365 days, FIFO per event group, publish-time dedup, replay by subscriber starting position, best-effort loop detection with `LOOP_DETECTED` in the DLQ, `eventsv2` API / `AWS::EventsV2::*`. It removes the need for fan-out rules, archives, and most of the compactor's dedupe, and gives ordering and replay natively — i.e. it is the product the platform account was going to assemble by hand. It is ten days old, has no LocalStack emulation, Terraform provider coverage is unverified, and pricing is per GB rather than per event.

## Tests that must also run in a real AWS sandbox before being trusted

Everything marked `@pytest.mark.sandbox` (`pytest -m sandbox`):

- `test_public_event_from_orders_reaches_payments_probe`, `test_public_event_reaches_payments_consumer_rule`, `test_fan_out_does_not_echo_own_event`, `test_three_bus_loop_terminates`, `test_envelope_preserved_across_two_hops`, `test_duplicate_put_is_delivered_twice` — all two-hop; **expected to fail on AWS as the topology stands**.
- `test_broken_target_lands_in_dlq` — DLQ delivery, DLQ message shape (`ERROR_CODE`/`ERROR_MESSAGE` attributes), DLQ latency, resource-policy denial. Also the manual `task send … && task dlq` path.
- `test_input_transformer_on_bus_target` — same-account only; cross-account is documented as unsupported.
- Plus, not tests here: IAM role evaluation on bus targets, `StartReplay` with the `replay-name` field, and whether `time` survives a Classic bus-to-bus hop.

## Recommended changes to roadmap / ADRs

**Recommendation: proceed to day one with these changes, not as written.**

1. **ADR-001 — replace the second hop.** Keep domain bus → central (rule + role, proven on AWS) and keep the fan-out *pattern* on central (proven on AWS), but make the fan-out target a platform-owned re-publisher that calls `PutEvents` on the domain bus (a tiny Lambda, or a Pipe when LocalStack supports it) instead of the domain bus itself. A re-published event is a new event with a fresh hop budget. Trade-off: one Lambda in the hot path per domain (ms of latency, a new failure mode, the loop guard is now the pattern alone), against the alternative of making every domain relay publish straight onto central cross-account (fewer moving parts, but the domain's own bus no longer sees its own public events and domain-local testing loses the forward rule). The drop is now demonstrated (`task sandbox-test`); the sandbox env stays in the repo as the place to prove the re-publisher.
2. **ADR-006 — drop "input transformer on the forward rule" from `revisit_when`.** The only viable path is a distinct public event with `derivedFrom`; say so.
3. **ADR-008 / ADR-009 / testing.md — mark replay, DLQ delivery, resource policies, IAM roles and every Firehose behaviour beyond "record reaches S3" `sandbox-only`.** platform-local's bronze comes from the Lambda shim sharing the real validation code. platform-local must stub them honestly (an `expect_dlq` that reads LocalStack's `TargetDeliveryFailure` log line is the most it can do) and the nightly sandbox run becomes a release gate for those mechanisms, not a nice-to-have.
4. **Day one toolchain — use the licensed image with `ENFORCE_IAM=1` for platform-local and CI** (the token is already available on this machine; the Taskfile shows the pattern). It is the only way IAM roles and resource policies fail locally, and it is the only line receiving fixes. Keep `4.14.0` as the documented no-licence fallback and note it cannot enforce IAM. Archives need `ENFORCE_IAM=0` until LocalStack fixes its internal archive rule.
5. **Add a named trigger to ADR-001 and ADR-008: evaluate the EventBridge Custom Event Bus** (one shared bus, per-account subscribers, retention, FIFO, dedup, replay) in the sandbox before Step 4 commits real accounts. If it holds up, it supersedes fan-out-all, the native archive and part of the compactor at once; the catalog generator would emit subscribers instead of rules. Do not build on it on day one: ten days old, no local emulation.
6. **Spike C** can proceed on LocalStack for everything pattern-shaped (forward, fan-out, consumer rules, own-event exclusion, pattern sizes); it must not claim end-to-end delivery across two hops as proven.

## Open questions

- Does the Classic bus-to-bus hop keep `time` on AWS, or re-stamp it like the Custom Event Bus does? (affects bronze partitioning by event time vs bus time)
- Is `LOOP_DETECTED` on the Custom Event Bus reliable enough to retire the pattern-based guard?
- Does the Terraform AWS provider cover `AWS::EventsV2::*` yet, and does LocalStack Pro?
- ~~Does LocalStack's Firehose honour dynamic partitioning, `ProcessingConfiguration` and `ErrorOutputPrefix`?~~ Answered above: no, no and no. platform-local needs the Lambda shim.
