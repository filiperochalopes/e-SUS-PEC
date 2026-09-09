"""Create the synthetic citizen cohort through PEC's official mutation."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from pec_demo.patients import SyntheticPatient
from pec_demo.pec_client import PecClientError, PecGraphQLClient


@dataclass(frozen=True, slots=True)
class ProvisionedCitizen:
    patient: SyntheticPatient
    pec_id: str
    created: bool


@dataclass(frozen=True, slots=True)
class TerritoryAssignment:
    """A PEC team and its synthetic microareas used by the demo cohort."""

    cnes: str
    ine: str
    cbo2002: str
    microareas: tuple[str, ...] = ("01", "02", "03")


def _citizen_input(
    patient: SyntheticPatient,
    *,
    citizen_id: str | None = None,
    municipality_id: str,
    professional_cns: str,
    cnes: str,
    ine: str,
    cbo2002: str,
    microarea: str,
) -> dict[str, Any]:
    return {
        "id": citizen_id,
        "nome": patient.name,
        "sexo": "FEMININO" if patient.sex == "F" else "MASCULINO",
        "dataNascimento": patient.birth_date.isoformat(),
        "cpf": patient.cpf,
        "cns": patient.cns,
        "stNaoPossuiCpf": False,
        "justificativaNaoPossuiCpf": None,
        "racaCor": patient.race,
        "nacionalidade": "BRASILEIRA",
        "municipioNascimento": municipality_id,
        "dataEntradaPais": None,
        "paisNascimento": "31",
        "dataNaturalizacao": None,
        "portariaNaturalizacao": None,
        "nomePai": patient.father_name,
        "nomeMae": patient.mother_name,
        "desejaInformarOrientacaoSexual": False,
        "identidadeGenero": None,
        "desejaInformarIdentidadeGenero": False,
        "orientacaoSexual": None,
        "vinculacaoCidadaoTerritorio": {
            "cbo2002": cbo2002,
            "cnes": cnes,
            "cns": professional_cns,
            "ine": ine,
            "microarea": microarea,
            "foraDeArea": False,
        },
        "vinculacaoCidadaoFamilia": {"isResponsavelFamiliar": False},
        "telefoneCelular": patient.phone,
        "endereco": None,
        "paisResidenciaId": "31",
        "informacoesSocioEconomicas": None,
        "informacoesSociodemograficas": None,
        "condicoesSaudeAutorreferidas": None,
        "stCompartilhaProntuario": True,
        "stSituacaoDeRua": False,
        "situacaoDeRua": None,
        "isCidadaoAldeado": False,
        "cidadaoAldeadoInput": None,
        "tipoEndereco": "LOGRADOURO",
        "numeroFamilia": None,
    }


def provision_citizens(
    patients: tuple[SyntheticPatient, ...],
    *,
    client: PecGraphQLClient,
    municipality_ibge: str,
    municipality_name: str,
    cnes: str,
    ine: str,
    cbo2002: str = "225130",
    territory_assignments: tuple[TerritoryAssignment, ...] | None = None,
    update_existing_territory: bool = False,
) -> tuple[ProvisionedCitizen, ...]:
    """Create the cohort with a current FCI in one of the supplied microareas.

    Existing citizens are left untouched by default.  The pack factory opts in
    to ``update_existing_territory`` because its versioned bootstrap predates
    microarea support and must be upgraded through PEC's official mutation.
    """
    assignments = territory_assignments or (
        TerritoryAssignment(cnes=cnes, ine=ine, cbo2002=cbo2002),
    )
    if not assignments or any(not item.microareas for item in assignments):
        raise ValueError(
            "at least one territory assignment with microareas is required"
        )
    municipality_id = client.municipality_id_by_ibge(
        municipality_ibge,
        query=municipality_name,
    )
    results = []
    for index, patient in enumerate(patients):
        assignment = assignments[index % len(assignments)]
        microarea = assignment.microareas[
            (index // len(assignments)) % len(assignment.microareas)
        ]
        access = client.select_assignment_access(
            cnes=assignment.cnes,
            cbo2002=assignment.cbo2002,
        )
        session = client.session()
        professional_cns = session["profissional"].get("cns")
        if not professional_cns:
            raise PecClientError("authenticated professional has no CNS")
        team = access.get("equipe") or {}
        if team.get("ine") != assignment.ine:
            raise PecClientError(
                f"selected assignment has INE {team.get('ine')}, expected {assignment.ine}"
            )
        existing = client.citizen_by_cpf(patient.cpf)
        if existing:
            if existing.get("nome") != patient.name:
                raise PecClientError(
                    f"CPF collision for synthetic patient {patient.key}"
                )
            if update_existing_territory:
                client.save_citizen(
                    _citizen_input(
                        patient,
                        citizen_id=str(existing["id"]),
                        municipality_id=municipality_id,
                        professional_cns=professional_cns,
                        cnes=assignment.cnes,
                        ine=assignment.ine,
                        cbo2002=assignment.cbo2002,
                        microarea=microarea,
                    )
                )
            results.append(
                ProvisionedCitizen(patient, str(existing["id"]), created=False)
            )
            continue
        saved = client.save_citizen(
            _citizen_input(
                patient,
                municipality_id=municipality_id,
                professional_cns=professional_cns,
                cnes=assignment.cnes,
                ine=assignment.ine,
                cbo2002=assignment.cbo2002,
                microarea=microarea,
            )
        )
        verified = client.citizen_by_cpf(patient.cpf)
        if not verified or str(verified["id"]) != str(saved["id"]):
            raise PecClientError(f"could not verify saved citizen {patient.key}")
        results.append(ProvisionedCitizen(patient, str(saved["id"]), created=True))
    return tuple(results)
