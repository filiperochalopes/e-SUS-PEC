"""Prove that the ten protected bootstrap patients survive the factory.

The plan authorises exactly one change to the protected cohort: renewing the
clinical dates of its encounters in the factory's copy.  Everything else must
come out byte-identical — identities, medical records, authorship, SOAP text,
coded problems, prescriptions and exams.

This module renders a read-only signature query and compares two runs of it.
Temporal columns the chronology adapter owns are reported separately, so a
renewed date is never mistaken for a preserved value and never hides a real
loss either.
"""

from __future__ import annotations

from dataclasses import dataclass
import json
from typing import Any


# Fields the chronology adapter is allowed to change on the protected cohort.
RENEWABLE_FIELDS = ("oldest_encounter", "latest_encounter")

# Fields that must be identical before and after the factory runs.
INVARIANT_FIELDS = (
    "name",
    "mother_name",
    "birth_date",
    "sex",
    "cns",
    "medical_records",
    "encounters",
    "professional_encounters",
    "authors",
    "soap_digest",
    "problem_digest",
    "prescription_digest",
    "exam_digest",
)


@dataclass(frozen=True, slots=True)
class PreservationReport:
    """The outcome of comparing two signatures of the protected cohort."""

    patients: int
    invariant_fields: tuple[str, ...]
    renewed: dict[str, dict[str, tuple[str, str]]]

    def as_dict(self) -> dict[str, Any]:
        return {
            "schema_version": 1,
            "patients": self.patients,
            "invariant_fields": list(self.invariant_fields),
            "renewed": {
                cpf: {field: list(values) for field, values in changes.items()}
                for cpf, changes in self.renewed.items()
            },
        }


def signature_query(cpfs: tuple[str, ...]) -> str:
    """Return a read-only query producing one signature row per patient.

    Digests are built from ordered, concatenated clinical content so that a
    changed text, a re-coded problem, a lost prescription or an encounter
    moved to another citizen all change the signature.  Creation timestamps
    and surrogate keys are deliberately excluded: they are allowed to differ
    between two builds of the same pack.
    """
    if not cpfs:
        raise ValueError("at least one protected CPF is required")
    if not all(item.isdigit() and len(item) == 11 for item in cpfs):
        raise ValueError("protected CPFs must be eleven digits")
    values = ", ".join(f"('{item}')" for item in cpfs)
    return f"""
WITH protegidos(nu_cpf) AS (VALUES {values}),
cidadao AS (
    SELECT c.co_seq_cidadao, c.nu_cpf, c.no_cidadao, c.no_mae,
           c.dt_nascimento, c.no_sexo, c.nu_cns
    FROM tb_cidadao c
    JOIN protegidos p ON p.nu_cpf = c.nu_cpf
),
prontuario AS (
    SELECT ci.nu_cpf, count(pr.co_seq_prontuario) AS medical_records
    FROM cidadao ci
    LEFT JOIN tb_prontuario pr ON pr.co_cidadao = ci.co_seq_cidadao
    GROUP BY ci.nu_cpf
),
atendimento AS (
    -- An attendance points at the medical record, never at the citizen, so an
    -- encounter moved to another citizen changes this join and the digests.
    SELECT ci.nu_cpf,
           prof.co_seq_atend_prof,
           prof.co_atend,
           prof.dt_inicio,
           prof.co_lotacao
    FROM cidadao ci
    JOIN tb_prontuario pron ON pron.co_cidadao = ci.co_seq_cidadao
    JOIN tb_atend atend ON atend.co_prontuario = pron.co_seq_prontuario
    JOIN tb_atend_prof prof ON prof.co_atend = atend.co_seq_atend
),
soap AS (
    SELECT a.nu_cpf,
           md5(string_agg(
               coalesce(s.ds_subjetivo, '') || '|' ||
               coalesce(o.ds_objetivo, '') || '|' ||
               coalesce(av.ds_avaliacao, '') || '|' ||
               coalesce(pl.ds_plano, ''),
               E'\\n' ORDER BY a.co_seq_atend_prof
           )) AS soap_digest
    FROM atendimento a
    LEFT JOIN tb_evolucao_subjetivo s ON s.co_atend_prof = a.co_seq_atend_prof
    LEFT JOIN tb_evolucao_objetivo o ON o.co_atend_prof = a.co_seq_atend_prof
    LEFT JOIN tb_evolucao_avaliacao av ON av.co_atend_prof = a.co_seq_atend_prof
    LEFT JOIN tb_evolucao_plano pl ON pl.co_atend_prof = a.co_seq_atend_prof
    GROUP BY a.nu_cpf
),
problema AS (
    SELECT a.nu_cpf,
           md5(coalesce(string_agg(
               coalesce(pe.co_unico_problema::text, '') || '|' ||
               coalesce(pe.co_situacao_problema::text, '') || '|' ||
               coalesce(pe.st_possui_cid::text, '') || '|' ||
               coalesce(pe.st_possui_ciap::text, '') || '|' ||
               coalesce(pe.ds_observacao, ''),
               E'\\n' ORDER BY pe.co_seq_problema_evolucao
           ), '')) AS problem_digest
    FROM atendimento a
    LEFT JOIN tb_problema_evolucao pe ON pe.co_atend_prof = a.co_seq_atend_prof
    GROUP BY a.nu_cpf
),
receita AS (
    SELECT a.nu_cpf,
           md5(coalesce(string_agg(
               coalesce(r.co_medicamento::text, '') || '|' ||
               coalesce(r.no_posologia, '') || '|' ||
               coalesce(r.st_uso_continuo::text, '') || '|' ||
               coalesce((r.dt_fim_tratamento - r.dt_inicio_tratamento)::text, ''),
               E'\\n' ORDER BY r.co_seq_receita_medicamento
           ), '')) AS prescription_digest
    FROM atendimento a
    LEFT JOIN tb_receita_medicamento r ON r.co_atend_prof = a.co_seq_atend_prof
    GROUP BY a.nu_cpf
),
exame AS (
    SELECT a.nu_cpf,
           md5(coalesce(string_agg(
               coalesce(e.co_proced::text, '')
               || '|' || coalesce(e.ds_resultado, ''),
               E'\\n' ORDER BY e.co_seq_exame_requisitado
           ), '')) AS exam_digest
    FROM atendimento a
    LEFT JOIN tb_exame_requisitado e
        ON e.co_atend_prof_solicitacao = a.co_seq_atend_prof
        OR e.co_atend_prof_resultado = a.co_seq_atend_prof
    GROUP BY a.nu_cpf
)
SELECT ci.nu_cpf AS cpf,
       ci.no_cidadao AS name,
       ci.no_mae AS mother_name,
       ci.dt_nascimento::text AS birth_date,
       ci.no_sexo AS sex,
       ci.nu_cns AS cns,
       pr.medical_records::text AS medical_records,
       count(DISTINCT a.co_atend)::text AS encounters,
       count(DISTINCT a.co_seq_atend_prof)::text AS professional_encounters,
       count(DISTINCT a.co_lotacao)::text AS authors,
       min(a.dt_inicio)::date::text AS oldest_encounter,
       max(a.dt_inicio)::date::text AS latest_encounter,
       so.soap_digest,
       prob.problem_digest,
       rec.prescription_digest,
       ex.exam_digest
FROM cidadao ci
JOIN prontuario pr ON pr.nu_cpf = ci.nu_cpf
LEFT JOIN atendimento a ON a.nu_cpf = ci.nu_cpf
LEFT JOIN soap so ON so.nu_cpf = ci.nu_cpf
LEFT JOIN problema prob ON prob.nu_cpf = ci.nu_cpf
LEFT JOIN receita rec ON rec.nu_cpf = ci.nu_cpf
LEFT JOIN exame ex ON ex.nu_cpf = ci.nu_cpf
GROUP BY ci.nu_cpf, ci.no_cidadao, ci.no_mae, ci.dt_nascimento, ci.no_sexo,
         ci.nu_cns, pr.medical_records, so.soap_digest, prob.problem_digest,
         rec.prescription_digest, ex.exam_digest
ORDER BY ci.nu_cpf
""".strip()


