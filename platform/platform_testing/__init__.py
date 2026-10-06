"""platform_testing — the LocalStack test harness every domain repo imports (seeded from Spike B, grown in step 3).

Put events, watch SQS probes and subscriber queues, read the bronze buckets, open DuckDB over them.
Queue URLs, DLQs and buckets come from `terraform output -json` (cached as .<name>.json by the Taskfile).
Valid payloads come from the catalog's own examples, so a test event is exactly what the generator validated.

Three locations, from the environment (a domain repo's Taskfile sets them; Spike B's tests/harness.py shim does too):
    PLATFORM_TF_DIR     the Terraform env that applied the buses        (default: terraform/envs/local under the cwd)
    PLATFORM_CATALOG    the catalog checkout whose examples are valid   (default: catalog under the cwd)
    PLATFORM_STATE_DIR  where the terraform-output caches are written   (default: the cwd)
"""
from __future__ import annotations

import json
import os
import subprocess
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path

import boto3

ENDPOINT = os.environ.get("AWS_ENDPOINT_URL", "http://localhost:4566")
REGION = os.environ.get("AWS_DEFAULT_REGION", "eu-west-1")
IS_LOCALSTACK = True
_cfg = dict(endpoint_url=ENDPOINT, region_name=REGION, aws_access_key_id="test", aws_secret_access_key="test")
events = boto3.client("events", **_cfg)
sqs = boto3.client("sqs", **_cfg)
s3 = boto3.client("s3", **_cfg)

ROOT = Path(os.environ.get("PLATFORM_STATE_DIR", ".")).resolve()
TF_DIR = Path(os.environ.get("PLATFORM_TF_DIR", "terraform/envs/local")).resolve()
CATALOG = Path(os.environ.get("PLATFORM_CATALOG", "catalog")).resolve()


def _tf_output(name: str):
    cache = ROOT / f".{name}.json"
    if cache.exists():
        return json.loads(cache.read_text())
    out = subprocess.check_output(["terraform", "output", "-json", name], cwd=TF_DIR)
    q = json.loads(out)
    cache.write_text(json.dumps(q))
    return q


def queues() -> dict[str, str]:
    """probe queues (`orders_probe`, `central_probe`...), subscriber queues (`subscriber:payments-order-placed`),
    same-domain consumer queues (`consumer:orders-consumer-...`) and the broken target's DLQ."""
    return _tf_output("queues")


def dlqs() -> dict[str, str]:
    """rule name -> DLQ url, for every forward rule, subscriber, consumer rule, the archiver and the broken target."""
    return _tf_output("dlqs")


def archive_buckets() -> dict[str, str]:
    """source prefix -> bronze bucket (from the generated routing map), plus '' -> the fallback bucket."""
    return _tf_output("archive_buckets")


def generated_dir() -> Path:
    return Path(_tf_output("generated_dir"))


def dlq_count(rule: str) -> int:
    """Approximate number of messages sitting on the DLQ of `rule` (messages are left in place)."""
    attrs = sqs.get_queue_attributes(QueueUrl=dlqs()[rule],
                                     AttributeNames=["ApproximateNumberOfMessages",
                                                     "ApproximateNumberOfMessagesNotVisible"])["Attributes"]
    return int(attrs["ApproximateNumberOfMessages"]) + int(attrs["ApproximateNumberOfMessagesNotVisible"])


def envelope(**extra) -> dict:
    """A minimal envelope for tests that do not care about the payload schema (internal events, probes)."""
    return {"eventId": str(uuid.uuid4()), "occurredAt": datetime.now(timezone.utc).isoformat(), "replay": False,
            "correlationId": str(uuid.uuid4()), "aggregateId": "agg-1", "aggregateVersion": 1, **extra}


