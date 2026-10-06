"""L1 · the domain's own API from its catalog spec, through gateway validation (testing.md). Schemathesis drives
`test_api_conforms_to_spec` (`task schemathesis` is the same run from the command line); the other two assert the
gateway and the outbox. Names from prompt 03; fill in, do not rename."""
import pytest

pytestmark = pytest.mark.l1
TODO = "step 1 (prompt 03) fills this in; the name is the acceptance criterion"


@pytest.mark.skip(reason=TODO + " — schemathesis.from_path(<catalog>/services/<domain>-service/openapi.yaml, base_url=API_URL)")
def test_api_conforms_to_spec(harness): ...


@pytest.mark.skip(reason=TODO)
def test_gateway_rejects_invalid_body(harness): ...


@pytest.mark.skip(reason=TODO)
def test_command_produces_event_with_correlation_id(harness): ...
