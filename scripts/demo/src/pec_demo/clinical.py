"""Provision deterministic SOAP histories through PEC's official mutations."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import date, timedelta
from html import escape
import json
import os
from pathlib import Path
import tempfile
from typing import Any

from pec_demo.patients import SyntheticPatient
from pec_demo.pec_client import PecClientError, PecGraphQLClient


DOCTOR_CBO = "225130"
NURSE_CBO = "223505"
DOCTOR_PROCEDURE = "0301010064"
NURSE_PROCEDURE = "0301010030"
PREVENTIVE_CIAP = "A98"


@dataclass(frozen=True, slots=True)
class PlannedPrescription:
    medication_query: str
    concentration: str | None
    dose: str
    frequency_hours: int
    quantity: int
    continuous_use: bool
    instructions: str


LOSARTAN = PlannedPrescription(
    "Losartana potássica",
    "50 mg",
    "1",
    24,
    30,
    True,
    "Tomar 1 comprimido por via oral pela manhã.",
)
METFORMIN = PlannedPrescription(
    "Metformina, Cloridrato",
    "500 mg",
    "1",
    12,
    60,
    True,
    "Tomar 1 comprimido por via oral após o café e o jantar.",
)

ENCOUNTER_COUNTS = {
    "lactente": 2,
    "pre_escolar": 3,
    "escolar": 4,
    "adolescente": 5,
    "adulta_jovem": 6,
    "adulto": 7,
    "meia_idade": 8,
    "idoso_jovem": 9,
    "idosa": 10,
    "longevo": 6,
}

HEALTH_TRAJECTORIES = {
    "lactente": {
        1: ("P92.5", True, (), "dificuldade inicial de alimentação"),
    },
    "pre_escolar": {
        1: ("J06.9", True, (), "quadro respiratório agudo sem alarme"),
        3: ("J30.4", True, ("J06.9",), "rinite alérgica mantida em seguimento"),
    },
    "escolar": {
        1: ("J45.9", True, (), "asma em acompanhamento longitudinal"),
        3: ("J30.4", True, (), "sintomas nasais sazonais associados"),
    },
    "adolescente": {
        1: ("L70.0", True, (), "queixa dermatológica própria da adolescência"),
        3: ("Z00.3", False, ("L70.0",), "avaliação geral do desenvolvimento"),
        5: ("R51", True, (), "cefaleia episódica ainda sem fechamento"),
    },
    "adulta_jovem": {
        1: ("Z30.0", False, (), "aconselhamento reprodutivo"),
        3: ("N76.0", True, (), "episódio ginecológico agudo"),
        5: ("R10.2", True, ("N76.0",), "dor pélvica mantida em investigação"),
    },
    "adulto": {
        1: ("M54.5", True, (), "lombalgia relacionada ao trabalho"),
        3: ("J06.9", True, ("M54.5",), "episódio respiratório autolimitado"),
        5: ("K30", True, ("J06.9",), "dispepsia indevidamente ainda aberta"),
        7: ("Z00.0", False, (), "avaliação geral preventiva"),
    },
    "meia_idade": {
        1: ("I10", True, (), "hipertensão arterial em seguimento"),
        3: ("E11.9", True, (), "diabetes tipo 2 sem complicação registrada"),
        5: ("E66.9", True, (), "obesidade como fator de risco persistente"),
        7: ("R51", False, (), "cefaleia episódica sem mudança das crônicas"),
    },
    "idoso_jovem": {
        1: ("I10", True, (), "hipertensão arterial em seguimento"),
        3: ("E78.5", True, (), "dislipidemia em acompanhamento"),
        5: ("M17.9", True, (), "dor mecânica crônica em joelho"),
        7: ("J06.9", True, (), "intercorrência respiratória aguda"),
        9: ("Z00.0", False, ("J06.9",), "reavaliação integral após recuperação"),
    },
    "idosa": {
        1: ("I10", True, (), "hipertensão arterial em seguimento"),
        3: ("M81.0", True, (), "osteoporose relacionada à idade"),
        5: ("M17.9", True, (), "osteoartrose de joelho sintomática"),
        7: ("R42", True, (), "episódio de tontura em investigação"),
        9: ("Z00.0", False, ("R42",), "revisão global e prevenção de quedas"),
    },
    "longevo": {
        1: ("R54", True, (), "fragilidade relacionada à idade"),
        3: ("J06.9", True, (), "intercorrência respiratória aguda"),
        5: ("Z00.0", False, ("J06.9",), "revisão após recuperação clínica"),
    },
}

# Height (cm), initial weight (kg), weight change per encounter, baseline BP.
# The cohort deliberately includes healthy, overweight and obese trajectories.
MEASUREMENT_PROFILES = {
    "lactente": (51.0, 3.6, 0.8, 72, 44),
    "pre_escolar": (105.0, 18.0, 0.3, 92, 58),
    "escolar": (142.0, 43.0, 0.5, 104, 66),
    "adolescente": (173.0, 76.0, 0.7, 116, 72),
    "adulta_jovem": (164.0, 61.0, 0.5, 112, 70),
    "adulto": (176.0, 84.0, 0.8, 124, 78),
    "meia_idade": (160.0, 81.0, 0.9, 142, 88),
    "idoso_jovem": (171.0, 86.0, 0.5, 138, 84),
    "idosa": (155.0, 68.0, -0.2, 132, 80),
    "longevo": (166.0, 61.0, -0.3, 136, 78),
}


@dataclass(frozen=True, slots=True)
class ClinicalAssignment:
    role: str
    cnes: str
    cbo2002: str
    automatic_procedure_code: str


@dataclass(frozen=True, slots=True)
class PlannedEncounter:
    key: str
    patient_key: str
    role: str
    subjective: str
    objective: str
    assessment: str
    plan: str
    encounter_number: int
    cid10_code: str | None
    include_problem: bool
    resolve_cid10_codes: tuple[str, ...]
    health_rationale: str
    measurements: dict[str, float | int | bool | None]
    prescriptions: tuple[PlannedPrescription, ...]


@dataclass(frozen=True, slots=True)
class ProvisionedEncounter:
    key: str
    patient_key: str
    role: str
    citizen_id: str
    attendance_id: str
    attendance_professional_id: str


def _age_on(birth_date: date, reference: date) -> int:
    return (
        reference.year
        - birth_date.year
        - ((reference.month, reference.day) < (birth_date.month, birth_date.day))
    )


def build_encounter_plan(patient: SyntheticPatient) -> tuple[PlannedEncounter, ...]:
    """Build a deterministic 2-10 encounter longitudinal history."""
    from pec_demo.coverage import CASES, build_coverage_encounters
    if patient.key in CASES:
        return build_coverage_encounters(patient)
    marker = patient.key.upper().replace("_", "-")
    context = patient.scenario
    count = ENCOUNTER_COUNTS[patient.key]
    height, initial_weight, weight_step, systolic, diastolic = MEASUREMENT_PROFILES[
        patient.key
    ]
    encounters = []
    for index in range(count):
        role = "medico" if index % 2 == 0 else "enfermagem"
        role_marker = "MED" if role == "medico" else "ENF"
        visit = index + 1
        # Small deterministic changes avoid cloned-looking records while keeping
        # anthropometry and vital signs coherent with the life-course profile.
        weight = round(initial_weight + weight_step * index, 3)
        current_height = round(
            height + (0.7 * index if patient.age_years <= 10 else 0.0),
            1,
        )
        bp_offset = (index % 3) - 1
        full_measurements = {
            "peso": weight,
            "altura": current_height,
            "pressaoArterialSistolica": systolic + (bp_offset * 3),
            "pressaoArterialDiastolica": diastolic + (bp_offset * 2),
            "frequenciaCardiaca": max(62, 132 - min(patient.age_years, 70) - index),
            "frequenciaRespiratoria": max(
                14, 36 - min(patient.age_years // 2, 20) - (index % 2)
            ),
            "temperatura": round(36.4 + ((index % 3) * 0.2), 1),
            "saturacaoO2": 97 + (index % 3),
            "vacinacaoEmDia": True,
            "exameFisico": None,
        }
        if patient.age_years == 0:
            full_measurements["perimetroCefalico"] = round(35.0 + 0.8 * index, 1)

        # Real records alternate between complete measurements, partial
        # measurements and no structured measurement at all.
        measurement_pattern = visit % 4
        if measurement_pattern == 1:
            measurements = full_measurements
        elif measurement_pattern == 2:
            measurements = {
                key: full_measurements[key]
                for key in (
                    "pressaoArterialSistolica",
                    "pressaoArterialDiastolica",
                    "frequenciaCardiaca",
                    "temperatura",
                    "saturacaoO2",
                )
            }
        elif measurement_pattern == 3:
            measurements = {key: full_measurements[key] for key in ("peso", "altura")}
        else:
            measurements = {}

        trajectory = HEALTH_TRAJECTORIES[patient.key].get(visit)
        if trajectory:
            cid10_code, include_problem, resolve_codes, rationale = trajectory
        else:
            cid10_code = None
            include_problem = False
            resolve_codes = ()
            rationale = (
                "registro clínico textual sem codificação diagnóstica estruturada"
            )

        prescriptions: tuple[PlannedPrescription, ...] = ()
        if role == "medico":
            if patient.key == "meia_idade" and visit == 1:
                prescriptions = (LOSARTAN,)
            elif patient.key == "meia_idade" and visit == 3:
                prescriptions = (METFORMIN,)
            elif patient.key in {"idoso_jovem", "idosa"} and visit == 1:
                prescriptions = (LOSARTAN,)
        encounters.append(
            PlannedEncounter(
                key=f"{patient.key}:{visit:02d}:{role}",
                patient_key=patient.key,
                role=role,
                subjective=(
                    f"Paciente ou responsável descreve evolução relacionada a {context}, "
                    f"sem sinais de alarme no momento. "
                    f"DEMO-SOAP-{marker}-{visit:02d}-{role_marker}."
                ),
                objective=(
                    f"Avaliação sintética longitudinal {visit}/{count}, com medidas "
                    "compatíveis com a faixa etária e o cenário clínico."
                ),
                assessment=(
                    f"{rationale.capitalize()}, dentro do cuidado de {context}; "
                    "cenário exclusivamente sintético."
                ),
                plan=(
                    "Orientações individualizadas, sinais de alarme, promoção da saúde "
                    "e retorno programado na Atenção Primária."
                ),
                encounter_number=visit,
                cid10_code=cid10_code,
                include_problem=include_problem,
                resolve_cid10_codes=resolve_codes,
                health_rationale=rationale,
                measurements=measurements,
                prescriptions=prescriptions,
            )
        )
    return tuple(encounters)


def _html_paragraph(value: str) -> str:
    return f"<p>{escape(value, quote=False)}</p>"


def _build_prescription_input(
    prescription: PlannedPrescription,
    *,
    medication: dict[str, Any],
    oral_application_id: str,
    fallback_dose_unit_id: str,
) -> dict[str, Any]:
    catalog_unit = medication.get("unidadeMedidaDose") or {}
    # The PEC container may already be on the next UTC date while the factory
    # host still uses America/Bahia. A one-day future start is valid and avoids
    # making the prescription earlier than its live attendance.
    start = date.today() + timedelta(days=1)
    duration = None if prescription.continuous_use else 28
    return {
        "id": None,
        "medicamentoId": str(medication["medicamento"]["id"]),
        "medicamentoRegistroManual": None,
        "tipoReceita": str(
            medication["principioAtivo"]["listaMaterial"]["tipoReceita"]
        ),
        "viaAdministracao": oral_application_id,
        "qtDose": prescription.dose,
        "qtDoseManha": None,
        "qtDoseTarde": None,
        "qtDoseNoite": None,
        "unidadeMedidaDose": str(catalog_unit.get("id") or fallback_dose_unit_id),
        "doseUnica": False,
        "tipoFrequencia": "INTERVALO",
        "intervaloDose": prescription.frequency_hours,
        "frequenciaDose": None,
        "quantidadePeriodoFrequenciaTurno": None,
        "unidadeMedidaTempoFrequenciaTurno": None,
        "turno": None,
        "posologia": prescription.instructions,
        "dataInicioTratamento": start.isoformat(),
        "dataFimTratamento": (
            (start + timedelta(days=duration - 1)).isoformat() if duration else None
        ),
        "duracao": duration,
        "escalaDuracao": ("INDETERMINADO" if prescription.continuous_use else "DIAS"),
        "quantidade": prescription.quantity,
        "usoContinuo": prescription.continuous_use,
        "recomendacoes": "Prescrição sintética para ambiente de demonstração.",
        "codigoPrescricaoDigital": None,
        "receitaUsoContinuoGrupoId": None,
        "motivoPrescricao": None,
    }


def build_individual_attendance_input(
    encounter: PlannedEncounter,
    *,
    attendance_id: str,
    ciap_id: str | None,
    cid10_id: str | None,
    resolved_problems: tuple[dict[str, str], ...] = (),
    prescription_inputs: tuple[dict[str, Any], ...] = (),
    resolution_date: date | None = None,
    automatic_procedure_id: str,
) -> dict[str, Any]:
    """Replicate the 5.5.24 web client's validated minimal SOAP payload."""
    return {
        "id": str(attendance_id),
        "antecedentes": {
            "pessoal": {
                "puericultura": {},
                "informacoesObstetricas": {"desfechoUltimaGestacao": "NAO_INFORMADO"},
                "cirurgiasInternacoes": [],
            },
            "familiar": {},
        },
        "subjetivo": {"texto": _html_paragraph(encounter.subjective)},
        "objetivo": {
            "texto": _html_paragraph(encounter.objective),
            "medicoes": encounter.measurements or None,
            "puericultura": None,
        },
        "avaliacao": {
            "texto": _html_paragraph(encounter.assessment),
            "problemasCondicoesAvaliadas": [
                *(
                    [
                        {
                            **({"ciapId": str(ciap_id)} if ciap_id else {}),
                            **({"cidId": str(cid10_id)} if cid10_id else {}),
                            **(
                                {
                                    "incluirListaProblemas": True,
                                    "situacao": "ATIVO",
                                }
                                if encounter.include_problem
                                else {}
                            ),
                        }
                    ]
                    if ciap_id or cid10_id
                    else []
                ),
                *[
                    {
                        "id": item["evaluation_id"],
                        "cidId": item["cid10_id"],
                        "problemaId": item["problem_id"],
                        "incluirListaProblemas": True,
                        "situacao": "RESOLVIDO",
                        "dataInicio": item.get("start_date"),
                        "dataFim": (
                            resolution_date.isoformat() if resolution_date else None
                        ),
                        "observacao": "Condição sintética resolvida em seguimento.",
                    }
                    for item in resolved_problems
                ],
            ],
            "alergiasAvaliadas": [],
            "vigilanciaSaudeBucal": None,
        },
        "plano": {
            "texto": _html_paragraph(encounter.plan),
            "procedimentos": [],
            "prescricaoMedicamento": (
                {"medicamentos": list(prescription_inputs)}
                if prescription_inputs
                else None
            ),
            "compartilhamentosCuidado": None,
        },
        "finalizacao": {
            "tipoAtendimento": "CONSULTA_NO_DIA",
            "procedimentosAdministrativos": [
                {"id": str(automatic_procedure_id), "automatico": True}
            ],
            "condutas": ["RETORNO_PARA_CUIDADO_CONTINUADO_PROGRAMADO"],
            "desfechoAtendimento": {"manterCidadaoLista": False},
            "agendamentoConsultas": {"enviarComprovantesParaCidadao": False},
            "tipoParticipacaoCidadao": "PRESENCIAL",
            "tipoParticipacaoProfissionalConvidado": "NAO_PARTICIPOU",
        },
        "medicoesAnteriores": [],
        "lembretes": [],
        "registrosVacinacao": [],
        "problemasECondicoes": [],
    }


