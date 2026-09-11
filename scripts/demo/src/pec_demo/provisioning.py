"""Provision and verify deterministic demo credentials through PEC services."""

from __future__ import annotations

from dataclasses import dataclass
import os
from pathlib import Path
import tempfile
from typing import Any, Callable

from pec_demo.models import DemoDataset, Professional
from pec_demo.pec_client import PecClientError, PecGraphQLClient


@dataclass(frozen=True, slots=True)
class ValidatedCredential:
    professional: Professional
    accesses: tuple[dict[str, Any], ...]

    @property
    def assignments(self) -> tuple[dict[str, Any], ...]:
        return tuple(
            access for access in self.accesses if access.get("tipo") == "LOTACAO"
        )

    @property
    def profile_names(self) -> tuple[str, ...]:
        return tuple(
            sorted(
                {
                    profile["nome"]
                    for access in self.accesses
                    for profile in access.get("perfis") or ()
                    if profile.get("nome")
                }
            )
        )


ClientFactory = Callable[[str], PecGraphQLClient]


def _default_client_factory(base_url: str) -> PecGraphQLClient:
    return PecGraphQLClient(base_url)


def validate_demo_credentials(
    dataset: DemoDataset,
    *,
    base_url: str,
    client_factory: ClientFactory = _default_client_factory,
) -> tuple[ValidatedCredential, ...]:
    validated = tuple(
        _validate_professional_login(
            base_url,
            professional,
            client_factory=client_factory,
        )
        for professional in dataset.professionals
    )
    multiprofile = next(
        item for item in validated if item.professional.key == "multiprofile"
    )
    if len(multiprofile.assignments) < 2:
        raise PecClientError(
            "multiprofile professional has fewer than two assignments"
        )
    return validated


def _validate_professional_login(
    base_url: str,
    professional: Professional,
    *,
    client_factory: ClientFactory,
) -> ValidatedCredential:
    client = client_factory(base_url)
    client.login(professional.cpf, professional.planned_password)
    session = client.session()
    current = session["profissional"]
    if current.get("cpf") != professional.cpf:
        raise PecClientError(
            f"authenticated CPF differs from generated CPF for {professional.key}"
        )
    user = current.get("usuario") or {}
    if user.get("forcarTrocaSenha"):
        raise PecClientError(
            f"PEC still requires a password change for {professional.key}"
        )
    accesses = tuple(current.get("acessos") or ())
    assignments = tuple(
        access for access in accesses if access.get("tipo") == "LOTACAO"
    )
    expected = {
        (assignment.cnes, assignment.ine or None, assignment.cbo)
        for assignment in professional.assignments
    }
    actual = {
        (
            (access.get("unidadeSaude") or {}).get("cnes"),
            (access.get("equipe") or {}).get("ine"),
            (access.get("cbo") or {}).get("cbo2002"),
        )
        for access in assignments
    }
    if not expected <= actual:
        missing = sorted(expected - actual)
        raise PecClientError(
            f"missing PEC assignments for {professional.key}: {missing}"
        )
    return ValidatedCredential(professional=professional, accesses=accesses)


def _render_credentials(credentials: tuple[ValidatedCredential, ...]) -> str:
    lines = [
        "CREDENCIAIS SINTETICAS — e-SUS PEC DEMO",
        "Uso exclusivo em ambiente de demonstracao e testes.",
        "",
    ]
    for credential in credentials:
        professional = credential.professional
        lines.extend(
            [
                f"[{professional.key}]",
                f"Nome: {professional.name.title()}",
                f"CPF / login: {professional.cpf}",
                f"Email: {professional.email}",
                f"Senha: {professional.planned_password}",
                f"Perfis planejados: {', '.join(professional.planned_profiles)}",
                "Perfis confirmados no PEC: "
                + (", ".join(credential.profile_names) or "(nenhum nome retornado)"),
                "Acessos e lotacoes:",
            ]
        )
        for access in credential.accesses:
            access_type = access.get("tipo", "DESCONHECIDO")
            if access_type == "LOTACAO":
                unit = access.get("unidadeSaude") or {}
                team = access.get("equipe") or {}
                cbo = access.get("cbo") or {}
                lines.append(
                    "  - LOTACAO | "
                    f"{unit.get('nome')} ({unit.get('cnes')}) | "
                    f"{cbo.get('nome')} ({cbo.get('cbo2002')}) | "
                    f"{team.get('nome')} ({team.get('ine')})"
                )
            else:
                lines.append(f"  - {access_type}")
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def _atomic_write_credentials(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{path.name}.",
        dir=path.parent,
        text=True,
    )
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8", newline="\n") as stream:
            stream.write(content)
            stream.flush()
            os.fsync(stream.fileno())
        os.chmod(temporary_name, 0o600)
        os.replace(temporary_name, path)
    except BaseException:
        try:
            os.unlink(temporary_name)
        except FileNotFoundError:
            pass
        raise


def provision_demo_credentials(
    dataset: DemoDataset,
    *,
    base_url: str,
    admin_login: str,
    admin_password: str,
    credentials_path: Path,
    client_factory: ClientFactory = _default_client_factory,
) -> tuple[ValidatedCredential, ...]:
    """Set the final password of each professional that still needs one.

    The check is per professional, not for the cohort as a whole.  A pack that
    already carries some provisioned professionals — the bootstrap does — must
    not have their password reset: PEC refuses to set a password equal to the
    current one, and a single unprovisioned newcomer would otherwise drag the
    whole cohort into a reset it cannot perform.
    """
    validated_by_key: dict[str, ValidatedCredential] = {}
    pending: list[Professional] = []
    for professional in dataset.professionals:
        try:
            validated_by_key[professional.key] = _validate_professional_login(
                base_url,
                professional,
                client_factory=client_factory,
            )
        except PecClientError:
            pending.append(professional)

    if pending:
        admin = client_factory(base_url)
        admin.login(admin_login, admin_password)
        admin.select_credential_admin_access()
        for professional in pending:
            if professional.cpf == admin_login:
                # Resetting the administrator revokes the very session used to
                # mint the tokens. The caller already logged in as this
                # professional, so a pending administrator is a real fault.
                raise PecClientError(
                    "the administrator professional is not usable with its "
                    "planned password"
                )
            token = admin.request_password_reset_token(professional.cpf)
            public = client_factory(base_url)
            public.reset_password(
                professional.cpf,
                token,
                professional.planned_password,
            )
            validated_by_key[professional.key] = _validate_professional_login(
                base_url,
                professional,
                client_factory=client_factory,
            )

    validated = tuple(
        validated_by_key[professional.key] for professional in dataset.professionals
    )
    multiprofile = next(
        item for item in validated if item.professional.key == "multiprofile"
    )
    if len(multiprofile.assignments) < 2:
        raise PecClientError("multiprofile professional has fewer than two assignments")

    _atomic_write_credentials(credentials_path, _render_credentials(validated))
    return validated
