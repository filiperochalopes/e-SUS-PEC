"""Apply the planned clinical chronology to the operational records.

PEC creates every attendance at the current instant.  ``salvarRegistroTardio``
accepts a retroactive date but only inside a seven-day window
(``DEFAULT_DATE_DIFF = 7`` in ``RegistroTardioInputValidatorKt``), so a
longitudinal history of months cannot be authored through the API alone.

This module closes that gap the way the plan requires: it derives one clinical
date per encounter from the coverage contract, then rewrites **only** the
operational timestamps that PEC itself derived from the creation instant.  It
never writes to FAT/DIM tables, never touches audit columns, and never touches
facts the API already dated by contract (exam results, vaccine applications,
last menstrual period).

The output is a list of parameterised statements plus a verification query, so
the caller can apply them inside a single transaction and prove the result.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
import json
from pathlib import Path
from typing import Any

from pec_demo.coverage import (
    CASES,
    encounter_dates,
    protected_encounter_dates,
)
from pec_demo.patients import SyntheticPatient


# Columns PEC derives from the creation instant, and which the adapter owns.
OWNED_COLUMNS = (
    "tb_atend.dt_inicio",
    "tb_atend.dt_fim",
    "tb_atend_prof.dt_inicio",
    "tb_atend_prof.dt_fim",
    "tb_medicao.dt_medicao",
    "tb_problema_evolucao.dt_inicio_problema",
    "tb_problema_evolucao.dt_fim_problema",
    "tb_receita_medicamento.dt_inicio_tratamento",
    "tb_receita_medicamento.dt_fim_tratamento",
)

# Columns the adapter must never rewrite: audit trails, and clinical facts the
# official contract already dated.
PROTECTED_COLUMNS = (
    "tb_atend.dt_criacao_registro",
    "tb_exame_requisitado.dt_realizacao",
    "tb_exame_requisitado.dt_resultado",
    "tb_registro_vacinacao.dt_aplicacao",
    "tb_pre_natal.dt_ultima_menstruacao",
    "tb_pre_natal.dt_desfecho",
)

# Encounters are placed inside working hours so a same-day pair stays ordered.
FIRST_SLOT = time(8, 30)
SLOT_STEP = timedelta(minutes=40)
VISIT_DURATION = timedelta(minutes=25)


@dataclass(frozen=True, slots=True)
class EncounterSchedule:
    """The clinical instant one provisioned encounter must end up carrying."""

    key: str
    patient_key: str
    attendance_id: str
    attendance_professional_id: str
    starts_at: datetime
    ends_at: datetime

    @property
    def clinical_date(self) -> date:
        return self.starts_at.date()


def _slot(day: date, index: int) -> tuple[datetime, datetime]:
    start = datetime.combine(day, FIRST_SLOT) + SLOT_STEP * index
    return start, start + VISIT_DURATION


def load_manifest(path: Path) -> dict[str, Any]:
    """Read the clinical manifest written by the provisioning steps."""
    content = json.loads(path.read_text(encoding="utf-8"))
    if content.get("version") != 4 or not isinstance(content.get("encounters"), dict):
        raise ValueError(f"unsupported clinical manifest {path}")
    return content


def plan_chronology(
    *,
    manifest: dict[str, Any],
    patients: tuple[SyntheticPatient, ...],
    reference_date: date,
) -> tuple[EncounterSchedule, ...]:
    """Derive one clinical instant per provisioned encounter.

    Extended scenarios take their dates from the coverage contract.  Protected
    bootstrap patients get a renewed chronology under the same recency rules,
    which is the only change the plan authorises for them.
    """
    encounters = manifest["encounters"]
    by_patient: dict[str, list[str]] = {}
    for key, record in encounters.items():
        by_patient.setdefault(record["patient_key"], []).append(key)

    known = {patient.key for patient in patients}
    unknown = set(by_patient) - known
    if unknown:
        raise ValueError(
            "manifest carries encounters for patients outside the cohort: "
            + ", ".join(sorted(unknown))
        )

    schedules: list[EncounterSchedule] = []
    for patient in patients:
        keys = sorted(by_patient.get(patient.key, ()))
        if not keys:
            continue
        case = CASES.get(patient.key)
        if case is not None:
            if len(keys) != case.encounters:
                raise ValueError(
                    f"{patient.key} has {len(keys)} encounters, "
                    f"the contract plans {case.encounters}"
                )
            days = encounter_dates(case, reference_date)
        else:
            days = protected_encounter_dates(
                patient_key=patient.key,
                encounters=len(keys),
                birth=patient.birth_date,
                reference_date=reference_date,
            )
        same_day: dict[date, int] = {}
        for key, day in zip(keys, days):
            index = same_day.get(day, 0)
            same_day[day] = index + 1
            starts_at, ends_at = _slot(day, index)
            record = encounters[key]
            schedules.append(
                EncounterSchedule(
                    key=key,
                    patient_key=patient.key,
                    attendance_id=str(record["attendance_id"]),
                    attendance_professional_id=str(
                        record["attendance_professional_id"]
                    ),
                    starts_at=starts_at,
                    ends_at=ends_at,
                )
            )
    return tuple(schedules)


def _values_clause(schedules: tuple[EncounterSchedule, ...]) -> str:
    rows = ",\n        ".join(
        "(%s::bigint, %s::bigint, %s::timestamp, %s::timestamp)"
        for _ in schedules
    )
    return rows


def render_statements(
    schedules: tuple[EncounterSchedule, ...],
) -> tuple[str, list[Any]]:
    """Return one parameterised SQL script and its ordered parameters.

    The script is a single transaction.  It materialises the plan in a
    temporary table and then updates only the owned columns, so a row that
    already carries the intended instant is left untouched and re-running the
    adapter is a no-op.
    """
    if not schedules:
        raise ValueError("no encounter to reschedule")
    parameters: list[Any] = []
    for item in schedules:
        parameters.extend(
            (
                int(item.attendance_id),
                int(item.attendance_professional_id),
                item.starts_at,
                item.ends_at,
            )
        )
    script = f"""
