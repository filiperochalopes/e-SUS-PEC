"""Tests for the chronology adapter."""

from datetime import date, datetime

import pytest

from pec_demo.clinical import build_encounter_plan
from pec_demo.coverage import CASES, build_coverage_cohort, encounter_dates
from pec_demo.patients import build_patient_cohort
from pec_demo.temporal import (
    OWNED_COLUMNS,
    PROTECTED_COLUMNS,
    EncounterSchedule,
    plan_chronology,
    render_sql_script,
    render_statements,
    verify,
)


REFERENCE = date(2026, 9, 10)
EPOCH = date(2026, 7, 27)


def _cohort():
    return build_patient_cohort(seed=5522, generated_on=EPOCH) + build_coverage_cohort(
        seed=5522, reference_date=REFERENCE
    )


def _manifest(cohort, *, reference_date=REFERENCE):
    encounters = {}
    for index, patient in enumerate(cohort):
        for order, encounter in enumerate(
            build_encounter_plan(patient, reference_date=reference_date)
        ):
            identifier = index * 100 + order + 1
            encounters[encounter.key] = {
                "key": encounter.key,
                "patient_key": patient.key,
                "role": encounter.role,
                "citizen_id": str(index + 1),
                "attendance_id": str(identifier),
                "attendance_professional_id": str(identifier + 50_000),
            }
    return {"version": 4, "encounters": encounters}


def test_owned_and_protected_columns_never_overlap():
    assert not set(OWNED_COLUMNS) & set(PROTECTED_COLUMNS)


def test_every_provisioned_encounter_gets_a_clinical_instant():
    cohort = _cohort()
    manifest = _manifest(cohort)

    schedules = plan_chronology(
        manifest=manifest, patients=cohort, reference_date=REFERENCE
    )

    assert len(schedules) == len(manifest["encounters"]) == 220
    assert {item.key for item in schedules} == set(manifest["encounters"])
    assert all(item.starts_at < item.ends_at for item in schedules)
    assert all(item.clinical_date <= REFERENCE for item in schedules)


def test_extended_scenarios_use_the_contract_dates():
    cohort = _cohort()
    schedules = plan_chronology(
        manifest=_manifest(cohort), patients=cohort, reference_date=REFERENCE
    )
    by_patient: dict[str, list[date]] = {}
    for item in schedules:
        by_patient.setdefault(item.patient_key, []).append(item.clinical_date)

    for key, case in CASES.items():
        if not case.encounters:
            assert key not in by_patient
            continue
        expected = list(encounter_dates(case, REFERENCE))
        assert sorted(by_patient[key]) == expected


def test_protected_patients_get_a_renewed_but_recent_chronology():
    cohort = _cohort()
    schedules = plan_chronology(
        manifest=_manifest(cohort), patients=cohort, reference_date=REFERENCE
    )
    protected = {patient.key for patient in build_patient_cohort(
        seed=5522, generated_on=EPOCH
    )}
    by_patient: dict[str, list[date]] = {}
    for item in schedules:
        if item.patient_key in protected:
            by_patient.setdefault(item.patient_key, []).append(item.clinical_date)

    assert set(by_patient) == protected
    for key, days in by_patient.items():
        birth = next(
            patient.birth_date for patient in cohort if patient.key == key
        )
        assert days == sorted(days)
        assert all(day > birth for day in days)
        assert 2 <= (REFERENCE - max(days)).days <= 15


def test_same_day_encounters_are_ordered_and_do_not_overlap():
    schedules = plan_chronology(
        manifest=_manifest(_cohort()), patients=_cohort(), reference_date=REFERENCE
    )
    by_day: dict[tuple[str, date], list[EncounterSchedule]] = {}
    for item in schedules:
        by_day.setdefault((item.patient_key, item.clinical_date), []).append(item)

    for items in by_day.values():
        ordered = sorted(items, key=lambda entry: entry.starts_at)
        for earlier, later in zip(ordered, ordered[1:]):
            assert earlier.ends_at < later.starts_at


def test_a_manifest_outside_the_cohort_is_refused():
    cohort = _cohort()
    manifest = _manifest(cohort)
    manifest["encounters"]["stranger:01:medico"] = {
        "key": "stranger:01:medico",
        "patient_key": "paciente_desconhecido",
        "role": "medico",
        "citizen_id": "999",
        "attendance_id": "999",
        "attendance_professional_id": "999",
    }

    with pytest.raises(ValueError, match="outside the cohort"):
        plan_chronology(
            manifest=manifest, patients=cohort, reference_date=REFERENCE
        )


def test_an_encounter_count_that_differs_from_the_contract_is_refused():
    cohort = _cohort()
    manifest = _manifest(cohort)
    victim = next(key for key in manifest["encounters"] if key.startswith("v5_"))
    del manifest["encounters"][victim]

    with pytest.raises(ValueError, match="the contract plans"):
        plan_chronology(
            manifest=manifest, patients=cohort, reference_date=REFERENCE
        )


def test_statements_bind_four_parameters_per_encounter():
    cohort = _cohort()
    schedules = plan_chronology(
        manifest=_manifest(cohort), patients=cohort, reference_date=REFERENCE
    )

    script, parameters = render_statements(schedules)

    assert script.count("%s") == len(parameters) == len(schedules) * 4
    assert script.startswith("BEGIN;")
    assert script.rstrip().endswith("COMMIT;")
    # The adapter writes no fact table and no protected column.
    assert "tb_fat_" not in script
    assert "tb_dim_" not in script
    assert "dt_criacao_registro" not in script
    assert "dt_aplicacao" not in script
    assert "dt_ultima_menstruacao" not in script


def test_the_rendered_script_only_carries_generated_literals():
    schedules = (
        EncounterSchedule(
            key="v5_x:01:medico",
            patient_key="v5_x",
            attendance_id="12",
            attendance_professional_id="34",
            starts_at=datetime(2026, 3, 1, 8, 30),
            ends_at=datetime(2026, 3, 1, 8, 55),
        ),
    )

    script = render_sql_script(schedules)

    assert "(12::bigint, 34::bigint" in script
    assert "'2026-03-01 08:30:00'::timestamp" in script
    assert "%s" not in script


def test_verification_fails_on_a_wrong_or_missing_instant():
    schedules = (
        EncounterSchedule(
            key="k",
            patient_key="p",
            attendance_id="1",
            attendance_professional_id="2",
            starts_at=datetime(2026, 3, 1, 8, 30),
            ends_at=datetime(2026, 3, 1, 8, 55),
        ),
    )
    good = [
        {
            "attendance_professional_id": 2,
            "attendance_id": 1,
            "starts_at": datetime(2026, 3, 1, 8, 30),
            "ends_at": datetime(2026, 3, 1, 8, 55),
        }
    ]

    verify(schedules, good)

    with pytest.raises(ValueError, match="carries"):
        verify(schedules, [{**good[0], "starts_at": datetime(2026, 3, 2, 8, 30)}])
    with pytest.raises(ValueError, match="did not return"):
        verify(schedules, [])
