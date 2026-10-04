"""Spike D — EventBridge Custom Event Bus as the central bus (real AWS, eu-west-1).

Each test proves one capability the design would lean on, or records how AWS behaves where the docs are silent.
Run: task apply && task test
"""
import json
import time
from datetime import datetime, timedelta, timezone

import pytest

from harness import (DLQ, Q, classic, count_deliveries, create_subscriber, delete_subscriber, dlq_records, drain, eb,
                     envelope, expect, expect_none, outputs, purge_all, put, put_classic, wait_running)

CLASSIC_BUS = outputs()["classic_bus_name"]
SUBS = outputs()["subscriber_arns"]


@pytest.fixture(autouse=True)
def _clean():
    purge_all()
    yield


# ---- routing: Classic patterns as DATA filters, consumer-owned subscribers, no fan-out ----------------------

def test_classic_pattern_as_data_filter_reaches_consumer_subscriber():
    d = put("orders.order-service", "OrderPlaced.v1", envelope(total=42.0))
    e = expect(Q["payments-consumer-order-placed"], d["detail"]["eventId"])
    # RAW transformer (the default) delivers the Classic envelope, so an existing consumer keeps working unchanged
    assert e["source"] == "orders.order-service" and e["detail-type"] == "OrderPlaced.v1" and e["detail"] == d["detail"]
    assert {"id", "time", "account", "region"} <= set(e)


def test_filter_excludes_other_detail_types():
    d = put("orders.order-service", "order.aggregate.updated", envelope(row={"internal": True}))
    expect(Q["probe-all"], d["detail"]["eventId"])
    expect_none(Q["payments-consumer-order-placed"], d["detail"]["eventId"])
    expect_none(Q["orders-consumer-payment-captured"], d["detail"]["eventId"])


def test_with_metadata_transform_exposes_system_metadata():
    d = put("payments.payment-service", "PaymentCaptured.v1", envelope(amount=7.0), group="agg-1", dedup="dd-" + envelope()["eventId"])
    e = expect(Q["probe-all"], d["detail"]["eventId"])
    sm = e["SystemMetadata"]
    assert e["Data"]["detail"] == d["detail"] and e["Data"]["source"] == "payments.payment-service"
    assert sm["aws:Source"] == "payments.payment-service" and sm["aws:DetailType"] == "PaymentCaptured.v1"
    assert sm["aws:DeliveryType"] == "LIVE" and sm["EventGroupId"] == "agg-1" and sm["aws:EventId"] == d["EventId"]
    assert "aws:SequenceNumber" in sm and "aws:IngestionTime" in sm


def test_no_echo_problem_without_fan_out():
    """There is no second hop in this topology: a payments event is seen by orders' subscriber and nowhere else."""
    d = put("payments.payment-service", "PaymentCaptured.v1", envelope())
    expect(Q["orders-consumer-payment-captured"], d["detail"]["eventId"])
    expect_none(Q["payments-consumer-order-placed"], d["detail"]["eventId"])
    assert count_deliveries(Q["probe-all"], d["detail"]["eventId"], settle=5) == 1


# ---- the four capabilities Classic cannot give ------------------------------------------------------------

def test_dedup_by_id_suppresses_duplicate_publish():
    d = envelope(total=4.0)
    first = put("orders.order-service", "OrderPlaced.v1", d, dedup=d["eventId"])
    second = put("orders.order-service", "OrderPlaced.v1", d, dedup=d["eventId"])
    assert first["SuccessCode"] == "PUBLISHED" and second["SuccessCode"] == "DEDUPLICATED", (first, second)
    assert count_deliveries(Q["payments-consumer-order-placed"], d["eventId"], settle=10) == 1


def test_content_based_dedup_suppresses_identical_publish():
    d = envelope(total=4.5)
    first = put("orders.order-service", "OrderPlaced.v1", d, content_dedup=True)
    second = put("orders.order-service", "OrderPlaced.v1", d, content_dedup=True)
    assert (first["SuccessCode"], second["SuccessCode"]) == ("PUBLISHED", "DEDUPLICATED")
    assert count_deliveries(Q["probe-all"], d["eventId"], settle=10) == 1


