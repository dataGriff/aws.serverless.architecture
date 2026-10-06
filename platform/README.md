# platform — the reusable tooling

What a platform team owns and every catalog and domain repo consumes. Written inside the spikes, moved here once the spikes proved it (#10), with its tests (#23): `task platform:test` runs the generator's and the checks' suite against `fixtures/catalog-two-domains`, a content snapshot of the worked-example catalog in `spikes/A-…` that `task platform:fixture:check` keeps identical. The LocalStack suites in Spikes B and C still run against the modules and the harness.

| Path | What | Proven by |
| --- | --- | --- |
| `catalog-gen/catalog_gen.py` | The generator: `build` / `check` / `explain`. Reads an EventCatalog folder, writes deterministic JSON/YAML under `--out` (forward rules split at 4 KB, one subscriber per cross-domain `receives[]`, consumer rules, archive routing map, validation bundles with `direct` fields as ciphertext envelopes, Parquet schemas, deploy order) and, into the catalog itself, the ODCS contract beside each public event and the per-event logical channel pages. | `catalog-gen/tests/` (38 tests, golden snapshot) against `fixtures/catalog-two-domains`, and `spikes/C-join/` (plan snapshots per catalog edit) |
| `checks/run_checks.py` | The ten catalog checks, each failing with the convention it enforces: `x-pii` on every field, `direct` on public needs encryption and decryptors, `receives[]` targets public or same-domain, source namespace, channel topology, `$ref`s into `schemas/` with `x-kind`, every OpenAPI operation has its command/query page, sync-hop depth, examples match the generated schema, schema diff against a base. `--base <catalog>` enables the diff; `--only <check>` runs one. | `catalog-gen/tests/fixtures/checks/<check>/`: one fixture per check that fails exactly that check |
| `checks/spectral.yaml` | The API conventions from `conventions.md` as Spectral rules: `/v{n}`, commands are POST with `Idempotency-Key`, queries are GET, `problem+json`, `X-Correlation-Id`, security scheme, `x-eventcatalog-message-type`, `x-pii` on body fields (`resolved: false`). | `catalog-gen/tests/fixtures/spectral/openapi-bad.yaml` |
| `checks/x-pii.metaschema.json` | Meta-schema that rejects any property without `x-pii` and forbids `special`; recursive through `$defs/property`. | `catalog-gen/tests/fixtures/checks/check_x_pii/` |
| `checks/schema_diff.py` | Breaking-change detector for event payload schemas (removed property, type or format change, newly required, narrowed enum, tightened `additionalProperties`). Day one should evaluate `json-schema-diff` rather than grow this. | `catalog-gen/tests/fixtures/schema-diff/` |
| `terraform/modules/` | `event-bus` (Classic, with its policy), `bus-forward-rule` (domain bus → central, role, DLQ), `bus-sqs-rule` (a subscriber-shaped rule: pattern, retry policy, DLQ, SQS target; the `platform-local` rendering of a subscriber), `bus-s3-archiver` (the archive shim: Lambda running `src/validate.py` with the generated bundles and routing map, `raw/` and `processing-failed/reason=…/`), `bus-firehose-archive` (the AWS-shaped Firehose stream with the same validator as its transform; LocalStack ignores most of it, ADR-024). | `spikes/B-localstack-buses-end-to-end/` (19 tests on LocalStack) |
| `platform_testing/` | The LocalStack harness domain tests import: `put`, `expect`, `expect_none`, `count_deliveries`, `dlq_count`, `rules_on`, `archived`, `quarantined`, `bronze_ids`, `duck()`, `example()` (a valid payload straight from the catalog). Configured by `PLATFORM_TF_DIR`, `PLATFORM_CATALOG`, `PLATFORM_STATE_DIR`. Step 3 (prompt 07) grows it into the published package (`assert_published`, `prism()`, `replay()`, `erase_subject()`, fixtures). | Spike B's and Spike C's suites import it through `spikes/B-…/tests/harness.py` |

## Using it from another repo

Pin it. A catalog repo or a domain repo references this directory by a tag (git submodule, a vendored copy, or a checkout the Taskfile's `PLATFORM` variable points at); `templates/catalog-repo/Taskfile.yml` and `templates/domain-repo/Taskfile.yml` show the variable. ADR-017: the generator is semver-pinned per account; a bump is a PR.

```sh
uv run platform/catalog-gen/catalog_gen.py build   --catalog <catalog> --out generated/<env>
uv run platform/catalog-gen/catalog_gen.py check   --catalog <catalog> --out generated/<env>
uv run platform/catalog-gen/catalog_gen.py explain --catalog <catalog> --out generated/<env> subscribers/<domain>-<event>.json
uv run platform/checks/run_checks.py --catalog <catalog> [--base <catalog on main>] [--only check_name]
npx -y @stoplight/spectral-cli lint -r platform/checks/spectral.yaml '<catalog>/services/**/openapi.y*ml'
```

## What is not here yet

The roadmap builds the rest in order: `custom-event-bus` and `subscriber` modules on `awscc` (Spike D has the proven resource shapes in `spikes/D-custom-event-bus/terraform/main.tf`), `compactor`, `domain-buckets`, `rest-api`, `outbox-relay`, `idempotency-store`, `saga`, `subject-keys`, `alarms`, `platform-local` (prompt 02); the emitters for API bodies, clients, alarms, roles and the ROPA (prompt 04); the reusable CI workflows (prompt 05). Each lands here, with its proof.
