from datetime import date

from pec_demo.clinical import (
    ClinicalAssignment,
    build_encounter_plan,
    build_individual_attendance_input,
    provision_clinical_histories,
)
from pec_demo.patients import build_patient_cohort
from pec_demo.pec_client import PecGraphQLClient


def test_encounter_plan_varies_from_two_to_ten_encounters():
    patients = build_patient_cohort(seed=5522, generated_on=date(2026, 7, 27))

    plans = [build_encounter_plan(patient) for patient in patients]
    counts = [len(items) for items in plans]

    assert min(counts) == 2
    assert max(counts) == 10
    assert len(set(counts)) > 2
    assert all(
        {item.role for item in encounters} == {"medico", "enfermagem"}
        for encounters in plans
    )
    assert all(
        "DEMO-SOAP-" in item.subjective for encounters in plans for item in encounters
    )
    assert len({item.key for encounters in plans for item in encounters}) == sum(counts)


def test_payload_replicates_captured_pec_5522_contract():
    patient = build_patient_cohort(seed=5522, generated_on=date(2026, 7, 27))[0]
    encounter = build_encounter_plan(patient)[0]

    payload = build_individual_attendance_input(
        encounter,
        attendance_id="41",
        ciap_id=None,
        cid10_id="18",
        resolved_problems=(
            {
                "cid10_id": "17",
                "problem_id": "301",
                "evaluation_id": "401",
                "start_date": "2026-07-20",
            },
        ),
        resolution_date=date(2026, 7, 27),
        automatic_procedure_id="1077",
    )

    assert payload["id"] == "41"
    assert payload["subjetivo"]["texto"].startswith("<p>")
    assert payload["avaliacao"]["problemasCondicoesAvaliadas"] == [
        {
            "cidId": "18",
            "incluirListaProblemas": True,
            "situacao": "ATIVO",
        },
        {
            "id": "401",
            "cidId": "17",
            "problemaId": "301",
            "incluirListaProblemas": True,
            "situacao": "RESOLVIDO",
            "dataInicio": "2026-07-20",
            "dataFim": "2026-07-27",
            "observacao": "Condição sintética resolvida em seguimento.",
        },
    ]
    assert payload["objetivo"]["medicoes"]["peso"] > 0
    assert payload["objetivo"]["medicoes"]["altura"] > 0
    assert payload["objetivo"]["medicoes"]["pressaoArterialSistolica"] > 0
    assert payload["finalizacao"]["tipoAtendimento"] == "CONSULTA_NO_DIA"
    assert payload["finalizacao"]["condutas"] == [
        "RETORNO_PARA_CUIDADO_CONTINUADO_PROGRAMADO"
    ]
    assert payload["finalizacao"]["procedimentosAdministrativos"] == [
        {"id": "1077", "automatico": True}
    ]

    nursing = build_encounter_plan(patient)[1]
    nursing_payload = build_individual_attendance_input(
        nursing,
        attendance_id="42",
        ciap_id="9",
        cid10_id=None,
        automatic_procedure_id="1074",
    )
    assert nursing_payload["avaliacao"]["problemasCondicoesAvaliadas"] == [
        {"ciapId": "9"}
    ]


class FakeClinicalClient:
    def __init__(self, patients):
        self.patient_ids = {
            patient.cpf: str(index) for index, patient in enumerate(patients, start=1)
        }
        self.selected = []
        self.saved = []

    def citizen_by_cpf(self, cpf):
        identifier = self.patient_ids[cpf]
        return {"id": identifier, "prontuario": {"id": f"p-{identifier}"}}

    def select_assignment_access(self, *, cnes, cbo2002):
        self.selected.append((cnes, cbo2002))

    def automatic_procedure_id(self, code):
        return {"0301010064": "1077", "0301010030": "1074"}[code]

    def ciap_id(self, code, *, sex, age):
        assert code == "A98"
        return "9"

    def cid10_id(self, code, *, sex, age):
        assert code
        return code

    def active_problem_by_cid(self, *, medical_record_id, cid10_id, ciap_id=None):
        return {
            "id": f"{medical_record_id}:{cid10_id}",
            "evolucaoAvaliacaoCiapCid": {
                "id": f"evaluation:{medical_record_id}:{cid10_id}"
            },
            "ultimaEvolucao": {"dataInicio": "2026-07-20"},
        }

    def medication(self, query, *, concentration=None):
        assert concentration
        return {
            "id": "catmat-1",
            "medicamento": {"id": f"med:{query}"},
            "principioAtivo": {"listaMaterial": {"tipoReceita": "COMUM"}},
            "unidadeMedidaDose": {"id": "unit-1"},
        }

    def medication_application_id(self, query):
        assert query == "Oral"
        return "oral-1"

    def dose_unit_id(self, query):
        assert query == "Comprimido"
        return "unit-1"

    def save_attendance(self, citizen_id):
        return {"id": str(len(self.saved) + 1)}

    def start_individual_attendance(self, attendance_id):
        return {"atendimentoProfissional": {"id": attendance_id}}

    def save_individual_attendance(self, input_data):
        self.saved.append(input_data)
        return {"atendProf": {"id": input_data["id"]}}


