"""Catalog-driven buses on LocalStack (Spike C over Spike B's modules): ADR-021 topology in its platform-local
rendering (ADR-025 L1). Domain bus -> generated forward rule -> Classic stub central -> generated subscriber
(a Classic rule with the subscriber's filter and retry policy) -> the consumer's queue. One bus-to-bus hop.

Run: task test   (after task up && task apply). The Spike B suite that proved ADR-001's second hop fails on AWS
is at commit eea52e9 (PR #1); its result is recorded in Spike B's findings and ADR-021.
"""
import json

import pytest

from harness import (archive_buckets, archived, bronze_ids, count_deliveries, dlq_count, drain, duck, envelope, example, expect,
                     expect_none, generated_dir, put, purge_all, quarantined, queues, rules_on)

Q = queues()
GEN = generated_dir()
ORDERS = "orders.order-service"
PAYMENTS = "payments.payment-service"

LOCALSTACK_GAP = ("LocalStack never writes to a target DLQ: Community 4.14 logs TargetDeliveryFailure and does not enforce the SQS policy; "
                  "2026.9 with ENFORCE_IAM logs AccessDenied and withholds the event, but still no DLQ record — sandbox-only")
TRANSFORMER_GAP = ("Community 4.14 accepts the transformer then drops the event; 2026.9 rejects it at PutTargets: "
                   "'Modifying the input for target ... is not supported' (apply fails, this test never runs); ADR-022")


@pytest.fixture(autouse=True)
def _clean():
    purge_all()
    yield


# ---- the hop AWS allows, and the subscriber that replaces the hop it refuses ----------------------

def test_public_event_reaches_central_in_one_hop():
    before = dlq_count("orders-public-forward")
    d = put("orders-bus", ORDERS, "OrderPlaced.v1", example("OrderPlaced"))
    e = expect(Q["central_probe"], d["eventId"])
    assert e["source"] == ORDERS and e["detail-type"] == "OrderPlaced.v1"
    assert dlq_count("orders-public-forward") == before


def test_public_event_reaches_payments_subscriber_queue():
    """payment-service receives OrderPlaced: the generated subscriber on central delivers to payments' own queue.
    One bus hop plus an SQS target, so LocalStack's answer is trustworthy (the eventsv2 subscriber itself is Spike D's)."""
    d = put("orders-bus", ORDERS, "OrderPlaced.v1", example("OrderPlaced"))
    e = expect(Q["subscriber:payments-order-placed"], d["eventId"])
    assert e["source"] == ORDERS and e["detail-type"] == "OrderPlaced.v1"
    assert dlq_count("payments-order-placed") == 0


def test_payment_captured_reaches_orders_subscriber_queue():
    d = put("payments-bus", PAYMENTS, "PaymentCaptured.v1", example("PaymentCaptured"))
    expect(Q["subscriber:orders-payment-captured"], d["eventId"])
    expect_none(Q["subscriber:payments-order-placed"], d["eventId"])


def test_internal_event_never_reaches_central_or_a_subscriber():
    d = put("orders-bus", ORDERS, "order.aggregate.updated.v1", envelope(order={"orderId": "o-1"}, changedFields=["status"]))
    expect(Q["orders_probe"], d["eventId"])          # it does exist on its own bus
    expect_none(Q["central_probe"], d["eventId"])
    expect_none(Q["subscriber:payments-order-placed"], d["eventId"])


def test_nothing_is_ever_delivered_back_to_a_domain_bus():
    """ADR-021: no fan-out. A public event is seen exactly once on its own bus and never on another domain's bus."""
    d = put("orders-bus", ORDERS, "OrderPlaced.v1", example("OrderPlaced"))
    expect(Q["subscriber:payments-order-placed"], d["eventId"])
    assert count_deliveries(Q["orders_probe"], d["eventId"], settle=8) == 1
    expect_none(Q["payments_probe"], d["eventId"], settle=5)


def test_subscriber_filter_is_exactly_the_receives_entry():
    """payments' subscriber matches OrderPlaced.v1 from orders. only; another orders event name is not delivered."""
    d = put("central-bus", ORDERS, "OrderCancelled.v1", example("OrderPlaced"))
    expect(Q["central_probe"], d["eventId"])
    expect_none(Q["subscriber:payments-order-placed"], d["eventId"])


def test_envelope_preserved_through_forward_and_subscriber():
    d = put("orders-bus", ORDERS, "OrderPlaced.v1", example("OrderPlaced"))
    origin = expect(Q["orders_probe"], d["eventId"])
    delivered = expect(Q["subscriber:payments-order-placed"], d["eventId"])
    for k in ("source", "detail-type", "detail", "time"):
        assert origin[k] == delivered[k], k
    assert origin["id"] != delivered["id"]   # central assigns its own id


def test_duplicate_put_is_delivered_twice():
    d = example("OrderPlaced")
    put("orders-bus", ORDERS, "OrderPlaced.v1", d)
    put("orders-bus", ORDERS, "OrderPlaced.v1", d)
    # at-least-once on Classic; publish-time dedup is the Custom bus's job (ADR-021, Spike D) — sandbox-only
    assert count_deliveries(Q["subscriber:payments-order-placed"], d["eventId"], settle=10) == 2


@pytest.mark.sandbox
@pytest.mark.xfail(reason=LOCALSTACK_GAP, strict=True)
def test_broken_target_lands_in_dlq():
    d = put("central-bus", "platform.spike", "BrokenTargetProbe.v1", envelope())
    dead = drain(Q["broken_target_dlq"], seconds=20)
    assert any(m.get("detail", {}).get("eventId") == d["eventId"] for m in dead)


# ---- the deployed rules are the generated files, nothing more ----------------------------------------

