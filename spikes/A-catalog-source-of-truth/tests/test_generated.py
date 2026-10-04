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
    files.update({"catalog/" + str(p.relative_to(catalog)): p.read_text() for p in catalog.glob("channels/*/index.mdx")
                  if "x-generated: catalog-gen" in p.read_text()})
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
        "catalog/channels/orders-bus.order.aggregate.updated.v1/index.mdx",      # gains the route to central
        "catalog/channels/central-bus.order.aggregate.updated.v1/index.mdx",     # new logical channel on central
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
    # ADR-021: a cross-domain receives[] is a subscriber on central plus its logical channel, nothing on any bus rule.
    assert changed(before, after) == {
        "subscribers/payments-customer-registered.json",
        "catalog/channels/payments-sub.CustomerRegistered.v1/index.mdx",
        "deploy-order.json",
    }
    sub = json.loads(after["subscribers/payments-customer-registered.json"])
    assert sub["filter"] == {"detail-type": ["CustomerRegistered.v1"]}
    assert sub["retryPolicy"] == {"maximumRetryAttempts": 185, "maximumEventAgeInSeconds": 86400}
    assert sub["targets"] == ["payment-service"]
    assert json.loads(after["deploy-order.json"])["consumers"]["subscribers/payments-customer-registered.json"] == ["payment-service"]


def test_consumer_rules_ignore_commands_and_queries(tmp_path):
    files = build(copy_catalog(tmp_path), tmp_path / "out")
    assert not [k for k in files if "get-order" in k or "place-order" in k]
    # Both receives[] in the catalog are cross-domain, so they are subscribers on central, not rules on a domain bus.
    assert not [k for k in files if "-consumer-" in k]
    assert set(k for k in files if k.startswith("subscribers/")) == {"subscribers/orders-payment-captured.json", "subscribers/payments-order-placed.json"}
    sub = json.loads(files["subscribers/payments-order-placed.json"])
    assert sub["filter"] == {"detail-type": ["OrderPlaced.v1"], "source": [{"prefix": "orders."}]}
    assert sub["channels"] == ["payments-sub.OrderPlaced.v1"]


def test_logical_channels_form_a_straight_line_per_event(tmp_path):
    import frontmatter
    files = build(copy_catalog(tmp_path), tmp_path / "out")
    chans = {k.split("/")[2]: frontmatter.loads(v) for k, v in files.items() if k.startswith("catalog/channels/")}
    assert set(chans) == {
        "orders-bus.OrderPlaced.v1", "orders-bus.order.aggregate.updated.v1", "payments-bus.PaymentCaptured.v1",
        "central-bus.OrderPlaced.v1", "central-bus.PaymentCaptured.v1",
        "payments-sub.OrderPlaced.v1", "orders-sub.PaymentCaptured.v1",
    }
    route = lambda c: [r["id"] for r in chans[c].get("routes", [])]
    assert route("orders-bus.OrderPlaced.v1") == ["central-bus.OrderPlaced.v1"]
    assert route("central-bus.OrderPlaced.v1") == ["payments-sub.OrderPlaced.v1"]
    assert route("payments-sub.OrderPlaced.v1") == []
    assert route("orders-bus.order.aggregate.updated.v1") == [], "internal events never route to central"
    for c, fm in chans.items():
        assert fm["x-generated"] == "catalog-gen" and fm["x-physical-channel"] in ("orders-bus", "payments-bus", "central-bus"), c
    # no physical channel ever appears as a route target or source: the graph is acyclic by construction
    targets = {t for c in chans for t in route(c)}
    assert targets <= set(chans) and not targets & {"orders-bus", "payments-bus", "central-bus"}


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
    r = gen("explain", c, out, "subscribers/payments-order-placed.json")
    assert "emitter: emit_subscribers" in r.stdout
    assert "services/payment-service" in r.stdout and "events/OrderPlaced" in r.stdout
    r = gen("explain", c, out, "catalog/channels/central-bus.OrderPlaced.v1/index.mdx")
    assert "emitter: emit_channels" in r.stdout and "services/payment-service" in r.stdout
    assert gen("explain", c, out, "rules/nothing.json").returncode == 1


# ---------------------------------------------------------------- loader and version guards (code-review findings)


def test_missing_schema_path_fails_the_build(tmp_path):
    def typo(c: Path):
        md = c / "events/OrderPlaced/index.mdx"
        md.write_text(md.read_text().replace("schemaPath: schema.json", "schemaPath: schmea.json"))
    r = gen("build", _mutated_catalog(tmp_path, typo), tmp_path / "out")
    assert r.returncode != 0 and "schmea.json" in r.stderr


def test_dangling_ref_fails_build_and_is_reported_by_checks(tmp_path):
    broken = copy_catalog(tmp_path)
    shutil.copytree(FIXTURES / "checks/check_refs_into_schemas", broken, dirs_exist_ok=True)
    r = gen("build", broken, tmp_path / "out")
    assert r.returncode != 0 and "does not resolve" in r.stderr and "Traceback" not in r.stderr
    results = run_checks.run(broken)                      # every check runs; none tracebacks
    assert any("does not resolve" in f for f in results["check_refs_into_schemas"])


