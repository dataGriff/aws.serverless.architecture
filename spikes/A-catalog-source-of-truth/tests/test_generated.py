"""Spike A — behavioural tests for catalog-gen and the checks. Names are the contract.

The catalog lives in ../catalog. Every build runs on a copy, because the generator writes the ODCS contracts into
the catalog beside their events; the repo copy is never touched by the tests.
"""
import json, os, shutil, subprocess, sys
from pathlib import Path
import pytest

ROOT = Path(__file__).resolve().parents[1]
CATALOG = ROOT / "catalog"
GEN = ROOT / "catalog-gen" / "catalog_gen.py"
CHECKS = ROOT / "checks"
FIXTURES = ROOT / "fixtures"
GOLDEN = ROOT / "tests" / "golden"
pytestmark = pytest.mark.skipif(not CATALOG.exists(), reason="create the catalog first (see README)")

sys.path.insert(0, str(CHECKS))
import run_checks  # noqa: E402

CATALOG_ODCS = {"catalog/events/OrderPlaced/odcs.yaml", "catalog/events/PaymentCaptured/odcs.yaml"}


def copy_catalog(tmp_path: Path, name="catalog") -> Path:
    c = tmp_path / name
    shutil.copytree(CATALOG, c, ignore=shutil.ignore_patterns("node_modules", "dist", ".astro", ".eventcatalog-core"))
    return c


def build(catalog: Path, out: Path, *extra) -> dict[str, str]:
    subprocess.run(["uv", "run", str(GEN), "build", "--catalog", str(catalog), "--out", str(out), *extra],
                   check=True, capture_output=True, text=True)
    files = {str(p.relative_to(out)): p.read_text() for p in out.rglob("*") if p.is_file()}
    files.update({"catalog/" + str(p.relative_to(catalog)): p.read_text() for p in catalog.glob("events/**/odcs.yaml")})
    return files


def gen(cmd: str, catalog: Path, out: Path, *extra) -> subprocess.CompletedProcess:
    return subprocess.run(["uv", "run", str(GEN), cmd, "--catalog", str(catalog), "--out", str(out), *extra],
                          capture_output=True, text=True)


def changed(before: dict, after: dict) -> set[str]:
    return {k for k in set(before) | set(after) if before.get(k) != after.get(k)}


def _mutated_catalog(tmp_path, mutate):
    c = copy_catalog(tmp_path)
    mutate(c)
    return c


# ---------------------------------------------------------------- determinism and drift


def test_build_is_deterministic(tmp_path):
    a = build(copy_catalog(tmp_path, "c1"), tmp_path / "a")
    b = build(copy_catalog(tmp_path, "c2"), tmp_path / "b")
    assert a == b


def test_golden_snapshot(tmp_path):
    files = build(copy_catalog(tmp_path), tmp_path / "out")
    if os.environ.get("UPDATE_GOLDEN"):
        shutil.rmtree(GOLDEN, ignore_errors=True)
        for rel, content in files.items():
            p = GOLDEN / rel
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(content)
    golden = {str(p.relative_to(GOLDEN)): p.read_text() for p in GOLDEN.rglob("*") if p.is_file()}
    assert golden, "no golden files; run UPDATE_GOLDEN=1 pytest"
    assert changed(golden, files) == set(), "generated output drifted from tests/golden (UPDATE_GOLDEN=1 to accept)"


@pytest.mark.parametrize("target", ["rules/orders-fan-out.json", "parquet/OrderPlaced.v1.json", "catalog/events/OrderPlaced/odcs.yaml"])
def test_check_fails_after_one_character_edit(tmp_path, target):
    c = copy_catalog(tmp_path)
    out = tmp_path / "out"
    build(c, out)
    assert gen("check", c, out).returncode == 0
    p = (c / target[len("catalog/"):]) if target.startswith("catalog/") else out / target
    p.write_text(p.read_text() + " ")
    r = gen("check", c, out)
    assert r.returncode != 0 and f"DRIFT {target}" in r.stdout


def test_check_fails_on_stray_and_missing_files(tmp_path):
    c = copy_catalog(tmp_path)
    out = tmp_path / "out"
    build(c, out)
    (out / "rules" / "hand-made.json").write_text("{}\n")
    (out / "archive" / "routing-map.json").unlink()
    r = gen("check", c, out)
    assert "DRIFT rules/hand-made.json  (not generated)" in r.stdout
    assert "DRIFT archive/routing-map.json  (missing on disk)" in r.stdout


# ---------------------------------------------------------------- exact change sets