def test_fifo_subscriber_preserves_order_within_event_group():
    tag, n = f"fifo-{int(time.time())}", 20
    for i in range(n):
        put("orders.order-service", "OrderPlaced.v1", envelope(seq=i, tag=tag), group="order-123")
    got, deadline = [], time.time() + 60
    while len(got) < n and time.time() < deadline:
        got += [e for e in drain(Q["probe-fifo"], seconds=5) if e["Data"]["detail"].get("tag") == tag]
    seqs = [e["Data"]["detail"]["seq"] for e in got]
    assert len(seqs) == n, f"{len(seqs)}/{n} delivered"
    assert seqs == list(range(n)), seqs
    assert all(e["SystemMetadata"]["EventGroupId"] == "order-123" for e in got)


def test_unordered_probe_does_not_guarantee_order():
    """Informational: the UNORDERED probe receives the same group; record whether it stayed in order."""
    tag, n = f"unord-{int(time.time())}", 20
    for i in range(n):
        put("orders.order-service", "OrderPlaced.v1", envelope(seq=i, tag=tag), group="order-456")
    got, deadline = [], time.time() + 60
    while len(got) < n and time.time() < deadline:
        got += [e for e in drain(Q["probe-all"], seconds=5) if e["Data"]["detail"].get("tag") == tag]
    seqs = [e["Data"]["detail"]["seq"] for e in got]
    assert len(seqs) == n
    print(f"\nUNORDERED probe order: {'in order' if seqs == sorted(seqs) else seqs}")


def test_replay_via_point_in_time_subscriber_marks_events_replay():
    # API rule: "PointInTimeConfiguration.StartingPoint must be at least 5 minutes in the past"
    start = datetime.now(timezone.utc) - timedelta(minutes=6)
    d = put("orders.order-service", "OrderPlaced.v1", envelope(total=9.0, replayme=True))
    expect(Q["payments-consumer-order-placed"], d["detail"]["eventId"])  # live delivery done
    arn = create_subscriber("replay", Q["probe-replay"], StartingPosition="POINT_IN_TIME",
                            PointInTimeConfiguration={"PointType": "TIMESTAMP", "StartingPoint": start},
                            Transformer={"Type": "WITH_METADATA"},
                            FilterConfiguration={"Filters": [{"Scope": "DATA", "Pattern": json.dumps({"detail": {"replayme": [True]}})}]})
    try:
        wait_running(arn)
        e = expect(Q["probe-replay"], d["detail"]["eventId"], timeout=180)  # "a replay has a startup delay"
        assert e["SystemMetadata"]["aws:DeliveryType"] == "REPLAY", e["SystemMetadata"]
        assert e["Data"]["detail"] == d["detail"]
    finally:
        delete_subscriber(arn)


def test_broken_target_lands_in_subscriber_dlq():
    d = put("platform.spike", "BrokenTargetProbe.v1", envelope())
    recs = dlq_records("broken-target", wait=150)
    assert recs, "nothing reached the subscriber DLQ within 150 s"
    r = recs[0]
    print("\nDLQ record:", json.dumps({k: v for k, v in r.items() if not k.startswith("_")}, default=str)[:1500])
    print("attrs:", r["_attrs"])
    # v2 DLQ record is an envelope, not the event: {id, version, busArn, subscriberArn, targetArn, errorCode,
    # errorMessage, retryAttempts, exhaustedRetryCondition, failedMessages[...]}
    assert r["_attrs"]["ERROR_CODE"] == "ACCESS_DENIED" and r["errorCode"] == "ACCESS_DENIED"
    assert any(d["detail"]["eventId"] in json.dumps(m) or d["EventId"] in json.dumps(m) for m in r["failedMessages"]), r["failedMessages"]


# ---- coexistence with Classic ----------------------------------------------------------------------------

def test_classic_rule_can_target_custom_bus():
    """A domain keeps its Classic bus and forward rule; the Custom central bus is the rule's target (hop 1)."""
    d = put_classic(CLASSIC_BUS, "orders.order-service", "OrderPlaced.v1", envelope(total=11.0, via="classic"))
    e = expect(Q["payments-consumer-order-placed"], d["eventId"], timeout=60)
    assert e["detail"] == d
    dead = [r for r in drain(DLQ["classic-forward"], seconds=3) if r.get("detail", {}).get("eventId") == d["eventId"]]
    assert not dead, dead[0]["_attrs"]


