"""Spike B — domain bus ↔ central bus end to end on LocalStack.

Names are the contract (see docs/architecture/prompts/spikes/B-localstack-buses-end-to-end.md).
Run: task test   (after task up && task apply)
"""
import json
import time
from pathlib import Path

import pytest

from harness import (IS_LOCALSTACK, archived, archived_ids, count_deliveries, dlq_count, drain, duck, envelope, events,
                     expect, expect_none, put, purge_all, queues)

localstack_only = pytest.mark.skipif(not IS_LOCALSTACK, reason="LocalStack-only (archiver / DuckDB are not in the sandbox env)")

Q = queues()
PATTERNS = Path(__file__).resolve().parents[1] / "patterns"

# CONFIRMED on real AWS 2026-10-04 (task sandbox-test): every two-hop test below fails there, and the fan-out
# DLQs hold the event with ERROR_CODE=THIRD_ACCOUNT_HOP_DETECTED: "an event can be sent to an event bus target
# only once. This event was previously delivered to an event bus target." LocalStack (Community and licensed)
# delivers the second hop anyway, so these tests pass locally for the wrong reason. See findings.md.
TWO_HOPS = pytest.mark.sandbox

LOCALSTACK_GAP = ("LocalStack never writes to a target DLQ: Community 4.14 logs TargetDeliveryFailure and does not enforce the SQS policy; "
                  "2026.9 with ENFORCE_IAM logs AccessDenied and withholds the event, but still no DLQ record — sandbox-only")
TRANSFORMER_GAP = ("Community 4.14 accepts the transformer then drops the event (DetailType lost → InvalidArgument); "
                   "2026.9 rejects it at PutTargets: 'Modifying the input for target ... is not supported' (apply fails, this test never runs); "
                   "AWS: InputTransformer unavailable on bus targets — ADR-006 trigger must change")


@pytest.fixture(autouse=True)
def _clean():
    purge_all()
    yield


@TWO_HOPS
def test_public_event_from_orders_reaches_payments_probe():
    d = put("orders-bus", "orders.order-service", "OrderPlaced.v1", envelope(total=42.0))
    e = expect(Q["payments_probe"], d["eventId"])
    assert e["source"] == "orders.order-service" and e["detail-type"] == "OrderPlaced.v1"


@TWO_HOPS
def test_public_event_reaches_payments_consumer_rule():
    d = put("orders-bus", "orders.order-service", "OrderPlaced.v1", envelope(total=1.0))
    expect(Q["payments_consumer_order_placed"], d["eventId"])


def test_public_event_reaches_central_in_one_hop():
    """The hop AWS does guarantee: domain bus -> central. Not marked sandbox."""
    before = dlq_count("orders-public-forward")  # delta, not absolute: AWS PurgeQueue is once per 60 s and async
    d = put("orders-bus", "orders.order-service", "OrderPlaced.v1", envelope(total=1.5))
    e = expect(Q["central_probe"], d["eventId"])
    assert e["source"] == "orders.order-service" and e["detail-type"] == "OrderPlaced.v1"
    assert dlq_count("orders-public-forward") == before


def test_fan_out_from_central_reaches_domain_in_one_hop():
    """The other hop AWS guarantees, taken on its own: an event put straight on central reaches payments-bus."""
    before = dlq_count("payments-fan-out")
    d = put("central-bus", "orders.order-service", "OrderPlaced.v1", envelope(total=1.6))
    expect(Q["payments_consumer_order_placed"], d["eventId"])
    expect_none(Q["orders_probe"], d["eventId"])
    assert dlq_count("payments-fan-out") == before


def test_internal_event_never_reaches_central_or_payments():
    d = put("orders-bus", "orders.order-service", "order.aggregate.updated", envelope(row={"internal": True}))
    expect(Q["orders_probe"], d["eventId"])          # it does exist on its own bus
    expect_none(Q["central_probe"], d["eventId"])
    expect_none(Q["payments_probe"], d["eventId"])


@TWO_HOPS
def test_fan_out_does_not_echo_own_event():
    d = put("orders-bus", "orders.order-service", "OrderPlaced.v1", envelope(total=2.0))
    expect(Q["central_probe"], d["eventId"])
    # exactly one delivery on orders' own bus: the original put, never a copy back from central
    assert count_deliveries(Q["orders_probe"], d["eventId"], settle=10) == 1


@TWO_HOPS
def test_three_bus_loop_terminates():
    d = put("payments-bus", "payments.payment-service", "PaymentCaptured.v1", envelope())
    expect(Q["orders_consumer_payment_captured"], d["eventId"])
    # one hop each way: payments-bus -> central -> orders-bus, exactly one copy per bus
    first = {name: count_deliveries(Q[name], d["eventId"], settle=5)
             for name in ("payments_probe", "central_probe", "orders_probe")}
    assert first == {"payments_probe": 1, "central_probe": 1, "orders_probe": 1}, first
    time.sleep(10)
    # after settling, nothing further arrives anywhere for this event
    for name in ("orders_probe", "payments_probe", "central_probe"):
        assert count_deliveries(Q[name], d["eventId"], settle=3) == 0


