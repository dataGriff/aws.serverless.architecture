# Spike B — domain bus ↔ central bus end to end on LocalStack

Prompt: `docs/architecture/prompts/spikes/B-localstack-buses-end-to-end.md` (or `/arch:spike-b-localstack-buses-end-to-end`).
**Result and evidence: [findings.md](findings.md).**

```sh
mise install          # terraform, task, uv, awscli (root .mise.toml)
task up               # LocalStack Community 4.14.0 (pinned; `latest` needs a licence token)
task up LICENSED=true # LocalStack 2026.09.0 with ENFORCE_IAM; needs LOCALSTACK_AUTH_TOKEN exported (never commit it)
task apply            # 3 buses · forward + fan-out rules · consumer rules · probes · broken target · S3 archiver
task test             # the 9 tests LocalStack can answer; sandbox-marked tests (two-hop, DLQ) are excluded here — LocalStack gives false positives
task test-all-local   # all 15 on LocalStack anyway (14 pass, 1 xfail) — to see the false positives for yourself
task probe            # pattern operators, archive/replay, ordering — prints a table
task query            # DuckDB over the S3 archive written by the central archiver Lambda (stretch)
task probe-firehose   # outside the spike boundary: does LocalStack honour ADR-009's Firehose features? (it does not — see findings)
task test-transformer # re-applies with the transformer rule and runs that one test (xfail on LocalStack)
task send -- events/order-placed.json && task dlq
task depths           # every queue's depth, DLQs included
task reset            # down → up → apply → test
```

Real AWS (after `aws sso login --profile admin`): `task sandbox-apply && task sandbox-test`, `task sandbox-dlq-peek`, `task sandbox-destroy`.
The two-hop tests fail there with `THIRD_ACCOUNT_HOP_DETECTED` — that is the point; see findings.

Patterns are hand-written JSON under `patterns/` — marked `SPIKE: replaced in spike C`.
`task apply FAN_OUT=enumerated && task test` runs the enumerated fan-out form; it was not needed (see findings).

Markers: `sandbox` = LocalStack's answer is not trustworthy for this test (run `pytest -m sandbox` against a real account);
`transformer` = needs the transformer rule applied. `xfail(strict=True)` marks the LocalStack gaps so a fix shows up as a failure.
