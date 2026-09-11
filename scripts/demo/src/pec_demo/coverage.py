"""Versioned coverage contract for the synthetic demonstration cohort.

The contract is declared before any generator runs.  It states, for every
scenario: a stable key, the team and microarea it belongs to, its age band,
how many encounters it has and when, which clinical facts each encounter must
produce, which gaps are deliberate, and which consumers (MCP tools and Saude
360 components) the scenario exercises.

Two rules protect the bootstrap cohort:

* the ten protected patients are built by :mod:`pec_demo.patients` and are
  never produced here;
* identities are derived from ``seed`` and the scenario key alone, through an
  independent random state, so appending a scenario cannot shift the identity
  of any existing patient.

Procedures are always referenced by natural code, never by the internal id of
one particular catalog.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import date, timedelta
import hashlib

from pec_demo.patients import (
    SyntheticPatient,
    _subtract_years,
    build_patient_cohort,
)


CONTRACT_VERSION = 5

# Identities of the extended cohort are drawn at a fixed epoch so that moving
# the clinical reference date renews chronology without renaming anybody.
IDENTITY_EPOCH = date(2026, 7, 27)

# Natural procedure codes confirmed in the catalog inspection.  Consumers must
# resolve these, never the internal ids of a single pack.
HBA1C_CODES = ("0202010503", "ABEX008")
FOOT_EXAM_CODES = ("0301040095", "ABPG011")
CYTOLOGY_CODES = ("0201020033", "0203010019", "ABEX001", "ABPG010")
MAMMOGRAPHY_CODES = ("0204030030", "0204030188", "ABEX010", "ABEX011")
# Confirmed in tb_proced: 0205020143 is ULTRASSONOGRAFIA OBSTETRICA. It is one
# of the imaging exams that require a structured gestational-age result.
# Confirmed in ProcedimentoExameDetalheEspecificoDbEnum.PRENATAL, whose codes
# are exactly the obstetric ultrasound procedures.
OBSTETRIC_ULTRASOUND_CODES = ("0205020143", "ABEX024")

# PEC refuses a prenatal block unless the evaluated condition carries a
# related CIAP-2 and CID-10 pair.
PREGNANCY_CIAP = "W78"
PREGNANCY_CID = "Z34.0"

TEAM_COUNT = 2
MICROAREAS = ("01", "02", "03")

# Recency classes described by the plan.  ``never`` has no encounter at all,
# ``overdue`` is the active-search control, ``recent`` is everyone else.
RECENCY_RECENT = "recent"
RECENCY_OVERDUE = "overdue"
RECENCY_NEVER = "never"


@dataclass(frozen=True, slots=True)
class PlannedExam:
    """A structured exam result attached to an encounter.

    Some exams carry a structured result instead of free text.  PEC lists them
    in ``ProcedimentoExameDetalheEspecificoDbEnum`` and rejects a plain
    ``resultado`` for any of them, so those scenarios name the enum value and
    supply the measured quantity.
    """

    codes: tuple[str, ...]
    label: str
    value: str
    encounter: int
    days_before_encounter: int = 0
    specific_procedure: str | None = None
    numeric_value: float | None = None
    gestational_weeks: int | None = None
    gestational_days: int | None = None


@dataclass(frozen=True, slots=True)
class PlannedProcedure:
    """A clinical procedure performed during the encounter.

    The diabetic foot assessment belongs here, not to the exam results: PEC
    only accepts diagnostic-purpose procedures as exam results, and the foot
    assessment is a clinical procedure.
    """

    codes: tuple[str, ...]
    label: str
    note: str
    encounter: int


@dataclass(frozen=True, slots=True)
class PlannedVaccination:
    """An effective dose, recorded with its own application date.

    ``immunobiological`` is the exact catalog name and ``search`` the term that
    narrows the server-side query; ``dose`` is the exact dose acronym.  All
    three were read from ``tb_imunobiologico``/``tb_dose_imunobiologico`` of the
    restored 5.5.28 pack.
    """

    immunobiological: str
    search: str
    dose: str
    encounter: int
    days_before_encounter: int = 0


# Exact catalog names, confirmed in the restored 5.5.28 pack.  The adult and
# the infant dTpa share an acronym up to letter case, so only the full name
# identifies them safely.
INFLUENZA = ("Vacina influenza tetravalente", "influenza tetravalente")
HPV = ("Vacina HPV quadrivalente", "HPV")
DTPA_ADULT = ("Vacina dTpa adulto", "dTpa")
PENTAVALENT = ("Vacina penta (DTP/HB/Hib)", "penta")
MMR = ("Vacina tríplice viral", "viral")


@dataclass(frozen=True, slots=True)
class PlannedScreening:
    """A cancer-screening request evaluated by the C7 component."""

    kind: str
    codes: tuple[str, ...]
    encounter: int
    days_before_encounter: int = 0


@dataclass(frozen=True, slots=True)
class PlannedProblem:
    """A coded condition, by CID-10 or CIAP-2, opened or resolved."""

    encounter: int
    cid10_code: str | None
    ciap_code: str | None
    include_in_list: bool
    resolves: tuple[str, ...]
    rationale: str
    # A problem opened with both codes can only be found with both codes.
    resolves_ciap: str | None = None


@dataclass(frozen=True, slots=True)
class ScenarioCase:
    """One extended-cohort scenario and everything it must demonstrate."""

    key: str
    group: str
    team: int
    microarea: str
    sex: str
    age_years: int
    encounters: int
    recency: str
    complete: bool
    narrative: str
    age_days: int | None = None
    gestation_days: int | None = None
    puerperium_days: int | None = None
    problems: tuple[PlannedProblem, ...] = ()
    exams: tuple[PlannedExam, ...] = ()
    procedures: tuple[PlannedProcedure, ...] = ()
    vaccinations: tuple[PlannedVaccination, ...] = ()
    screenings: tuple[PlannedScreening, ...] = ()
    prescriptions: tuple[tuple[str, int], ...] = ()
    gaps: tuple[str, ...] = ()
    components: tuple[str, ...] = ()
    tools: tuple[str, ...] = ()
    # Domains the scenario needs but the factory cannot yet author through an
    # official contract.  A non-empty value must fail coverage, never pass.
    pending_contracts: tuple[str, ...] = ()


def _problem(
    encounter: int,
    *,
    cid: str | None = None,
    ciap: str | None = None,
    include: bool = True,
    resolves: tuple[str, ...] = (),
    resolves_ciap: str | None = None,
    rationale: str,
) -> PlannedProblem:
    return PlannedProblem(
        encounter, cid, ciap, include, resolves, rationale, resolves_ciap
    )


def _hba1c_series(count: int, *, controlled: bool) -> tuple[PlannedExam, ...]:
    """Return a descending or worsening HbA1c series across the history.

    The latest value is deliberately below 8% for the controlled trajectory and
    above 8% for the other, so both sides of the threshold exist in the cohort.
    """
    if controlled:
        values = (9.4, 8.6, 7.9, 7.4)
    else:
        values = (7.6, 8.2, 8.8, 9.1)
    stride = max(1, count // len(values))
    planned = []
    for index, value in enumerate(values):
        encounter = min(count, 1 + index * stride)
        planned.append(
            PlannedExam(
                HBA1C_CODES,
                "Hemoglobina glicada",
                f"{value:.1f} %",
                encounter,
                days_before_encounter=4,
                specific_procedure="HEMOGLOBINA_GLICADA",
                numeric_value=value,
            )
        )
    # Keep one result per encounter so a single visit never carries the series.
    unique: dict[int, PlannedExam] = {}
    for item in planned:
        unique.setdefault(item.encounter, item)
    return tuple(unique[key] for key in sorted(unique))


def _child_case(
    *, key: str, team: int, microarea: str, sex: str, encounters: int, complete: bool
) -> ScenarioCase:
    age_days = 610 if encounters >= 10 else 430
    vaccinations: tuple[PlannedVaccination, ...] = ()
    if complete:
        vaccinations = (
            PlannedVaccination(*PENTAVALENT, "D", 2),
            PlannedVaccination(*MMR, "D3", max(1, encounters - 3)),
            PlannedVaccination(*INFLUENZA, "D", encounters),
        )
    return ScenarioCase(
        key=key,
        group="infantil",
        team=team,
        microarea=microarea,
        sex=sex,
        age_years=1,
        age_days=age_days,
        encounters=encounters,
        recency=RECENCY_RECENT,
        complete=complete,
        narrative="puericultura e acompanhamento do crescimento",
        problems=(
            _problem(
                2,
                ciap="A97",
                include=False,
                rationale="puericultura de rotina sem intercorrencia",
            ),
            _problem(
                max(2, encounters - 2),
                cid="J06.9",
                rationale="intercorrencia respiratoria aguda autolimitada",
            ),
        ),
        vaccinations=vaccinations,
        gaps=()
        if complete
        else ("antropometria ausente em parte das consultas", "sem influenza"),
        components=("C1", "C2", "C6"),
        tools=("listar_criancas", "resumo_longitudinal", "medicoes_paciente"),
        pending_contracts=("visita_domiciliar",),
    )


def _diabetes_case(
    *, key: str, team: int, microarea: str, sex: str, age: int, encounters: int,
    complete: bool, hypertensive: bool,
) -> ScenarioCase:
    problems = [
        _problem(1, cid="E11.9", rationale="diabetes tipo 2 em seguimento"),
    ]
    if hypertensive:
        problems.append(
            _problem(2, cid="I10", rationale="hipertensao arterial coexistente")
        )
    exams = _hba1c_series(encounters, controlled=complete)
    screenings: tuple[PlannedScreening, ...] = ()
    foot: tuple[PlannedProcedure, ...] = ()
    if complete:
        foot = (
            PlannedProcedure(
                FOOT_EXAM_CODES,
                "Avaliacao dos pes",
                "Sem lesoes; sensibilidade preservada.",
                max(1, encounters - 1),
            ),
        )
    prescriptions = ((("METFORMIN", 1),)
                     + ((("LOSARTAN", 2),) if hypertensive else ()))
    return ScenarioCase(
        key=key,
        group="diabetes",
        team=team,
        microarea=microarea,
        sex=sex,
        age_years=age,
        encounters=encounters,
        recency=RECENCY_RECENT,
        complete=complete,
        narrative="diabetes tipo 2 em acompanhamento na APS",
        problems=tuple(problems),
        exams=exams,
        procedures=foot,
        prescriptions=prescriptions,
        screenings=screenings,
        gaps=() if complete else ("sem avaliacao dos pes", "HbA1c acima de 8%"),
        components=("C1", "C4"),
        tools=("listar_diabeticos", "exames_paciente", "medicoes_paciente"),
        pending_contracts=("visita_domiciliar",),
    )


def _hypertension_case(
    *, key: str, team: int, microarea: str, sex: str, age: int, encounters: int,
    complete: bool,
) -> ScenarioCase:
    return ScenarioCase(
        key=key,
        group="hipertensao",
        team=team,
        microarea=microarea,
        sex=sex,
        age_years=age,
        encounters=encounters,
        recency=RECENCY_RECENT,
        complete=complete,
        narrative="hipertensao arterial em acompanhamento na APS",
        problems=(
            _problem(1, cid="I10", rationale="hipertensao arterial em seguimento"),
            _problem(
                max(2, encounters - 2),
                cid="E78.5",
                rationale="dislipidemia associada ao risco cardiovascular",
            ),
        ),
        prescriptions=(("LOSARTAN", 1), ("AMOXICILLIN", 3))
        if encounters >= 5
        else (("LOSARTAN", 1),),
        gaps=() if complete else ("pressao arterial ausente em parte das consultas",),
        components=("C1", "C4"),
        tools=("listar_hipertensos", "medicoes_paciente"),
        pending_contracts=("visita_domiciliar",),
    )


def _elderly_case(
    *, key: str, team: int, microarea: str, sex: str, age: int, encounters: int,
    complete: bool,
) -> ScenarioCase:
    vaccinations: tuple[PlannedVaccination, ...] = ()
    if complete:
        vaccinations = (PlannedVaccination(*INFLUENZA, "D", encounters),)
    return ScenarioCase(
        key=key,
        group="idoso",
        team=team,
        microarea=microarea,
        sex=sex,
        age_years=age,
        encounters=encounters,
        recency=RECENCY_RECENT,
        complete=complete,
        narrative="pessoa idosa em cuidado longitudinal",
        problems=(
            _problem(1, cid="I10", rationale="hipertensao arterial em seguimento"),
            _problem(
                max(2, encounters - 1),
                cid="M81.0",
                include=False,
                resolves=(),
                rationale="risco de fratura avaliado sem abertura de problema",
            ),
        ),
        vaccinations=vaccinations,
        prescriptions=(("LOSARTAN", 1),),
        gaps=() if complete else ("sem influenza", "antropometria incompleta"),
        components=("C1", "C6"),
        tools=("listar_idosos", "resumo_longitudinal"),
        pending_contracts=("visita_domiciliar",),
    )


def _screening_case(
    *, key: str, team: int, microarea: str, age: int, encounters: int, complete: bool
) -> ScenarioCase:
    screenings: list[PlannedScreening] = []
    if complete:
        screenings.append(
            PlannedScreening("citopatologico", CYTOLOGY_CODES, max(1, encounters - 1))
        )
        if age >= 50:
            screenings.append(PlannedScreening("mamografia", MAMMOGRAPHY_CODES, encounters))
    else:
        # Out-of-window control: the request exists but predates the window.
        screenings.append(
            PlannedScreening(
                "citopatologico", CYTOLOGY_CODES, 1, days_before_encounter=0
            )
        )
    return ScenarioCase(
        key=key,
        group="rastreamento",
        team=team,
        microarea=microarea,
        sex="F",
        age_years=age,
        encounters=encounters,
        recency=RECENCY_RECENT,
        complete=complete,
        narrative="rastreamento de cancer do colo do utero e de mama",
        problems=(
            _problem(
                1,
                ciap="A98",
                include=False,
                rationale="acao preventiva sem diagnostico estruturado",
            ),
        ),
        screenings=tuple(screenings),
        gaps=()
        if complete
        else ("rastreamento fora da janela", "sem mamografia"),
        components=("C1", "C7"),
        tools=("listar_rastreamento", "exames_paciente"),
    )


def _hpv_case(
    *, key: str, team: int, microarea: str, sex: str, age: int, encounters: int,
    complete: bool,
) -> ScenarioCase:
    vaccinations: tuple[PlannedVaccination, ...] = ()
    if complete:
        vaccinations = (
            PlannedVaccination(*HPV, "D1", 1),
            PlannedVaccination(*HPV, "D2", encounters),
        )
    return ScenarioCase(
        key=key,
        group="hpv",
        team=team,
        microarea=microarea,
        sex=sex,
        age_years=age,
        encounters=encounters,
        recency=RECENCY_RECENT,
        complete=complete,
        narrative="saude do adolescente e vacinacao contra HPV",
        problems=(
            _problem(
                1,
                ciap="A98",
                include=False,
                rationale="consulta preventiva do adolescente",
            ),
        ),
        vaccinations=vaccinations,
        gaps=() if complete else ("esquema de HPV incompleto",),
        components=("C1", "C7"),
        tools=("listar_adolescentes", "vacinas_paciente"),
    )


def _pregnancy_case(
    *, key: str, team: int, microarea: str, age: int, encounters: int,
    gestation_days: int,
) -> ScenarioCase:
    weeks = gestation_days // 7
    vaccinations: tuple[PlannedVaccination, ...] = ()
    if weeks >= 20:
        # dTpa is only due from 20 weeks; earlier gestations must stay negative.
        vaccinations = (PlannedVaccination(*DTPA_ADULT, "DU", encounters),)
    return ScenarioCase(
        key=key,
        group="gestante",
        team=team,
        microarea=microarea,
        sex="F",
        age_years=age,
        encounters=encounters,
        recency=RECENCY_RECENT,
        complete=weeks >= 20,
        narrative=f"gestacao em andamento, aproximadamente {weeks} semanas",
        gestation_days=gestation_days,
        problems=(
            _problem(1, cid="Z34.0", rationale="supervisao de gravidez normal"),
        ),
        exams=(
            PlannedExam(
                OBSTETRIC_ULTRASOUND_CODES,
                "Ultrassonografia obstetrica",
                "Gestacao unica, topica, com feto vivo",
                min(2, encounters),
                days_before_encounter=5,
                specific_procedure="PRENATAL",
                gestational_weeks=max(6, (gestation_days - 30) // 7),
                gestational_days=(gestation_days - 30) % 7,
            ),
        ),
        vaccinations=vaccinations,
        components=("C1", "C3"),
        tools=("listar_gestantes", "resumo_longitudinal"),
        gaps=() if weeks >= 20 else ("gestacao inicial: componentes ainda nao devidos",),
        pending_contracts=("visita_domiciliar",),
    )


def _puerperium_case(
    *, key: str, team: int, microarea: str, age: int, encounters: int
) -> ScenarioCase:
    return ScenarioCase(
        key=key,
        group="puerpera",
        team=team,
        microarea=microarea,
        sex="F",
        age_years=age,
        encounters=encounters,
        recency=RECENCY_RECENT,
        complete=True,
        narrative="puerperio apos gestacao encerrada",
        gestation_days=300,
        puerperium_days=20,
        problems=(
            _problem(1, cid="Z34.0", rationale="supervisao de gravidez normal"),
            _problem(
                encounters,
                cid="Z39.2",
                include=False,
                resolves=(PREGNANCY_CID,),
                resolves_ciap=PREGNANCY_CIAP,
                rationale="acompanhamento puerperal de rotina",
            ),
        ),
        vaccinations=(PlannedVaccination(*DTPA_ADULT, "DU", encounters - 3),),
        components=("C1", "C3"),
        tools=("listar_gestantes", "resumo_longitudinal"),
        pending_contracts=("visita_domiciliar",),
    )


def _never_seen_case(*, key: str, team: int, microarea: str, age: int) -> ScenarioCase:
    return ScenarioCase(
        key=key,
        group="sem_consulta",
        team=team,
        microarea=microarea,
        sex="M",
        age_years=age,
        encounters=0,
        recency=RECENCY_NEVER,
        complete=False,
        narrative="cadastro territorial ativo e nenhuma consulta registrada",
        gaps=("nunca consultou",),
        components=("C1",),
        tools=("busca_ativa", "listar_microareas"),
    )


def _overdue_case(
    *, key: str, team: int, microarea: str, sex: str, age: int
) -> ScenarioCase:
    return ScenarioCase(
        key=key,
        group="atrasado",
        team=team,
        microarea=microarea,
        sex=sex,
        age_years=age,
        encounters=4,
        recency=RECENCY_OVERDUE,
        complete=False,
        narrative="acompanhamento interrompido ha mais de seis meses",
        problems=(
            _problem(1, cid="I10", rationale="hipertensao arterial em seguimento"),
        ),
        prescriptions=(("LOSARTAN", 1),),
        gaps=("ultima consulta entre 210 e 240 dias",),
        components=("C1", "C4"),
        tools=("busca_ativa", "listar_hipertensos"),
    )


def _assign_microareas(cases: list[ScenarioCase]) -> tuple[ScenarioCase, ...]:
    """Distribute microareas by an explicit per-team round robin.

    Balancing must not depend on the order in which scenarios happen to be
    generated, so the rule is stated here and asserted by the tests.
    """
    counters = [0] * TEAM_COUNT
    assigned = []
    for case in cases:
        microarea = MICROAREAS[counters[case.team] % len(MICROAREAS)]
        counters[case.team] += 1
        assigned.append(replace(case, microarea=microarea))
    return tuple(assigned)


def coverage_cases() -> tuple[ScenarioCase, ...]:
    """Return the 32 extended scenarios in a stable, versioned order."""
    cases: list[ScenarioCase] = []
    placeholder = "00"

    for index, (encounters, complete) in enumerate(
        ((10, True), (10, True), (7, False), (7, False))
    ):
        cases.append(
            _child_case(
                key=f"v5_infantil_{index + 1}",
                team=index % 2,
                microarea=placeholder,
                sex="F" if index % 2 == 0 else "M",
                encounters=encounters,
                complete=complete,
            )
        )

    for index, (age, encounters, complete, hypertensive) in enumerate(
        ((54, 8, True, True), (61, 8, True, False), (49, 5, False, True), (66, 5, False, False))
    ):
        cases.append(
            _diabetes_case(
                key=f"v5_diabetes_{index + 1}",
                team=index % 2,
                microarea=placeholder,
                sex="F" if index % 2 == 0 else "M",
                age=age,
                encounters=encounters,
                complete=complete,
                hypertensive=hypertensive,
            )
        )

    for index, (age, encounters, complete) in enumerate(
        ((47, 8, True), (58, 8, True), (52, 5, False), (44, 5, False))
    ):
        cases.append(
            _hypertension_case(
                key=f"v5_hipertensao_{index + 1}",
                team=index % 2,
                microarea=placeholder,
                sex="M" if index % 2 == 0 else "F",
                age=age,
                encounters=encounters,
                complete=complete,
            )
        )

    for index, (age, encounters, complete) in enumerate(
        ((68, 6, True), (74, 6, True), (79, 3, False), (83, 3, False))
    ):
        cases.append(
            _elderly_case(
                key=f"v5_idoso_{index + 1}",
                team=index % 2,
                microarea=placeholder,
                sex="M" if index % 2 == 0 else "F",
                age=age,
                encounters=encounters,
                complete=complete,
            )
        )

    for index, (age, encounters, complete) in enumerate(
        ((52, 4, True), (58, 4, True), (34, 2, False), (46, 2, False))
    ):
        cases.append(
            _screening_case(
                key=f"v5_rastreamento_{index + 1}",
                team=index % 2,
                microarea=placeholder,
                age=age,
                encounters=encounters,
                complete=complete,
            )
        )

    for index, (age, encounters, complete) in enumerate(
        ((11, 3, True), (12, 3, True), (13, 2, False), (14, 2, False))
    ):
        cases.append(
            _hpv_case(
                key=f"v5_hpv_{index + 1}",
                team=index % 2,
                microarea=placeholder,
                sex="F" if index % 2 == 0 else "M",
                age=age,
                encounters=encounters,
                complete=complete,
            )
        )

    for index, (age, encounters, gestation_days) in enumerate(
        ((24, 3, 70), (29, 5, 154), (34, 8, 224))
    ):
        cases.append(
            _pregnancy_case(
                key=f"v5_gestante_{index + 1}",
                team=index % 2,
                microarea=placeholder,
                age=age,
                encounters=encounters,
                gestation_days=gestation_days,
            )
        )

    cases.append(
        _puerperium_case(
            key="v5_puerpera_1", team=1, microarea=placeholder, age=27, encounters=10
        )
    )

    for index, age in enumerate((39, 45)):
        cases.append(
            _never_seen_case(
                key=f"v5_sem_consulta_{index + 1}",
                team=index % 2,
                microarea=placeholder,
                age=age,
            )
        )

    for index, (age, sex) in enumerate(((51, "M"), (63, "F"))):
        cases.append(
            _overdue_case(
                key=f"v5_atrasado_{index + 1}",
                team=index % 2,
                microarea=placeholder,
                sex=sex,
                age=age,
            )
        )

    return _assign_microareas(cases)


CASES = {case.key: case for case in coverage_cases()}


def birth_date(case: ScenarioCase, reference_date: date) -> date:
    """Return a deterministic birth date inside the scenario's age band.

    The policy is explicit: the age band is preserved relative to the clinical
    reference date, so moving the reference date keeps a child a child and an
    elderly patient elderly.  Birth dates of the protected cohort are never
    touched by this module.
    """
    if case.age_days is not None:
        return reference_date - timedelta(days=case.age_days)
    digest = hashlib.sha256(f"birth:{case.key}".encode()).digest()
    offset = int.from_bytes(digest[:2], "big") % 300
    return _subtract_years(reference_date, case.age_years) - timedelta(days=offset)


def build_coverage_cohort(
    *, seed: int, reference_date: date
) -> tuple[SyntheticPatient, ...]:
    """Build the 32 extended patients without disturbing the protected cohort."""
    patients = []
    for case in coverage_cases():
        digest = hashlib.sha256(f"{seed}:{case.key}".encode()).digest()
        case_seed = int.from_bytes(digest[:4], "big")
        template_index = 4 if case.sex == "F" else 5
        identity = build_patient_cohort(
            seed=case_seed, generated_on=IDENTITY_EPOCH
        )[template_index]
        birth = birth_date(case, reference_date)
        patients.append(
            replace(
                identity,
                key=case.key,
                sex=case.sex,
                birth_date=birth,
                scenario=(
                    f"{case.group}; {case.narrative}; "
                    f"equipe {case.team + 1}; microarea {case.microarea}"
                ),
                age_years=(reference_date - birth).days // 365,
            )
        )
    return tuple(patients)


def _latest_offset(case: ScenarioCase) -> int:
    """Days between the reference date and the most recent encounter."""
    if case.recency == RECENCY_NEVER:
        raise ValueError(f"{case.key} has no encounter")
    digest = hashlib.sha256(f"latest:{case.key}".encode()).digest()
    spread = int.from_bytes(digest[:2], "big")
    if case.recency == RECENCY_OVERDUE:
        return 210 + spread % 31
    return 2 + spread % 14


def _oldest_offset(case: ScenarioCase, reference_date: date) -> int:
    """Days between the reference date and the first encounter."""
    latest = _latest_offset(case)
    if case.recency == RECENCY_OVERDUE:
        return latest + 200
    if case.group == "infantil":
        # The first childcare visit happens within 30 days of life.
        return (case.age_days or 610) - 7
    if case.gestation_days:
        # The first prenatal visit happens before 12 weeks of gestational age.
        return case.gestation_days - min(case.gestation_days - 21, 77)
    return 300 if case.encounters >= 6 else 210


def encounter_dates(case: ScenarioCase, reference_date: date) -> tuple[date, ...]:
    """Return the chronological, never-future encounter dates of a scenario.

    At least three quarters of the encounters land inside the last 180 days:
    only the leading quarter is used as a historical anchor.
    """
    if case.encounters == 0:
        return ()
    latest = _latest_offset(case)
    oldest = max(_oldest_offset(case, reference_date), latest + case.encounters)
    if case.age_days is not None:
        # No event may predate birth, however young the patient is.
        oldest = min(oldest, case.age_days - 3)

    def _spread(count: int, first: int, last: int) -> list[int]:
        if count <= 0:
            return []
        if count == 1:
            return [last]
        return [
            round(first - (first - last) * index / (count - 1))
            for index in range(count)
        ]

    if case.recency == RECENCY_OVERDUE:
        offsets = _spread(case.encounters, oldest, latest)
    else:
        # Only the leading quarter may sit outside the 180-day recency window.
        anchors = case.encounters // 4 if oldest > 181 else 0
        recent_count = case.encounters - anchors
        offsets = _spread(anchors, oldest, 182) if anchors else []
        offsets += _spread(recent_count, min(175, oldest), latest)
    offsets = sorted(set(offsets), reverse=True)
    while len(offsets) < case.encounters:
        offsets = sorted(set(offsets + [max(1, offsets[-1] - 1)]), reverse=True)
    offsets = offsets[: case.encounters]
    dates = tuple(reference_date - timedelta(days=value) for value in offsets)
    birth = birth_date(case, reference_date)
    if dates[0] <= birth:
        raise ValueError(f"{case.key} plans an encounter before birth")
    if dates[-1] > reference_date:
        raise ValueError(f"{case.key} plans a future encounter")
    return dates


def protected_encounter_dates(
    *,
    patient_key: str,
    encounters: int,
    birth: date,
    reference_date: date,
) -> tuple[date, ...]:
    """Return renewed clinical dates for one protected bootstrap patient.

    The plan authorises renewing the chronology of the ten protected patients
    in the factory's copy, and nothing else about them.  Their birth dates stay
    fixed, so the spread is clamped to keep every encounter after birth.
    """
    if encounters <= 0:
        return ()
    age_days = (reference_date - birth).days
    if age_days <= encounters:
        raise ValueError(f"{patient_key} is too young for {encounters} encounters")
    case = ScenarioCase(
        key=f"protected:{patient_key}",
        group="protegido",
        team=0,
        microarea=MICROAREAS[0],
        sex="F",
        age_years=age_days // 365,
        age_days=age_days,
        encounters=encounters,
        recency=RECENCY_RECENT,
        complete=True,
        narrative="coorte protegida do bootstrap",
    )
    return encounter_dates(case, reference_date)


def coverage_contract(reference_date: date) -> dict:
    """Return the publishable manifest of scenarios, dates and expectations."""
    scenarios = []
    for case in coverage_cases():
        dates = encounter_dates(case, reference_date)
        scenarios.append(
            {
                "key": case.key,
                "group": case.group,
                "team": case.team + 1,
                "microarea": case.microarea,
                "sex": case.sex,
                "birth_date": birth_date(case, reference_date).isoformat(),
                "age_years": case.age_years,
                "recency": case.recency,
                "complete": case.complete,
                "narrative": case.narrative,
                "encounters": [item.isoformat() for item in dates],
                "problems": [
                    {
                        "encounter": item.encounter,
                        "cid10": item.cid10_code,
                        "ciap": item.ciap_code,
                        "include_in_list": item.include_in_list,
                        "resolves": list(item.resolves),
                        "rationale": item.rationale,
                    }
                    for item in case.problems
                ],
                "exams": [
                    {
                        "codes": list(item.codes),
                        "label": item.label,
                        "value": item.value,
                        "encounter": item.encounter,
                    }
                    for item in case.exams
                ],
                "procedures": [
                    {
                        "codes": list(item.codes),
                        "label": item.label,
                        "encounter": item.encounter,
                    }
                    for item in case.procedures
                ],
                "vaccinations": [
                    {
                        "immunobiological": item.immunobiological,
                        "dose": item.dose,
                        "encounter": item.encounter,
                    }
                    for item in case.vaccinations
                ],
                "screenings": [
                    {"kind": item.kind, "codes": list(item.codes), "encounter": item.encounter}
                    for item in case.screenings
                ],
                "prescriptions": [
                    {"medication": name, "encounter": encounter}
                    for name, encounter in case.prescriptions
                ],
                "gaps": list(case.gaps),
                "components": list(case.components),
                "tools": list(case.tools),
                "pending_contracts": list(case.pending_contracts),
            }
        )
    return {
        "contract_version": CONTRACT_VERSION,
        "identity_epoch": IDENTITY_EPOCH.isoformat(),
        "reference_date": reference_date.isoformat(),
        "protected_patients": 10,
        "extended_patients": len(scenarios),
        "planned_encounters": sum(len(item["encounters"]) for item in scenarios),
        "scenarios": scenarios,
    }


def _child_anthropometry(age_days: int) -> dict[str, float]:
    """Derive growth from the age on the encounter date, not the visit number."""
    months = age_days / 30.44
    if months <= 12:
        height = 50.0 + 2.1 * months
        weight = 3.4 + 0.60 * months
        head = 34.5 + 0.9 * min(months, 12)
    else:
        height = 75.2 + 1.0 * (months - 12)
        weight = 10.6 + 0.22 * (months - 12)
        head = 45.3 + 0.15 * (months - 12)
    return {
        "peso": round(weight, 2),
        "altura": round(height, 1),
        "perimetroCefalico": round(head, 1),
    }


def _blood_pressure(case: ScenarioCase, index: int) -> dict[str, int]:
    """Return a trajectory that crosses the thresholds the tools rely on."""
    if case.complete:
        systolic = max(118, 152 - 4 * index)
        diastolic = max(74, 96 - 2 * index)
    else:
        systolic = 148 + (index % 3) * 6
        diastolic = 92 + (index % 3) * 3
    return {
        "pressaoArterialSistolica": systolic,
        "pressaoArterialDiastolica": diastolic,
    }


def _measurements(
    case: ScenarioCase,
    *,
    index: int,
    encounter_date: date,
    birth: date,
) -> dict[str, object]:
    """Build the structured measurements of one encounter.

    Deliberate absences are part of the contract: a scenario marked incomplete
    keeps whole visits without anthropometry so active search and the report
    denominators have real negatives to find.
    """
    visit = index + 1
    if case.group == "infantil":
        measurements: dict[str, object] = {}
        if case.complete or visit % 3 != 0:
            measurements.update(_child_anthropometry((encounter_date - birth).days))
        if case.complete:
            measurements["vacinacaoEmDia"] = True
        return measurements

    if not case.complete and visit % 3 == 0:
        # A whole visit without structured measurements.
        return {}

    measurements = {}
    if case.group in {"diabetes", "hipertensao", "idoso", "atrasado", "puerpera"}:
        base_weight = 62.0 + case.team * 9 + case.age_years * 0.15
        measurements["peso"] = round(base_weight + index * 0.4, 2)
        measurements["altura"] = round(158.0 + case.team * 7.0, 1)
        measurements.update(_blood_pressure(case, index))
    elif case.group == "gestante":
        measurements["peso"] = round(64.0 + index * 0.9, 2)
        measurements["altura"] = round(162.0 + case.team * 4.0, 1)
        measurements.update(
            pressaoArterialSistolica=112 + (index % 3) * 4,
            pressaoArterialDiastolica=70 + (index % 3) * 2,
        )
    else:
        measurements["peso"] = round(52.0 + case.age_years * 0.4 + index * 0.3, 2)
        measurements["altura"] = round(160.0 + case.team * 5.0, 1)

    if case.group == "diabetes":
        # Capillary glucose alternates fasting and post-prandial contexts.
        measurements["glicemia"] = 118 + (index % 4) * 17 + (0 if case.complete else 45)
        measurements["tipoGlicemia"] = "JEJUM" if index % 2 == 0 else "POSPRANDIAL"
    if case.group == "idoso":
        measurements["circunferenciaAbdominal"] = round(94.0 + index * 0.6, 1)
    return measurements


def _soap_text(case: ScenarioCase, visit: int, total: int, has_measurements: bool):
    marker = case.key.upper().replace("_", "-")
    subjective = (
        f"Relato sintetico de acompanhamento de {case.narrative}. "
        f"DEMO-SOAP-{marker}-{visit:02d}."
    )
    objective = (
        f"Avaliacao longitudinal {visit}/{total}; "
        + (
            "medidas registradas nesta consulta."
            if has_measurements
            else "sem medidas estruturadas nesta consulta."
        )
    )
    assessment = (
        f"Cenario sintetico {case.group}, "
        + ("acompanhamento completo." if case.complete else "com lacunas planejadas.")
    )
    plan = (
        "Orientacoes, revisao de resultados e pendencias, retorno programado na APS."
    )
    return subjective, objective, assessment, plan


def build_coverage_encounters(patient: SyntheticPatient, reference_date: date):
    """Turn one scenario into its planned, dated encounters."""
    from pec_demo.clinical import (
        PRESCRIPTION_CATALOG,
        PlannedEncounter,
        PlannedPrenatal,
    )

    case = CASES[patient.key]
    dates = encounter_dates(case, reference_date)
    total = len(dates)
    problems_by_visit = {item.encounter: item for item in case.problems}
    exams_by_visit: dict[int, list[PlannedExam]] = {}
    for exam in case.exams:
        exams_by_visit.setdefault(exam.encounter, []).append(exam)
    vaccines_by_visit: dict[int, list[PlannedVaccination]] = {}
    for vaccine in case.vaccinations:
        vaccines_by_visit.setdefault(vaccine.encounter, []).append(vaccine)
    procedures_by_visit: dict[int, list[PlannedProcedure]] = {}
    for procedure in case.procedures:
        procedures_by_visit.setdefault(procedure.encounter, []).append(procedure)
    screenings_by_visit: dict[int, list[PlannedScreening]] = {}
    for screening in case.screenings:
        screenings_by_visit.setdefault(screening.encounter, []).append(screening)
    prescriptions_by_visit: dict[int, list[str]] = {}
    for name, visit in case.prescriptions:
        prescriptions_by_visit.setdefault(min(visit, total), []).append(name)

    conception = (
        reference_date - timedelta(days=case.gestation_days)
        if case.gestation_days
        else None
    )
    planned = []
    pregnancy_opened = False
    for index, encounter_date in enumerate(dates):
        visit = index + 1
        # Nursing leads the alternate visits; the first visit is always medical
        # so that CID-10 coding is available for the opening problem.
        role = "medico" if index % 2 == 0 else "enfermagem"
        problem = problems_by_visit.get(visit)
        if problem and role == "enfermagem" and problem.cid10_code:
            role = "medico"
        measurements = _measurements(
            case,
            index=index,
            encounter_date=encounter_date,
            birth=patient.birth_date,
        )
        prenatal = None
        gestational = conception is not None and encounter_date > conception
        if gestational:
            ended = (
                case.puerperium_days is not None
                and (reference_date - encounter_date).days < case.puerperium_days
            )
            if ended or role != "medico":
                # Prenatal care needs a CIAP-2 related to a CID-10, and the
                # standard nursing access cannot code CID-10. Nursing visits of
                # a pregnant citizen are therefore recorded as follow-up, with
                # no last-menstrual-period and no prenatal block; the medical
                # visits carry the pregnancy itself.
                gestational = False
            else:
                gestational_days = (encounter_date - conception).days
                measurements = dict(measurements)
                measurements["dum"] = conception.isoformat()
                prenatal = PlannedPrenatal(
                    gestational_days=gestational_days,
                    uterine_height=max(8, min(36, gestational_days // 7)),
                    fetal_heart_rate=142 + (index % 3) * 3,
                    fetal_movement=gestational_days >= 140,
                    planned_pregnancy=True,
                    pregnancy_type="UNICA",
                )
        subjective, objective, assessment, plan = _soap_text(
            case, visit, total, bool(measurements)
        )
        planned.append(
            PlannedEncounter(
                key=f"{case.key}:{visit:02d}:{role}",
                patient_key=case.key,
                role=role,
                subjective=subjective,
                objective=objective,
                assessment=assessment,
                plan=plan,
                encounter_number=visit,
                cid10_code=(
                    PREGNANCY_CID
                    if prenatal
                    else (problem.cid10_code if problem and role == "medico" else None)
                ),
                # A medical record holds at most one pregnancy condition: the
                # first gestational encounter opens it, the following ones
                # evolve it without adding it to the list again.
                include_problem=(gestational and not pregnancy_opened)
                or bool(problem and problem.include_in_list),
                resolve_cid10_codes=problem.resolves if problem else (),
                resolve_ciap_code=problem.resolves_ciap if problem else None,
                health_rationale=problem.rationale if problem else case.narrative,
                measurements=measurements,
                prescriptions=tuple(
                    PRESCRIPTION_CATALOG[name]
                    for name in prescriptions_by_visit.get(visit, ())
                ),
                ciap_code=(
                    PREGNANCY_CIAP
                    if gestational
                    else (problem.ciap_code if problem else None)
                ),
                encounter_date=encounter_date,
                exam_results=tuple(exams_by_visit.get(visit, ())),
                procedures=tuple(procedures_by_visit.get(visit, ())),
                vaccinations=tuple(vaccines_by_visit.get(visit, ())),
                screenings=tuple(screenings_by_visit.get(visit, ())),
                prenatal=prenatal,
            )
        )
        pregnancy_opened = pregnancy_opened or gestational
    return tuple(planned)
