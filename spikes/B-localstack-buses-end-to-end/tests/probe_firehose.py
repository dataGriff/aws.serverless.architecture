"""Firehose probe — not pytest, prints a table for findings.md. Run: task probe-firehose

Puts one valid public event and one with a `direct` PII field in clear on central-bus, then watches the
bronze bucket for up to 150 s and reports which ADR-009 mechanisms LocalStack honoured.
"""
from __future__ import annotations

import json
import subprocess
import time

from harness import ENDPOINT, TF_DIR, envelope, put, s3


def bucket() -> str:
    return subprocess.check_output(["terraform", "output", "-raw", "firehose_bucket"], cwd=TF_DIR).decode().strip()


def objects(b: str) -> list[dict]:
    out = []
    for page in s3.get_paginator("list_objects_v2").paginate(Bucket=b):
        out.extend(page.get("Contents", []))
    return out


def main() -> None:
    b = bucket()
    for o in objects(b):
        s3.delete_object(Bucket=b, Key=o["Key"])
    good = put("central-bus", "orders.order-service", "OrderPlaced.v1", envelope(total=9.0, customerEmail="enc:AQIDBA=="))
    bad = put("central-bus", "orders.order-service", "OrderPlaced.v1", envelope(total=9.5, customerEmail="alice@example.com"))
    t0 = time.time()
    seen: list[dict] = []
    while time.time() - t0 < 150:
        seen = objects(b)
        if len(seen) >= 2:
            break
        time.sleep(3)
    latency = time.time() - t0

    rows: list[tuple[str, str]] = [("objects written within 150 s", f"{len(seen)} (first seen after ~{latency:.0f} s)")]
    keys = [o["Key"] for o in seen]
    bodies = {k: s3.get_object(Bucket=b, Key=k)["Body"].read().decode() for k in keys}
    good_key = next((k for k, v in bodies.items() if good["eventId"] in v), None)
    bad_key = next((k for k, v in bodies.items() if bad["eventId"] in v), None)

    rows.append(("valid event delivered to S3", good_key or "NOT DELIVERED"))
    if good_key:
        rows.append(("validation Lambda ran (body is the Lambda's NDJSON line)",
                     "yes" if bodies[good_key].endswith("\n") and json.loads(bodies[good_key].splitlines()[0])["detail"]["eventId"] == good["eventId"] else "NO: " + bodies[good_key][:80]))
        rows.append(("dynamic partitioning: prefix evaluated from Lambda partition keys",
                     "yes" if good_key.startswith("bronze/source=orders.order-service/detail_type=OrderPlaced.v1/") else f"NO: key is {good_key}"))
    rows.append(("invalid event (direct PII in clear) quarantined under processing-failed/",
                 bad_key if bad_key and bad_key.startswith("processing-failed/") else f"NO: {bad_key or 'not written anywhere'}"))
    if good_key and good_key.startswith("bronze/"):
        import duckdb
        con = duckdb.connect()
        con.execute("INSTALL httpfs; LOAD httpfs;")
        host = ENDPOINT.split("://", 1)[1]
        con.execute(f"SET s3_endpoint='{host}'; SET s3_use_ssl=false; SET s3_url_style='path'; SET s3_region='eu-west-2'; "
                    "SET s3_access_key_id='test'; SET s3_secret_access_key='test';")
        n = con.execute(f"SELECT source, detail_type, count(*) FROM read_ndjson_auto('s3://{b}/bronze/**/*', hive_partitioning=true) GROUP BY ALL").fetchall()
        rows.append(("DuckDB read_ndjson_auto over bronze/ with hive partitions", str(n)))
    print("| Firehose on LocalStack | Result |\n| --- | --- |")
    for k, v in rows:
        print(f"| {k} | {v} |")
    print("\nkeys:", *keys, sep="\n  ")


if __name__ == "__main__":
    main()
