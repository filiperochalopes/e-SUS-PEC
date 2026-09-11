"""Python replica of the CNES 5.5.24 validation invariants."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
import re

from validate_docbr import CNPJ, CNS, CPF

from pec_demo.models import DemoDataset


BRAZILIAN_UFS = frozenset(
    {
        "AC",
        "AL",
        "AP",
        "AM",
        "BA",
        "CE",
        "DF",
        "ES",
        "GO",
        "MA",
        "MT",
        "MS",
        "MG",
        "PA",
        "PB",
        "PR",
        "PE",
        "PI",
        "RJ",
        "RN",
        "RS",
        "RO",
        "RR",
        "SC",
        "SP",
        "SE",
        "TO",
    }
)


@dataclass(frozen=True, slots=True)
class CnesCatalog:
    """Version-bound catalog slice required by the synthetic cohort."""

    unit_type_codes: frozenset[str] = frozenset({"2"})
    complexity_codes: frozenset[str] = frozenset({"AB"})
    team_type_codes: frozenset[str] = frozenset({"01"})
    # Confirmed in tb_cbo of the restored 5.5.28 pack: 225130 MEDICO DE FAMILIA
    # E COMUNIDADE, 223505 ENFERMEIRO, 515105 AGENTE COMUNITARIO DE SAUDE.
    # The community health agent is what signs the individual registration
    # forms the territorial filters depend on.
    cbo_codes: frozenset[str] = frozenset({"225130", "223505", "515105"})
    uf_codes: frozenset[str] = BRAZILIAN_UFS


@dataclass(frozen=True, slots=True)
class ValidationIssue:
    path: str
    code: str
    message: str


@dataclass(frozen=True, slots=True)
class ValidationReport:
    issues: tuple[ValidationIssue, ...]

    @property
    def is_valid(self) -> bool:
        return not self.issues

    def require_valid(self) -> None:
        if self.is_valid:
            return
        details = "\n".join(
            f"- {issue.path}: {issue.code}: {issue.message}" for issue in self.issues
        )
        raise ValueError(f"CNES dataset is invalid:\n{details}")


class CnesReplicaValidator:
    """Mirror the relevant Java validators before handing XML to the PEC."""

    def __init__(self, catalog: CnesCatalog | None = None) -> None:
        self.catalog = catalog or CnesCatalog()
        self._cpf = CPF()
        self._cnpj = CNPJ()
        self._cns = CNS()

    def validate(self, dataset: DemoDataset) -> ValidationReport:
        issues: list[ValidationIssue] = []

        def add(path: str, code: str, message: str) -> None:
            issues.append(ValidationIssue(path, code, message))

        if not re.fullmatch(r"\d{7}", dataset.municipality_ibge):
            add("identification.municipality_ibge", "format", "must have 7 digits")
        if dataset.uf not in self.catalog.uf_codes:
            add("identification.uf", "catalog", "UF does not exist")
        if dataset.xsd_version != "3.1":
            add("identification.xsd_version", "version", "must be 3.1")
        if dataset.origin != "PORTAL" or dataset.destination != "ESUS_AB":
            add(
                "identification",
                "routing",
                "origin/destination must be PORTAL/ESUS_AB",
            )

        unit_by_cnes = {}
        team_pairs: set[tuple[str, str]] = set()
        seen_ines: set[str] = set()
        for unit_index, unit in enumerate(dataset.units):
            path = f"units[{unit_index}]"
            if not unit.name.strip():
                add(f"{path}.name", "required", "unit name is required")
            if not self._cnpj.validate(unit.cnpj):
                add(f"{path}.cnpj", "cnpj", "invalid CNPJ")
            if not re.fullmatch(r"\d{7}", unit.cnes):
                add(f"{path}.cnes", "format", "CNES must have 7 digits")
            elif unit.cnes in unit_by_cnes:
                add(f"{path}.cnes", "duplicate", "CNES must be unique")
            else:
                unit_by_cnes[unit.cnes] = unit
            if unit.unit_type_code not in self.catalog.unit_type_codes:
                add(f"{path}.unit_type_code", "catalog", "invalid unit type")
            if not unit.unit_type_description.strip():
                add(
                    f"{path}.unit_type_description",
                    "required",
                    "unit type description is required",
                )
            if not unit.complexities:
                add(f"{path}.complexities", "required", "complexity is required")
            for complexity in unit.complexities:
                if complexity not in self.catalog.complexity_codes:
                    add(
                        f"{path}.complexities",
                        "catalog",
                        f"invalid complexity: {complexity}",
                    )
            self._validate_unit_address(
                path,
                unit.address,
                dataset.municipality_ibge,
                dataset.uf,
                add,
            )

            for team_index, team in enumerate(unit.teams):
                team_path = f"{path}.teams[{team_index}]"
                if team.type_code not in self.catalog.team_type_codes:
                    add(f"{team_path}.type_code", "catalog", "invalid team type")
                for field_name, value in (
                    ("abbreviation", team.abbreviation),
                    ("description", team.description),
                    ("reference_name", team.reference_name),
                ):
                    if not value.strip():
                        add(f"{team_path}.{field_name}", "required", "value is required")
                if not re.fullmatch(r"\d{10}", team.ine):
                    add(f"{team_path}.ine", "format", "INE must have 10 digits")
                elif team.ine in seen_ines:
                    add(f"{team_path}.ine", "duplicate", "INE must be unique")
                else:
                    seen_ines.add(team.ine)
                    team_pairs.add((unit.cnes, team.ine))
                if team.home_care_type not in {"", "NASF", "EMAD", "EMAP", "EMSI", "EMSIAL"}:
                    add(
                        f"{team_path}.home_care_type",
                        "enum",
                        "invalid home-care team type",
                    )
                if team.deactivation_date:
                    try:
                        datetime.strptime(team.deactivation_date, "%d/%m/%Y")
                    except ValueError:
                        add(
                            f"{team_path}.deactivation_date",
                            "date",
                            "must use dd/MM/yyyy",
                        )

        cpf_to_cns: dict[str, str] = {}
        cns_to_cpf: dict[str, str] = {}
        for professional_index, professional in enumerate(dataset.professionals):
            path = f"professionals[{professional_index}]"
            if not professional.name.strip():
                add(f"{path}.name", "required", "professional name is required")
            if "DEMO" not in professional.name.upper():
                add(f"{path}.name", "synthetic-marker", "name must contain DEMO")
            if not self._cpf.validate(professional.cpf):
                add(f"{path}.cpf", "cpf", "invalid CPF")
            if not self._cns.validate(professional.cns):
                add(f"{path}.cns", "cns", "invalid CNS")
            previous_cns = cpf_to_cns.setdefault(professional.cpf, professional.cns)
            previous_cpf = cns_to_cpf.setdefault(professional.cns, professional.cpf)
            if previous_cns != professional.cns or previous_cpf != professional.cpf:
                add(
                    path,
                    "cpf-cns-pair",
                    "CPF or CNS conflicts with another professional",
                )
            if professional.sex not in {"F", "M"}:
                add(f"{path}.sex", "enum", "sex must be F or M")
            if not professional.assignments:
                add(f"{path}.assignments", "required", "assignment is required")

            seen_assignments: set[tuple[str, str, str]] = set()
            for assignment_index, assignment in enumerate(professional.assignments):
                assignment_path = f"{path}.assignments[{assignment_index}]"
                key = (assignment.cnes, assignment.ine, assignment.cbo)
                if key in seen_assignments:
                    add(assignment_path, "duplicate", "assignment is duplicated")
                seen_assignments.add(key)
                if assignment.cnes not in unit_by_cnes:
                    add(assignment_path, "cnes-reference", "CNES does not resolve")
                if assignment.cbo not in self.catalog.cbo_codes:
                    add(assignment_path, "cbo-catalog", "CBO is not eligible")
                if assignment.ine and (assignment.cnes, assignment.ine) not in team_pairs:
                    add(
                        assignment_path,
                        "ine-reference",
                        "INE does not belong to the assignment CNES",
                    )
                if assignment.microarea and not re.fullmatch(r"\d{1,2}", assignment.microarea):
                    add(
                        f"{assignment_path}.microarea",
                        "format",
                        "microarea must have 1 or 2 digits",
                    )

        if len(dataset.units) < 2:
            add("units", "demo-diversity", "demo requires at least two units")
        if len(team_pairs) < 2:
            add("teams", "demo-diversity", "demo requires at least two teams")
        if len(dataset.professionals) < 3:
            add(
                "professionals",
                "demo-diversity",
                "demo requires at least three professionals",
            )
        if sum(len(item.assignments) for item in dataset.professionals) < 4:
            add(
                "assignments",
                "demo-diversity",
                "demo requires at least four assignments",
            )
        if not any(len(item.assignments) >= 2 for item in dataset.professionals):
            add(
                "assignments",
                "demo-diversity",
                "one professional must have multiple assignments",
            )

        return ValidationReport(tuple(issues))

    def _validate_unit_address(
        self,
        path,
        address,
        expected_municipality,
        expected_uf,
        add,
    ) -> None:
        if not re.fullmatch(r"\d{8}", address.cep):
            add(f"{path}.address.cep", "format", "CEP must have 8 digits")
        if address.uf not in self.catalog.uf_codes:
            add(f"{path}.address.uf", "catalog", "UF does not exist")
        if address.uf != expected_uf:
            add(f"{path}.address.uf", "municipality", "UF differs from import UF")
        if address.municipality_ibge != expected_municipality:
            add(
                f"{path}.address.municipality_ibge",
                "municipality",
                "unit does not belong to the import municipality",
            )
        for field_name, value in (
            ("neighborhood", address.neighborhood),
            ("street", address.street),
            ("number", address.number),
        ):
            if not value.strip():
                add(f"{path}.address.{field_name}", "required", "value is required")
