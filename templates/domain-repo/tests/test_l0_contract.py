"""L0 · contract tests (testing.md). No infrastructure: the catalog's own examples for this domain's public events must
validate against the generated validation bundle, which is the schema the archive enforces on AWS and locally
(envelope flattened in, `direct` fields typed as the ciphertext envelope). Replace `example_events` with events built
by this domain's own code as soon as there is any; the assertion stays the same."""
from __future__ import annotations

import json
from pathlib import Path

import fastjsonschema
import pytest

from conftest import DOMAIN

pytestmark = pytest.mark.l0


def example_events(catalog: Path, bundle: dict) -> list[tuple[str, Path, dict]]:
    out = []
    for detail_type in bundle:
        name = detail_type.rsplit(".v", 1)[0]
        for ex in sorted((catalog / "events" / name / "examples").glob("*.json")):
            out.append((detail_type, ex, json.loads(ex.read_text())))
    return out


def test_every_public_example_validates_against_the_generated_bundle(catalog, validation_bundle):
    cases = example_events(catalog, validation_bundle)
    assert cases, f"domain {DOMAIN} has no public event examples; a public event needs two (conventions.md)"
    for detail_type, path, envelope in cases:
        entry = validation_bundle[detail_type]
        assert envelope["source"] == entry["source"], f"{path.name}: source {envelope['source']} is not {entry['source']}"
        assert envelope["detail-type"] == detail_type
        fastjsonschema.validate(entry["schema"], envelope["detail"])


def test_direct_fields_are_ciphertext_in_public_examples(catalog, validation_bundle):
    for detail_type, path, envelope in example_events(catalog, validation_bundle):
        for field in validation_bundle[detail_type].get("ciphertextFields", []):
            value = envelope["detail"].get(field)
            assert isinstance(value, dict) and set(value) == {"enc", "kid", "ct"}, \
                f"{path.name}: {field} is x-pii direct on a public event and must travel as a ciphertext envelope (pii.md)"


def test_clear_text_direct_field_is_rejected(catalog, validation_bundle):
    """The negative case the archive's `pii-in-clear` quarantine relies on."""
    for detail_type, path, envelope in example_events(catalog, validation_bundle):
        for field in validation_bundle[detail_type].get("ciphertextFields", []):
            broken = {**envelope["detail"], field: "jo.bloggs@example.com"}
            with pytest.raises(fastjsonschema.JsonSchemaException):
                fastjsonschema.validate(validation_bundle[detail_type]["schema"], broken)