def _load_manifest(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {"version": 4, "encounters": {}}
    try:
        content = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise PecClientError(f"invalid clinical manifest {path}: {error}") from error
    if content.get("version") != 4 or not isinstance(content.get("encounters"), dict):
        raise PecClientError(
            f"unsupported clinical manifest {path}; regenerate the demo "
            "database and manifest for the longitudinal v4 cohort"
        )
    return content


def _write_manifest(path: Path, content: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{path.name}.", dir=path.parent, text=True
    )
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8", newline="\n") as stream:
            json.dump(content, stream, ensure_ascii=False, indent=2, sort_keys=True)
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary_name, path)
    except BaseException:
        try:
            os.unlink(temporary_name)
        except FileNotFoundError:
            pass
        raise


def provision_clinical_histories(
    patients: tuple[SyntheticPatient, ...],
    *,
    client: PecGraphQLClient,
    assignments: tuple[ClinicalAssignment, ...],
    reference_date: date,
    manifest_path: Path,
) -> tuple[ProvisionedEncounter, ...]:
    """Create 2-10 verified, finalized SOAP encounters per citizen."""
    by_role = {assignment.role: assignment for assignment in assignments}
    if set(by_role) != {"medico", "enfermagem"}:
        raise PecClientError("clinical assignments must include medico and enfermagem")

    # Citizen lookup is protected by an operational access. Select the medical
    # assignment before resolving the cohort, then switch per encounter group.
    doctor = by_role["medico"]
    client.select_assignment_access(cnes=doctor.cnes, cbo2002=doctor.cbo2002)
    citizens: dict[str, str] = {}
    medical_records: dict[str, str] = {}
    for patient in patients:
        citizen = client.citizen_by_cpf(patient.cpf)
        if not citizen:
            raise PecClientError(
                f"synthetic citizen {patient.key} must be provisioned first"
            )
        citizens[patient.key] = str(citizen["id"])
        medical_record = citizen.get("prontuario") or {}
        if not medical_record.get("id"):
            raise PecClientError(
                f"synthetic citizen {patient.key} has no medical record"
            )
        medical_records[patient.key] = str(medical_record["id"])

    manifest = _load_manifest(manifest_path)
    results = []
    current_role = None
    procedure_ids: dict[str, str] = {}
    cid_ids: dict[tuple[str, str], str] = {}
    medications: dict[str, dict[str, Any]] = {}
    oral_application_id: str | None = None
    fallback_dose_unit_id: str | None = None
    for patient in patients:
        sex = "FEMININO" if patient.sex == "F" else "MASCULINO"
        age = _age_on(patient.birth_date, reference_date)

        def resolve_cid_id(code: str) -> str:
            cache_key = (patient.key, code)
            if cache_key not in cid_ids:
                cid_ids[cache_key] = client.cid10_id(code, sex=sex, age=age)
            return cid_ids[cache_key]

        for encounter in build_encounter_plan(patient):
            role = encounter.role
            if role != current_role:
                assignment = by_role[role]
                client.select_assignment_access(
                    cnes=assignment.cnes,
                    cbo2002=assignment.cbo2002,
                )
                current_role = role
            if role not in procedure_ids:
                procedure_ids[role] = client.automatic_procedure_id(
                    by_role[role].automatic_procedure_code
                )
            previous = manifest["encounters"].get(encounter.key)
            if previous:
                results.append(ProvisionedEncounter(**previous))
                continue
            # PEC's standard nursing access is CIAP-only. Medical encounters
            # receive selective CID-10 coding; omissions are intentional.
            if role == "medico" and encounter.cid10_code:
                ciap_id = None
                cid10_id = resolve_cid_id(encounter.cid10_code)
            else:
                ciap_id = (
                    client.ciap_id(PREVENTIVE_CIAP, sex=sex, age=age)
                    if role == "enfermagem"
                    else None
                )
                cid10_id = None
            resolved = []
            for code in encounter.resolve_cid10_codes:
                resolved_cid_id = resolve_cid_id(code)
                problem = client.active_problem_by_cid(
                    medical_record_id=medical_records[patient.key],
                    cid10_id=resolved_cid_id,
                )
                if not problem:
                    raise PecClientError(
                        f"active synthetic problem {code} was not found "
                        f"before encounter {encounter.key}"
                    )
                evaluation = problem.get("evolucaoAvaliacaoCiapCid") or {}
                last_evolution = problem.get("ultimaEvolucao") or {}
                if not evaluation.get("id"):
                    raise PecClientError(
                        f"synthetic problem {code} has no evaluation link"
                    )
                resolved.append(
                    {
                        "cid10_id": resolved_cid_id,
                        "problem_id": str(problem["id"]),
                        "evaluation_id": str(evaluation["id"]),
                        "start_date": last_evolution.get("dataInicio"),
                    }
                )
            prescription_inputs = []
            for prescription in encounter.prescriptions:
                if oral_application_id is None:
                    oral_application_id = client.medication_application_id("Oral")
                if fallback_dose_unit_id is None:
                    fallback_dose_unit_id = client.dose_unit_id("Comprimido")
                if prescription.medication_query not in medications:
                    medications[prescription.medication_query] = client.medication(
                        prescription.medication_query,
                        concentration=prescription.concentration,
                    )
                prescription_inputs.append(
                    _build_prescription_input(
                        prescription,
                        medication=medications[prescription.medication_query],
                        oral_application_id=oral_application_id,
                        fallback_dose_unit_id=fallback_dose_unit_id,
                    )
                )
            attendance = client.save_attendance(citizens[patient.key])
            attendance_id = str(attendance["id"])
            started = client.start_individual_attendance(attendance_id)
            try:
                finalized = client.save_individual_attendance(
                    build_individual_attendance_input(
                        encounter,
                        attendance_id=attendance_id,
                        ciap_id=ciap_id,
                        cid10_id=cid10_id,
                        resolved_problems=tuple(resolved),
                        prescription_inputs=tuple(prescription_inputs),
                        # Attendances are created through the live PEC API and cannot
                        # be backdated to the cohort reference date.
                        resolution_date=date.today(),
                        automatic_procedure_id=procedure_ids[role],
                    )
                )
            except PecClientError as error:
                raise PecClientError(
                    f"failed to finalize synthetic encounter {encounter.key}: {error}"
                ) from error
            result = ProvisionedEncounter(
                key=encounter.key,
                patient_key=patient.key,
                role=role,
                citizen_id=citizens[patient.key],
                attendance_id=attendance_id,
                attendance_professional_id=str(finalized["atendProf"]["id"]),
            )
            started_id = str(started["atendimentoProfissional"]["id"])
            if result.attendance_professional_id != started_id:
                raise PecClientError(
                    f"professional attendance changed while finalizing {encounter.key}"
                )
            manifest["encounters"][encounter.key] = asdict(result)
            _write_manifest(manifest_path, manifest)
            results.append(result)
    return tuple(results)
