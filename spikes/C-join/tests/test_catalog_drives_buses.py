"""Spike C: a catalog PR is the only thing that changes behaviour on the buses.

Each test edits a copy of the catalog, regenerates, plans Spike B's Terraform against the new output, checks the
plan against a committed snapshot (the exact set of changes), applies, proves the behaviour with a real event,
then takes the edit back and proves the behaviour stops. The tests run in file order and share LocalStack state;
the last one leaves the buses on the baseline output. Run: task test  (from spikes/C-join; ~6 min).
"""
import json
import subprocess
import sys
import uuid

import pytest

from scenarios import B, BASELINE, CURRENT, apply, check_snapshot, generated_diff, generated_for, plan, plan_is_empty

sys.path.insert(0, str(B / "tests"))
import harness  # noqa: E402  (Spike B's harness: put, expect, archived, queues...)

ORDERS = "orders.order-service"
INTERNAL = "order.aggregate.updated.v1"


def public_order_updated() -> dict:
    """order.aggregate.updated as it must look once public: `order` is x-pii direct, so it travels as ciphertext."""
    return {"eventId": str(uuid.uuid4()), "occurredAt": "2026-10-04T09:15:09.500Z", "replay": False,
            "correlationId": "req-1", "causationId": "cmd-1", "aggregateId": "ord_1", "aggregateVersion": 2,
            "order": {"enc": "v1", "kid": "sk/orders/cus_1", "ct": "AQIDBAUGBwgJCgsMDQ4PEBESExQVFhcYGRobHB0eHyA="},
            "changedFields": ["status"]}


@pytest.fixture(scope="module", autouse=True)
def baseline_applied():
    assert BASELINE.exists(), "run `task -d ../A-catalog-source-of-truth gen` first"
    assert plan_is_empty(BASELINE), "LocalStack is not on the baseline output; run `task -d ../B-localstack-buses-end-to-end apply`"
    yield
    if CURRENT[0] != BASELINE:
        apply(BASELINE)


def put_internal(detail: dict) -> dict:
    return harness.put("orders-bus", ORDERS, INTERNAL, detail)


# ---- 1. visibility -------------------------------------------------------------------------------------

def test_flip_to_public_changes_only_the_forward_rule_and_the_archive_shim():
    public = generated_for("public")
    assert generated_diff(BASELINE, public) == {
        "rules/orders-public-forward.json", "archive/routing-map.json", "validation/orders.json",
        "parquet/order.aggregate.updated.v1.json", "deploy-order.json",
    }
    changes = plan(public)
    check_snapshot("1-flip-internal-to-public", changes)
    assert [c["address"] for c in changes] == [
        "module.central_archive.aws_lambda_function.fn",
        'module.public_forward["orders-public-forward"].aws_cloudwatch_event_rule.this',
    ]
    rule = changes[1]
    assert INTERNAL not in rule["event_pattern"]["before"]["detail-type"]
    assert INTERNAL in rule["event_pattern"]["after"]["detail-type"]
    shim = changes[0]
    assert shim["changed"] == ["source_code_hash"]   # bundle + routing map are packaged in the zip, not env vars


def test_public_event_now_reaches_central_and_bronze_then_stops_when_reverted():
    public = generated_for("public")
    apply(public)
    q = harness.queues()
    d = put_internal(public_order_updated())
    harness.expect(q["central_probe"], d["eventId"])
    obj = harness.archived(d["eventId"], source=ORDERS, detail_type=INTERNAL)
    assert obj["_bucket"] == "orders-events-bronze"
    # still nobody receives it: no receives[] names it, so no subscriber exists
    harness.expect_none(q["subscriber:payments-order-placed"], d["eventId"], settle=5)
    # the example in the catalog carries the email in clear; once public, that same payload is quarantined
    clear = harness.example("order.aggregate.updated", "status-paid")
    put_internal(clear)
    harness.quarantined(clear["eventId"], source=ORDERS, detail_type=INTERNAL, reason="pii-in-clear")

    revert = plan(BASELINE)
    check_snapshot("1-revert-to-internal", revert)
    apply(BASELINE)
    d2 = put_internal(public_order_updated())
    harness.expect(harness.queues()["orders_probe"], d2["eventId"])
    harness.expect_none(harness.queues()["central_probe"], d2["eventId"])
    assert d2["eventId"] not in harness.bronze_ids(source=ORDERS, detail_type=INTERNAL)