BEGIN;

DROP TABLE IF EXISTS demo_chronology, demo_chronology_shift;

CREATE TEMPORARY TABLE demo_chronology (
    co_atend bigint PRIMARY KEY,
    co_atend_prof bigint NOT NULL,
    dt_inicio timestamp NOT NULL,
    dt_fim timestamp NOT NULL
) ON COMMIT DROP;

INSERT INTO demo_chronology (co_atend, co_atend_prof, dt_inicio, dt_fim)
VALUES
        {_values_clause(schedules)};

-- Every planned encounter must exist and belong to the planned attendance.
DO $$
DECLARE
    missing bigint;
BEGIN
    SELECT count(*) INTO missing
    FROM demo_chronology plan
    LEFT JOIN tb_atend_prof prof
        ON prof.co_seq_atend_prof = plan.co_atend_prof
       AND prof.co_atend = plan.co_atend
    WHERE prof.co_seq_atend_prof IS NULL;
    IF missing > 0 THEN
        RAISE EXCEPTION
            'chronology plan references % unknown professional attendances',
            missing;
    END IF;
END $$;

-- The shift each encounter needs, used to move dependent clinical dates by
-- the same amount instead of overwriting them with an unrelated value.
CREATE TEMPORARY TABLE demo_chronology_shift AS
SELECT plan.co_atend,
       plan.co_atend_prof,
       plan.dt_inicio,
       plan.dt_fim,
       (plan.dt_inicio::date - prof.dt_inicio::date) AS day_shift
FROM demo_chronology plan
JOIN tb_atend_prof prof ON prof.co_seq_atend_prof = plan.co_atend_prof;

-- A null dt_fim means the attendance was never closed on the list. Filling it
-- would change state, not date, so nulls are preserved on both tables.
UPDATE tb_atend_prof prof
SET dt_inicio = shift.dt_inicio,
    dt_fim = CASE WHEN prof.dt_fim IS NULL THEN NULL ELSE shift.dt_fim END
FROM demo_chronology_shift shift
WHERE prof.co_seq_atend_prof = shift.co_atend_prof
  AND (prof.dt_inicio, prof.dt_fim) IS DISTINCT FROM
      (shift.dt_inicio,
       CASE WHEN prof.dt_fim IS NULL THEN NULL ELSE shift.dt_fim END);

