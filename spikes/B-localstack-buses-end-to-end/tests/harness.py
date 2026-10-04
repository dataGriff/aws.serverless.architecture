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

ENDPOINT = os.environ.get("AWS_ENDPOINT_URL", "http://localhost:4566")
_cfg = dict(endpoint_url=ENDPOINT, region_name="eu-west-2",
            aws_access_key_id="test", aws_secret_access_key="test")
events = boto3.client("events", **_cfg)
sqs = boto3.client("sqs", **_cfg)
s3 = boto3.client("s3", **_cfg)

TF_DIR = Path(__file__).resolve().parents[1] / "terraform" / "envs" / "local"


def _tf_output(name: str) -> dict[str, str]:
    cache = Path(__file__).resolve().parents[1] / f".{name}.json"
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


def archived(event_id: str, timeout: float = 20.0) -> dict:
    """Wait for the archiver to land the event in S3; return the object as a dict."""
    bucket, deadline = archive_bucket(), time.time() + timeout
    while time.time() < deadline:
        for page in s3.get_paginator("list_objects_v2").paginate(Bucket=bucket, Prefix="raw/"):
            for obj in page.get("Contents", []):
                body = json.loads(s3.get_object(Bucket=bucket, Key=obj["Key"])["Body"].read())
                if body.get("detail", {}).get("eventId") == event_id:
                    body["_key"] = obj["Key"]
                    return body
        time.sleep(1)
    raise AssertionError(f"eventId {event_id} was not archived to s3://{bucket}/raw/ within {timeout}s")


def archived_ids() -> set[str]:
    bucket, ids = archive_bucket(), set()
    for page in s3.get_paginator("list_objects_v2").paginate(Bucket=bucket, Prefix="raw/"):
        for obj in page.get("Contents", []):
            body = json.loads(s3.get_object(Bucket=bucket, Key=obj["Key"])["Body"].read())
            ids.add(body.get("detail", {}).get("eventId"))
    return ids


def duck():
    """DuckDB connection pointed at LocalStack's S3 (httpfs, path-style, test creds)."""
    import duckdb
    host = ENDPOINT.split("://", 1)[1]
    con = duckdb.connect()
    con.execute("INSTALL httpfs; LOAD httpfs;")
    con.execute(f"SET s3_endpoint='{host}'; SET s3_use_ssl=false; SET s3_url_style='path'; "
                "SET s3_region='eu-west-2'; SET s3_access_key_id='test'; SET s3_secret_access_key='test';")
    con.execute(f"CREATE VIEW archive AS SELECT * FROM read_json_auto('s3://{archive_bucket()}/raw/**/*.json', "
                "hive_partitioning=true, union_by_name=true)")
    return con