def test_flip_visibility_changes_exactly_the_expected_files(tmp_path):
    before = build(copy_catalog(tmp_path, "before-cat"), tmp_path / "before")

    def flip(c: Path):
        md = next(c.glob("events/order.aggregate.updated/**/index.md*"))
        md.write_text(md.read_text().replace("visibility: internal", "visibility: public"))

    after = build(_mutated_catalog(tmp_path, flip), tmp_path / "after")
    expected = {
        "rules/orders-public-forward.json",
        "archive/routing-map.json",
        "validation/orders.json",
        "parquet/order.aggregate.updated.v1.json",
        "catalog/events/order.aggregate.updated/odcs.yaml",
        "deploy-order.json",
    }
    assert changed(before, after) == expected
    assert "order.aggregate.updated.v1" in json.loads(after["rules/orders-public-forward.json"])["detail-type"]


def test_add_receives_changes_only_consumer_pattern_and_manifest(tmp_path):
    before = build(copy_catalog(tmp_path, "before-cat"), tmp_path / "before")

    def subscribe(c: Path):
        md = next(c.glob("services/payment-service/index.md*"))
        md.write_text(md.read_text().replace("receives:", "receives:\n  - id: CustomerRegistered\n    version: 1.0.0", 1))

    after = build(_mutated_catalog(tmp_path, subscribe), tmp_path / "after")
    assert changed(before, after) == {"rules/payments-consumer-customer-registered.json", "deploy-order.json"}
    assert json.loads(after["rules/payments-consumer-customer-registered.json"]) == {"detail-type": ["CustomerRegistered.v1"]}
    assert json.loads(after["deploy-order.json"])["consumers"]["rules/payments-consumer-customer-registered.json"] == ["payment-service"]


def test_consumer_rules_ignore_commands_and_queries(tmp_path):
    files = build(copy_catalog(tmp_path), tmp_path / "out")
    assert not [k for k in files if "consumer-get-order" in k or "consumer-place-order" in k]
    assert set(k for k in files if "-consumer-" in k) == {"rules/orders-consumer-payment-captured.json", "rules/payments-consumer-order-placed.json"}


# ---------------------------------------------------------------- pattern size


def twelve_public(tmp_path: Path) -> Path:
    """The real catalog plus ten more public orders events: twelve public events in total."""
    c = copy_catalog(tmp_path, "twelve")
    svc = c / "services/order-service/index.mdx"
    extra = ""
    for i in range(1, 11):
        name = f"OrderPlacedVariant{i:02d}"
        shutil.copytree(c / "events/OrderPlaced", c / "events" / name, ignore=shutil.ignore_patterns("odcs.yaml", "examples"))
        md = c / "events" / name / "index.mdx"
        md.write_text(md.read_text().replace("id: OrderPlaced\n", f"id: {name}\n", 1))
        extra += f"  - id: {name}\n    version: 1.0.0\n    to:\n      - id: orders-bus\n      - id: central-bus\n"
    svc.write_text(svc.read_text().replace("sends:\n", "sends:\n" + extra, 1))
    return c


def test_patterns_under_4kb_or_split(tmp_path):
    c = twelve_public(tmp_path)
    files = build(c, tmp_path / "out")
    assert sum(1 for k in files if k.startswith("parquet/")) == 12
    for k, v in files.items():
        if k.startswith("rules/"):
            assert len(json.dumps(json.loads(v), separators=(",", ":"))) < 4096, k
    assert not json.loads(files["deploy-order.json"])["splitRules"]


def test_generator_splits_forward_pattern_at_the_limit(tmp_path):
    c = twelve_public(tmp_path)
    full = json.loads(build(c, tmp_path / "full")["rules/orders-public-forward.json"])["detail-type"]
    files = build(c, tmp_path / "split", "--pattern-limit", "160")
    parts = sorted(k for k in files if k.startswith("rules/orders-public-forward.part-"))
    assert len(parts) > 1 and "rules/orders-public-forward.json" not in files
    union = []
    for k in parts:
        p = json.loads(files[k])
        assert len(json.dumps(p, separators=(",", ":"))) < 160, k
        assert p["source"] == [{"prefix": "orders."}]
        union += p["detail-type"]
    assert union == full
    assert json.loads(files["deploy-order.json"])["splitRules"] == parts


# ---------------------------------------------------------------- checks


CHECK_NAMES = [c.__name__ for c in run_checks.CHECKS]


@pytest.mark.parametrize("check", CHECK_NAMES)
def test_each_check_fails_on_its_fixture_and_passes_on_clean(tmp_path, check):
    fixture = FIXTURES / "checks" / check
    assert fixture.is_dir(), f"no fixture for {check}"
    clean = copy_catalog(tmp_path, "clean")
    base = clean if check == "check_schema_diff" else None
    assert run_checks.run(clean, base, only=check)[check] == []
    broken = copy_catalog(tmp_path, "broken")
    shutil.copytree(fixture, broken, dirs_exist_ok=True)
    fails = run_checks.run(broken, base, only=check)[check]
    assert fails, f"{check} passed on its own fixture"


