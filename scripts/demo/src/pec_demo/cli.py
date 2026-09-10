"""Command-line entry point for the PEC demo factory."""

from __future__ import annotations

import argparse
from datetime import date
from pathlib import Path
import sys

from pec_demo.artifacts import write_generation_artifacts
from pec_demo.citizens import provision_citizens
from pec_demo.clinical import (
    ClinicalAssignment,
    DOCTOR_CBO,
    DOCTOR_PROCEDURE,
    NURSE_CBO,
    NURSE_PROCEDURE,
    provision_clinical_histories,
)
from pec_demo.factory import build_demo_dataset
from pec_demo.patients import build_patient_cohort
from pec_demo.pack import refresh_demo_pack, validate_demo_pack
from pec_demo.patient_index import write_patient_index
from pec_demo.pec_client import PecClientError, PecGraphQLClient
from pec_demo.provisioning import provision_demo_credentials
from pec_demo.version import DEFAULT_PEC_VERSION


def _iso_date(value: str) -> date:
    try:
        return date.fromisoformat(value)
    except ValueError as error:
        raise argparse.ArgumentTypeError("expected YYYY-MM-DD") from error


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="pec-demo")
    subparsers = parser.add_subparsers(dest="command", required=True)
    generate = subparsers.add_parser(
        "generate-cnes",
        help="generate and validate a synthetic CNES 3.1 XML/ZIP",
    )
    generate.add_argument("--output-dir", type=Path, required=True)
    generate.add_argument(
        "--backend-jar",
        type=Path,
        required=True,
        help="PEC backend, pec-bundle, or installer JAR containing cnes_3.1.xsd",
    )
    generate.add_argument("--municipality-ibge", required=True)
    generate.add_argument("--uf", required=True)
    generate.add_argument("--cep", required=True)
    generate.add_argument("--seed", type=int, default=5522)
    generate.add_argument("--generated-on", type=_iso_date, required=True)
    generate.add_argument("--pec-version", default=DEFAULT_PEC_VERSION)
    generate.add_argument("--include-acs", action="store_true")
    provision = subparsers.add_parser(
        "provision-credentials",
        help="set final PEC passwords and publish only validated credentials",
    )
    provision.add_argument("--base-url", default="http://127.0.0.1:8082")
    provision.add_argument("--admin-login", required=True)
    provision.add_argument("--admin-password", required=True)
    provision.add_argument("--credentials-file", type=Path, required=True)
    provision.add_argument("--municipality-ibge", required=True)
    provision.add_argument("--uf", required=True)
    provision.add_argument("--cep", required=True)
    provision.add_argument("--seed", type=int, default=5522)
    provision.add_argument("--generated-on", type=_iso_date, required=True)
    provision.add_argument("--pec-version", default=DEFAULT_PEC_VERSION)
    patients = subparsers.add_parser(
        "provision-patients",
        help="idempotently create the ten-patient synthetic cohort through PEC",
    )
    patients.add_argument("--base-url", default="http://127.0.0.1:8082")
    patients.add_argument("--login", required=True)
    patients.add_argument("--password", required=True)
    patients.add_argument("--municipality-ibge", required=True)
    patients.add_argument("--municipality-name", required=True)
    patients.add_argument("--cnes", required=True)
    patients.add_argument("--ine", required=True)
    patients.add_argument("--cbo", default="225130")
    patients.add_argument("--seed", type=int, default=5522)
    patients.add_argument("--generated-on", type=_iso_date, required=True)
    histories = subparsers.add_parser(
        "provision-histories",
        help="idempotently create medical and nursing SOAP histories",
    )
    histories.add_argument("--base-url", default="http://127.0.0.1:8082")
    histories.add_argument("--login", required=True)
    histories.add_argument("--password", required=True)
    histories.add_argument("--doctor-cnes", required=True)
    histories.add_argument("--nurse-cnes", required=True)
    histories.add_argument("--manifest-file", type=Path, required=True)
    histories.add_argument("--seed", type=int, default=5522)
    histories.add_argument("--generated-on", type=_iso_date, required=True)
    refresh = subparsers.add_parser(
        "refresh-pack",
        help="refresh a restored synthetic pack without UI or external credentials",
    )
    refresh.add_argument("--base-url", default="http://127.0.0.1:18082")
    refresh.add_argument("--cnes-archive", type=Path, required=True)
    refresh.add_argument("--credentials-file", type=Path, required=True)
    refresh.add_argument("--manifest-file", type=Path, required=True)
    refresh.add_argument("--municipality-ibge", default="2927408")
    refresh.add_argument("--municipality-name", default="SALVADOR")
    refresh.add_argument("--uf", default="BA")
    refresh.add_argument("--cep", default="40000000")
    refresh.add_argument("--seed", type=int, default=5522)
    refresh.add_argument(
        "--generated-on",
        type=_iso_date,
        default=date(2026, 7, 27),
    )
    refresh.add_argument("--pec-version", default=DEFAULT_PEC_VERSION)
    refresh.add_argument("--reference-date", type=_iso_date)
    validate = subparsers.add_parser(
        "validate-pack",
        help="strictly validate a restored pack without writing",
    )
    validate.add_argument("--base-url", default="http://127.0.0.1:18082")
    validate.add_argument("--manifest-file", type=Path, required=True)
    validate.add_argument("--municipality-ibge", default="2927408")
    validate.add_argument("--uf", default="BA")
    validate.add_argument("--cep", default="40000000")
    validate.add_argument("--seed", type=int, default=5522)
    validate.add_argument(
        "--generated-on",
        type=_iso_date,
        default=date(2026, 7, 27),
    )
    validate.add_argument("--pec-version", default=DEFAULT_PEC_VERSION)
    validate.add_argument("--reference-date", type=_iso_date)
    patient_index = subparsers.add_parser(
        "generate-patient-index",
        help="write a one-line clinical summary for every synthetic patient",
    )
    patient_index.add_argument("--output", type=Path, required=True)
    patient_index.add_argument("--seed", type=int, default=5522)
    patient_index.add_argument(
        "--generated-on",
        type=_iso_date,
        default=date(2026, 7, 27),
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.command == "generate-patient-index":
        cohort = build_patient_cohort(
            seed=args.seed,
            generated_on=args.generated_on,
        )
        write_patient_index(cohort, args.output)
        print(f"patient_index={args.output}")
        return 0

    if args.command == "generate-cnes":
        if not args.backend_jar.is_file():
            parser.error(f"backend JAR not found: {args.backend_jar}")
        dataset = build_demo_dataset(
            seed=args.seed,
            municipality_ibge=args.municipality_ibge,
            uf=args.uf.upper(),
            cep=args.cep,
            generated_on=args.generated_on,
            pec_version=args.pec_version,
            include_acs=args.include_acs,
        )
        try:
            paths = write_generation_artifacts(
                dataset,
                output_dir=args.output_dir,
                backend_jar=args.backend_jar,
            )
        except ValueError as error:
            print(str(error), file=sys.stderr)
            return 1
        for name, path in paths.items():
            print(f"{name}={path}")
        return 0

    if args.command == "provision-patients":
        cohort = build_patient_cohort(
            seed=args.seed,
            generated_on=args.generated_on,
        )
        client = PecGraphQLClient(args.base_url)
        try:
            client.login(args.login, args.password)
            provisioned = provision_citizens(
                cohort,
                client=client,
                municipality_ibge=args.municipality_ibge,
                municipality_name=args.municipality_name,
                cnes=args.cnes,
                ine=args.ine,
                cbo2002=args.cbo,
            )
        except PecClientError as error:
            print(str(error), file=sys.stderr)
            return 1
        print(f"validated_patients={len(provisioned)}")
        print(f"created_patients={sum(item.created for item in provisioned)}")
        return 0

    if args.command == "provision-histories":
        cohort = build_patient_cohort(
            seed=args.seed,
            generated_on=args.generated_on,
        )
        client = PecGraphQLClient(args.base_url)
        assignments = (
            ClinicalAssignment(
                role="medico",
                cnes=args.doctor_cnes,
                cbo2002=DOCTOR_CBO,
                automatic_procedure_code=DOCTOR_PROCEDURE,
            ),
            ClinicalAssignment(
                role="enfermagem",
                cnes=args.nurse_cnes,
                cbo2002=NURSE_CBO,
                automatic_procedure_code=NURSE_PROCEDURE,
            ),
        )
        try:
            client.login(args.login, args.password)
            provisioned = provision_clinical_histories(
                cohort,
                client=client,
                assignments=assignments,
                reference_date=args.generated_on,
                manifest_path=args.manifest_file,
            )
        except PecClientError as error:
            print(str(error), file=sys.stderr)
            return 1
        print(f"validated_histories={len(provisioned)}")
        print(f"medical_histories={sum(item.role == 'medico' for item in provisioned)}")
        print(
            "nursing_histories="
            f"{sum(item.role == 'enfermagem' for item in provisioned)}"
        )
        return 0

    if args.command == "provision-credentials":
        dataset = build_demo_dataset(
            seed=args.seed,
            municipality_ibge=args.municipality_ibge,
            uf=args.uf.upper(),
            cep=args.cep,
            generated_on=args.generated_on,
            pec_version=args.pec_version,
        )
        try:
            validated = provision_demo_credentials(
                dataset,
                base_url=args.base_url,
                admin_login=args.admin_login,
                admin_password=args.admin_password,
                credentials_path=args.credentials_file,
            )
        except PecClientError as error:
            print(str(error), file=sys.stderr)
            return 1
        print(f"credentials={args.credentials_file}")
        print(f"validated_logins={len(validated)}")
        print(
            f"validated_assignments={sum(len(item.assignments) for item in validated)}"
        )
        return 0

    if args.command == "refresh-pack":
        try:
            refreshed = refresh_demo_pack(
                base_url=args.base_url,
                cnes_archive=args.cnes_archive,
                credentials_path=args.credentials_file,
                clinical_manifest_path=args.manifest_file,
                municipality_ibge=args.municipality_ibge,
                municipality_name=args.municipality_name,
                uf=args.uf.upper(),
                cep=args.cep,
                seed=args.seed,
                generated_on=args.generated_on,
                pec_version=args.pec_version,
                reference_date=args.reference_date,
            )
        except PecClientError as error:
            print(str(error), file=sys.stderr)
            return 1
        print(f"cnes_import_id={refreshed.cnes_import_id}")
        print(f"validated_credentials={refreshed.credentials}")
        print(f"validated_assignments={refreshed.assignments}")
        print(f"validated_patients={refreshed.patients}")
        print(f"created_patients={refreshed.patients_created}")
        print(f"validated_histories={refreshed.histories}")
        return 0

    if args.command == "validate-pack":
        try:
            validated = validate_demo_pack(
                base_url=args.base_url,
                clinical_manifest_path=args.manifest_file,
                municipality_ibge=args.municipality_ibge,
                uf=args.uf.upper(),
                cep=args.cep,
                seed=args.seed,
                generated_on=args.generated_on,
                pec_version=args.pec_version,
                reference_date=args.reference_date,
            )
        except PecClientError as error:
            print(str(error), file=sys.stderr)
            return 1
        print(f"validated_credentials={validated.credentials}")
        print(f"validated_assignments={validated.assignments}")
        print(f"validated_patients={validated.patients}")
        print(f"validated_histories={validated.histories}")
        return 0

    parser.error(f"unsupported command: {args.command}")
    return 2
