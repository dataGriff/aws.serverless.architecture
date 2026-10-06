# aws.serverless.architecture

An event and API platform pattern on AWS serverless, written so that an organisation can fork it, replace the parameters, and have agents build it: the decisions with the only triggers that reopen them, the conventions a catalog CI enforces, one ready-to-run prompt per roadmap step and per recurring operation, and the spikes that proved the load-bearing ideas before day one.

## Who this is for

- Several business domains, each owning its services, its API and its events, each in its own AWS account, with a platform team owning the routing, archive and data layer between them
- Event-first on EventBridge, REST APIs from OpenAPI, S3 + Parquet + DuckDB for analytics, EventCatalog as the single source of truth that generates every account's IaC
- Personal data in events as a fact to classify and encrypt per subject rather than a thing to ban, with erasure as key deletion
- Teams that want agents to do the building from written-down decisions, and a reviewer to check the result against the same decisions

Not for: a single service, a single account, a team that wants Kafka or a workflow engine on day one, or a system that must run in a region without the EventBridge Custom Event Bus (see the limits below).

## What you get

| | Where |
| --- | --- |
| 25 architecture decision records, each with `revisit_when` triggers in machine-readable frontmatter; one decisions table that is the review checklist | [`docs/architecture/decisions.md`](docs/architecture/decisions.md), [`adr/`](docs/architecture/adr/) |
| The conventions, PII model, data layer, data contracts (ODCS v3), testing layers and the accepted trade-offs, one short file each | [`docs/architecture/`](docs/architecture/README.md) |
| A five-step roadmap where every step proves one mechanism and has an exit criterion | [`roadmap.md`](docs/architecture/roadmap.md) |
| 19 agent prompts: three for day one, one per step, one for trigger evaluation, one for architecture review, four for recurring operations (add an event, add an API operation, onboard a domain, handle an erasure request), three for the spikes. Installed as `/arch:*` commands for Claude Code | [`prompts/`](docs/architecture/prompts/README.md), [`.claude/commands/arch/`](.claude/commands/arch/) |
| A working catalog generator with 10 catalog checks, a Spectral ruleset, golden snapshots and 27 tests; Terraform modules for the buses, rules, subscribers and archive; a LocalStack harness with 19 bus tests and 6 behaviour-through-the-catalog scenario tests with committed plan snapshots; 18 tests against the real Custom Event Bus | [`spikes/`](spikes/README.md) |
| A one-page shareable overview with the diagrams | [`overview.html`](docs/architecture/overview.html) |

## Limits and cost of entry

Read these before deciding to adopt. Each is a consequence of a row in the decisions table and is explained in [`trade-offs.md`](docs/architecture/trade-offs.md).

- **One region, eu-west-1.** The EventBridge Custom Event Bus used as the central bus has no London (eu-west-2) endpoint at the time of writing. Data stays in the EU; UK-only residency is a named trigger, not a default.
- **EventBridge only.** Classic buses per domain, a Custom Event Bus as central, one bus-to-bus hop per event. Kinesis, Kafka, Step Functions outside the saga module, Temporal, a central gateway and a Schema Registry are each behind a named trigger.
- **Licensed LocalStack is a paid dependency of every domain repo.** Domain-local tests (L1) run on the licensed image with `ENFORCE_IAM=1`. The Community image works for a look around but cannot enforce IAM.
- **The central bus is not emulated locally.** LocalStack has nothing for the Custom Event Bus; domain-local tests use a Classic stub whose rules have the subscriber's shape. Hop limits, loop detection, DLQ records, IAM, replay and Firehose behaviour are proven only in a real AWS sandbox account, nightly and per branch (ADR-025). You need that account.
- **Cross-account delivery through the RAM-shared bus is not yet proven.** Spike D ran in one account; step 4 of the roadmap is where it gets proven.
- **EventCatalog core (MIT) is enough.** The generator emits the command and query pages itself so the Scale licence is not required. Analytics are batch, two to three hours behind, until a trigger says otherwise.
- **The generator is bespoke software your platform team owns.** Snapshot tests and two owners are the minimum.

## Adopting it

1. Fork or use as a template. Check the [LICENSE](LICENSE).
2. Replace the placeholders: organisation name, region, DNS suffix (`{domain}.api.example.com`), the schema `$id` base (`https://platform.example/...`), the example domains (`orders`, `payments`), account names and the IdP. `/arch:day-one-decisions-and-conventions` does this with you and will not invent organisational facts.
3. Prerequisites: Docker, `mise`, then `mise install && task doctor`. Optional for day one: a real AWS sandbox account, a LocalStack licence key in `LOCALSTACK_AUTH_TOKEN`.
4. Open a Claude Code session at the repo root and run the day-one prompts in order, in plan mode first: `/arch:day-one-decisions-and-conventions`, `/arch:day-one-bootstrap-catalog`, `/arch:day-one-module-library-and-toolchain`. Then `/arch:step-1-walking-skeleton` and on through the roadmap. Each prompt ends with a report-back that goes in the PR; reviewers run `/arch:architecture-review`.
5. When a request would need something the decisions table does not permit, run `/arch:evaluate-a-trigger`. "No trigger fired, do this instead" is the normal outcome.

Read [`docs/architecture/README.md`](docs/architecture/README.md) first: it is the index and the glossary.

## Layout

```
docs/architecture/        the pattern: decisions, ADRs, conventions, PII, data layer, contracts, testing, roadmap, trade-offs
docs/architecture/prompts the agent prompts; `task prompts` installs them as .claude/commands/arch/*
spikes/                   the evidence: four spikes with findings, the generator, checks, modules and harness as they were proven
```

The spikes are kept as they finished. Their findings are cited by ADR-021 to ADR-025; the reusable code in them (the generator, the checks, the Terraform modules, the harness) is what the day-one prompts start from. See [`spikes/README.md`](spikes/README.md) to run them again.
