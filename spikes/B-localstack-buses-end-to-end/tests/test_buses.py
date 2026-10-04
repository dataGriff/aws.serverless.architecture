"""Spike B — domain bus ↔ central bus end to end on LocalStack.

Names are the contract (see docs/architecture/prompts/spikes/B-localstack-buses-end-to-end.md).
Run: task test   (after task up && task apply)
"""
import json
import time
from pathlib import Path

import pytest

from harness import (count_deliveries, drain, envelope, events, expect, expect_none, put, purge_all, queues)

Q = queues()
PATTERNS = Path(__file__).resolve().parents[1] / "patterns"


@pytest.fixture(autouse=True)
def _clean():
    purge_all()
    yield


def test_public_event_from_orders_reaches_payments_probe():
    d = put("orders-bus", "orders.order-service", "OrderPlaced.v1", envelope(total=42.0))
    e = expect(Q["payments_probe"], d["eventId"])
    assert e["source"] == "orders.order-service" and e["detail-type"] == "OrderPlaced.v1"


def test_public_event_reaches_payments_consumer_rule():
    d = put("orders-bus", "orders.order-service", "OrderPlaced.v1", envelope(total=1.0))
    expect(Q["payments_consumer_order_placed"], d["eventId"])


def test_internal_event_never_reaches_central_or_payments():
    d = put("orders-bus", "orders.order-service", "order.aggregate.updated", envelope(row={"internal": True}))
    expect(Q["orders_probe"], d["eventId"])          # it does exist on its own bus
    expect_none(Q["central_probe"], d["eventId"])
    expect_none(Q["payments_probe"], d["eventId"])


def test_fan_out_does_not_echo_own_event():
    d = put("orders-bus", "orders.order-service", "OrderPlaced.v1", envelope(total=2.0))
    expect(Q["central_probe"], d["eventId"])
    # exactly one delivery on orders' own bus: the original put, never a copy back from central
    assert count_deliveries(Q["orders_probe"], d["eventId"], settle=10) == 1


def test_three_bus_loop_terminates():
    d = put("payments-bus", "payments.payment-service", "PaymentCaptured.v1", envelope())
    expect(Q["orders_consumer_payment_captured"], d["eventId"])
    time.sleep(10)
    # after settling, nothing further arrives anywhere for this event
    for name in ("orders_probe", "payments_probe", "central_probe"):
        assert count_deliveries(Q[name], d["eventId"], settle=3) == 0


def test_envelope_preserved_across_two_hops():
    d = put("orders-bus", "orders.order-service", "OrderPlaced.v1", envelope(total=3.0, nested={"a": [1, 2]}))
    origin = expect(Q["orders_probe"], d["eventId"])
    hop2 = expect(Q["payments_probe"], d["eventId"])
    for k in ("source", "detail-type", "detail", "time"):
        assert origin[k] == hop2[k], k
    assert origin["id"] != hop2["id"]   # each bus assigns its own id


def test_broken_target_lands_in_dlq():
    """The DLQ message body is the undeliverable event itself (plus ERROR_CODE / ERROR_MESSAGE attributes)."""
    d = put("central-bus", "platform.spike", "BrokenTargetProbe.v1", envelope())
    dead = drain(Q["broken_target_dlq"], seconds=20)
    assert any(m.get("detail", {}).get("eventId") == d["eventId"] for m in dead), \
        "nothing reached the DLQ — record in findings whether LocalStack implements DLQ delivery for denied SQS targets"


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


@pytest.mark.transformer
def test_input_transformer_on_bus_target():
    """Only meaningful with -var enable_transformer_rule=true. ADR-006 assumes this works for bus targets;
    verify here AND against real AWS before relying on it. Record the outcome in findings.md."""
    d = put("orders-bus", "orders.order-service", "OrderPlacedTransformed.v1", envelope(total=5.0, internalNote="drop me"))
    e = expect(Q["central_probe"], d["eventId"])
    assert "internalNote" not in e["detail"], "transformer did not strip the field (or was ignored for a bus target)"
