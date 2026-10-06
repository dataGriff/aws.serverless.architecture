"""Behaviour-through-the-catalog plumbing: copy the catalog, mutate it, regenerate, plan/apply Spike B's
Terraform against that generator output, and reduce a plan to the reviewable set of changes.

Nothing here edits the real catalog or generated/local: every scenario lives under .scenarios/<name>/.
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
from pathlib import Path

HERE = Path(__file__).resolve().parents[1]
SPIKES = HERE.parent
A = SPIKES / "A-catalog-source-of-truth"
B = SPIKES / "B-localstack-buses-end-to-end"
TF_DIR = B / "terraform" / "envs" / "local"
GEN = SPIKES.parent / "platform" / "catalog-gen" / "catalog_gen.py"
BASELINE = A / "generated" / "local"
SCENARIOS = HERE / ".scenarios"
SNAPSHOTS = HERE / "snapshots"
ENV = {**os.environ, "AWS_ENDPOINT_URL": "http://localhost:4566", "AWS_ACCESS_KEY_ID": "test",
       "AWS_SECRET_ACCESS_KEY": "test", "AWS_DEFAULT_REGION": "eu-west-1"}

INTERNAL = "events/order.aggregate.updated/index.mdx"
PAYMENT_SERVICE = "services/payment-service/index.mdx"
ORDER_SERVICE = "services/order-service/index.mdx"


def _edit(path: Path, old: str, new: str) -> None:
    text = path.read_text()
    assert old in text, f"{path.name}: {old!r} not found"
    path.write_text(text.replace(old, new, 1))


# ---- the catalog edits a domain team would open a PR for -----------------------------------------------

def make_public(c: Path) -> None:
    """order.aggregate.updated becomes public. On the wire its `direct` field (order) must then be ciphertext."""
    _edit(c / INTERNAL, "x-visibility: internal", "x-visibility: public")


def payments_receives_internal_turned_public(c: Path) -> None:
    """payment-service subscribes to order.aggregate.updated (cross-domain → a subscriber on central)."""
    _edit(c / PAYMENT_SERVICE, "receives:\n",
          "receives:\n  - id: order.aggregate.updated\n    version: 1.0.0\n    from:\n      - id: payments-sub.order.aggregate.updated.v1\n")


def orders_consumes_its_own_internal_event(c: Path) -> None:
    """order-service subscribes to its own internal event (same domain → a consumer rule on orders-bus)."""
    _edit(c / ORDER_SERVICE, "receives:\n",
          "receives:\n  - id: order.aggregate.updated\n    version: 1.0.0\n    from:\n      - id: orders-bus.order.aggregate.updated.v1\n")


SCENARIO_EDITS = {
    "public": [make_public],
    "public+subscribe": [make_public, payments_receives_internal_turned_public],
    "consume-own": [orders_consumes_its_own_internal_event],
}


def generated_for(name: str) -> Path:
    """Build generator output for a scenario (or return the baseline for 'baseline'); idempotent per run."""
    if name == "baseline":
        return BASELINE
    root = SCENARIOS / name
    catalog, out = root / "catalog", root / "generated"
    if root.exists():
        shutil.rmtree(root)
    shutil.copytree(A / "catalog", catalog, ignore=shutil.ignore_patterns("node_modules", "dist", ".astro", ".eventcatalog-core"))
    for edit in SCENARIO_EDITS[name]:
        edit(catalog)
    subprocess.run(["uv", "run", str(GEN), "build", "--catalog", str(catalog), "--out", str(out)],
                   check=True, capture_output=True, text=True)
    return out


def generated_diff(before: Path, after: Path) -> set[str]:
    def files(d: Path) -> dict[str, str]:
        return {str(p.relative_to(d)): p.read_text() for p in d.rglob("*") if p.is_file()}
    a, b = files(before), files(after)
    return {k for k in set(a) | set(b) if a.get(k) != b.get(k)}


# ---- terraform ------------------------------------------------------------------------------------------

def _tf(*args: str, check: bool = True) -> subprocess.CompletedProcess:
    return subprocess.run(["terraform", f"-chdir={TF_DIR}", *args], env=ENV, capture_output=True, text=True, check=check)


def plan(generated: Path) -> list[dict]:
    """Plan Spike B's env against `generated` and return the reduced change set."""
    out = SCENARIOS / "plan.bin"
    out.parent.mkdir(exist_ok=True)
    r = _tf("plan", "-input=false", "-detailed-exitcode", f"-var=generated_dir={generated}", f"-out={out}", check=False)
    assert r.returncode in (0, 2), r.stderr
    show = _tf("show", "-json", str(out))
    return reduce_plan(json.loads(show.stdout))


CURRENT: list[Path] = [BASELINE]   # what the last apply() in this process pointed LocalStack at


def apply(generated: Path) -> None:
    _tf("apply", "-input=false", "-auto-approve", f"-var=generated_dir={generated}")
    CURRENT[0] = generated
    for cache in B.glob(".*.json"):
        cache.unlink()


def plan_is_empty(generated: Path) -> bool:
    return _tf("plan", "-input=false", "-detailed-exitcode", f"-var=generated_dir={generated}", check=False).returncode == 0


def reduce_plan(plan_json: dict) -> list[dict]:
    """Address, action and the attributes that change for every resource the plan touches, plus the before/after
    event pattern for rules and environment for the archive shim: the "exact set of changes" a reviewer reads."""
    out = []
    for rc in plan_json.get("resource_changes", []):
        ch = rc["change"]
        actions = ch["actions"]
        if actions in (["no-op"], ["read"]):
            continue
        before, after, unknown = ch.get("before") or {}, ch.get("after") or {}, ch.get("after_unknown") or {}
        entry = {"address": rc["address"], "actions": actions}
        if actions == ["update"]:
            entry["changed"] = sorted(k for k in set(before) | set(after)
                                      if before.get(k) != after.get(k) and unknown.get(k) is not True)
            if rc["type"] == "aws_cloudwatch_event_rule":
                entry["event_pattern"] = {"before": json.loads(before["event_pattern"]), "after": json.loads(after["event_pattern"])}
            if rc["type"] == "aws_lambda_function":
                env = lambda side: (side.get("environment") or [{}])[0].get("variables", {})  # noqa: E731
                entry["environment"] = {"before": env(before), "after": env(after)}
        out.append(entry)
    return sorted(out, key=lambda e: e["address"])


def check_snapshot(name: str, changes: list[dict]) -> None:
    """Compare with snapshots/<name>.json; UPDATE_SNAPSHOTS=1 rewrites it."""
    path = SNAPSHOTS / f"{name}.json"
    text = json.dumps(changes, indent=2, sort_keys=True) + "\n"
    if os.environ.get("UPDATE_SNAPSHOTS"):
        SNAPSHOTS.mkdir(exist_ok=True)
        path.write_text(text)
    assert path.exists(), f"no snapshot for {name}; review the plan below and run UPDATE_SNAPSHOTS=1 to create snapshots/{name}.json:\n{text}"
    assert path.read_text() == text, f"plan for {name} differs from snapshots/{name}.json (UPDATE_SNAPSHOTS=1 to accept):\n{text}"
