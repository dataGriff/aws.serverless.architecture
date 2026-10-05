# Spike C — join: the catalog drives the LocalStack buses

Prompt: `docs/architecture/prompts/spikes/C-join-catalog-to-buses.md` (or `/arch:spike-c-join-catalog-to-buses`).
**Result and evidence: [findings.md](findings.md).**

Spike C has no infrastructure of its own. It points Spike B's Terraform at Spike A's generator output, deletes every
hand-written pattern, and proves that a catalog edit is the only thing that changes behaviour on the buses.

```sh
task up                 # licensed LocalStack with ENFORCE_IAM=1 (Spike B's compose; LOCALSTACK_AUTH_TOKEN from your shell)
task apply              # catalog-gen → ../A-catalog-source-of-truth/generated/local → Spike B's terraform/envs/local
task test               # Spike B's suite behind its drift gates, then the scenarios below (~8 min)
task scenarios          # only the behaviour-through-the-catalog tests
task snapshots:update   # accept changed plans into snapshots/
task no-spike-markers   # done-when: no hand-written stand-in marked for this spike is left under spikes/
task -d ../B-localstack-buses-end-to-end query    # DuckDB over bronze: raw/ and processing-failed/ side by side
```

## What lives where

| Path | What |
| --- | --- |
| `tests/scenarios.py` | Copy the catalog → apply one edit → `catalog-gen build` → `terraform plan/apply -var generated_dir=…` → reduce the plan to addresses, actions and changed attributes (with before/after event patterns and the shim's routing map). |
| `tests/test_catalog_drives_buses.py` | The scenarios: flip `order.aggregate.updated` to public and back; add and remove a cross-domain `receives[]`; add and remove a same-domain `receives[]`; the drift gates are wired into `task test`. |
| `snapshots/*.json` | The committed plan for each scenario step — the "exact set of changes" claim, reviewable in a PR. |
| `.scenarios/` (gitignored) | Per-scenario catalog copies and generator output. |

Everything the scenarios exercise is in Spike B's directory, which Spike C modified in place:

- `terraform/envs/local/main.tf` reads `rules/*-public-forward*.json`, `rules/*-consumer-*.json`, `subscribers/*.json`,
  `archive/routing-map.json` and `validation/*.json` from `generated/local`; bus-policy principals and the domain list
  come from the same files. Probe and broken-target patterns are test scaffolding and stay inline.
- `modules/bus-s3-archiver` is the ADR-024 shim: `src/validate.py` (the function Firehose would call) + `fastjsonschema`
  + the generated bundles in one zip; routes by the routing map to `<domain>-events-bronze`, quarantines to
  `processing-failed/reason=<schema|pii-in-clear|unknown-event>/`.
- `modules/bus-sqs-rule` gained the subscriber's `retryPolicy`.
- `Taskfile.yml`: `apply` regenerates first; `test` runs `catalog-gen check` and `terraform plan -detailed-exitcode` before pytest.
