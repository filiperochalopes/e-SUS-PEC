"""Bounded, versioned scenarios and relative dates for MCP acceptance tests.

The legacy cohort is intentionally independent of this module. Appending a case
must not consume random state used to identify any existing patient.
"""
from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import date, timedelta
import hashlib

from pec_demo.patients import SyntheticPatient, build_patient_cohort, _subtract_years


@dataclass(frozen=True)
class CoverageCase:
    key: str
    group: str
    unit: int
    microarea: str
    complete: bool
    age: int
    sex: str
    visits: int
    gestation_days: int | None = None


def coverage_cases() -> tuple[CoverageCase, ...]:
    cases = []
    groups = (
        ("infantil", 1, "F", 10),
        ("diabetes", 54, "F", 8),
        ("hipertensao", 47, "M", 8),
        ("idoso", 72, "M", 6),
        ("rastreamento", 58, "F", 4),
        ("hpv", 12, "F", 3),
    )
    for group_index, (group, age, sex, visits) in enumerate(groups):
        for complete in (True, False):
            for unit in (0, 1):
                suffix = "completo" if complete else "lacuna"
                cases.append(CoverageCase(
                    f"v5_{group}_{suffix}_{unit + 1}", group, unit,
                    f"{group_index % 3 + 1:02d}", complete, age, sex,
                    visits if complete else max(2, visits - 3),
                ))
    for index, days in enumerate((70, 154, 224, 300)):
        group = "puerpera" if days == 300 else "gestante"
        cases.append(CoverageCase(
            f"v5_{group}_{index + 1}", group, index % 2,
            f"{index % 3 + 1:02d}", index != 1, 26 + index * 3, "F",
            (3, 5, 8, 10)[index], days,
        ))
    for unit in (0, 1):
        cases.append(CoverageCase(
            f"v5_sem_consulta_{unit + 1}", "sem_consulta", unit, "03",
            False, 39, "M", 0,
        ))
    return tuple(cases)


CASES = {case.key: case for case in coverage_cases()}


def build_coverage_cohort(*, seed: int, reference_date: date) -> tuple[SyntheticPatient, ...]:
    patients = []
    for case in coverage_cases():
        digest = hashlib.sha256(f"{seed}:{case.key}".encode()).digest()
        case_seed = int.from_bytes(digest[:4], "big")
        # A fixed identity epoch avoids changes in Faker output across backup dates.
        identity = build_patient_cohort(seed=case_seed, generated_on=date(2026, 7, 27))[4 if case.sex == "F" else 5]
        birth = (_subtract_years(reference_date, case.age) - timedelta(days=90))
        if case.group == "infantil":
            birth = reference_date - timedelta(days=480)
        patients.append(replace(
            identity, key=case.key, sex=case.sex, birth_date=birth,
            scenario=f"{case.group}; {'acompanhamento completo' if case.complete else 'lacunas planejadas'}; equipe {case.unit + 1}; microarea {case.microarea}",
            age_years=case.age,
        ))
    return tuple(patients)


def encounter_dates(case: CoverageCase, reference_date: date) -> tuple[date, ...]:
    """Chronological, never future; > half within 180 days, latest <= 15 days."""
    if not case.visits:
        return ()
    latest = 2 + int.from_bytes(hashlib.sha256(case.key.encode()).digest()[:2], "big") % 12
    oldest = 165
    if case.gestation_days:
        oldest = min(case.gestation_days - 49, 260)
    offsets = [round(oldest - (oldest - latest) * i / (case.visits - 1)) for i in range(case.visits)]
    if case.group == "infantil" and case.complete:
        # First appointment within 30 days of birth; remaining density is recent.
        offsets[0] = 460
    elif case.group in {"diabetes", "hipertensao", "idoso"}:
        offsets[0] = 300
    return tuple(reference_date - timedelta(days=value) for value in offsets)


def build_coverage_encounters(patient: SyntheticPatient):
    from pec_demo.clinical import PlannedEncounter, LOSARTAN, METFORMIN
    case = CASES[patient.key]
    result = []
    for i in range(case.visits):
        role = "medico" if i % 2 == 0 else "enfermagem"
        cid = {"diabetes": "E11.9", "hipertensao": "I10", "idoso": "I10"}.get(case.group) if i == 0 else None
        if case.group == "diabetes" and i == 2:
            cid = "I10"
        measurements = {}
        if case.complete or i % 3 == 0:
            weight, height = ((11.0 + i * .15, 81.0 + i * .3) if case.group == "infantil" else (62.0 + i * .4 + case.unit * 10, 163.0 + case.unit * 7))
            measurements = {"peso": round(weight, 2), "altura": round(height, 1)}
            if case.complete:
                measurements.update(pressaoArterialSistolica=120 + i % 3 * 5,
                                    pressaoArterialDiastolica=78 + i % 3 * 2)
        prescriptions = ()
        if i == 0:
            if case.group == "diabetes":
                prescriptions = (METFORMIN,)
            elif case.group in {"hipertensao", "idoso"}:
                prescriptions = (LOSARTAN,)
        result.append(PlannedEncounter(
            key=f"{case.key}:{i+1:02d}:{role}", patient_key=case.key, role=role,
            subjective=f"Seguimento sintético de {case.group}. DEMO-SOAP-{case.key.upper()}-{i+1:02d}.",
            objective=f"Avaliação longitudinal {i+1}/{case.visits}; {'medidas registradas' if measurements else 'medidas não registradas nesta consulta'}.",
            assessment=f"Cenário {case.group}, {'com acompanhamento completo' if case.complete else 'com lacunas de acompanhamento para busca ativa'}.",
            plan="Revisar evolução, resultados disponíveis e pendências; retorno programado na APS.",
            encounter_number=i+1, cid10_code=cid, include_problem=bool(cid),
            resolve_cid10_codes=(), health_rationale=case.group,
            measurements=measurements, prescriptions=prescriptions,
        ))
    return tuple(result)
