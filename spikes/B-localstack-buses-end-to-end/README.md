# Spike B — domain bus ↔ central bus end to end on LocalStack

Prompt: `docs/architecture/prompts/spikes/B-localstack-buses-end-to-end.md` (or `/arch:spike-b-localstack-buses-end-to-end`).

```sh
mise install          # terraform, task, uv, awscli (root .mise.toml)
task up               # LocalStack
task apply            # 3 buses · forward + fan-out rules · consumer rules · probes · broken target
task test             # 10 tests; names are the contract
task test-transformer # re-applies with the transformer rule and runs that one test
task send -- events/order-placed.json && task dlq
```

Patterns are hand-written JSON under `patterns/` — marked `SPIKE: replaced in spike C`.
If `test_anything_but_prefix_supported_or_fallback` fails: `task apply FAN_OUT=enumerated && task test`, and record it.

Write `findings.md` as you go; it is the deliverable.
