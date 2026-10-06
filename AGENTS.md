# Working in this repository

An event and API platform pattern on AWS serverless, written so that an organisation can fork it, replace the parameters and have agents build it. Tool-neutral guidance; `CLAUDE.md` imports this file.

## The four layers

| Layer | Where | What it is for |
| --- | --- | --- |
| The pattern | `docs/architecture/` | The decisions with the only triggers that reopen them (`decisions.md`, `adr/`), the conventions, PII model, data layer, data contracts, testing layers, trade-offs and the roadmap. Read before proposing anything. |
| The prompts | `docs/architecture/prompts/` | One self-contained prompt per roadmap step and per recurring operation, installed as `/arch:*` commands and as skills. The source prompt includes shared blocks from `_partials/`; the installed copy is self-contained. |
| The tooling | `platform/` | The catalog generator, the ten catalog checks and Spectral rules, the Terraform modules, the `platform_testing` harness. Pinned by tag from the catalog and domain repos. |
| The templates and the evidence | `templates/`, `spikes/` | `templates/catalog-repo` and `templates/domain-repo` are lifted into an adopter's own repositories. The spikes are the evidence ADR-021 to ADR-025 cite; their suites run against `platform/` and are its regression tests. |

## Read first

1. `docs/architecture/README.md` (index and glossary), then `docs/architecture/decisions.md`.
2. The files the prompt you are running lists under **Read first**. Load nothing else until a task needs it.
3. `platform.yaml` when a value looks like a placeholder (`example.com`, `platform.example`, `orders`, `payments`): it says which are parameters and which are the worked example.

## Hard rules

- Everything in an account is generated from the catalog. Never hand-edit a rule, bucket, route, role, alarm or contract; change the catalog or the generator.
- Do not introduce Athena, Glue, Iceberg, Kinesis, Temporal, Step Functions outside the saga module, a central gateway, CloudFront, a Schema Registry or a data platform account. If you believe an ADR trigger has fired, stop and run `prompts/10-evaluate-a-trigger.md` instead.
- PII: every schema field carries `x-pii`. `indirect` travels in clear, `direct` is encrypted per subject in public events through the subject-key service, `special` never enters an event.
- Facts are events. One synchronous hop between domains, through a generated client. Never another domain's database or bucket.
- Tests before infrastructure: L0 contract (no infra) → L1 domain-local (LocalStack + pinned `platform-local`) → L2 platform. Never depend on another domain's code or a shared environment.
- Small commits with the ADR or doc section they implement named in the message. If a decision cannot be undone and the docs do not settle it, stop and ask, giving the options and your recommendation.

The same six rules are the `hard-rules` partial every prompt carries; `task prompts:check` fails if this file and the partial drift apart.

## Running things

- `task` at the root lists everything. `task doctor` checks the toolchain. `task prompts` regenerates the installed commands and skills; `task prompts:check` lints the prompts. `task localise:report` shows which placeholders are still in place.
- Spike A (`task -d spikes/A-catalog-source-of-truth all`) needs no Docker and proves the generator and the checks in about two minutes. Spikes B and C need Docker and licensed LocalStack (`LOCALSTACK_AUTH_TOKEN` in your shell, never in the repo). Spike D needs a real AWS account and costs money.
- `terraform apply` and `terraform destroy` against a real account are never run by an agent on its own; the Taskfiles run them against LocalStack, and the step-4 prompt says when a person does it for real.
- Test names in a prompt are the acceptance criteria. Do not rename them.

## Vocabulary

`decisions.md` and the glossary in `docs/architecture/README.md` define: central (the Custom Event Bus), domain bus, subscriber, public/internal, audience, bronze/silver, platform-local, saga module, replay flag, `x-pii`, subject-key service, ODCS, data product. Use those words.