def test_provision_histories_is_manifest_idempotent(tmp_path):
    patients = build_patient_cohort(seed=5522, generated_on=date(2026, 7, 27))[:2]
    client = FakeClinicalClient(patients)
    assignments = (
        ClinicalAssignment("medico", "1111111", "225130", "0301010064"),
        ClinicalAssignment("enfermagem", "2222222", "223505", "0301010030"),
    )
    manifest = tmp_path / "clinical.json"

    first = provision_clinical_histories(
        patients,
        client=client,
        assignments=assignments,
        reference_date=date(2026, 7, 27),
        manifest_path=manifest,
    )
    second = provision_clinical_histories(
        patients,
        client=client,
        assignments=assignments,
        reference_date=date(2026, 7, 27),
        manifest_path=manifest,
    )

    expected = sum(len(build_encounter_plan(patient)) for patient in patients)
    assert len(first) == len(second) == expected
    assert len(client.saved) == expected
    assert len({item.key for item in first}) == expected


def test_measurements_are_age_coherent_and_include_excess_weight():
    patients = build_patient_cohort(seed=5522, generated_on=date(2026, 7, 27))
    adult_bmis = []
    complete = partial = missing = 0
    for patient in patients:
        for encounter in build_encounter_plan(patient):
            values = encounter.measurements
            if not values:
                missing += 1
            elif {"peso", "altura", "pressaoArterialSistolica"} <= values.keys():
                complete += 1
            else:
                partial += 1
            if "pressaoArterialSistolica" in values:
                assert 45 <= values["pressaoArterialSistolica"] <= 180
                assert 30 <= values["pressaoArterialDiastolica"] <= 110
                assert (
                    values["pressaoArterialSistolica"]
                    > values["pressaoArterialDiastolica"]
                )
            if "peso" in values:
                assert values["peso"] > 0
                assert values["altura"] > 0
            if patient.age_years >= 18 and "peso" in values:
                adult_bmis.append(values["peso"] / ((values["altura"] / 100) ** 2))

    assert complete and partial and missing
    assert any(25 <= bmi < 30 for bmi in adult_bmis)
    assert any(bmi >= 30 for bmi in adult_bmis)


def test_health_trajectories_are_incremental_with_coding_gaps():
    patients = build_patient_cohort(seed=5522, generated_on=date(2026, 7, 27))
    all_encounters = []
    resolutions = 0
    tracked = 0
    untracked_coded = 0

    for patient in patients:
        seen_codes = set()
        resolved_codes = set()
        encounters = build_encounter_plan(patient)
        all_encounters.extend(encounters)
        for encounter in encounters:
            assert set(encounter.resolve_cid10_codes) <= seen_codes
            resolved_codes.update(encounter.resolve_cid10_codes)
            resolutions += len(encounter.resolve_cid10_codes)
            if encounter.cid10_code:
                assert encounter.cid10_code not in seen_codes
                seen_codes.add(encounter.cid10_code)
                tracked += encounter.include_problem
                untracked_coded += not encounter.include_problem
        tracked_codes = {
            item.cid10_code
            for item in encounters
            if item.cid10_code and item.include_problem
        }
        assert tracked_codes - resolved_codes

    coded = [item for item in all_encounters if item.cid10_code]
    gaps = [item for item in all_encounters if item.cid10_code is None]
    assert coded
    assert gaps
    assert len(coded) < len(all_encounters)
    assert resolutions > 0
    assert tracked > 0
    assert untracked_coded > 0


def test_chronic_conditions_receive_structured_continuous_prescriptions():
    patients = {
        patient.key: patient
        for patient in build_patient_cohort(seed=5522, generated_on=date(2026, 7, 27))
    }
    middle_age = build_encounter_plan(patients["meia_idade"])
    continuous = [
        prescription
        for encounter in middle_age
        for prescription in encounter.prescriptions
        if prescription.continuous_use
    ]
    assert {item.medication_query for item in continuous} == {
        "Losartana potássica",
        "Metformina, Cloridrato",
    }
    assert any(not encounter.prescriptions for encounter in middle_age)


def test_cid10_lookup_normalizes_catalog_codes_without_punctuation():
    client = PecGraphQLClient("http://pec")
    captured = {}

    def fake_execute(_operation, variables):
        captured.update(variables)
        return {
            "cids": {"content": [{"id": "42", "codigo": "E119", "nome": "DIABETES"}]}
        }

    client.execute = fake_execute

    assert client.cid10_id("E11.9", sex="FEMININO", age=48) == "42"
    assert captured["input"]["query"] == "E119"
