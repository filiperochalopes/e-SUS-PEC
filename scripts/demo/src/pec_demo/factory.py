"""Build the deterministic CNES cohort used by the demo."""

from __future__ import annotations

from calendar import monthrange
from datetime import date
import hashlib
from random import Random
import unicodedata

from faker import Faker

from pec_demo.identifiers import (
    generate_cnpj,
    generate_cns,
    generate_cpf,
    generate_numeric_code,
)
from pec_demo.models import (
    Address,
    Assignment,
    DemoDataset,
    HealthUnit,
    Professional,
    Team,
)
from pec_demo.version import DEFAULT_PEC_VERSION


# Community health agent; the CBO that authors individual registration forms.
ACS_CBO = "515105"


def _upper_asciiish(value: str) -> str:
    normalized = unicodedata.normalize("NFKC", value)
    letters_and_spaces = "".join(
        character
        for character in normalized
        if character.isalpha() or character.isspace()
    )
    return " ".join(letters_and_spaces.upper().split())


def _demo_password(seed: int, key: str) -> str:
    digest = hashlib.sha256(f"pec-demo:{seed}:{key}".encode()).hexdigest()[:14]
    # The PEC rejects passwords containing tokens from personal data. Synthetic
    # names deliberately contain "DEMO", so the password must not repeat it.
    return f"P7!{digest}"


def _subtract_years(value: date, years: int) -> date:
    year = value.year - years
    day = min(value.day, monthrange(year, value.month)[1])
    return value.replace(year=year, day=day)


def build_demo_dataset(
    *,
    seed: int,
    municipality_ibge: str,
    uf: str,
    cep: str,
    generated_on: date,
    pec_version: str = DEFAULT_PEC_VERSION,
    include_acs: bool = False,
) -> DemoDataset:
    """Create two units, two teams, three professionals and four assignments."""
    rng = Random(seed)
    fake = Faker("pt_BR")
    fake.seed_instance(seed)

    used_cnes: set[str] = set()
    used_ine: set[str] = set()
    cnes_1 = generate_numeric_code(rng, width=7, prefix="99", used=used_cnes)
    cnes_2 = generate_numeric_code(rng, width=7, prefix="99", used=used_cnes)
    ine_1 = generate_numeric_code(rng, width=10, prefix="99", used=used_ine)
    ine_2 = generate_numeric_code(rng, width=10, prefix="99", used=used_ine)

    team_1 = Team(
        ine=ine_1,
        type_code="01",
        abbreviation="ESF DEMO 01",
        description="EQUIPE DE SAUDE DA FAMILIA DEMO 01",
        area_code="0001",
        area_description="AREA DEMO 01",
        reference_name="EQUIPE DEMO NORTE",
    )
    team_2 = Team(
        ine=ine_2,
        type_code="01",
        abbreviation="ESF DEMO 02",
        description="EQUIPE DE SAUDE DA FAMILIA DEMO 02",
        area_code="0002",
        area_description="AREA DEMO 02",
        reference_name="EQUIPE DEMO SUL",
    )

    unit_1 = HealthUnit(
        name="UBS DEMONSTRACAO NORTE",
        cnpj=generate_cnpj(rng),
        cnes=cnes_1,
        unit_type_code="2",
        unit_type_description="CENTRO DE SAUDE/UNIDADE BASICA",
        address=Address(
            cep=cep,
            uf=uf,
            municipality_ibge=municipality_ibge,
            neighborhood="BAIRRO DEMONSTRACAO NORTE",
            street="RUA DOS DADOS SINTETICOS",
            number="100",
            reference="AMBIENTE EXCLUSIVO DE TESTES",
        ),
        teams=(team_1,),
    )
    unit_2 = HealthUnit(
        name="UBS DEMONSTRACAO SUL",
        cnpj=generate_cnpj(rng),
        cnes=cnes_2,
        unit_type_code="2",
        unit_type_description="CENTRO DE SAUDE/UNIDADE BASICA",
        address=Address(
            cep=cep,
            uf=uf,
            municipality_ibge=municipality_ibge,
            neighborhood="BAIRRO DEMONSTRACAO SUL",
            street="AVENIDA DA BASE SINTETICA",
            number="200",
            reference="SEM VINCULO COM ESTABELECIMENTO REAL",
        ),
        teams=(team_2,),
    )

    roles = (
        (
            "multiprofile",
            "F",
            32,
            48,
            (
                Assignment(cnes=cnes_1, ine=ine_1, cbo="225130"),
                Assignment(cnes=cnes_2, ine=ine_2, cbo="223505"),
            ),
            (
                "INSTALADOR",
                "ADMINISTRADOR_MUNICIPAL",
                "MEDICO",
                "ENFERMEIRO",
            ),
        ),
        (
            "medico",
            "M",
            29,
            55,
            (Assignment(cnes=cnes_2, ine=ine_2, cbo="225130"),),
            ("MEDICO",),
        ),
        (
            "enfermeiro",
            "F",
            25,
            50,
            (Assignment(cnes=cnes_1, ine=ine_1, cbo="223505"),),
            ("ENFERMEIRO",),
        ),
    )

    if include_acs:
        roles += tuple(
            (f"acs_{i + 1}", "F", 30, 45,
             (Assignment(cnes=unit.cnes, ine=unit.teams[0].ine, cbo=ACS_CBO),),
             ("AGENTE_COMUNITARIO_SAUDE",))
            for i, unit in enumerate((unit_1, unit_2))
        )

    professionals: list[Professional] = []
    for key, sex, min_age, max_age, assignments, profiles in roles:
        generated_name = _upper_asciiish(fake.name())
        birth_date = fake.date_between_dates(
            date_start=_subtract_years(generated_on, max_age + 1),
            date_end=_subtract_years(generated_on, min_age),
        )
        professionals.append(
            Professional(
                key=key,
                name=f"PROFISSIONAL DEMO {generated_name}",
                cpf=generate_cpf(rng),
                cns=generate_cns(rng),
                birth_date=birth_date,
                sex=sex,
                assignments=assignments,
                planned_profiles=profiles,
                planned_password=_demo_password(seed, key),
                email=f"{key}@demo.pec.br",
            )
        )

    return DemoDataset(
        seed=seed,
        pec_version=pec_version,
        generated_on=generated_on,
        municipality_ibge=municipality_ibge,
        uf=uf,
        units=(unit_1, unit_2),
        professionals=tuple(professionals),
    )
