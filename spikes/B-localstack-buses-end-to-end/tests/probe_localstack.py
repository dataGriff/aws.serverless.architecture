"""LocalStack feature probes for findings.md — not pytest, just prints a table.

Run: task probe   (after task up && task apply)

Covers what the done-when list asks for beyond the ten tests:
pattern operators via TestEventPattern, CreateArchive / StartReplay availability,
and the LocalStack version actually running.
"""
from __future__ import annotations

import json
import time
import urllib.request

import boto3
from botocore.config import Config

from harness import ENDPOINT, _cfg, drain, envelope, events, put, queues

EVENT = {"id": "1", "account": "000000000000", "time": "2026-10-04T15:00:00Z", "region": "eu-west-2",
         "resources": [], "source": "payments.payment-service", "detail-type": "PaymentCaptured.v1",
         "detail": {"eventId": "x", "replay": False, "nested": {"a": 1}}}

OPERATORS = [
    ("prefix",                      {"source": [{"prefix": "payments."}]},                     True),
    ("prefix (miss)",               {"source": [{"prefix": "orders."}]},                       False),
    ("anything-but + prefix",       {"source": [{"anything-but": {"prefix": "orders."}}]},     True),
    ("anything-but + prefix (own)", {"source": [{"anything-but": {"prefix": "payments."}}]},   False),
    ("anything-but list",           {"source": [{"anything-but": ["orders.order-service"]}]},  True),
    ("exists true",                 {"detail": {"replay": [{"exists": True}]}},                True),
    ("exists false",                {"detail": {"missing": [{"exists": False}]}},              True),
    ("exists on nested",            {"detail": {"nested": {"a": [{"exists": True}]}}},         True),
    ("suffix",                      {"detail-type": [{"suffix": ".v1"}]},                      True),
    ("equals-ignore-case",          {"source": [{"equals-ignore-case": "PAYMENTS.payment-service"}]}, True),
    ("wildcard",                    {"detail-type": [{"wildcard": "Payment*.v1"}]},            True),
    ("numeric",                     {"detail": {"nested": {"a": [{"numeric": [">", 0]}]}}},    True),
    ("$or",                         {"$or": [{"source": ["nope"]}, {"detail-type": ["PaymentCaptured.v1"]}]}, True),
]


def version() -> str:
    with urllib.request.urlopen(f"{ENDPOINT}/_localstack/info", timeout=5) as r:
        info = json.load(r)
    return f"{info.get('version')} ({info.get('edition')})"


def probe_operators() -> list[tuple[str, str]]:
    rows = []
    for name, pattern, want in OPERATORS:
        try:
            got = events.test_event_pattern(EventPattern=json.dumps(pattern), Event=json.dumps(EVENT))["Result"]
            rows.append((name, "ok" if got == want else f"WRONG: expected {want}, got {got}"))
        except Exception as e:  # noqa: BLE001 — we want the error text in the table
            rows.append((name, f"REJECTED: {type(e).__name__}: {str(e)[:120]}"))
    return rows


def probe_archive_replay() -> list[tuple[str, str]]:
    rows, bus_arn = [], "arn:aws:events:eu-west-2:000000000000:event-bus/central-bus"
    name = f"spike-archive-{int(time.time())}"
    try:
        events.create_archive(ArchiveName=name, EventSourceArn=bus_arn, RetentionDays=1,
                              EventPattern=json.dumps({"source": [{"prefix": ""}]}))
        rows.append(("CreateArchive", "ok"))
    except Exception as e:  # noqa: BLE001
        rows.append(("CreateArchive", f"REJECTED: {type(e).__name__}: {str(e)[:120]}"))
        return rows
    d = put("central-bus", "payments.payment-service", "PaymentCaptured.v1", envelope(probe="archive"))
    time.sleep(3)
    drain(queues()["central_probe"], seconds=3)
    try:
        now = time.time()
        # no retries: LocalStack 4.14 returns 500 on the first call and registers the replay anyway,
        # so boto's retry would report a misleading ResourceAlreadyExistsException
        no_retry = boto3.client("events", config=Config(retries={"max_attempts": 0}), **_cfg)
        r = no_retry.start_replay(ReplayName=f"{name}-replay", EventSourceArn=f"arn:aws:events:eu-west-2:000000000000:archive/{name}",
                                EventStartTime=now - 600, EventEndTime=now + 60,
                                Destination={"Arn": bus_arn})
        rows.append(("StartReplay", f"ok ({r.get('State')})"))
        replayed = [e for e in drain(queues()["central_probe"], seconds=15) if e.get("detail", {}).get("eventId") == d["eventId"]]
        if replayed:
            rows.append(("replayed event reaches central probe", "ok"))
            rows.append(("replay-name in envelope", str(replayed[0].get("replay-name", "ABSENT"))))
        else:
            rows.append(("replayed event reaches central probe", "NOT DELIVERED within 15s"))
    except Exception as e:  # noqa: BLE001
        rows.append(("StartReplay", f"REJECTED: {type(e).__name__}: {str(e)[:120]}"))
    finally:
        try:
            events.delete_archive(ArchiveName=name)
        except Exception:  # noqa: BLE001
            pass
    return rows


def probe_ordering(n: int = 20) -> list[tuple[str, str]]:
    """Put n events one after another on orders-bus; read the order they reach payments' probe (two hops)."""
    q = queues()["payments_probe"]
    drain(q, seconds=2)
    tag = f"order-{int(time.time())}"
    for i in range(n):
        put("orders-bus", "orders.order-service", "OrderPlaced.v1", envelope(seq=i, tag=tag))
    got = [e["detail"]["seq"] for e in drain(q, seconds=15) if e.get("detail", {}).get("tag") == tag]
    in_order = got == sorted(got)
    return [("ordering: %d sequential puts, 2 hops" % n,
             f"{len(got)}/{n} delivered, {'in order' if in_order else 'OUT OF ORDER: ' + str(got)}")]


if __name__ == "__main__":
    print(f"LocalStack: {version()}\n")
    print("| Probe | Result |\n| --- | --- |")
    for n, r in probe_operators() + probe_archive_replay() + probe_ordering():
        print(f"| {n} | {r} |")
