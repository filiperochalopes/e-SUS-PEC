"""Refresh a restored demo pack exclusively through official PEC contracts."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
import json
from pathlib import Path

from pec_demo.citizens import TerritoryAssignment, provision_citizens
from pec_demo.clinical import (
    ClinicalAssignment,
    DOCTOR_CBO,
    DOCTOR_PROCEDURE,
    NURSE_CBO,
    NURSE_PROCEDURE,
    build_encounter_plan,
    provision_clinical_histories,
)
from pec_demo.factory import build_demo_dataset
from pec_demo.patients import build_patient_cohort
from pec_demo.coverage import CASES, build_coverage_cohort
from pec_demo.pec_client import PecClientError, PecGraphQLClient
from pec_demo.provisioning import provision_demo_credentials
from pec_demo.provisioning import validate_demo_credentials


@dataclass(frozen=True, slots=True)
class RefreshedPack:
    credentials: int
    assignments: int
    patients: int
    patients_created: int
    histories: int
    cnes_import_id: str


@dataclass(frozen=True, slots=True)
class ValidatedPack:
    credentials: int
    assignments: int
    patients: int
    histories: int


def _sum_stat(
    import_result: dict,
    new_field: str,
    updated_field: str,
) -> int:
    return int(import_result.get(new_field) or 0) + int(
        import_result.get(updated_field) or 0
    )


def refresh_demo_pack(
    *,
    base_url: str,
    cnes_archive: Path,
    credentials_path: Path,
    clinical_manifest_path: Path,
    municipality_ibge: str,
    municipality_name: str,
    uf: str,
    cep: str,
    seed: int,
    generated_on: date,
    pec_version: str,
    reference_date: date | None = None,
) -> RefreshedPack:
    """Import CNES, normalize credentials, and idempotently refresh clinical data."""
    dataset = build_demo_dataset(
        seed=seed,
        municipality_ibge=municipality_ibge,
        uf=uf,
        cep=cep,
        generated_on=generated_on,
        pec_version=pec_version,
        include_acs=reference_date is not None,
    )
    administrator = next(
        item for item in dataset.professionals if item.key == "multiprofile"
    )
    importer = PecGraphQLClient(base_url)
    importer.login(administrator.cpf, administrator.planned_password)
    importer.select_general_admin_access()
    municipality_id = importer.municipality_id_by_ibge(
        municipality_ibge,
        query=municipality_name,
    )
    imported = importer.import_cnes_and_wait(
        cnes_archive,
        municipality_id=municipality_id,
    )
    expected = (
        (
            "unidades de saúde",
            "unidadesSaudeNovas",
            "unidadesSaudeAtualizadas",
            len(dataset.units),
        ),
        (
            "equipes",
            "equipesNovas",
            "equipesAtualizadas",
            sum(len(unit.teams) for unit in dataset.units),
        ),
        (
            "profissionais",
            "profissionaisNovos",
            "profissionaisAtualizados",
            len(dataset.professionals),
        ),
        (
            "lotações",
            "lotacoesNovas",
            "lotacoesAtualizadas",
            sum(len(item.assignments) for item in dataset.professionals),
        ),
    )
    for label, new_field, updated_field, minimum in expected:
        if _sum_stat(imported, new_field, updated_field) < minimum:
            raise PecClientError(f"CNES import processed fewer {label} than expected")

    credentials = provision_demo_credentials(
        dataset,
        base_url=base_url,
        admin_login=administrator.cpf,
        admin_password=administrator.planned_password,
        credentials_path=credentials_path,
    )
    cohort = build_patient_cohort(seed=seed, generated_on=generated_on)
    medical_unit = dataset.units[0]
    nursing_unit = dataset.units[1]
    medical_team = medical_unit.teams[0]

    clinical_client = PecGraphQLClient(base_url)
    clinical_client.login(
        administrator.cpf,
        administrator.planned_password,
    )
    patients = provision_citizens(
        cohort,
        client=clinical_client,
        municipality_ibge=municipality_ibge,
        municipality_name=municipality_name,
        cnes=medical_unit.cnes,
        ine=medical_team.ine,
        cbo2002=DOCTOR_CBO,
        territory_assignments=(
            TerritoryAssignment(
                cnes=medical_unit.cnes,
                ine=medical_team.ine,
                cbo2002=DOCTOR_CBO,
            ),
            TerritoryAssignment(
                cnes=nursing_unit.cnes,
                ine=nursing_unit.teams[0].ine,
                cbo2002=NURSE_CBO,
            ),
        ),
        update_existing_territory=False,
    )
    histories = provision_clinical_histories(
        cohort,
        client=clinical_client,
        assignments=(
            ClinicalAssignment(
                "medico",
                medical_unit.cnes,
                DOCTOR_CBO,
                DOCTOR_PROCEDURE,
            ),
            ClinicalAssignment(
                "enfermagem",
                nursing_unit.cnes,
                NURSE_CBO,
                NURSE_PROCEDURE,
            ),
        ),
        reference_date=generated_on,
        manifest_path=clinical_manifest_path,
    )
    if reference_date is not None:
        extension = build_coverage_cohort(seed=seed, reference_date=reference_date)
        for patient in extension:
            case = CASES[patient.key]
            unit = dataset.units[case.unit]
            acs = next(p for p in dataset.professionals if p.key == f"acs_{case.unit + 1}")
            registration_client = PecGraphQLClient(base_url)
            registration_client.login(acs.cpf, acs.planned_password)
            patients += provision_citizens(
                (patient,), client=registration_client,
                municipality_ibge=municipality_ibge, municipality_name=municipality_name,
                cnes=unit.cnes, ine=unit.teams[0].ine, cbo2002="515105",
                territory_assignments=(TerritoryAssignment(unit.cnes, unit.teams[0].ine, "515105", (case.microarea,)),),
            )
        histories += provision_clinical_histories(
            extension, client=clinical_client,
            assignments=(
                ClinicalAssignment("medico", medical_unit.cnes, DOCTOR_CBO, DOCTOR_PROCEDURE),
                ClinicalAssignment("enfermagem", nursing_unit.cnes, NURSE_CBO, NURSE_PROCEDURE),
            ), reference_date=reference_date, manifest_path=clinical_manifest_path,
        )
    return RefreshedPack(
        credentials=len(credentials),
        assignments=sum(len(item.assignments) for item in credentials),
        patients=len(patients),
        patients_created=sum(item.created for item in patients),
        histories=len(histories),
        cnes_import_id=str(imported["id"]),
    )


def validate_demo_pack(
    *,
    base_url: str,
    clinical_manifest_path: Path,
    municipality_ibge: str,
    uf: str,
    cep: str,
    seed: int,
    generated_on: date,
    pec_version: str,
    reference_date: date | None = None,
) -> ValidatedPack:
    """Strictly validate a restored pack without importing or writing."""
    dataset = build_demo_dataset(
        seed=seed,
        municipality_ibge=municipality_ibge,
        uf=uf,
        cep=cep,
        generated_on=generated_on,
        pec_version=pec_version,
        include_acs=reference_date is not None,
    )
    credentials = validate_demo_credentials(dataset, base_url=base_url)
    administrator = next(
        item for item in dataset.professionals if item.key == "multiprofile"
    )
    cohort = build_patient_cohort(seed=seed, generated_on=generated_on)
    if reference_date is not None:
        cohort += build_coverage_cohort(seed=seed, reference_date=reference_date)
    medical_unit = dataset.units[0]
    nursing_unit = dataset.units[1]
    client = PecGraphQLClient(base_url)
    client.login(administrator.cpf, administrator.planned_password)
    client.select_assignment_access(
        cnes=medical_unit.cnes,
        cbo2002=DOCTOR_CBO,
    )
    citizens = {}
    for patient in cohort:
        citizen = client.citizen_by_cpf(patient.cpf)
        if not citizen or citizen.get("nome") != patient.name:
            raise PecClientError(
                f"missing or mismatched synthetic citizen {patient.key}"
            )
        citizens[patient.key] = str(citizen["id"])

    try:
        manifest = json.loads(clinical_manifest_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise PecClientError(f"invalid clinical manifest: {error}") from error
    encounters = manifest.get("encounters")
    if manifest.get("version") != 4 or not isinstance(encounters, dict):
        raise PecClientError("unsupported clinical manifest")
    planned = {
        item.key: item for patient in cohort for item in build_encounter_plan(patient)
    }
    if set(encounters) != set(planned):
        raise PecClientError("clinical manifest differs from the encounter plan")

    current_role = None
    for key in sorted(planned):
        plan = planned[key]
        if plan.role != current_role:
            assignment = (
                (medical_unit.cnes, DOCTOR_CBO)
                if plan.role == "medico"
                else (nursing_unit.cnes, NURSE_CBO)
            )
            client.select_assignment_access(
                cnes=assignment[0],
                cbo2002=assignment[1],
            )
            current_role = plan.role
        record = encounters[key]
        attendance = client.individual_attendance(record["attendance_professional_id"])
        if not attendance.get("finalizadoEm"):
            raise PecClientError(f"clinical encounter {key} is not finalized")
        citizen_id = ((attendance.get("atendimento") or {}).get("cidadao") or {}).get(
            "id"
        )
        if str(citizen_id) != citizens[plan.patient_key]:
            raise PecClientError(f"clinical encounter {key} has another citizen")
        soap = (
            ("evolucaoSubjetivo", plan.subjective),
            ("evolucaoObjetivo", plan.objective),
            ("evolucaoAvaliacao", plan.assessment),
            ("evolucaoPlano", plan.plan),
        )
        for field, expected_text in soap:
            actual = (attendance.get(field) or {}).get("descricao") or ""
            if expected_text not in actual:
                raise PecClientError(f"clinical encounter {key} has mismatched {field}")
    return ValidatedPack(
        credentials=len(credentials),
        assignments=sum(len(item.assignments) for item in credentials),
        patients=len(citizens),
        histories=len(encounters),
    )