UPDATE tb_atend atend
SET dt_inicio = shift.dt_inicio,
    dt_fim = CASE WHEN atend.dt_fim IS NULL THEN NULL ELSE shift.dt_fim END
FROM demo_chronology_shift shift
WHERE atend.co_seq_atend = shift.co_atend
  AND (atend.dt_inicio, atend.dt_fim) IS DISTINCT FROM
      (shift.dt_inicio,
       CASE WHEN atend.dt_fim IS NULL THEN NULL ELSE shift.dt_fim END);

-- Measurements authored with their own dataMedicao already carry a clinical
-- date; only the ones PEC stamped with the creation instant are moved.
UPDATE tb_medicao medicao
SET dt_medicao = shift.dt_inicio
FROM demo_chronology_shift shift
WHERE medicao.co_atend_prof = shift.co_atend_prof
  AND medicao.dt_medicao::date <> shift.dt_inicio::date
  AND medicao.dt_medicao::date > shift.dt_inicio::date;

UPDATE tb_problema_evolucao evolucao
SET dt_inicio_problema = evolucao.dt_inicio_problema + shift.day_shift,
    dt_fim_problema = evolucao.dt_fim_problema + shift.day_shift
FROM demo_chronology_shift shift
WHERE evolucao.co_atend_prof = shift.co_atend_prof
  AND shift.day_shift <> 0;

UPDATE tb_receita_medicamento receita
SET dt_inicio_tratamento = receita.dt_inicio_tratamento + shift.day_shift,
    dt_fim_tratamento = receita.dt_fim_tratamento + shift.day_shift
FROM demo_chronology_shift shift
WHERE receita.co_atend_prof = shift.co_atend_prof
  AND shift.day_shift <> 0;

DROP TABLE IF EXISTS demo_chronology_shift;

COMMIT;
""".strip()
    return script, parameters


def render_sql_script(schedules: tuple[EncounterSchedule, ...]) -> str:
    """Return the chronology transaction as a standalone SQL script.

    Every value is produced by this module: attendance identifiers are integers
    read from the manifest and instants are datetimes derived from the coverage
    contract.  Both are asserted here before being rendered as literals, so no
    free text ever reaches the script.
    """
    script, parameters = render_statements(schedules)
    parts = script.split("%s")
    if len(parts) != len(parameters) + 1:
        raise ValueError("placeholder count does not match the parameters")
    rendered = [parts[0]]
    for value, tail in zip(parameters, parts[1:]):
        if isinstance(value, bool) or not isinstance(value, (int, datetime)):
            raise TypeError(f"refusing to render {type(value).__name__} as SQL literal")
        literal = (
            str(value)
            if isinstance(value, int)
            else "'" + value.isoformat(sep=" ", timespec="seconds") + "'"
        )
        rendered.append(literal)
        rendered.append(tail)
    return "".join(rendered) + "\n"


VERIFICATION_QUERY = """
SELECT prof.co_seq_atend_prof AS attendance_professional_id,
       prof.co_atend AS attendance_id,
       prof.dt_inicio AS starts_at,
       prof.dt_fim AS ends_at
FROM tb_atend_prof prof
WHERE prof.co_seq_atend_prof = ANY(%s::bigint[])
ORDER BY prof.co_seq_atend_prof
""".strip()


def verify(
    schedules: tuple[EncounterSchedule, ...],
    rows: list[dict[str, Any]],
) -> None:
    """Fail unless every encounter carries exactly its planned instant."""
    expected = {
        int(item.attendance_professional_id): (item.starts_at, item.ends_at)
        for item in schedules
    }
    seen = set()
    for row in rows:
        identifier = int(row["attendance_professional_id"])
        seen.add(identifier)
        if identifier not in expected:
            raise ValueError(f"unexpected professional attendance {identifier}")
        starts_at, ends_at = expected[identifier]
        actual = (row["starts_at"], row["ends_at"])
        if actual != (starts_at, ends_at):
            raise ValueError(
                f"professional attendance {identifier} carries {actual}, "
                f"expected {(starts_at, ends_at)}"
            )
    missing = set(expected) - seen
    if missing:
        raise ValueError(
            "verification did not return "
            f"{len(missing)} planned professional attendances"
        )
