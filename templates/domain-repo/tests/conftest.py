"""Fixtures for a domain's L0 and L1 suites. L0 needs only the pinned catalog and the generator's output; L1 needs
LocalStack up and `task apply` done. `platform_testing` comes from the pinned platform checkout (pytest.ini pythonpath)."""
from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
DOMAIN = os.environ.get("DOMAIN", "sample")
CATALOG = Path(os.environ.get("PLATFORM_CATALOG", ROOT / ".catalog" / "catalog"))
GENERATED = Path(os.environ.get("GENERATED", ROOT / "generated" / "local"))


@pytest.fixture(scope="session")
def catalog() -> Path:
    if not CATALOG.exists():
        pytest.skip(f"no catalog at {CATALOG}: run `task catalog:checkout` (pins.yaml) or set PLATFORM_CATALOG")
    return CATALOG


@pytest.fixture(scope="session")
def validation_bundle(catalog) -> dict:
    """detail-type -> {source, schema, ciphertextFields} for this domain, as the archive validator sees it."""
    f = GENERATED / "validation" / f"{DOMAIN}.json"
    if not f.exists():
        pytest.skip(f"no validation bundle at {f}: run `task gen`")
    return json.loads(f.read_text())


@pytest.fixture(scope="session")
def harness():
    """platform_testing, pointed at this repo's Terraform env (PLATFORM_TF_DIR) and the pinned catalog."""
    try:
        import platform_testing
    except ImportError:
        pytest.skip("platform_testing not importable: pin the platform checkout (pins.yaml) and check pytest.ini pythonpath")
    if not (Path(os.environ.get("PLATFORM_TF_DIR", ROOT / "terraform/envs/local")) / "terraform.tfstate").exists():
        pytest.skip("domain-local env not applied: `task up && task apply`")
    return platform_testing
