"""Tests for the extended cohort's payloads and per-team authorship."""

from datetime import date

import pytest

from pec_demo.clinical import (
    ClinicalAssignment,
    DOCTOR_CBO,
    DOCTOR_PROCEDURE,
    NURSE_CBO,
    NURSE_PROCEDURE,
    build_encounter_plan,
    build_exam_request_input,
    build_exam_result_input,
    build_individual_attendance_input,
    build_prenatal_input,
    build_vaccination_input,
    provision_clinical_histories,
)
from pec_demo.coverage import CASES, build_coverage_cohort
from pec_demo.patients import build_patient_cohort
from pec_demo.pec_client import PecClientError


REFERENCE = date(2026, 9, 10)


class FakeExtendedClient:
    """A client that records what the factory asks of each selected access."""

    base_url = "http://127.0.0.1:18082"

    def __init__(self, patients):
        self.patient_ids = {
            patient.cpf: str(index + 1) for index, patient in enumerate(patients)
        }
        self.selected = []
        self.saved = []
        self.access = None

    def citizen_by_cpf(self, cpf):
        identifier = self.patient_ids[cpf]
        return {"id": identifier, "prontuario": {"id": f"p-{identifier}"}}

    def select_assignment_access(self, *, cnes, cbo2002):
        self.access = (cnes, cbo2002)
        self.selected.append(self.access)

    def automatic_procedure_id(self, code):
        return {"0301010064": "1077", "0301010030": "1074"}[code]

    def ciap_id(self, code, *, sex, age):
        return f"ciap:{code}"

    def cid10_id(self, code, *, sex, age):
        return f"cid:{code}"

    def active_problem_by_cid(self, *, medical_record_id, cid10_id, ciap_id=None):
        return {
            "id": f"{medical_record_id}:{cid10_id}",
            "evolucaoAvaliacaoCiapCid": {"id": f"ev:{cid10_id}"},
            "ultimaEvolucao": {"dataInicio": "2026-01-10"},
        }

    def medication(self, query, *, concentration=None):
        return {
            "id": "catmat-1",
            "medicamento": {"id": f"med:{query}"},
            "principioAtivo": {"listaMaterial": {"tipoReceita": "COMUM"}},
            "unidadeMedidaDose": {"id": "unit-1"},
        }

    def medication_application_id(self, query):
        return "oral-1"

    def dose_unit_id(self, query):
        return "unit-1"

    def procedure_id(self, codes):
        return f"proc:{codes[0]}"

    def immunobiological_id(self, name):
        return "77"

    def immunobiological_dose_id(self, dose, *, immunobiological_id):
        return "88"

    def save_attendance(self, citizen_id):
        return {"id": str(len(self.saved) + 1)}

    def start_individual_attendance(self, attendance_id):
        return {"atendimentoProfissional": {"id": attendance_id}}

    def save_individual_attendance(self, input_data):
        self.saved.append((self.access, input_data))
        return {"atendProf": {"id": input_data["id"]}}


def _team_assignments():
    return (
        ClinicalAssignment("medico", "1111111", DOCTOR_CBO, DOCTOR_PROCEDURE, team=0),
        ClinicalAssignment("enfermagem", "1111111", NURSE_CBO, NURSE_PROCEDURE, team=0),
        ClinicalAssignment("medico", "2222222", DOCTOR_CBO, DOCTOR_PROCEDURE, team=1),
        ClinicalAssignment("enfermagem", "2222222", NURSE_CBO, NURSE_PROCEDURE, team=1),
    )


def test_exam_result_is_dated_before_its_encounter():
    patient = next(
        item
        for item in build_coverage_cohort(seed=5522, reference_date=REFERENCE)
        if item.key == "v5_diabetes_1"
    )
    encounter = next(
        item
        for item in build_encounter_plan(patient, reference_date=REFERENCE)
        if item.exam_results
    )
    exam = encounter.exam_results[0]

    payload = build_exam_result_input(
        exam, procedure_id="4321", encounter_date=encounter.encounter_date
    )

    assert payload["exameId"] == 4321
    assert date.fromisoformat(payload["dataRealizacao"]) < encounter.encounter_date
    assert payload["dataRealizacao"] == payload["dataResultado"]
    # HbA1c is a specific-result exam: the value travels structured, and PEC
    # rejects the payload if free text is sent instead.
    assert payload["resultado"] is None
    assert payload["especifico"]["procedimento"] == "HEMOGLOBINA_GLICADA"
    assert payload["especifico"]["valor"] == exam.numeric_value


