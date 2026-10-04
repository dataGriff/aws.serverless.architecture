# Spike B — findings

> Fill in as you go. Every claim needs the test name or command that proves it.

## Result
- [ ] go / go-with-changes / stop — and why

## LocalStack fidelity (Community, version: ____)
| Mechanism | Works? | Evidence | Note for real AWS |
| --- | --- | --- | --- |
| bus-to-bus target with role | | `test_public_event_from_orders_reaches_payments_probe` | |
| `anything-but` + `prefix` | | `test_anything_but_prefix_supported_or_fallback` | |
| enumerated fan-out fallback needed? | | | |
| DLQ on denied SQS target | | `test_broken_target_lands_in_dlq` | latency observed: |
| input transformer on a bus target | | `test_input_transformer_on_bus_target` | **verify against AWS docs/sandbox — ADR-006 depends on it** |
| archive / replay (`CreateArchive`, `StartReplay`) | | | |
| ordering observed | | `test_duplicate_put_is_delivered_twice` and ad-hoc | |

## Differences from docs/architecture assumptions
-

## Tests that must also run in a real AWS sandbox before being trusted
-

## Recommended changes to roadmap / ADRs
-
