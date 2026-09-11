"""Tests for the protected-cohort preservation signature."""

import json
from datetime import date

import pytest

from pec_demo.patients import build_patient_cohort
from pec_demo.preservation import (
    INVARIANT_FIELDS,
    RENEWABLE_FIELDS,
    compare,
    parse_signature,
    signature_query,
    signature_script,
)


def _row(cpf: str, **overrides) -> dict[str, str]:
    row = {
        "cpf": cpf,
        "name": "PACIENTE DEMO X",
        "mother_name": "MAE DEMO Y",
        "birth_date": "2010-11-08",
        "sex": "MASCULINO",
        "cns": "798953254016006",
        "medical_records": "1",
        "encounters": "5",
        "professional_encounters": "5",
        "authors": "2",
        "oldest_encounter": "2026-09-09",
        "latest_encounter": "2026-09-09",
        "soap_digest": "a" * 32,
        "problem_digest": "b" * 32,
        "prescription_digest": "c" * 32,
        "exam_digest": "d" * 32,
    }
    row.update(overrides)
    return row


def _signature(count: int = 10) -> dict[str, dict[str, str]]:
    return {f"{index:011d}": _row(f"{index:011d}") for index in range(1, count + 1)}


def test_renewable_and_invariant_fields_are_disjoint():
    assert not set(RENEWABLE_FIELDS) & set(INVARIANT_FIELDS)


def test_the_query_covers_the_real_protected_cohort():
    cohort = build_patient_cohort(seed=5522, generated_on=date(2026, 7, 27))

    query = signature_query(tuple(item.cpf for item in cohort))

    assert all(item.cpf in query for item in cohort)
    # The signature is read-only and never looks at the analytical layer.
    for forbidden in ("UPDATE", "INSERT", "DELETE", "tb_fat_", "tb_dim_"):
        assert forbidden not in query
    assert signature_script(tuple(item.cpf for item in cohort)).endswith(") s;\n")


def test_a_malformed_cpf_is_refused():
    with pytest.raises(ValueError, match="eleven digits"):
        signature_query(("123",))
    with pytest.raises(ValueError, match="at least one"):
        signature_query(())


def test_identical_signatures_report_no_change():
    signature = _signature()

    report = compare(signature, signature, expected_patients=10)

    assert report.patients == 10
    assert report.renewed == {}
    assert json.loads(json.dumps(report.as_dict()))["patients"] == 10


def test_a_renewed_chronology_is_allowed_and_reported():
    before = _signature()
    after = {
        cpf: _row(cpf, oldest_encounter="2025-01-15", latest_encounter="2026-09-07")
        for cpf in before
    }

    report = compare(before, after, expected_patients=10)

    assert set(report.renewed) == set(before)
    assert report.renewed[next(iter(before))]["latest_encounter"] == (
        "2026-09-09",
        "2026-09-07",
    )


@pytest.mark.parametrize(
    "field",
    ("name", "birth_date", "cns", "soap_digest", "problem_digest", "encounters"),
)
def test_any_clinical_or_identity_change_is_refused(field):
    before = _signature()
    victim = next(iter(before))
    after = dict(before)
    after[victim] = _row(victim, **{field: "alterado"})

    with pytest.raises(ValueError, match=f"changed {field}"):
        compare(before, after, expected_patients=10)


def test_a_disappeared_patient_is_refused():
    before = _signature()
    after = dict(before)
    after.pop(next(iter(before)))

    with pytest.raises(ValueError, match="disappeared"):
        compare(before, after, expected_patients=10)


def test_an_unexpected_cohort_size_is_refused():
    with pytest.raises(ValueError, match="expected 10"):
        compare(_signature(9), _signature(9), expected_patients=10)


def test_the_error_message_never_leaks_a_full_cpf():
    before = _signature()
    victim = next(iter(before))
    after = dict(before)
    after[victim] = _row(victim, soap_digest="alterado")

    with pytest.raises(ValueError) as error:
        compare(before, after, expected_patients=10)
    assert victim not in str(error.value)


def test_parsing_tolerates_nulls_and_an_empty_result():
    payload = json.dumps([{"cpf": "00000000001", "soap_digest": None}])

    assert parse_signature(payload)["00000000001"]["soap_digest"] == ""
    assert parse_signature("") == {}
