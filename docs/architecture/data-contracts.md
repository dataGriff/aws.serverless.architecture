# Data contracts (ODCS)

The event schema is the producer's contract with consumers of the bus. The silver table built from it is a second product with different consumers — analysts, finance, other domains' read models — and it needs its own contract: columns and types as they are on disk, classification, freshness, retention, quality, ownership, terms. ODCS v3 is that contract. It is generated from the same catalog entry so it cannot drift from the event, stored beside the event version, rendered on a data-product page, and tested against the real files.

| Dataset | Contract | Source of the contract | Tested |
| --- | --- | --- | --- |
| Silver table per public event version (`silver/{source}/{detail-type}/`) | `events/<Event>/versioned/<v>/odcs.yaml` | Generated: schema from the event JSON Schema and the type mapping; `classification` from `x-pii`; owner, domain, tags from the catalog. Hand-written overlay `data-product.yaml`: SLAs, quality thresholds, terms of use, intended consumers. | L1 against local silver; nightly against the real bucket; CI diff against main |
| Bronze per domain (raw envelope) | `domains/<domain>/bronze.odcs.yaml` | Generated from the envelope convention; one per domain; classification "as published, direct fields ciphertext" | Nightly: envelope fields present, quarantine ratio, freshness ≤ Firehose buffer |
| Gold / derived datasets (later) | `data-products/<name>/odcs.yaml` | Hand-authored by the owning team; lineage back to the silver contracts it reads | Same nightly suite; cannot be consumed until the contract exists |

## Event entry → ODCS mapping

- `id` = `{domain}.{Event}.v{n}`; `version` follows the event version; `status` from `deprecated`/`sunset`
- `domain`, `dataProduct` (`{domain}-events-silver`), `team`/`roles` from the catalog owners and the generated reader roles
- `schema[].properties[]`: envelope columns + `d_*` columns; `logicalType`/`physicalType` from the JSON Schema type mapping; `classification` = `x-pii`; `direct` fields appear as "present only as ciphertext inside `detail`"
- `servers`: one per environment — `type: s3`, `location` from the env pin, `format: parquet`, plus the DuckDB view name; Athena added when that trigger fires
- `slaProperties`: freshness ≤ 3 h behind bus time; retention per PII class; availability; `frequency: hourly`
- `quality`: `event_id` unique; envelope not-null; partition completeness ≥ 99.9 %; reconciliation tolerance vs outbox; row count within expected band
- `authoritativeDefinitions`: links to the event page, the JSON Schema, and the ADRs

## In the catalog

- Each public event page links to its data-product page; the data-product page renders the ODCS, the latest test result badge, the consumers (`readsFrom`) and the freshness
- Consumers of a dataset register in the catalog exactly as event consumers do, so the dependency graph covers bus, API and data in one view, and the sunset check covers all three
- The overlay is the only hand-written part, reviewed by the owning domain through CODEOWNERS; changing the generated part means changing the event schema

## In the estate

- The compactor's Parquet schema and the DuckDB view DDL are derived from the contract, so what the contract promises is what the file is
- The nightly checks Lambda runs the contract's quality rules with DuckDB (or `datacontract test`) and publishes results to alarms and the catalog
- Reader-role grants and retention lifecycle come from the contract's roles and SLAs; a dataset with no contract has no grants, which is how "nothing consumed without a contract" is enforced rather than requested

## Example — generated contract for the `OrderPlaced.v1` silver table (illustrative)

```yaml
apiVersion: v3.0.2
kind: DataContract
id: orders.OrderPlaced.v1
name: orders · OrderPlaced v1 · silver
version: 1.2.0            # follows the event version; patch bumps for overlay-only changes
status: active            # from deprecated/sunset in the catalog
domain: orders
dataProduct: orders-events-silver
description:
  purpose: Analytical copy of every public OrderPlaced.v1 event, one row per eventId.
  limitations: direct PII fields are ciphertext inside `detail`; request a decryptor grant via the catalog.
  usage: Query the DuckDB view silver_orders_order_placed_v1; always filter on dt.
schema:
  - name: orders_order_placed_v1
    physicalType: parquet
    physicalName: silver/orders.order-service/OrderPlaced.v1/
    properties:
      - {name: event_id,          logicalType: string,    physicalType: string,             required: true, unique: true, primaryKey: true, classification: none}
      - {name: occurred_at,       logicalType: timestamp, physicalType: "timestamp[us,UTC]", required: true, classification: none}
      - {name: correlation_id,    logicalType: string,    physicalType: string,             classification: none}
      - {name: aggregate_id,      logicalType: string,    physicalType: string,             classification: indirect, tags: [customer-linked]}
      - {name: aggregate_version, logicalType: integer,   physicalType: int64,              classification: none}
      - {name: replay,            logicalType: boolean,   physicalType: bool,               classification: none}
      - {name: d_total,           logicalType: number,    physicalType: "decimal(18,4)",    classification: none}
      - {name: d_currency,        logicalType: string,    physicalType: string,             classification: none}
      - name: detail
        logicalType: object
        physicalType: string
        classification: direct
        description: Full payload as JSON. customerEmail is a ciphertext envelope; no d_ column exists for it.
    quality:
      - {type: library, rule: duplicateCount, column: event_id, mustBe: 0}
      - {type: sql, query: "SELECT count(*) FROM ${object} WHERE occurred_at IS NULL", mustBe: 0}
      - {type: custom, engine: platform-checks, implementation: "partitionCompleteness(min=0.999)"}
      - {type: custom, engine: platform-checks, implementation: "reconciliation(outbox=orders, tolerance=0.001)"}
servers:
  - {server: prod, type: s3, environment: prod, format: parquet,
     location: "s3://orders-events-silver/silver/orders.order-service/OrderPlaced.v1/"}
  - {server: test, type: s3, environment: test, format: parquet,
     location: "s3://orders-events-silver-nonprod/test/silver/orders.order-service/OrderPlaced.v1/"}
slaProperties:
  - {property: latency,   value: 3, unit: h, element: occurred_at}   # silver no more than 3 h behind
  - {property: frequency, value: 1, unit: h}
  - {property: retention, value: 2, unit: y}                          # per PII class; direct is ciphertext
team:
  - {username: orders-team, role: owner}
roles:
  - {role: orders-reader,    access: read}
  - {role: orders-decryptor, access: decrypt}   # may fetch subject keys for detail.customerEmail
authoritativeDefinitions:
  - {type: businessDefinition, url: "https://catalog.example.com/events/OrderPlaced/v1"}
  - {type: implementation,     url: "docs/architecture/adr/ADR-012-data-contracts.md"}
customProperties:
  - {property: catalogRelease, value: "2026.10.04"}
  - {property: xPiiMax,        value: direct}
  - {property: eventSchema,    value: "events/OrderPlaced/versioned/1/schema.json"}
```

Everything above `description` and every `properties` entry is generated; `description`, `slaProperties`, the `custom` quality rules' thresholds and `team` come from the hand-written `data-product.yaml` overlay.