def test_every_deployed_rule_is_a_generated_file():
    """The nightly guardrail from generation-and-ci.md, run locally: on every bus, each rule that is not test
    scaffolding (probe, broken target, archiver) has a generated file whose pattern equals the deployed one."""
    buses = sorted({f"{p.rstrip('.')}-bus" for p in archive_buckets() if p} | {"central-bus"})   # from the routing map
    scaffolding = {f"{b.removesuffix('-bus')}-probe-all" for b in buses} | {"central-broken-target", "central-archive"}
    expected = json.loads(open(GEN / "deploy-order.json").read())["files"]
    generated = {}
    for rel in expected:
        if rel.startswith("rules/"):
            generated[rel.split("/")[-1][:-5]] = json.loads((GEN / rel).read_text())
        elif rel.startswith("subscribers/"):
            sub = json.loads((GEN / rel).read_text())
            generated[sub["name"]] = sub["filter"]
    deployed = {}
    for bus in buses:
        deployed.update({n: p for n, p in rules_on(bus).items() if n not in scaffolding and not n.startswith("orders-transformer")})
    assert set(deployed) == set(generated), f"hand-made or missing rules: {set(deployed) ^ set(generated)}"
    for name, pattern in deployed.items():
        assert pattern == generated[name], name


def test_no_fan_out_rule_exists_on_central():
    assert not [n for n in rules_on("central-bus") if "fan-out" in n]


def test_pattern_sizes_under_4kb():
    for f in list(GEN.glob("rules/*.json")) + list(GEN.glob("subscribers/*.json")):
        doc = json.loads(f.read_text())
        pattern = doc["filter"] if "filter" in doc else doc
        assert len(json.dumps(pattern, separators=(",", ":"))) < 4096, f.name


# ---- archive shim on central: validate against the generated bundle, route by the routing map -------

def test_valid_public_event_is_archived_in_its_domain_bucket():
    d = put("orders-bus", ORDERS, "OrderPlaced.v1", example("OrderPlaced"))
    obj = archived(d["eventId"], source=ORDERS, detail_type="OrderPlaced.v1")
    assert obj["_bucket"] == "orders-events-bronze" and obj["detail"] == d
    assert obj["_key"] == f"raw/source={ORDERS}/detail_type=OrderPlaced.v1/{obj['id']}.json"
    assert dlq_count("central-archive") == 0
    p = put("payments-bus", PAYMENTS, "PaymentCaptured.v1", example("PaymentCaptured"))
    assert archived(p["eventId"], source=PAYMENTS, detail_type="PaymentCaptured.v1")["_bucket"] == "payments-events-bronze"


def test_schema_violation_is_quarantined():
    d = example("OrderPlaced")
    del d["orderId"]
    put("orders-bus", ORDERS, "OrderPlaced.v1", d)
    obj = quarantined(d["eventId"], source=ORDERS, detail_type="OrderPlaced.v1", reason="schema")
    assert "orderId" in obj["_metadata"]["message"]


def test_direct_field_in_clear_is_quarantined():
    d = example("OrderPlaced")
    d["customerEmail"] = "jo.bloggs@example.com"
    put("orders-bus", ORDERS, "OrderPlaced.v1", d)
    obj = quarantined(d["eventId"], source=ORDERS, detail_type="OrderPlaced.v1", reason="pii-in-clear")
    assert "customerEmail" in obj["_metadata"]["message"]


def test_unknown_event_on_central_is_quarantined_in_the_fallback_bucket():
    d = put("central-bus", "platform.spike", "BrokenTargetProbe.v1", envelope())
    obj = quarantined(d["eventId"], source="platform.spike", detail_type="BrokenTargetProbe.v1", reason="unknown-event")
    assert obj["_bucket"] == "platform-events-bronze"


def test_internal_event_is_never_archived():
    d = put("orders-bus", ORDERS, "order.aggregate.updated.v1", envelope(order={"orderId": "o-2"}, changedFields=[]))
    expect(Q["orders_probe"], d["eventId"])
    expect_none(Q["central_probe"], d["eventId"], settle=5)
    assert d["eventId"] not in bronze_ids(source=ORDERS, detail_type="order.aggregate.updated.v1")


def test_duckdb_shows_raw_and_quarantine_prefixes():
    ok = put("orders-bus", ORDERS, "OrderPlaced.v1", example("OrderPlaced"))
    bad = example("OrderPlaced")
    bad["customerEmail"] = "in-clear@example.com"
    put("orders-bus", ORDERS, "OrderPlaced.v1", bad)
    archived(ok["eventId"], source=ORDERS, detail_type="OrderPlaced.v1")
    quarantined(bad["eventId"], source=ORDERS, detail_type="OrderPlaced.v1", reason="pii-in-clear")
    con = duck()
    rows = con.execute("SELECT status, reason, source, detail_type FROM bronze WHERE source = ? GROUP BY ALL ORDER BY 1, 2", [ORDERS]).fetchall()
    assert ("processing-failed", "pii-in-clear", ORDERS, "OrderPlaced.v1") in rows, rows
    assert ("raw", None, ORDERS, "OrderPlaced.v1") in rows, rows
    one = con.execute("SELECT detail.eventId, detail.total.amount FROM archive WHERE detail.eventId = ?", [ok["eventId"]]).fetchone()
    assert (str(one[0]), one[1]) == (ok["eventId"], "42.50")


@pytest.mark.transformer
@pytest.mark.sandbox
@pytest.mark.xfail(reason=TRANSFORMER_GAP, strict=True)
def test_input_transformer_on_bus_target():
    d = put("orders-bus", ORDERS, "OrderPlacedTransformed.v1", envelope(total=5.0, internalNote="drop me"))
    e = expect(Q["central_probe"], d["eventId"])
    assert "internalNote" not in e["detail"]