def example(event: str, name: str | None = None) -> dict:
    """The catalog's example for `event` (events/<event>/examples/*.json), with a fresh eventId: a payload the
    generated validation bundle accepts, so a test only has to break one thing at a time."""
    folder = CATALOG / "events" / event / "examples"
    path = folder / f"{name}.json" if name else sorted(folder.glob("*.json"))[0]
    detail = json.loads(path.read_text())["detail"]
    detail["eventId"] = str(uuid.uuid4())
    return detail


def put(bus: str, source: str, detail_type: str, detail: dict) -> dict:
    resp = events.put_events(Entries=[{"EventBusName": bus, "Source": source,
                                       "DetailType": detail_type, "Detail": json.dumps(detail)}])
    assert resp["FailedEntryCount"] == 0, resp
    return detail


def drain(queue_url: str, seconds: float = 10.0) -> list[dict]:
    """Return every EventBridge event delivered to the queue within `seconds` (messages are deleted)."""
    found, deadline = [], time.time() + seconds
    while time.time() < deadline:
        r = sqs.receive_message(QueueUrl=queue_url, MaxNumberOfMessages=10, WaitTimeSeconds=1)
        msgs = r.get("Messages", [])
        for m in msgs:
            found.append(json.loads(m["Body"]))
            sqs.delete_message(QueueUrl=queue_url, ReceiptHandle=m["ReceiptHandle"])
        if not msgs and found:
            r2 = sqs.receive_message(QueueUrl=queue_url, MaxNumberOfMessages=10, WaitTimeSeconds=2)
            if not r2.get("Messages"):
                break
            for m in r2["Messages"]:
                found.append(json.loads(m["Body"]))
                sqs.delete_message(QueueUrl=queue_url, ReceiptHandle=m["ReceiptHandle"])
    return found


def expect(queue_url: str, event_id: str, timeout: float = 15.0) -> dict:
    deadline = time.time() + timeout
    while time.time() < deadline:
        for e in drain(queue_url, seconds=2):
            if e.get("detail", {}).get("eventId") == event_id:
                return e
    raise AssertionError(f"eventId {event_id} did not arrive on {queue_url.rsplit('/', 1)[-1]} within {timeout}s")


def expect_none(queue_url: str, event_id: str, settle: float = 8.0) -> None:
    hits = [e for e in drain(queue_url, seconds=settle) if e.get("detail", {}).get("eventId") == event_id]
    assert not hits, f"eventId {event_id} unexpectedly arrived on {queue_url.rsplit('/', 1)[-1]}"


def count_deliveries(queue_url: str, event_id: str, settle: float = 10.0) -> int:
    return sum(1 for e in drain(queue_url, seconds=settle) if e.get("detail", {}).get("eventId") == event_id)


def purge_all() -> None:
    for url in {**queues(), **dlqs()}.values():
        try:
            sqs.purge_queue(QueueUrl=url)
        except Exception:
            pass


def rules_on(bus: str) -> dict[str, dict]:
    """name -> parsed event pattern for every rule on `bus`."""
    out = {}
    for page in events.get_paginator("list_rules").paginate(EventBusName=bus):
        for r in page["Rules"]:
            out[r["Name"]] = json.loads(r["EventPattern"]) if r.get("EventPattern") else None
    return out


# ---- bronze: written by the archive shim on central, read back directly or with DuckDB ------------

def bucket_for(source: str) -> str:
    buckets = archive_buckets()
    for prefix in sorted((p for p in buckets if p), key=len, reverse=True):
        if source.startswith(prefix):
            return buckets[prefix]
    return buckets[""]


def _partition(source: str, detail_type: str) -> str:
    return f"source={source}/detail_type={detail_type}/"


def _find(bucket: str, prefix: str, event_id: str, timeout: float) -> dict | None:
    deadline, seen = time.time() + timeout, set()
    while time.time() < deadline:
        for page in s3.get_paginator("list_objects_v2").paginate(Bucket=bucket, Prefix=prefix):
            for obj in page.get("Contents", []):
                if obj["Key"] in seen:
                    continue
                seen.add(obj["Key"])
                got = s3.get_object(Bucket=bucket, Key=obj["Key"])
                body = json.loads(got["Body"].read())
                if body.get("detail", {}).get("eventId") == event_id:
                    body["_key"], body["_bucket"], body["_metadata"] = obj["Key"], bucket, got.get("Metadata", {})
                    return body
        time.sleep(1)
    return None


