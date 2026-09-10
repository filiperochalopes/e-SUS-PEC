"""Emit an isolated-laboratory SQL fixture from the API encounter manifest.

This is deliberately a factory artifact, never a tool exposed by MCP. Native
SOAP remains API-authored. The manifest supplies the exact ownership boundary.
"""
from __future__ import annotations

from dataclasses import asdict
from datetime import date
import json
from pathlib import Path

from pec_demo.coverage import build_coverage_cohort, coverage_cases, encounter_dates


def write_materialization_plan(*, seed: int, reference_date: date, manifest_path: Path, output_path: Path) -> None:
    manifest = json.loads(manifest_path.read_text())
    if manifest.get('version') != 4:
        raise ValueError('unsupported clinical manifest')
    patients = {p.key: p for p in build_coverage_cohort(seed=seed, reference_date=reference_date)}
    records = []
    legacy_ids = {str(v['citizen_id']) for k,v in manifest['encounters'].items() if not k.startswith('v5_')}
    for case in coverage_cases():
        patient = patients[case.key]
        visits = sorted((v for v in manifest['encounters'].values() if v['patient_key'] == case.key), key=lambda v:v['key'])
        if len(visits) != case.visits:
            raise ValueError(f'missing encounters for {case.key}')
        if any(str(v['citizen_id']) in legacy_ids for v in visits):
            raise ValueError('extension overlaps protected patients')
        records.append({**asdict(case), 'cpf':patient.cpf, 'birth_date':patient.birth_date.isoformat(),
                        'encounters':[{**visit, 'date':d.isoformat()} for visit,d in zip(visits,encounter_dates(case,reference_date))]})
    payload=json.dumps({'reference_date':reference_date.isoformat(),'cases':records},ensure_ascii=False)
    # JSON is passed as a quoted SQL value, never interpolated into shell code.
    literal="'"+payload.replace("'","''")+"'::jsonb"
    template=Path(__file__).with_name('materialize.sql').read_text()
    output_path.write_text(template.replace('/* DEMO_PLAN */',literal))
