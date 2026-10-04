"""Tiny harness for Spike B: put events, watch SQS probes, count DLQs.

Queue URLs come from `terraform output -json queues` (cached in .queues.json by the Taskfile).
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

# Target selection: SPIKE_TARGET=local (default) talks to LocalStack with test creds;
# SPIKE_TARGET=sandbox uses the default boto3 credential chain (AWS_PROFILE) against real AWS.
TARGET = os.environ.get("SPIKE_TARGET", "local")
IS_LOCALSTACK = TARGET == "local"
ENDPOINT = os.environ.get("AWS_ENDPOINT_URL", "http://localhost:4566") if IS_LOCALSTACK else None
REGION = os.environ.get("AWS_DEFAULT_REGION", "eu-west-2")
_cfg = (dict(endpoint_url=ENDPOINT, region_name=REGION, aws_access_key_id="test", aws_secret_access_key="test")
        if IS_LOCALSTACK else dict(region_name=REGION))
events = boto3.client("events", **_cfg)
sqs = boto3.client("sqs", **_cfg)
s3 = boto3.client("s3", **_cfg)

TF_DIR = Path(__file__).resolve().parents[1] / "terraform" / "envs" / TARGET


def _tf_output(name: str) -> dict[str, str]:
    cache = Path(__file__).resolve().parents[1] / (f".{name}.json" if IS_LOCALSTACK else f".{name}.{TARGET}.json")
    if cache.exists():
        return json.loads(cache.read_text())
    out = subprocess.check_output(["terraform", "output", "-json", name], cwd=TF_DIR)
    q = json.loads(out)
    cache.write_text(json.dumps(q))
    return q


def queues() -> dict[str, str]:
    return _tf_output("queues")


def dlqs() -> dict[str, str]:
    """rule name -> DLQ url, for every bus-to-bus target plus the broken SQS target."""
    return _tf_output("dlqs")


def dlq_count(rule: str) -> int:
    """Approximate number of messages sitting on the DLQ of `rule` (messages are left in place)."""
    attrs = sqs.get_queue_attributes(QueueUrl=dlqs()[rule],
                                     AttributeNames=["ApproximateNumberOfMessages",
                                                     "ApproximateNumberOfMessagesNotVisible"])["Attributes"]
    return int(attrs["ApproximateNumberOfMessages"]) + int(attrs["ApproximateNumberOfMessagesNotVisible"])


def envelope(**extra) -> dict:
    return {"eventId": str(uuid.uuid4()), "occurredAt": datetime.now(timezone.utc).isoformat(),
            "correlationId": str(uuid.uuid4()), "causationId": None,
            "aggregateId": "agg-1", "aggregateVersion": 1, **extra}


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
            body = json.loads(m["Body"])
            found.append(body)
            sqs.delete_message(QueueUrl=queue_url, ReceiptHandle=m["ReceiptHandle"])
        if not msgs and found:
            # settle: one more empty poll after we've seen something
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


# ---- archive (stretch): S3 written by the central archiver Lambda, read with DuckDB ------------

def archive_bucket() -> str:
    out = subprocess.check_output(["terraform", "output", "-raw", "archive_bucket"], cwd=TF_DIR)
    return out.decode().strip()


def _archive_prefix(source: str | None, detail_type: str | None) -> str:
    """The archiver's key is deterministic, so scan only the partition the event belongs to."""
    if source and detail_type:
        return f"raw/source={source}/detail_type={detail_type}/"
    return "raw/"


def archived(event_id: str, timeout: float = 20.0, *, source: str | None = None, detail_type: str | None = None) -> dict:
    """Wait for the archiver to land the event in S3; return the object as a dict. Keys already read are not re-fetched."""
    bucket, prefix, deadline, seen = archive_bucket(), _archive_prefix(source, detail_type), time.time() + timeout, set()
    while time.time() < deadline:
        for page in s3.get_paginator("list_objects_v2").paginate(Bucket=bucket, Prefix=prefix):
            for obj in page.get("Contents", []):
                if obj["Key"] in seen:
                    continue
                seen.add(obj["Key"])
                body = json.loads(s3.get_object(Bucket=bucket, Key=obj["Key"])["Body"].read())
                if body.get("detail", {}).get("eventId") == event_id:
                    body["_key"] = obj["Key"]
                    return body
        time.sleep(1)
    raise AssertionError(f"eventId {event_id} was not archived to s3://{bucket}/{prefix} within {timeout}s")


def archived_ids(*, source: str | None = None, detail_type: str | None = None) -> set[str]:
    bucket, ids = archive_bucket(), set()
    for page in s3.get_paginator("list_objects_v2").paginate(Bucket=bucket, Prefix=_archive_prefix(source, detail_type)):
        for obj in page.get("Contents", []):
            body = json.loads(s3.get_object(Bucket=bucket, Key=obj["Key"])["Body"].read())
            ids.add(body.get("detail", {}).get("eventId"))
    return ids


def duck_s3():
    """DuckDB connection able to read LocalStack's S3 (httpfs, path-style, test creds, no views)."""
    import duckdb
    assert IS_LOCALSTACK, "DuckDB-over-S3 helpers are wired for LocalStack only; the sandbox env has no archiver"
    host = ENDPOINT.split("://", 1)[1]
    con = duckdb.connect()
    con.execute("INSTALL httpfs; LOAD httpfs;")
    con.execute(f"SET s3_endpoint='{host}'; SET s3_use_ssl=false; SET s3_url_style='path'; "
                f"SET s3_region='{REGION}'; SET s3_access_key_id='test'; SET s3_secret_access_key='test';")
    return con


def duck():
    """duck_s3() plus the `archive` view over the central archiver's bucket."""
    con = duck_s3()
    con.execute(f"CREATE VIEW archive AS SELECT * FROM read_json_auto('s3://{archive_bucket()}/raw/**/*.json', "
                "hive_partitioning=true, union_by_name=true)")
    return con