def test_vaccination_is_a_previous_record_strictly_before_the_encounter():
    encounter_date = date(2026, 8, 20)

    class Dose:
        immunobiological = "Influenza"
        dose = "Dose anual"
        days_before_encounter = 0

    payload = build_vaccination_input(
        Dose(), immunobiological_id="7", dose_id="9", encounter_date=encounter_date
    )

    assert payload["isRegistroAnterior"] is True
    assert payload["isCadastrarNovoLote"] is False
    assert payload["loteImunobiologicoId"] is None
    assert payload["viaAdministracaoId"] is None
    assert date.fromisoformat(payload["dataAplicacao"]) < encounter_date


def test_prenatal_and_screening_payloads_follow_the_official_shapes():
    patient = next(
        item
        for item in build_coverage_cohort(seed=5522, reference_date=REFERENCE)
        if item.key == "v5_gestante_3"
    )
    encounter = next(
        item
        for item in build_encounter_plan(patient, reference_date=REFERENCE)
        if item.prenatal
    )

    prenatal = build_prenatal_input(encounter.prenatal)
    request = build_exam_request_input(
        procedure_ids=("11", "22"), justification="Rastreamento sintético."
    )

    assert prenatal["fonteIdadeGestacional"] == "DUM"
    assert prenatal["tipoGravidez"] == "UNICA"
    assert 8 <= prenatal["alturaUterina"] <= 36
    assert [item["exameId"] for item in request["examesRequisitados"]] == [11, 22]
    assert request["tipoExame"] == "COMUM"
    assert request["rastreioCitopatologicoColoUtero"] is None


def test_protected_cohort_payload_omits_every_extended_section():
    patient = build_patient_cohort(seed=5522, generated_on=date(2026, 7, 27))[0]
    encounter = build_encounter_plan(patient)[0]

    payload = build_individual_attendance_input(
        encounter,
        attendance_id="41",
        ciap_id=None,
        cid10_id="18",
        automatic_procedure_id="1077",
    )

    assert "resultadosExame" not in payload["objetivo"]
    assert "solicitacoesExame" not in payload["plano"]
    assert "preNatal" not in payload
    assert payload["registrosVacinacao"] == []
    assert "dataMedicao" not in (payload["objetivo"]["medicoes"] or {})


def test_measurements_of_the_extended_cohort_carry_their_clinical_date():
    patient = next(
        item
        for item in build_coverage_cohort(seed=5522, reference_date=REFERENCE)
        if item.key == "v5_hipertensao_1"
    )
    encounter = build_encounter_plan(patient, reference_date=REFERENCE)[0]

    payload = build_individual_attendance_input(
        encounter,
        attendance_id="1",
        ciap_id=None,
        cid10_id="18",
        automatic_procedure_id="1077",
    )

    assert payload["objetivo"]["medicoes"]["dataMedicao"] == (
        encounter.encounter_date.isoformat()
    )


def test_each_team_authors_its_own_encounters(tmp_path):
    cohort = build_coverage_cohort(seed=5522, reference_date=REFERENCE)
    selected = [
        item
        for item in cohort
        if item.key in {"v5_hipertensao_1", "v5_hipertensao_2"}
    ]
    client = FakeExtendedClient(selected)

    provision_clinical_histories(
        tuple(selected),
        client=client,
        assignments=_team_assignments(),
        reference_date=REFERENCE,
        manifest_path=tmp_path / "clinical.json",
    )

    per_patient = {}
    for patient in selected:
        expected_cnes = "1111111" if CASES[patient.key].team == 0 else "2222222"
        per_patient[patient.key] = expected_cnes
    authored = {
        access[0]
        for access, payload in client.saved
    }
    assert authored == set(per_patient.values())
    assert len(authored) == 2


def test_a_team_without_both_roles_is_refused(tmp_path):
    cohort = build_coverage_cohort(seed=5522, reference_date=REFERENCE)[:1]
    client = FakeExtendedClient(cohort)

    with pytest.raises(PecClientError, match="no clinical assignment"):
        provision_clinical_histories(
            tuple(cohort),
            client=client,
            assignments=(
                ClinicalAssignment(
                    "medico", "1111111", DOCTOR_CBO, DOCTOR_PROCEDURE, team=0
                ),
            ),
            reference_date=REFERENCE,
            manifest_path=tmp_path / "clinical.json",
        )