def test_undeclared_domain_fails_the_build(tmp_path):
    def orphan(c: Path):
        md = c / "services/payment-service/index.mdx"
        md.write_text(md.read_text().replace("x-account: payments", "x-domain: shipping\nx-account: payments"))
    r = gen("build", _mutated_catalog(tmp_path, orphan), tmp_path / "out")
    assert r.returncode != 0 and "domains/shipping/index.mdx" in r.stderr and "Traceback" not in r.stderr


def test_domain_without_public_events_gets_no_forward_rule(tmp_path):
    def privatise(c: Path):
        md = c / "events/PaymentCaptured/index.mdx"
        md.write_text(md.read_text().replace("x-visibility: public", "x-visibility: internal"))
        svc = c / "services/order-service/index.mdx"
        svc.write_text(svc.read_text().replace("orders-sub.PaymentCaptured.v1", "payments-bus.PaymentCaptured.v1"))
    files = build(_mutated_catalog(tmp_path, privatise), tmp_path / "out")
    assert "rules/payments-public-forward.json" not in files
    assert all('"detail-type": []' not in v for k, v in files.items() if k.startswith("rules/"))


def test_unmatched_receives_version_fails_instead_of_falling_back(tmp_path):
    def wrong(c: Path):
        md = c / "services/payment-service/index.mdx"
        md.write_text(md.read_text().replace("- id: OrderPlaced\n    version: 1.0.0", "- id: OrderPlaced\n    version: 3.0.0"))
    r = gen("build", _mutated_catalog(tmp_path, wrong), tmp_path / "out")
    assert r.returncode != 0 and "version '3.0.0' matches none of ['OrderPlaced.v1']" in r.stderr


def test_second_event_version_keeps_generator_and_check_consistent(tmp_path):
    """OrderPlaced v2 is current, v1 is kept under versioned/; payments still receives v1 (caret range).
    The generator emits channels for the versions that are named; the topology check expects exactly those."""
    def bump(c: Path):
        ev = c / "events/OrderPlaced"
        old = ev / "versioned/1"
        old.mkdir(parents=True)
        for f in ("index.mdx", "schema.json", "data-product.yaml"):
            shutil.copy(ev / f, old / f)
        (ev / "index.mdx").write_text((ev / "index.mdx").read_text().replace("version: 1.0.0", "version: 2.0.0"))
        ps = c / "services/payment-service/index.mdx"
        ps.write_text(ps.read_text().replace("- id: OrderPlaced\n    version: 1.0.0", "- id: OrderPlaced\n    version: ^1.0.0"))
        os_ = c / "services/order-service/index.mdx"
        os_.write_text(os_.read_text().replace("- id: OrderPlaced\n    version: 1.0.0\n    to:\n      - id: orders-bus.OrderPlaced.v1",
                                               "- id: OrderPlaced\n    version: 2.0.0\n    to:\n      - id: orders-bus.OrderPlaced.v2"))
    c = _mutated_catalog(tmp_path, bump)
    files = build(c, tmp_path / "out")
    assert "catalog/channels/payments-sub.OrderPlaced.v1/index.mdx" in files
    assert "catalog/channels/payments-sub.OrderPlaced.v2/index.mdx" not in files
    assert {"catalog/channels/orders-bus.OrderPlaced.v1/index.mdx", "catalog/channels/orders-bus.OrderPlaced.v2/index.mdx"} <= set(files)
    assert "catalog/events/OrderPlaced/versioned/1/odcs.yaml" in files
    assert json.loads(files["subscribers/payments-order-placed.json"])["filter"]["detail-type"] == ["OrderPlaced.v1"]
    assert run_checks.run(c, only="check_channel_topology")["check_channel_topology"] == []


def test_forward_rule_reference_on_channel_pages_matches_split_files(tmp_path):
    import frontmatter
    files = build(twelve_public(tmp_path), tmp_path / "split", "--pattern-limit", "160")
    parts = sorted(k for k in files if k.startswith("rules/orders-public-forward.part-"))
    page = frontmatter.loads(files["catalog/channels/orders-bus.OrderPlaced.v1/index.mdx"])
    assert page["x-forward-rules"] == parts and all(p in files for p in page["x-forward-rules"])


def test_misspelled_only_fails():
    r = subprocess.run(["uv", "run", str(CHECKS / "run_checks.py"), "--catalog", str(CATALOG), "--only", "check_channel_topolgy"],
                       capture_output=True, text=True)
    assert r.returncode != 0 and "matches no check" in r.stderr


def test_example_check_uses_the_generators_ciphertext_schema(tmp_path):
    def loosen(c: Path):
        ex = c / "events/OrderPlaced/examples/order-placed.json"
        doc = json.loads(ex.read_text())
        doc["detail"]["customerEmail"] = {"enc": "v1", "kid": "", "ct": "", "extra": 1}
        ex.write_text(json.dumps(doc))
    fails = run_checks.run(_mutated_catalog(tmp_path, loosen), only="check_examples_match_schema")["check_examples_match_schema"]
    assert fails, "an envelope the Firehose validator would quarantine must fail the example check"


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