# ---- 2. a cross-domain receives[] ------------------------------------------------------------------------

def test_add_receives_changes_only_the_subscriber_on_central():
    public, subscribed = generated_for("public"), generated_for("public+subscribe")
    # (the two channel pages that also change are written into the catalog copy, not under generated/)
    assert generated_diff(public, subscribed) == {"subscribers/payments-order-aggregate-updated.json", "deploy-order.json"}
    apply(public)
    changes = plan(subscribed)
    check_snapshot("2-add-cross-domain-receives", changes)
    assert {c["actions"][0] for c in changes} == {"create"}
    assert {c["address"].split(".aws_")[0] for c in changes} == {'module.subscriber["payments-order-aggregate-updated"]'}


def test_subscriber_delivers_then_stops_when_receives_is_removed():
    public, subscribed = generated_for("public"), generated_for("public+subscribe")
    apply(subscribed)
    q = harness.queues()
    sub = json.loads((subscribed / "subscribers/payments-order-aggregate-updated.json").read_text())
    assert harness.rules_on("central-bus")[sub["name"]] == sub["filter"]
    d = put_internal(public_order_updated())
    e = harness.expect(q["subscriber:payments-order-aggregate-updated"], d["eventId"])
    assert e["detail"] == d

    removal = plan(public)
    check_snapshot("2-remove-cross-domain-receives", removal)
    assert {c["actions"][0] for c in removal} == {"delete"}
    apply(public)
    assert sub["name"] not in harness.rules_on("central-bus")
    d2 = put_internal(public_order_updated())
    harness.expect(harness.queues()["central_probe"], d2["eventId"])   # the bus still carries it
    assert "subscriber:payments-order-aggregate-updated" not in harness.queues()
    apply(BASELINE)


# ---- 3. a same-domain receives[] -------------------------------------------------------------------------

def test_same_domain_receives_changes_only_a_consumer_rule_on_the_domain_bus():
    own = generated_for("consume-own")
    assert generated_diff(BASELINE, own) == {"rules/orders-consumer-order-aggregate-updated.json", "deploy-order.json"}
    changes = plan(own)
    check_snapshot("3-add-same-domain-receives", changes)
    assert {c["actions"][0] for c in changes} == {"create"}
    assert {c["address"].split(".aws_")[0] for c in changes} == {'module.consumer_rule["orders-consumer-order-aggregate-updated"]'}
    apply(own)
    q = harness.queues()
    d = put_internal(harness.envelope(order={"orderId": "o-9"}, changedFields=["status"]))
    harness.expect(q["consumer:orders-consumer-order-aggregate-updated"], d["eventId"])
    harness.expect_none(q["central_probe"], d["eventId"], settle=5)   # still internal: never leaves orders-bus

    removal = plan(BASELINE)
    check_snapshot("3-remove-same-domain-receives", removal)
    apply(BASELINE)
    assert "orders-consumer-order-aggregate-updated" not in harness.rules_on("orders-bus")


# ---- 4. drift gates ---------------------------------------------------------------------------------------

def test_task_test_runs_the_drift_gates_before_the_suite():
    """`task test` in Spike B fails on catalog→generated drift (catalog-gen check) and on generated→applied drift
    (an empty plan) before any delivery test runs. Checked via task's dry run so it is cheap to assert here;
    Spike A's test_check_fails_after_one_character_edit proves the check itself bites."""
    dry = subprocess.run(["task", "-d", str(B), "--dry", "test"], stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, check=True).stdout
    assert "[gen:check] task -d" in dry   # task --dry does not descend into the nested Spike A task
    assert "-detailed-exitcode" in dry
    assert dry.index("[gen:check]") < dry.index("-detailed-exitcode") < dry.index("pytest")
