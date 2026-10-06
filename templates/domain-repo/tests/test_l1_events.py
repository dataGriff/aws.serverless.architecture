"""L1 · domain-local event tests on LocalStack with the pinned platform-local (testing.md). The names are the
contract from prompt 03 (step 1): fill the bodies in, do not rename them. Each uses `harness` (platform_testing)."""
import pytest

pytestmark = pytest.mark.l1
TODO = "step 1 (prompt 03) fills this in; the name is the acceptance criterion"


@pytest.mark.skip(reason=TODO)
def test_public_event_reaches_central_and_bronze_with_shape_intact(harness): ...


@pytest.mark.skip(reason=TODO)
def test_internal_event_never_leaves_domain_bus(harness): ...


@pytest.mark.skip(reason=TODO)
def test_nothing_is_ever_delivered_back_to_a_domain_bus(harness): ...


@pytest.mark.skip(reason=TODO)
@pytest.mark.sandbox
def test_dlq_catches_broken_target(harness): ...


@pytest.mark.skip(reason=TODO)
def test_bad_payload_is_quarantined_with_alarm(harness): ...


@pytest.mark.skip(reason=TODO)
def test_direct_field_in_clear_is_quarantined(harness): ...


@pytest.mark.skip(reason=TODO)
def test_cross_hour_duplicate_yields_one_silver_row(harness): ...


@pytest.mark.skip(reason=TODO)
def test_rerun_window_is_idempotent(harness): ...


@pytest.mark.skip(reason=TODO)
@pytest.mark.sandbox
def test_replay_flag_causes_no_side_effect(harness): ...


@pytest.mark.skip(reason=TODO)
def test_direct_field_ciphertext_in_bronze_and_absent_from_silver_columns(harness): ...


@pytest.mark.skip(reason=TODO)
def test_granted_role_decrypts_ungranted_cannot(harness): ...


@pytest.mark.skip(reason=TODO)
def test_silver_passes_odcs_contract(harness): ...