def test_all_checks_pass_on_clean_catalog_via_cli(tmp_path):
    c = copy_catalog(tmp_path)
    r = subprocess.run(["uv", "run", str(CHECKS / "run_checks.py"), "--catalog", str(c), "--base", str(c)], capture_output=True, text=True)
    assert r.returncode == 0, r.stdout
    assert r.stdout.count("OK   ") == len(CHECK_NAMES)


def test_schema_diff_cli_flags_removed_field():
    r = subprocess.run(["uv", "run", str(CHECKS / "schema_diff.py"), str(CATALOG / "events/OrderPlaced/schema.json"),
                        str(FIXTURES / "schema-diff/OrderPlaced.v2.removes-customerEmail.json")], capture_output=True, text=True)
    assert r.returncode == 1 and "BREAKING removed property customerEmail" in r.stdout
    same = subprocess.run(["uv", "run", str(CHECKS / "schema_diff.py"), str(CATALOG / "events/OrderPlaced/schema.json"),
                           str(CATALOG / "events/OrderPlaced/schema.json")], capture_output=True, text=True)
    assert same.returncode == 0


def test_validation_bundle_accepts_examples_and_rejects_clear_text_direct(tmp_path):
    import jsonschema
    files = build(copy_catalog(tmp_path), tmp_path / "out")
    bundle = json.loads(files["validation/orders.json"])["OrderPlaced.v1"]
    assert bundle["ciphertextFields"] == ["customerEmail"]
    validator = jsonschema.Draft202012Validator(bundle["schema"])
    for ex in (CATALOG / "events/OrderPlaced/examples").glob("*.json"):
        detail = json.loads(ex.read_text())["detail"]
        assert not list(validator.iter_errors(detail)), ex.name
        detail["customerEmail"] = "jo.bloggs@example.com"
        assert list(validator.iter_errors(detail)), "clear text in a direct field must fail validation"


def test_overlay_may_not_set_generated_keys(tmp_path):
    def conflict(c: Path):
        p = c / "events/OrderPlaced/data-product.yaml"
        p.write_text(p.read_text() + "schema:\n  - name: hand-written\n")
    r = gen("build", _mutated_catalog(tmp_path, conflict), tmp_path / "out")
    assert r.returncode != 0 and "overlay may not set generated keys ['schema']" in r.stderr


def test_explain_names_the_catalog_files_that_drive_a_generated_file(tmp_path):
    c = copy_catalog(tmp_path)
    out = tmp_path / "out"
    build(c, out)
    r = gen("explain", c, out, "catalog/events/OrderPlaced/odcs.yaml")
    assert r.returncode == 0
    assert "emitter: emit_odcs" in r.stdout
    for src in ("events/OrderPlaced/schema.json", "events/OrderPlaced/data-product.yaml", "schemas/Money.json", "domains/orders"):
        assert src in r.stdout, r.stdout
    r = gen("explain", c, out, "rules/payments-consumer-order-placed.json")
    assert "services/payment-service" in r.stdout and "events/OrderPlaced" in r.stdout
    assert gen("explain", c, out, "rules/nothing.json").returncode == 1


# ---------------------------------------------------------------- external linters (need npx / uvx)


@pytest.mark.slow
def test_spectral_fails_on_fixture_and_passes_on_catalog():
    def lint(path: Path):
        return subprocess.run(["npx", "-y", "@stoplight/spectral-cli", "lint", "-r", str(CHECKS / "spectral.yaml"), "-f", "json", str(path)],
                              capture_output=True, text=True, cwd=ROOT)
    good = lint(CATALOG / "services/order-service/openapi.yaml")
    assert good.returncode == 0, good.stdout
    bad = lint(FIXTURES / "spectral/openapi-bad.yaml")
    assert bad.returncode != 0
    codes = {r["code"] for r in json.loads(bad.stdout)}
    assert {"path-must-be-versioned", "operation-has-message-type", "post-requires-idempotency-key", "errors-are-problem-json",
            "security-declared", "commands-are-post", "correlation-id-accepted"} <= codes, codes


@pytest.mark.slow
def test_odcs_lint_passes_generated_and_fails_fixture(tmp_path):
    c = copy_catalog(tmp_path)
    build(c, tmp_path / "out")

    def lint(path: Path):
        return subprocess.run(["uvx", "--from", "datacontract-cli", "datacontract", "lint", str(path)], capture_output=True, text=True)
    for p in c.glob("events/**/odcs.yaml"):
        assert lint(p).returncode == 0, p
    assert lint(FIXTURES / "odcs/bad.odcs.yaml").returncode != 0
