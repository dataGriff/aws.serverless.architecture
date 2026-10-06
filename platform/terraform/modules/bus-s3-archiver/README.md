# bus-s3-archiver

ADR-024's **local shim** for the Firehose archive: a Lambda on a bus that validates every matching event against the catalog-generated validation bundle, routes it to the domain's bronze bucket by the generated routing map, and quarantines failures under `processing-failed/reason=<schema|pii-in-clear|unknown-event>/`. `src/validate.py` is the validation function the Firehose transform calls on AWS; the bundles and the routing map are packaged into the zip because an environment variable has a 4 KB ceiling the routing map outgrows, so a catalog change is a code change here (`source_code_hash`).

| Input | Type | Default | Meaning |
| --- | --- | --- | --- |
| `name` | string | required | |
| `bus_name` | string | required | The bus the archive listens on (the stub central locally; on AWS a Firehose subscriber on central) |
| `event_pattern` | any | required | Usually everything (`source` prefix `""`) |
| `routing_map` | map(object) | required | `generated/archive/routing-map.json`: source prefix → `{ bucket, detailTypes }` |
| `fallback_bucket` | string | required | Where events whose source matches no prefix are quarantined (`unknown-event`) |
| `validation_files` | list(string) | required | `generated/validation/*.json`, packaged as `validation/<domain>.json` |
| `tags` | map(string) | `{}` | |

| Output | |
| --- | --- |
| `buckets` | bucket per routing-map prefix plus the fallback |
| `dlq_url`, `function_name` | |

Needs `fastjsonschema` vendored under `.build/deps` before apply (`task deps` in Spike B does it; gitignored). Layout written: `raw/source=<source>/detail_type=<dt>/<id>.json` and `processing-failed/reason=<r>/source=…/detail_type=…/<id>.json`, the Hive layout `platform_testing.duck()` reads.

LocalStack: fully functional; this module exists because **Firehose dynamic partitioning, `ProcessingConfiguration` and `ErrorOutputPrefix` are ignored by LocalStack on both editions** (Spike B's Firehose probe). Retire it when the trigger in ADR-024 fires.
