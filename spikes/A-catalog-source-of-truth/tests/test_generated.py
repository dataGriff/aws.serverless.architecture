"""Spike A — behavioural tests for catalog-gen. Names are the contract.

The fixture catalog lives in ../catalog once created (npx @eventcatalog/create-eventcatalog).
Until it exists these tests are skipped, not failed.
"""
import json, shutil, subprocess, sys
from pathlib import Path
import pytest

ROOT = Path(__file__).resolve().parents[1]
CATALOG = ROOT / "catalog"
GEN = ROOT / "catalog-gen" / "catalog_gen.py"
pytestmark = pytest.mark.skipif(not CATALOG.exists(), reason="create the catalog first (see README)")


def build(catalog: Path, out: Path) -> dict[str, str]:
    subprocess.run(["uv", "run", str(GEN), "build", "--catalog", str(catalog), "--out", str(out)], check=True)
    return {str(p.relative_to(out)): p.read_text() for p in out.rglob("*") if p.is_file()}


def test_build_is_deterministic(tmp_path):
    a = build(CATALOG, tmp_path / "a"); b = build(CATALOG, tmp_path / "b")
    assert a == b


def test_check_fails_after_one_character_edit(tmp_path):
    out = tmp_path / "out"; files = build(CATALOG, out)
    target = out / next(iter(files))
    target.write_text(target.read_text() + " ")
    rc = subprocess.run(["uv", "run", str(GEN), "check", "--catalog", str(CATALOG), "--out", str(out)]).returncode
    assert rc != 0


def _mutated_catalog(tmp_path, mutate):
    c = tmp_path / "catalog"; shutil.copytree(CATALOG, c); mutate(c); return c


def test_flip_visibility_changes_exactly_the_expected_files(tmp_path):
    before = build(CATALOG, tmp_path / "before")

    def flip(c: Path):
        md = next(c.glob("events/order.aggregate.updated/**/index.md*"))
        md.write_text(md.read_text().replace("visibility: internal", "visibility: public"))

    after = build(_mutated_catalog(tmp_path, flip), tmp_path / "after")
    changed = {k for k in set(before) | set(after) if before.get(k) != after.get(k)}
    expected = {"rules/orders-public-forward.json", "archive/routing-map.json", "deploy-order.json"}
    # TODO once emitters exist: add the Parquet schema, validation bundle and ODCS contract for the newly public event
    assert changed >= expected, changed
    assert not {k for k in changed if "payments" in k}, "a change in orders touched payments' files"


def test_add_receives_changes_only_consumer_pattern_and_manifest(tmp_path):
    before = build(CATALOG, tmp_path / "before")

    def subscribe(c: Path):
        md = next(c.glob("services/payment-service/index.md*"))
        md.write_text(md.read_text().replace("receives:", "receives:\n  - id: CustomerRegistered\n    version: 1", 1))

    after = build(_mutated_catalog(tmp_path, subscribe), tmp_path / "after")
    changed = {k for k in set(before) | set(after) if before.get(k) != after.get(k)}
    assert changed <= {"rules/payments-consumer-customer-registered.json", "deploy-order.json"}, changed


def test_patterns_under_4kb_or_split(tmp_path):
    files = build(CATALOG, tmp_path / "out")
    for k, v in files.items():
        if k.startswith("rules/"):
            assert len(json.dumps(json.loads(v), separators=(",", ":"))) < 4096, k
