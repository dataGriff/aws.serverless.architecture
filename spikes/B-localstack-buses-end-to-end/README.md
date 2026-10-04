# Spike B — domain bus ↔ central bus end to end on LocalStack

Prompt: `docs/architecture/prompts/spikes/B-localstack-buses-end-to-end.md` (or `/arch:spike-b-localstack-buses-end-to-end`).
**Spike B's result and evidence: [findings.md](findings.md).** Spike C then replaced the hand-written patterns with
Spike A's generator output and re-shaped the buses to ADR-021; what is here now is that joined state
(see [`../C-join/findings.md`](../C-join/findings.md)). The Spike B suite as it ran, with the ADR-001 fan-out and the
real-AWS sandbox env that produced `THIRD_ACCOUNT_HOP_DETECTED`, is at commit `eea52e9` (PR #1).

```sh
mise install            # terraform, task, uv, awscli (root .mise.toml)
task up LICENSED=true   # LocalStack 2026.09.0 with ENFORCE_IAM=1 (ADR-025 L1); LOCALSTACK_AUTH_TOKEN from your shell, never from the repo
task up                 # LocalStack Community 4.14.0: the documented no-licence fallback, cannot enforce IAM
task apply              # catalog-gen → generated/local → 3 buses · forward rules · subscribers as rules on the stub central · probes · archive shim
task test               # drift gates (catalog-gen check, empty plan), then the suite; sandbox-marked tests excluded (ADR-025)
task test-all-local     # sandbox-marked tests included, to see the LocalStack gaps for yourself (xfail strict)
task query              # DuckDB over the bronze buckets: raw/ and processing-failed/ with reasons
task rules              # every deployed catalog-driven rule next to the generated file it came from
task plan GENERATED=<dir>   # plan against another generator run (what Spike C's scenario tests do)
task send -- events/order-placed.json && task dlq-peek
task depths · task sizes · task probe · task probe-firehose · task test-transformer · task reset
```

Topology (ADR-021 in its platform-local rendering, ADR-025 L1): `orders-bus`/`payments-bus` (Classic) → generated
public-forward rule → `central-bus` (a Classic stub for the Custom Event Bus) → one Classic rule per generated
subscriber, with the subscriber's filter and retry policy and its own DLQ, targeting the consumer's queue. No fan-out,
nothing is ever delivered back to a domain bus. The archive shim on central validates every event against the
generated bundle and writes it to the domain's bronze bucket, or quarantines it.

Markers: `sandbox` = LocalStack's answer is not trustworthy for this test (DLQ records, IAM); `transformer` = needs
the transformer rule applied (ADR-022: rejected). `xfail(strict=True)` marks the LocalStack gaps so a fix shows up as a failure.
