"""Contract tests for the extended-cohort coverage manifest."""

from collections import Counter
from datetime import date

import pytest

from pec_demo.clinical import build_encounter_plan
from pec_demo.coverage import (
    CONTRACT_VERSION,
    MICROAREAS,
    TEAM_COUNT,
    birth_date,
    build_coverage_cohort,
    coverage_cases,
    coverage_contract,
    encounter_dates,
)
from pec_demo.patients import build_patient_cohort


REFERENCE_DATES = (
    date(2026, 9, 10),
    date(2026, 12, 31),
    date(2027, 3, 1),
    date(2028, 2, 29),
)


def test_cohort_matches_the_planned_size_and_encounter_budget():
    cases = coverage_cases()

    assert len(cases) == 32
    assert sum(case.encounters for case in cases) == 160
    assert len({case.key for case in cases}) == 32
    assert Counter(case.recency for case in cases)["never"] == 2
    assert Counter(case.recency for case in cases)["overdue"] == 2


def test_territory_is_balanced_by_an_explicit_rule():
    cases = coverage_cases()
    per_team = Counter(case.team for case in cases)
    per_microarea = Counter((case.team, case.microarea) for case in cases)

    assert set(per_team) == set(range(TEAM_COUNT))
    assert set(per_team.values()) == {16}
    assert len(per_microarea) == TEAM_COUNT * len(MICROAREAS)
    assert min(per_microarea.values()) >= 4


@pytest.mark.parametrize("reference_date", REFERENCE_DATES)
def test_chronology_obeys_every_rule_of_the_plan(reference_date):
    followed_total = followed_recent = 0
    for case in coverage_cases():
        dates = encounter_dates(case, reference_date)
        assert len(dates) == case.encounters
        if not dates:
            assert case.recency == "never"
            continue
        assert list(dates) == sorted(dates)
        assert len(set(dates)) == len(dates)
        assert dates[-1] <= reference_date
        assert all(item > birth_date(case, reference_date) for item in dates)
        latest = (reference_date - dates[-1]).days
        if case.recency == "recent":
            assert 2 <= latest <= 15
            followed_total += len(dates)
            followed_recent += sum(
                1 for item in dates if (reference_date - item).days <= 180
            )
        else:
            assert 210 <= latest <= 240

    assert followed_recent / followed_total >= 0.75


@pytest.mark.parametrize("reference_date", REFERENCE_DATES)
def test_children_and_pregnancies_respect_their_clinical_windows(reference_date):
    for case in coverage_cases():
        dates = encounter_dates(case, reference_date)
        if case.group == "infantil" and case.complete:
            first_visit_age = (dates[0] - birth_date(case, reference_date)).days
            assert first_visit_age <= 30
        if case.group == "gestante":
            gestational_age = case.gestation_days - (reference_date - dates[0]).days
            assert gestational_age <= 84


def test_same_seed_and_reference_produce_the_same_plan():
    reference = date(2026, 9, 10)
    first = build_coverage_cohort(seed=5522, reference_date=reference)
    second = build_coverage_cohort(seed=5522, reference_date=reference)

    assert first == second
    assert len({item.cpf for item in first}) == len(first)
    assert len({item.cns for item in first}) == len(first)


def test_a_new_reference_date_keeps_identities_and_moves_only_time():
    early = build_coverage_cohort(seed=5522, reference_date=date(2026, 9, 10))
    later = build_coverage_cohort(seed=5522, reference_date=date(2027, 3, 1))

    for before, after in zip(early, later):
        assert before.key == after.key
        assert before.name == after.name
        assert before.cpf == after.cpf
        assert before.cns == after.cns
        assert before.birth_date != after.birth_date


def test_extending_the_cohort_does_not_disturb_the_protected_patients():
    protected = build_patient_cohort(seed=5522, generated_on=date(2026, 7, 27))
    extended = build_coverage_cohort(seed=5522, reference_date=date(2026, 9, 10))

    again = build_patient_cohort(seed=5522, generated_on=date(2026, 7, 27))
    assert protected == again
    assert not {item.cpf for item in protected} & {item.cpf for item in extended}
    assert not {item.key for item in protected} & {item.key for item in extended}


def test_procedures_are_referenced_by_natural_code_only():
    for case in coverage_cases():
        for exam in case.exams:
            assert exam.codes
            assert all(not code.isdigit() or len(code) == 10 for code in exam.codes)
        for screening in case.screenings:
            assert screening.codes


def test_deliberate_gaps_stay_absent_and_negatives_exist():
    cohort = build_coverage_cohort(seed=5522, reference_date=date(2026, 9, 10))
    plans = {
        patient.key: build_encounter_plan(patient, reference_date=date(2026, 9, 10))
        for patient in cohort
    }

    for case in coverage_cases():
        encounters = plans[case.key]
        if case.group == "diabetes" and not case.complete:
            assert not any(
                "pes" in exam.label.lower()
                for encounter in encounters
                for exam in encounter.exam_results
            )
        if case.recency == "never":
            assert encounters == ()
        if not case.complete and case.encounters >= 3 and case.group != "gestante":
            # A gestation still too early for a component is not a data gap;
            # every other incomplete scenario must really miss measurements.
            assert any(not encounter.measurements for encounter in encounters)


def test_soap_text_carries_no_identifying_data():
    reference = date(2026, 9, 10)
    cohort = build_coverage_cohort(seed=5522, reference_date=reference)

    for patient in cohort:
        for encounter in build_encounter_plan(patient, reference_date=reference):
            blob = " ".join(
                (
                    encounter.subjective,
                    encounter.objective,
                    encounter.assessment,
                    encounter.plan,
                )
            )
            assert patient.cpf not in blob
            assert patient.cns not in blob
            assert patient.name not in blob
            assert patient.mother_name not in blob


def test_published_contract_is_self_describing():
    contract = coverage_contract(date(2026, 9, 10))

    assert contract["contract_version"] == CONTRACT_VERSION
    assert contract["extended_patients"] == 32
    assert contract["planned_encounters"] == 160
    assert contract["reference_date"] == "2026-09-10"
    assert contract["identity_epoch"] == "2026-07-27"
    covered = {
        component
        for scenario in contract["scenarios"]
        for component in scenario["components"]
    }
    assert {"C1", "C2", "C3", "C4", "C6", "C7"} <= covered


def test_pending_contracts_are_declared_instead_of_being_faked():
    pending = {
        item
        for case in coverage_cases()
        for item in case.pending_contracts
    }

    # C5 counts home visits, which no official contract in this factory can
    # author yet.  The gap must be declared, never simulated.
    assert pending == {"visita_domiciliar"}
    assert not any("C5" in case.components for case in coverage_cases())