@pytest.mark.record
def test_subscriber_back_to_classic_bus_from_classic_origin():
    """Classic orders-bus -> Custom central -> subscriber -> Classic orders-bus. Delivered twice, dropped, or LOOP_DETECTED?"""
    d = put_classic(CLASSIC_BUS, "orders.order-service", "OrderPlaced.v1", envelope(total=12.0, via="classic-loop"))
    copies, dead, deadline = 0, [], time.time() + 150  # subscriber retry policy: 1 attempt / 60 s before the DLQ
    while time.time() < deadline and not (copies >= 2 or dead):
        copies += count_deliveries(Q["probe-classic"], d["eventId"], settle=5)
        dead += [r for r in drain(DLQ["loop-back-to-classic"], seconds=5)
                 if d["eventId"] in json.dumps(r.get("failedMessages", "")) or d["eventId"] in json.dumps(r)]
    codes = [(r["_attrs"].get("ERROR_CODE"), r.get("errorMessage", "")[:160]) for r in dead]
    print(f"\ncopies on Classic orders-bus probe: {copies}; loop-back DLQ records: {len(dead)} {codes}")
    # Recorded 2026-10-04: the event is NOT delivered back to its Classic bus of origin and NO DLQ record is written
    # within 150 s — a silent drop. (The other direction, direct publish -> subscriber -> Classic -> forward rule ->
    # Custom bus, IS surfaced: LOOP_DETECTED on the forward rule's DLQ.) If this assertion fails, AWS changed behaviour.
    assert copies == 1 and not dead, f"behaviour changed: copies={copies}, dlq={codes}"


def test_subscriber_to_classic_bus_from_direct_publish_is_one_hop():
    """Published straight on the Custom bus, the subscriber's bus-to-bus delivery to Classic orders-bus is hop 1."""
    d = put("orders.order-service", "OrderPlaced.v1", envelope(total=13.0, via="direct"))
    expect(Q["probe-classic"], d["detail"]["eventId"], timeout=60)


# ---- API-level facts the generator must respect --------------------------------------------------------------

def test_wildcard_filter_is_rejected():
    with pytest.raises(eb.exceptions.InvalidInputException) as ex:
        arn = create_subscriber("wildcard", Q["probe-replay"],
                                FilterConfiguration={"Filters": [{"Scope": "DATA", "Pattern": json.dumps({"source": [{"wildcard": "orders.*"}]})}]})
        delete_subscriber(arn)  # only reached if AWS accepted it
    assert "wildcard" in str(ex.value).lower(), str(ex.value)


def test_anything_but_prefix_filter_is_accepted():
    arn = create_subscriber("anything-but", Q["probe-replay"],
                            FilterConfiguration={"Filters": [{"Scope": "DATA", "Pattern": json.dumps({"source": [{"anything-but": {"prefix": "payments."}}]})}]})
    try:
        d = eb.describe_subscriber(SubscriberArn=arn)
        assert d["FilterConfiguration"]["Filters"][0]["Scope"] == "DATA"
    finally:
        delete_subscriber(arn)


def test_default_retry_policy_is_five_attempts_in_five_minutes():
    arn = create_subscriber("defaults", Q["probe-replay"])
    try:
        d = eb.describe_subscriber(SubscriberArn=arn)
        print("\ndefaults:", {k: d.get(k) for k in ("RetryPolicy", "BatchConfiguration", "Type", "StartingPosition", "Transformer")})
        rp = d.get("RetryPolicy") or {}
        assert (rp.get("MaxRetryAttempts"), rp.get("MaxEventAgeInSeconds")) == (5, 300), rp
    finally:
        delete_subscriber(arn)


def test_explicit_retry_policy_matches_classic_defaults():
    d = eb.describe_subscriber(SubscriberArn=SUBS["payments-consumer-order-placed"])
    assert d["RetryPolicy"]["MaxRetryAttempts"] == 185 and d["RetryPolicy"]["MaxEventAgeInSeconds"] == 86400


def test_bus_retention_and_window():
    b = eb.describe_event_bus(EventBusArn=outputs()["bus_arn"])
    print("\nbus:", {k: str(b.get(k)) for k in ("State", "StorageConfiguration", "RetentionWindowStartTime")})
    assert b["State"] == "ACTIVE" and b["StorageConfiguration"]["RetentionPeriodInDays"] == 7