def signature_script(cpfs: tuple[str, ...]) -> str:
    """Wrap the signature query so ``psql -Atq -f`` emits a single JSON array."""
    return (
        "SELECT coalesce(json_agg(row_to_json(s)), '[]'::json) FROM (\n"
        + signature_query(cpfs)
        + "\n) s;\n"
    )


def parse_signature(payload: str) -> dict[str, dict[str, str]]:
    """Parse the JSON array psql produces for the signature query."""
    rows = json.loads(payload) if payload.strip() else []
    signature: dict[str, dict[str, str]] = {}
    for row in rows:
        record = {
            key: ("" if value is None else str(value)) for key, value in row.items()
        }
        signature[record["cpf"]] = record
    return signature


def compare(
    before: dict[str, dict[str, str]],
    after: dict[str, dict[str, str]],
    *,
    expected_patients: int,
) -> PreservationReport:
    """Fail unless the protected cohort changed only in its renewable fields."""
    if len(before) != expected_patients:
        raise ValueError(
            f"signature covers {len(before)} protected patients, "
            f"expected {expected_patients}"
        )
    lost = set(before) - set(after)
    if lost:
        raise ValueError(
            "protected patients disappeared: " + ", ".join(sorted(lost))
        )
    if len(after) != len(before):
        raise ValueError(
            f"signature grew from {len(before)} to {len(after)} protected patients"
        )
    renewed: dict[str, dict[str, tuple[str, str]]] = {}
    for cpf, original in before.items():
        current = after[cpf]
        for field in INVARIANT_FIELDS:
            if field not in original:
                raise ValueError(f"signature is missing the field {field}")
            if original[field] != current.get(field):
                raise ValueError(
                    f"protected patient {cpf[:3]}*** changed {field}: "
                    f"{original[field]!r} became {current.get(field)!r}"
                )
        changes = {
            field: (original[field], current.get(field, ""))
            for field in RENEWABLE_FIELDS
            if original[field] != current.get(field)
        }
        if changes:
            renewed[cpf] = changes
    return PreservationReport(
        patients=len(before),
        invariant_fields=INVARIANT_FIELDS,
        renewed=renewed,
    )