@TWO_HOPS
def test_envelope_preserved_across_two_hops():
    d = put("orders-bus", "orders.order-service", "OrderPlaced.v1", envelope(total=3.0, nested={"a": [1, 2]}))
    origin = expect(Q["orders_probe"], d["eventId"])
    hop2 = expect(Q["payments_probe"], d["eventId"])
    for k in ("source", "detail-type", "detail", "time"):
        assert origin[k] == hop2[k], k
    assert origin["id"] != hop2["id"]   # each bus assigns its own id


@pytest.mark.sandbox
@pytest.mark.xfail(IS_LOCALSTACK, reason=LOCALSTACK_GAP, strict=True)
def test_broken_target_lands_in_dlq():
    """The DLQ message body is the undeliverable event itself (plus ERROR_CODE / ERROR_MESSAGE attributes)."""
    d = put("central-bus", "platform.spike", "BrokenTargetProbe.v1", envelope())
    dead = drain(Q["broken_target_dlq"], seconds=20)
    assert any(m.get("detail", {}).get("eventId") == d["eventId"] for m in dead), \
        "nothing reached the DLQ — record in findings whether LocalStack implements DLQ delivery for denied SQS targets"
    assert dlq_count("central-broken-target") == 0  # drain() deleted it


@TWO_HOPS
def test_duplicate_put_is_delivered_twice():
    d = envelope(total=4.0)
    put("orders-bus", "orders.order-service", "OrderPlaced.v1", d)
    put("orders-bus", "orders.order-service", "OrderPlaced.v1", d)
    # at-least-once: the platform does not dedupe; consumers must (documented, not fixed)
    assert count_deliveries(Q["payments_probe"], d["eventId"], settle=10) == 2


def test_pattern_sizes_under_4kb():
    for f in PATTERNS.glob("*.json"):
        assert len(json.dumps(json.loads(f.read_text()), separators=(",", ":"))) < 4096, f.name


def test_anything_but_prefix_supported_or_fallback():
    """If this fails, re-apply with -var fan_out_variant=enumerated and record it in findings.md."""
    pattern = json.dumps(json.loads((PATTERNS / "orders-fan-out.json").read_text()))
    r = events.test_event_pattern(EventPattern=pattern, Event=json.dumps({
        "id": "1", "detail-type": "PaymentCaptured.v1", "source": "payments.payment-service",
        "account": "000000000000", "time": "2026-10-04T15:00:00Z", "region": "eu-west-2", "resources": [], "detail": {}}))
    assert r["Result"] is True, "LocalStack did not match anything-but+prefix; use the enumerated variant"
    r2 = events.test_event_pattern(EventPattern=pattern, Event=json.dumps({
        "id": "2", "detail-type": "OrderPlaced.v1", "source": "orders.order-service",
        "account": "000000000000", "time": "2026-10-04T15:00:00Z", "region": "eu-west-2", "resources": [], "detail": {}}))
    assert r2["Result"] is False, "own-prefix exclusion did not hold"


# ---- stretch: archiver Lambda on central -> S3, read back with DuckDB ------------------------------

@localstack_only
def test_archiver_writes_every_central_event_to_s3():
    d = put("orders-bus", "orders.order-service", "OrderPlaced.v1", envelope(total=6.0))
    obj = archived(d["eventId"])
    assert obj["source"] == "orders.order-service" and obj["detail"] == d
    assert obj["_key"] == f"raw/source=orders.order-service/detail_type=OrderPlaced.v1/{obj['id']}.json"
    assert dlq_count("central-archive") == 0


@localstack_only
def test_internal_event_is_never_archived():
    d = put("orders-bus", "orders.order-service", "order.aggregate.updated", envelope(row={"internal": True}))
    expect(Q["orders_probe"], d["eventId"])
    time.sleep(5)
    assert d["eventId"] not in archived_ids()


@localstack_only
def test_duckdb_reads_archive_with_hive_partitions():
    d = put("payments-bus", "payments.payment-service", "PaymentCaptured.v1", envelope(amount=7.0))
    archived(d["eventId"])
    con = duck()
    rows = con.execute("SELECT source, detail_type, count(*) FROM archive GROUP BY ALL ORDER BY 1, 2").fetchall()
    assert ("payments.payment-service", "PaymentCaptured.v1") in {(r[0], r[1]) for r in rows}, rows
    one = con.execute("SELECT detail.eventId, detail.amount FROM archive WHERE detail.eventId = ?", [d["eventId"]]).fetchone()
    # read_json_auto infers eventId as UUID, not VARCHAR — a typed column for free, but a cast the compactor must pin
    assert (str(one[0]), one[1]) == (d["eventId"], 7.0)


@pytest.mark.transformer
@pytest.mark.sandbox
@pytest.mark.xfail(reason=TRANSFORMER_GAP, strict=True)
def test_input_transformer_on_bus_target():
    """Only meaningful with -var enable_transformer_rule=true. ADR-006 assumes this works for bus targets;
    verify here AND against real AWS before relying on it. Record the outcome in findings.md."""
    d = put("orders-bus", "orders.order-service", "OrderPlacedTransformed.v1", envelope(total=5.0, internalNote="drop me"))
    e = expect(Q["central_probe"], d["eventId"])
    assert "internalNote" not in e["detail"], "transformer did not strip the field (or was ignored for a bus target)"
