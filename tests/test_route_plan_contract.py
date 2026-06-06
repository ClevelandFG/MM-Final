from pathlib import Path

from mm_final.contracts import REQUIRED_VISIT_NODES, load_route_plan_json


FIXTURE_DIR = Path(__file__).parent / "fixtures" / "route_plans"


def load_fixture(name: str):
    return load_route_plan_json(FIXTURE_DIR / name)


def diagnostic_codes(result):
    return {diagnostic.code for diagnostic in result.diagnostics}


def test_schema_smoke_fixture_reads_route_plan():
    result = load_fixture("schema-smoke-001.json")

    assert result.is_valid
    assert not result.warnings
    assert result.plan is not None
    assert result.plan.schema_version == "route-plan-v1"
    assert result.plan.routes[0].required_visit_order == ["C", "A", "33"]
    assert result.plan.routes[0].expanded_node_path is None


def test_full_coverage_smoke_fixture_covers_all_required_visit_nodes():
    result = load_fixture("full-coverage-smoke-001.json")

    assert result.is_valid
    assert result.plan is not None
    covered = set()
    for route in result.plan.routes:
        covered.update(route.required_visit_order)

    assert covered == REQUIRED_VISIT_NODES


def test_missing_nullable_field_is_contract_error():
    result = load_fixture("invalid-missing-nullable-field.json")

    assert not result.is_valid
    assert "missing_field" in diagnostic_codes(result)


def test_schema_version_must_match_exactly():
    result = load_fixture("invalid-schema-version.json")

    assert not result.is_valid
    assert "invalid_schema_version" in diagnostic_codes(result)


def test_depot_must_not_appear_in_required_visit_order():
    result = load_fixture("invalid-required-order-has-depot.json")

    assert not result.is_valid
    assert "depot_in_required_visit_order" in diagnostic_codes(result)


def test_auxiliary_node_must_not_appear_in_required_visit_order():
    result = load_fixture("invalid-required-order-has-auxiliary.json")

    assert not result.is_valid
    assert "auxiliary_in_required_visit_order" in diagnostic_codes(result)


def test_extra_fields_warn_but_do_not_block_reading_defined_fields():
    result = load_fixture("warn-extra-field.json")

    assert result.is_valid
    assert "unknown_field" in diagnostic_codes(result)
    assert result.plan is not None
    assert result.plan.extra_fields["note"] == "extra plan field"
    assert result.plan.routes[0].extra_fields["note"] == "extra route field"
