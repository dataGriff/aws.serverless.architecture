# Spike A — EventCatalog as the source of truth (no AWS)

Prompt: `docs/architecture/prompts/spikes/A-catalog-source-of-truth.md` (or `/arch:spike-a-catalog-source-of-truth`).
Result and findings: [`findings.md`](findings.md).
Live site: https://datagriff.github.io/aws.serverless.architecture/ (published by `.github/workflows/pages.yml` at the repo root; the MIT core's static build needs no licence key).

```sh
task catalog:install     # npm ci inside catalog/ (Node 22 via this directory's .mise.toml)
task all                 # gen → gen:check → checks → spectral → odcs:lint → catalog:build:clean  (tests: task platform:test at the root)
task catalog:dev         # look at the site on http://localhost:3000
```

## Layout

| Path | What |
| --- | --- |
| `catalog/` | EventCatalog 4.12.3 site. Hand-written: domains, services (+ `openapi.yaml`), events (`index.mdx`, `schema.json`, `examples/`, `data-product.yaml`), commands, queries, the `orders-api` channel, teams, data products, `schemas/`, `CODEOWNERS`. Generated and committed: `events/*/odcs.yaml` and the logical channel pages `channels/{bus}.{DetailType}/`, `channels/central-bus.{DetailType}/`, `channels/{domain}-sub.{DetailType}/`. |
| `../../platform/catalog-gen/catalog_gen.py` | `build` / `check` / `explain`. Deterministic; writes `generated/local/` (rules, subscribers, routing map, validation bundles, Parquet schemas, manifest; gitignored) plus the ODCS and channel pages inside the catalog. Written here, moved to `platform/` once proven; the Taskfile points at it. |
| `../../platform/checks/` | `run_checks.py` (ten checks), `x-pii.metaschema.json`, `schema_diff.py`, `spectral.yaml`. Moved with the generator. |
| `../../platform/catalog-gen/tests/` | The generator's and the checks' behavioural tests, golden snapshot and per-check fixtures, moved with the tooling; they run against `platform/fixtures/catalog-two-domains`, a content snapshot of this catalog that `task platform:fixture:check` keeps identical. |
| (CI) | The same Taskfile tasks run on every pull request from the root `.github/workflows/ci.yml` (job `platform`). The specimen `catalog-pr.yml` that used to sit here became `templates/catalog-repo/.github/workflows/catalog-pr.yml`, live once that template is lifted into its own repository. |

## Conventions the spike settled on

- Platform fields in frontmatter are `x-` prefixed (`x-visibility`, `x-audience`, `x-source`); EventCatalog rejects unknown top-level keys at build time.
- Channels are **logical, one per event per physical bus, and generated** (ADR-021 topology): `orders-bus.OrderPlaced.v1` → `central-bus.OrderPlaced.v1` → `payments-sub.OrderPlaced.v1` → payment-service. Services reference them in `sends[].to` / `receives[].from`; `catalog-gen` emits the channel pages (`x-generated: catalog-gen`) and the matching `subscribers/*.json`. There are no standalone bus pages: the physical bus is named by `x-bus` on the domain and `x-physical-channel` on every logical channel. The only hand-written channel is `orders-api`. `check_channel_topology` enforces the shape; the build rewrites message-level `channels:` in place, so `task catalog:build:clean` fails on a dirty tree.
- `x-pii` lives on every property in JSON Schema, including shared `schemas/`. Direct fields of public events are the ciphertext envelope on the wire; the generator rewrites the validation schema accordingly.
- Event payload schemas describe the business fields only; the generator flattens `schemas/Envelope.json` into them for validation.
