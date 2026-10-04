# Spike A — EventCatalog as the source of truth (no AWS)

Prompt: `docs/architecture/prompts/spikes/A-catalog-source-of-truth.md` (or `/arch:spike-a-catalog-source-of-truth`).
Result and findings: [`findings.md`](findings.md).
Live site: https://datagriff.github.io/aws.serverless.architecture/ (published by `.github/workflows/pages.yml` at the repo root; the MIT core's static build needs no licence key).

```sh
task catalog:install     # npm ci inside catalog/ (Node 22 via this directory's .mise.toml)
task all                 # gen → gen:check → checks → spectral → odcs:lint → test → catalog:build:clean
task catalog:dev         # look at the site on http://localhost:3000
```

## Layout

| Path | What |
| --- | --- |
| `catalog/` | EventCatalog 4.12.3 site. Hand-written: domains, services (+ `openapi.yaml`), events (`index.mdx`, `schema.json`, `examples/`, `data-product.yaml`), commands, queries, channels, teams, data products, `schemas/`, `CODEOWNERS`. Generated and committed: `events/*/odcs.yaml`. |
| `catalog-gen/catalog_gen.py` | `build` / `check` / `explain`. Deterministic; writes `generated/local/` (gitignored) and the ODCS beside each public event. |
| `checks/` | `run_checks.py` (ten checks), `x-pii.metaschema.json`, `schema_diff.py`, `spectral.yaml`. |
| `tests/` | 28 behavioural tests; `tests/golden/` is the committed snapshot of the generator output (`task test:update-golden` to accept a change). |
| `fixtures/checks/<check>/` | Files overlaid on a copy of the catalog so that exactly that check fails. `fixtures/schema-diff`, `fixtures/spectral`, `fixtures/odcs` serve the standalone linters. |
| `.github/workflows/catalog-pr.yml` | The PR pipeline, calling the same Taskfile tasks. Not under the repo root on purpose: it is a specimen, unexecuted. |

## Conventions the spike settled on

- Platform fields in frontmatter are `x-` prefixed (`x-visibility`, `x-audience`, `x-source`); EventCatalog rejects unknown top-level keys at build time.
- Channels are declared on the services (`sends[].to`, `receives[].from`) and the bus chain on the channels: a service publishes only to its own domain bus, each domain bus `routes` to `central-bus`, `central-bus` lists its fan-out targets under `x-fan-out-to` (not `routes`: EventCatalog 4.12.3 overflows on the hub cycle), and a consumer receives from its own bus. `check_channel_topology` enforces it. The build rewrites message-level `channels:` in place, so `task catalog:build:clean` fails on a dirty tree.
- `x-pii` lives on every property in JSON Schema, including shared `schemas/`. Direct fields of public events are the ciphertext envelope on the wire; the generator rewrites the validation schema accordingly.
- Event payload schemas describe the business fields only; the generator flattens `schemas/Envelope.json` into them for validation.
