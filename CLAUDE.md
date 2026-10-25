# Spikes repo — read this first

Four spikes (A, B, C, D), run from `docs/architecture/prompts/spikes/` (also `/arch:spike-a-*`, `/arch:spike-b-*`, `/arch:spike-c-*`).

- Spike A lives in `spikes/A-catalog-source-of-truth/` and must not touch AWS, LocalStack or Terraform.
- Spike B lives in `spikes/B-localstack-buses-end-to-end/`. While Spike B ran it read no catalog or generator output; since Spike C (PR #4) its Terraform, Taskfile and harness read `spikes/A-catalog-source-of-truth/generated/local` and the catalog's examples on purpose — that is the join.
- Spike C (`spikes/C-join/`) joined them after both `findings.md` said green; its scenario tests re-apply Spike B's env and own the plan snapshots.
- Spike D lives in `spikes/D-custom-event-bus/` and runs against a real AWS account in eu-west-1 (no LocalStack); it exists because Spike B proved Classic buses deliver one bus-to-bus hop only.

All four spikes are done and have a `findings.md`; test names are the contract, so change behaviour rather than renaming tests.
Vocabulary and the decisions the spikes are testing: `docs/architecture/README.md` and `docs/architecture/decisions.md`.
Do not add AWS services or widen scope; a spike that ends with "blocked, here is why" is a valid result.

Routes:
- Before proposing or changing infrastructure, routing, data or API design, read `docs/architecture/decisions.md`; to challenge one decision, read its `docs/architecture/adr/ADR-*.md`.
- Before touching a spike, read its `findings.md` (`spikes/<X>-*/findings.md`) and `README.md`.
- Before writing an event, API operation or catalog entry, read `docs/architecture/conventions.md`; for personal data, `docs/architecture/pii.md`.
- Before changing the generator or CI, read `docs/architecture/generation-and-ci.md`; before writing tests, `docs/architecture/testing.md`.
- Before editing `docs/architecture/prompts/*.md`, read `docs/architecture/prompts/README.md`, then run `task prompts` (the `.claude/commands/arch/` copies are generated).
- To explain the architecture to someone new, open `docs/architecture/overview.html`.
- Setup and env vars: `README.md` and `.env.example`.
