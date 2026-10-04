# Spike B — domain bus ↔ central bus end to end on LocalStack

Prompt: `docs/architecture/prompts/spikes/B-localstack-buses-end-to-end.md` (or `/arch:spike-b-localstack-buses-end-to-end`).
**Result and evidence: [findings.md](findings.md).**

```sh
mise install          # terraform, task, uv, awscli (root .mise.toml)
task up               # LocalStack Community 4.14.0 (pinned; `latest` needs a licence token)
task up LICENSED=true # LocalStack 2026.09.0 with ENFORCE_IAM; needs LOCALSTACK_AUTH_TOKEN exported (never commit it)
task apply            # 3 buses · forward + fan-out rules · consumer rules · probes · broken target
task test             # 12 tests; names are the contract (11 pass, 1 xfail on LocalStack)
task probe            # pattern operators, archive/replay, ordering — prints a table
task test-transformer # re-applies with the transformer rule and runs that one test (xfail on LocalStack)
task send -- events/order-placed.json && task dlq
task depths           # every queue's depth, DLQs included
task reset            # down → up → apply → test
```

Patterns are hand-written JSON under `patterns/` — marked `SPIKE: replaced in spike C`.
`task apply FAN_OUT=enumerated && task test` runs the enumerated fan-out form; it was not needed (see findings).

Markers: `sandbox` = LocalStack's answer is not trustworthy for this test (run `pytest -m sandbox` against a real account);
`transformer` = needs the transformer rule applied. `xfail(strict=True)` marks the LocalStack gaps so a fix shows up as a failure.