def archived(event_id: str, *, source: str, detail_type: str, timeout: float = 20.0) -> dict:
    """Wait for the shim to land the event under raw/ in the domain's bronze bucket; return it with _key/_bucket."""
    bucket = bucket_for(source)
    body = _find(bucket, "raw/" + _partition(source, detail_type), event_id, timeout)
    assert body, f"eventId {event_id} was not archived to s3://{bucket}/raw/{_partition(source, detail_type)} within {timeout}s"
    return body


def quarantined(event_id: str, *, source: str, detail_type: str, reason: str, timeout: float = 20.0) -> dict:
    """Wait for the shim to quarantine the event under processing-failed/reason=<reason>/ and return it."""
    bucket = bucket_for(source)
    prefix = f"processing-failed/reason={reason}/" + _partition(source, detail_type)
    body = _find(bucket, prefix, event_id, timeout)
    assert body, f"eventId {event_id} was not quarantined to s3://{bucket}/{prefix} within {timeout}s"
    return body


def bronze_ids(*, source: str, detail_type: str) -> set[str]:
    """Every eventId under raw/ or processing-failed/ for this partition, in the bucket the routing map points at."""
    bucket, ids = bucket_for(source), set()
    for page in s3.get_paginator("list_objects_v2").paginate(Bucket=bucket):
        for obj in page.get("Contents", []):
            if _partition(source, detail_type) in obj["Key"]:
                body = json.loads(s3.get_object(Bucket=bucket, Key=obj["Key"])["Body"].read())
                ids.add(body.get("detail", {}).get("eventId"))
    return ids


def duck_s3():
    """DuckDB connection able to read LocalStack's S3 (httpfs, path-style, test creds, no views)."""
    import duckdb
    host = ENDPOINT.split("://", 1)[1]
    con = duckdb.connect()
    con.execute("INSTALL httpfs; LOAD httpfs;")
    con.execute(f"SET s3_endpoint='{host}'; SET s3_use_ssl=false; SET s3_url_style='path'; "
                f"SET s3_region='{REGION}'; SET s3_access_key_id='test'; SET s3_secret_access_key='test';")
    return con


def _globs(prefix: str) -> list[str]:
    """s3 globs for every bronze bucket that has at least one object under `prefix` (DuckDB errors on an empty glob)."""
    out = []
    for b in sorted(set(archive_buckets().values())):
        if s3.list_objects_v2(Bucket=b, Prefix=prefix, MaxKeys=1).get("KeyCount"):
            out.append(f"'s3://{b}/{prefix}**/*.json'")
    return out


def duck():
    """duck_s3() plus two views over every bronze bucket: `archive` (raw/) and `quarantine` (processing-failed/,
    with a `reason` column from the Hive prefix), and `bronze` = both with a `status` column."""
    con = duck_s3()
    empty = "SELECT NULL::VARCHAR AS reason, NULL::VARCHAR AS source, NULL::VARCHAR AS detail_type, NULL::VARCHAR AS id, NULL::TIMESTAMP AS time, NULL::JSON AS detail WHERE false"
    for view, prefix in (("archive", "raw/"), ("quarantine", "processing-failed/")):
        globs = _globs(prefix)
        body = f"SELECT * FROM read_json_auto([{', '.join(globs)}], hive_partitioning=true, union_by_name=true)" if globs else empty
        con.execute(f"CREATE VIEW {view} AS {body}")
    con.execute("CREATE VIEW bronze AS SELECT 'raw' AS status, NULL AS reason, source, detail_type, id, time FROM archive "
                "UNION ALL SELECT 'processing-failed', reason, source, detail_type, id, time FROM quarantine")
    return con
