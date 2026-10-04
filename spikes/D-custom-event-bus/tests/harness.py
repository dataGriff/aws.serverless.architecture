"""Spike D harness: publish to the Custom Event Bus (eventbridgev2), watch SQS probes, read DLQs.

Terraform outputs are cached in .outputs.json (removed by `task apply` / `task destroy`).
Default boto3 credential chain: AWS_PROFILE (Taskfile sets it), region eu-west-1.
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

REGION = os.environ.get("AWS_DEFAULT_REGION", "eu-west-1")
ROOT = Path(__file__).resolve().parents[1]
TF_DIR = ROOT / os.environ.get("SPIKE_TF_DIR", "terraform")

eb = boto3.client("eventbridgev2", region_name=REGION)
classic = boto3.client("events", region_name=REGION)
sqs = boto3.client("sqs", region_name=REGION)


def outputs() -> dict:
    cache = ROOT / ".outputs.json"
    if cache.exists():
        return json.loads(cache.read_text())
    raw = json.loads(subprocess.check_output(["terraform", "output", "-json"], cwd=TF_DIR))
    out = {k: v["value"] for k, v in raw.items()}
    cache.write_text(json.dumps(out))
    return out


O = outputs()
BUS_ARN: str = O["bus_arn"]
Q: dict[str, str] = O["queues"]
DLQ: dict[str, str] = O["dlqs"]
ROLE_ARN: str = O["delivery_role_arn"]


def envelope(**extra) -> dict:
    return {"eventId": str(uuid.uuid4()), "occurredAt": datetime.now(timezone.utc).isoformat(),
            "correlationId": str(uuid.uuid4()), "causationId": None,
            "aggregateId": "agg-1", "aggregateVersion": 1, **extra}


def put(source: str, detail_type: str, detail: dict, *, group: str | None = None, dedup: str | None = None,
        content_dedup: bool = False) -> dict:
    """Publish one entry to the Custom bus. Returns the PutEvents result entry plus the detail."""
    entry = {"Source": source, "DetailType": detail_type, "Detail": json.dumps(detail)}
    meta = {k: v for k, v in (("EventGroupId", group), ("DeduplicationId", dedup)) if v}
    if meta:
        entry["SystemMetadata"] = meta
    kwargs = {"EventBusArn": BUS_ARN, "Entries": [entry]}
    if content_dedup:
        kwargs["DeduplicationConfiguration"] = {"DeduplicationType": "CONTENT_BASED"}
    r = eb.put_events(**kwargs)
    assert r["FailedEntryCount"] == 0, r
    return {**r["Entries"][0], "detail": detail}


def put_classic(bus: str, source: str, detail_type: str, detail: dict) -> dict:
    r = classic.put_events(Entries=[{"EventBusName": bus, "Source": source, "DetailType": detail_type,
                                     "Detail": json.dumps(detail)}])
    assert r["FailedEntryCount"] == 0, r
    return detail


def _event_id_of(body: dict) -> str | None:
    """eventId from either a RAW body (Classic envelope) or a WITH_METADATA body ({Data, Metadata, SystemMetadata})."""
    data = body.get("Data", body)
    detail = data.get("detail") if isinstance(data, dict) else None
    return detail.get("eventId") if isinstance(detail, dict) else None


def drain(queue_url: str, seconds: float = 10.0) -> list[dict]:
    """Every message delivered within `seconds`; returns parsed bodies with `_attrs` (SQS message attributes). Deletes them."""
    found, deadline = [], time.time() + seconds
    while time.time() < deadline:
        r = sqs.receive_message(QueueUrl=queue_url, MaxNumberOfMessages=10, WaitTimeSeconds=2,
                                MessageAttributeNames=["All"], AttributeNames=["All"])
        msgs = r.get("Messages", [])
        for m in msgs:
            try:
                body = json.loads(m["Body"])
            except json.JSONDecodeError:
                body = {"_raw": m["Body"]}
            body["_attrs"] = {k: v.get("StringValue") for k, v in (m.get("MessageAttributes") or {}).items()}
            body["_sqs"] = m.get("Attributes", {})
            found.append(body)
            sqs.delete_message(QueueUrl=queue_url, ReceiptHandle=m["ReceiptHandle"])
        if not msgs and found:
            break
    return found


def expect(queue_url: str, event_id: str, timeout: float = 30.0) -> dict:
    deadline = time.time() + timeout
    while time.time() < deadline:
        for e in drain(queue_url, seconds=3):
            if _event_id_of(e) == event_id:
                return e
    raise AssertionError(f"eventId {event_id} did not arrive on {queue_url.rsplit('/', 1)[-1]} within {timeout}s")


def expect_none(queue_url: str, event_id: str, settle: float = 10.0) -> None:
    hits = [e for e in drain(queue_url, seconds=settle) if _event_id_of(e) == event_id]
    assert not hits, f"eventId {event_id} unexpectedly arrived on {queue_url.rsplit('/', 1)[-1]}"


def count_deliveries(queue_url: str, event_id: str, settle: float = 10.0) -> int:
    return sum(1 for e in drain(queue_url, seconds=settle) if _event_id_of(e) == event_id)


def dlq_records(name: str, wait: float = 60.0) -> list[dict]:
    deadline, found = time.time() + wait, []
    while time.time() < deadline and not found:
        found = drain(DLQ[name], seconds=5)
    return found


def purge_all() -> None:
    for url in {**Q, **DLQ}.values():
        try:
            sqs.purge_queue(QueueUrl=url)
        except Exception:  # noqa: BLE001 — PurgeQueueInProgress on AWS is once per 60 s
            pass


def create_subscriber(name: str, target_queue_url: str, **kwargs) -> str:
    """Create a subscriber owned by the test (deleted by the caller). Returns its ARN."""
    target_arn = sqs.get_queue_attributes(QueueUrl=target_queue_url, AttributeNames=["QueueArn"])["Attributes"]["QueueArn"]
    r = eb.create_subscriber(Name=f"spike-d-{name}-{int(time.time())}", EventBusArn=BUS_ARN,
                             InvokeConfiguration={"TargetArn": target_arn, "RoleArn": ROLE_ARN},
                             OnFailureConfiguration={"Arn": O["dlq_arns"]["test-owned"]},
                             **kwargs)
    return r["SubscriberArn"]


def delete_subscriber(subscriber_arn: str) -> None:
    for _ in range(10):  # ConcurrentModificationException: one create/delete at a time per bus
        try:
            eb.delete_subscriber(SubscriberArn=subscriber_arn)
            return
        except eb.exceptions.ConcurrentModificationException:
            time.sleep(3)
        except eb.exceptions.ResourceNotFoundException:
            return


def wait_running(subscriber_arn: str, timeout: float = 120.0) -> dict:
    deadline = time.time() + timeout
    while time.time() < deadline:
        d = eb.describe_subscriber(SubscriberArn=subscriber_arn)
        if d.get("State") == "RUNNING":
            return d
        time.sleep(2)
    raise AssertionError(f"subscriber never reached RUNNING: {d}")
