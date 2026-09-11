from __future__ import annotations

from copy import deepcopy

import pytest

from pec_demo.pec_client import PecClientError
from pec_demo.provisioning import provision_demo_credentials


class FakePec:
    def __init__(self, dataset):
        self.dataset = dataset
        self.passwords = {dataset.professionals[0].cpf: dataset.professionals[0].planned_password}
        self.tokens: dict[str, str] = {}

    def client(self, _base_url):
        return FakeClient(self)


class FakeClient:
    def __init__(self, pec):
        self.pec = pec
        self.cpf = None

    def login(self, username, password, *, force=True):
        if self.pec.passwords.get(username) != password:
            raise PecClientError("bad credentials")
        self.cpf = username

    def select_credential_admin_access(self):
        return {"id": "3", "tipo": "ADMINISTRADOR_MUNICIPAL"}

    def request_password_reset_token(self, cpf):
        token = f"token-{cpf}"
        self.pec.tokens[token] = cpf
        return token

    def reset_password(self, cpf, token, password):
        assert self.pec.tokens.pop(token) == cpf
        self.pec.passwords[cpf] = password

    def session(self):
        professional = next(
            item for item in self.pec.dataset.professionals if item.cpf == self.cpf
        )
        units = {
            unit.cnes: unit
            for unit in self.pec.dataset.units
        }
        accesses = []
        if professional.key == "multiprofile":
            accesses.append(
                {
                    "id": "3",
                    "tipo": "ADMINISTRADOR_MUNICIPAL",
                    "perfis": [{"id": "1", "nome": "ADMINISTRADOR_MUNICIPAL"}],
                }
            )
        for index, assignment in enumerate(professional.assignments):
            unit = units[assignment.cnes]
            team = next(
                team for team in unit.teams if team.ine == assignment.ine
            )
            accesses.append(
                {
                    "id": str(10 + index),
                    "tipo": "LOTACAO",
                    "perfis": [{"id": "2", "nome": professional.key.upper()}],
                    "unidadeSaude": {"nome": unit.name, "cnes": unit.cnes},
                    "equipe": {"nome": team.reference_name, "ine": team.ine},
                    "cbo": {"nome": assignment.cbo, "cbo2002": assignment.cbo},
                }
            )
        return {
            "profissional": {
                "cpf": professional.cpf,
                "usuario": {"forcarTrocaSenha": False},
                "acessos": accesses,
            }
        }


def test_credentials_are_written_only_after_all_logins_validate(dataset, tmp_path):
    pec = FakePec(dataset)
    output = tmp_path / "demo_credentials.txt"

    validated = provision_demo_credentials(
        dataset,
        base_url="http://pec",
        admin_login=dataset.professionals[0].cpf,
        admin_password=dataset.professionals[0].planned_password,
        credentials_path=output,
        client_factory=pec.client,
    )

    assert len(validated) == 3
    assert len(validated[0].assignments) == 2
    text = output.read_text(encoding="utf-8")
    assert all(item.cpf in text for item in dataset.professionals)
    assert all(item.planned_password in text for item in dataset.professionals)
    assert (output.stat().st_mode & 0o777) == 0o600


def test_credentials_file_is_not_published_after_failed_validation(dataset, tmp_path):
    pec = FakePec(dataset)
    broken = deepcopy(pec.dataset)
    pec.dataset = broken
    output = tmp_path / "demo_credentials.txt"
    pec.passwords[dataset.professionals[1].cpf] = "wrong-after-reset"

    original_reset = FakeClient.reset_password

    def broken_reset(self, cpf, token, password):
        original_reset(self, cpf, token, password)
        if cpf == dataset.professionals[1].cpf:
            self.pec.passwords[cpf] = "wrong-after-reset"

    FakeClient.reset_password = broken_reset
    try:
        with pytest.raises(PecClientError):
            provision_demo_credentials(
                dataset,
                base_url="http://pec",
                admin_login=dataset.professionals[0].cpf,
                admin_password=dataset.professionals[0].planned_password,
                credentials_path=output,
                client_factory=pec.client,
            )
    finally:
        FakeClient.reset_password = original_reset

    assert not output.exists()


def test_only_the_professionals_without_a_password_are_reset(dataset, tmp_path):
    """A pack with some professionals already provisioned must not reset them."""
    pec = FakePec(dataset)
    # The bootstrap ships the administrator and the two single-role
    # professionals already usable; only the newcomers still need a password.
    for professional in dataset.professionals[:3]:
        pec.passwords[professional.cpf] = professional.planned_password
    reset_calls = []
    original_reset = FakeClient.reset_password

    def recording_reset(self, cpf, token, password):
        reset_calls.append(cpf)
        return original_reset(self, cpf, token, password)

    FakeClient.reset_password = recording_reset
    try:
        validated = provision_demo_credentials(
            dataset,
            base_url="http://127.0.0.1:18082",
            admin_login=dataset.professionals[0].cpf,
            admin_password=dataset.professionals[0].planned_password,
            credentials_path=tmp_path / "credentials.txt",
            client_factory=pec.client,
        )
    finally:
        FakeClient.reset_password = original_reset

    already_usable = {item.cpf for item in dataset.professionals[:3]}
    assert not already_usable & set(reset_calls)
    assert len(validated) == len(dataset.professionals)
    assert [item.professional.key for item in validated] == [
        item.key for item in dataset.professionals
    ]


def test_an_administrator_that_cannot_be_validated_fails_loudly(dataset, tmp_path):
    """The administrator cannot reset itself: its own session mints the tokens."""
    pec = FakePec(dataset)
    original_session = FakeClient.session

    def session_forcing_password_change(self):
        payload = original_session(self)
        payload["profissional"]["usuario"]["forcarTrocaSenha"] = True
        return payload

    FakeClient.session = session_forcing_password_change
    try:
        with pytest.raises(PecClientError, match="administrator professional"):
            provision_demo_credentials(
                dataset,
                base_url="http://127.0.0.1:18082",
                admin_login=dataset.professionals[0].cpf,
                admin_password=dataset.professionals[0].planned_password,
                credentials_path=tmp_path / "credentials.txt",
                client_factory=pec.client,
            )
    finally:
        FakeClient.session = original_session
    assert not (tmp_path / "credentials.txt").exists()
