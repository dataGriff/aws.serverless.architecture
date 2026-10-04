# Data layer formats

What is on disk in bronze and silver, exactly. The compactor, the DuckDB views and the ODCS contracts are all derived from the same catalog entry, so this file describes the output, not a separate design.

## Bronze

- **Format:** newline-delimited JSON, GZIP, written by Firehose; one EventBridge envelope per line exactly as delivered (`id`, `source`, `detail-type`, `time`, `account`, `detail`…)
- **Layout:** `{source}/{detail-type}/{yyyy}/{mm}/{dd}/{hh}/<stream-file>.json.gz` from dynamic partitioning; failures under `processing-failed/` with the error reason
- **Protection:** SSE-KMS with the domain CMK, Object Lock, versioning, cross-region replication in prod; `direct` fields are ciphertext as published
- **Readers:** DuckDB `read_ndjson_auto`, the compactor, the nightly checks, replay tooling. Never mutated.

## Silver

- **Format:** Apache Parquet, zstd, written by the compactor with PyArrow. Not Iceberg, not Delta — a table format is the PyIceberg trigger, and the files are laid out so that adding one is a metadata change
- **Layout:** `silver/{source}/{detail-type}/dt=YYYY-MM-DD/hour=HH/part-0.parquet`; Hive-style partitions on bus time; one file per (type, hour), overwritten atomically on re-compaction; the version in `detail-type` gives each directory one schema lineage
- **Columns:** fixed envelope — `id`, `source`, `detail_type`, `bus_time`, `event_id`, `occurred_at`, `correlation_id`, `causation_id`, `aggregate_id`, `aggregate_version`, `replay`, `pii_class` (highest class present) — then `detail` as the full JSON string, then typed `d_<field>` columns for every catalog field classed `none` or `indirect`
- **Types from JSON Schema:** string → string; integer → int64; number → double; `format: decimal` / money → decimal128(18,4); `format: date` → date32; `format: date-time` → timestamp[µs, UTC]; object → struct; array → list; anything open-ended stays inside `detail`
- **File metadata:** catalog release tag, event schema version, compactor version, window — written into the Parquet key-value metadata for lineage
- **Readers:** DuckDB views with `hive_partitioning`, `union_by_name` and the read-time dedupe; an Athena external table or PyIceberg later, same files
