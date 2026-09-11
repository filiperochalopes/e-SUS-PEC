"""Small stdlib-only GraphQL client for the PEC application contracts."""

from __future__ import annotations

from dataclasses import dataclass
from http.cookiejar import CookieJar
import json
from pathlib import Path
import time
import unicodedata
from typing import Any
from urllib.parse import unquote
from urllib.error import HTTPError, URLError
from urllib.request import HTTPCookieProcessor, Request, build_opener
from uuid import uuid4

from pec_demo.version import DEFAULT_PEC_VERSION


class PecClientError(RuntimeError):
    """Raised when PEC rejects or cannot complete a GraphQL operation."""


@dataclass(frozen=True, slots=True)
class GraphQLOperation:
    name: str
    query: str


LOGIN = GraphQLOperation(
    "Login",
    """
    mutation Login($input: LoginInput!) {
      login(input: $input) { success }
    }
    """,
)

SESSION = GraphQLOperation(
    "SessaoDemo",
    """
    query SessaoDemo {
      sessao {
        acesso { id tipo perfis { id nome } }
        profissional {
          id cpf cns nome
          usuario { id forcarTrocaSenha aceitouTermosUso }
          acessos {
            id tipo perfis { id nome }
            ... on AdministradorMunicipal { autorizado habilitado }
            ... on Lotacao {
              unidadeSaude { id nome cnes }
              equipe { id nome ine }
              cbo { id nome cbo2002 }
            }
          }
        }
      }
    }
    """,
)

SELECT_ACCESS = GraphQLOperation(
    "SelecionarAcesso",
    """
    mutation SelecionarAcesso($input: SelecionarAcessoInput!) {
      selecionarAcesso(input: $input) {
        id
        acesso { id tipo }
      }
    }
    """,
)

REQUEST_PASSWORD_RESET = GraphQLOperation(
    "SolicitarRedefinicaoSenha",
    """
    mutation SolicitarRedefinicaoSenha($input: SolicitarRecuperacaoSenhaInput!) {
      solicitarRedefinicaoSenha(input: $input) { value }
    }
    """,
)

RESET_PASSWORD = GraphQLOperation(
    "RedefinirSenha",
    """
    mutation RedefinirSenha($input: RedefinirSenhaInput!) {
      redefinirSenha(input: $input)
    }
    """,
)

MUNICIPALITIES = GraphQLOperation(
    "MunicipioSelectField",
    """
    query MunicipioSelectField($input: MunicipiosQueryInput!) {
      municipios(input: $input) {
        content { id nome ibge uf { id nome sigla } }
      }
    }
    """,
)

CITIZENS_BY_DOCUMENTS = GraphQLOperation(
    "CidadaoBuscaCpfCnsDnvNis",
    """
    query CidadaoBuscaCpfCnsDnvNis($filtro: FiltroDocumentosCidadaoInput!) {
      cidadaosByDocumentos(input: $filtro) {
        id nome cpf cns dataNascimento
        prontuario { id }
      }
    }
    """,
)

SAVE_CITIZEN = GraphQLOperation(
    "SalvarCidadao",
    """
    mutation SalvarCidadao($input: CidadaoInput!) {
      salvarCidadao(input: $input) { id cns }
    }
    """,
)

SAVE_ATTENDANCE = GraphQLOperation(
    "SalvarAtendimento",
    """
    mutation SalvarAtendimento($input: AtendimentoInput!) {
      salvarAtendimento(input: $input) {
        id
        cidadao { id nome }
      }
    }
    """,
)

START_INDIVIDUAL_ATTENDANCE = GraphQLOperation(
    "Atender",
    """
    mutation Atender($atendimento: ID!) {
      realizarAtendimentoIndividual(atendimento: $atendimento) {
        id
        statusAtendimento
        cidadao { id }
        atendimentoProfissional { id }
      }
    }
    """,
)

AUTOMATIC_PROCEDURES = GraphQLOperation(
    "ProcedimentosAutomaticos",
    """
    query ProcedimentosAutomaticos {
      procedimentosAutomaticos {
        id
        descricao
        codigo
      }
    }
    """,
)

PROCEDURES_BY_CODES = GraphQLOperation(
    "ProcedimentosPorCodigo",
    """
    query ProcedimentosPorCodigo($codigos: [String!]!) {
      procedimentosByCodigos(codigos: $codigos) {
        id
        descricao
        codigo
        ativo
      }
    }
    """,
)

IMMUNOBIOLOGICALS = GraphQLOperation(
    "ImunobiologicoSelectField",
    """
    query ImunobiologicoSelectField($input: ImunobiologicoQueryInput!) {
      imunobiologicos(input: $input) {
        content { id nome sigla }
      }
    }
    """,
)

IMMUNOBIOLOGICAL_DOSES = GraphQLOperation(
    "DoseImunobiologicoSelectField",
    """
    query DoseImunobiologicoSelectField(
      $input: DoseImunobiologicoVacinacaoQueryInput!
    ) {
      doseImunobiologicoVacinacao(input: $input) {
        content { id nome sigla }
      }
    }
    """,
)

CIAPS = GraphQLOperation(
    "CiapSelectField",
    """
    query CiapSelectField($input: CiapQueryInput!) {
      ciaps(input: $input) {
        content { id codigo descricao }
      }
    }
    """,
)

CIDS = GraphQLOperation(
    "Cid10SelectField",
    """
    query Cid10SelectField($input: Cid10QueryInput!) {
      cids(input: $input) {
        content { id codigo nome }
      }
    }
    """,
)

MEDICATIONS = GraphQLOperation(
    "MedicamentoCatmatSelectField",
    """
    query MedicamentoCatmatSelectField($input: MedicamentoCatmatQueryInput!) {
      medicamentosCatmat(input: $input) {
        content {
          id
          ativo
          medicamento { id principioAtivo concentracao }
          principioAtivo {
            id
            nome
            listaMaterial { tipoReceita }
          }
          unidadeMedidaDose { id nome nomePlural }
        }
      }
    }
    """,
)

MEDICATION_APPLICATIONS = GraphQLOperation(
    "ViaAdministracaoSelectField",
    """
    query ViaAdministracaoSelectField($input: AplicacaoMedicamentoQueryInput) {
      aplicacoesMedicamento(input: $input) {
        content { id nome }
      }
    }
    """,
)

DOSE_UNITS = GraphQLOperation(
    "UnidadeMedidaSelectField",
    """
    query UnidadeMedidaSelectField($input: UnidadeMedidaQueryInput) {
      unidadesMedida(input: $input) {
        content { id nome nomePlural }
      }
    }
    """,
)

PROBLEM_BY_CID = GraphQLOperation(
    "ProblemaAtivoPorCid",
    """
    query ProblemaAtivoPorCid($input: ProblemaByCiapCidQueryInput!) {
      problemaByCiapCid(input: $input) {
        id
        cid10 { id codigo }
        situacao
        evolucaoAvaliacaoCiapCid { id }
        ultimaEvolucao { id situacao dataInicio dataFim }
      }
    }
    """,
)

SAVE_INDIVIDUAL_ATTENDANCE = GraphQLOperation(
    "SalvarAtendimentoIndividual",
    """
    mutation SalvarAtendimentoIndividual($input: AtendimentoIndividualInput!) {
      salvarAtendimentoIndividual(input: $input) {
        atendProf { id }
        agendamentosCriadosIds
      }
    }
    """,
)

INDIVIDUAL_ATTENDANCE = GraphQLOperation(
    "AtendimentoIndividualDemo",
    """
    query AtendimentoIndividualDemo($id: ID!) {
      atendimentoIndividual(id: $id) {
        id
        finalizadoEm
        atendimento { cidadao { id } }
        evolucaoSubjetivo { descricao }
        evolucaoObjetivo { descricao }
        evolucaoAvaliacao { descricao }
        evolucaoPlano { descricao }
      }
    }
    """,
)


def _normalize_label(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", value or "")
    return "".join(
        character
        for character in normalized
        if not unicodedata.combining(character)
    ).casefold().strip()


def _single_exact_match(
    content: list[dict[str, Any]],
    wanted: str,
    *,
    field: str,
    label: str,
) -> dict[str, Any]:
    """Pick the one catalog entry whose ``field`` equals ``wanted`` exactly.

    Only exact matches are accepted.  Substring matching is unsafe here: the
    5.5.28 catalog carries six influenza products whose names share a prefix,
    and the acronyms of the infant and the adult dTpa differ only in letter
    case, so a loose match silently resolves to the wrong vaccine.
    """
    normalized = _normalize_label(wanted)
    candidates = [
        item for item in content if _normalize_label(item.get(field)) == normalized
    ]
    if len(candidates) != 1:
        raise PecClientError(
            f"expected one {label} whose {field} is {wanted!r}, "
            f"found {len(candidates)}"
        )
    return candidates[0]


class PecGraphQLClient:
    """Cookie-backed client that follows the same GraphQL API as the web UI."""

    def __init__(
        self,
        base_url: str,
        *,
        timeout: float = 30.0,
        pec_version: str = DEFAULT_PEC_VERSION,
    ):
        self.base_url = base_url.rstrip("/")
        self.endpoint = f"{self.base_url}/api/graphql"
        self.timeout = timeout
        self.pec_version = pec_version
        self.cookies = CookieJar()
        self.opener = build_opener(HTTPCookieProcessor(self.cookies))

    def execute(
        self,
        operation: GraphQLOperation,
        variables: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        payload = json.dumps(
            {
                "operationName": operation.name,
                "variables": variables or {},
                "query": operation.query,
            },
            separators=(",", ":"),
        ).encode()
        request = Request(
            self.endpoint,
            data=payload,
            headers={
                "Accept": "application/json",
                "Content-Type": "application/json",
                # PEC maps Apollo's client metadata to its required
                # Api-Consumer-Id contract.
                "apollographql-client-name": "PEC Web",
                "apollographql-client-version": self.pec_version,
                "Api-Consumer-Id": "ESUS_WEB_CLIENT",
                "User-Agent": "pec-demo-factory/0.1",
            },
            method="POST",
        )
        try:
            with self.opener.open(request, timeout=self.timeout) as response:
                decoded = json.load(response)
        except HTTPError as error:
            detail = error.read().decode("utf-8", errors="replace")
            raise PecClientError(
                f"{operation.name} failed with HTTP {error.code}: {detail}"
            ) from error
        except (URLError, TimeoutError, json.JSONDecodeError) as error:
            raise PecClientError(f"{operation.name} failed: {error}") from error

        # Apollo may accept either a single operation object or a one-item batch.
        if isinstance(decoded, list):
            if len(decoded) != 1:
                raise PecClientError(
                    f"{operation.name} returned an unexpected batch size"
                )
            decoded = decoded[0]
        if not isinstance(decoded, dict):
            raise PecClientError(f"{operation.name} returned invalid JSON")
        if decoded.get("errors"):
            messages = []
            for item in decoded["errors"]:
                message = str(item.get("message", item))
                extensions = item.get("extensions")
                if extensions:
                    message += " " + json.dumps(
                        extensions,
                        ensure_ascii=False,
                        sort_keys=True,
                    )
                messages.append(message)
            raise PecClientError(
                f"{operation.name} rejected by PEC: {'; '.join(messages)}"
            )
        data = decoded.get("data")
        if not isinstance(data, dict):
            raise PecClientError(f"{operation.name} returned no data")
        return data

    def login(self, username: str, password: str, *, force: bool = True) -> None:
        data = self.execute(
            LOGIN,
            {"input": {"username": username, "password": password, "force": force}},
        )
        if not data.get("login", {}).get("success"):
            raise PecClientError(f"PEC did not authenticate user {username}")

    def session(self) -> dict[str, Any]:
        session = self.execute(SESSION).get("sessao")
        if not isinstance(session, dict) or not session.get("profissional"):
            raise PecClientError("PEC returned no authenticated professional session")
        return session

    def select_access(self, access_id: str | int) -> None:
        self.execute(SELECT_ACCESS, {"input": {"id": str(access_id)}})

    def select_municipal_admin_access(self) -> dict[str, Any]:
        session = self.session()
        accesses = session["profissional"].get("acessos") or []
        access = next(
            (
                item
                for item in accesses
                if item.get("tipo") == "ADMINISTRADOR_MUNICIPAL"
                and item.get("habilitado", True)
                and item.get("autorizado", True)
            ),
            None,
        )
        if access is None:
            raise PecClientError(
                "authenticated user has no active municipal admin access"
            )
        self.select_access(access["id"])
        return access

    def select_general_admin_access(self) -> dict[str, Any]:
        session = self.session()
        accesses = session["profissional"].get("acessos") or []
        access = next(
            (item for item in accesses if item.get("tipo") == "ADMINISTRADOR_GERAL"),
            None,
        )
        if access is None:
            raise PecClientError(
                "authenticated user has no general administrator access"
            )
        self.select_access(access["id"])
        return access

    def select_credential_admin_access(self) -> dict[str, Any]:
        """Select an access allowed to manage demo credentials in either mode."""
        session = self.session()
        accesses = session["profissional"].get("acessos") or []
        municipal = next(
            (
                item
                for item in accesses
                if item.get("tipo") == "ADMINISTRADOR_MUNICIPAL"
                and item.get("habilitado", True)
                and item.get("autorizado", True)
            ),
            None,
        )
        if municipal is not None:
            self.select_access(municipal["id"])
            return municipal
        return self.select_general_admin_access()

    def select_assignment_access(
        self,
        *,
        cnes: str,
        cbo2002: str,
    ) -> dict[str, Any]:
        session = self.session()
        accesses = session["profissional"].get("acessos") or []
        access = next(
            (
                item
                for item in accesses
                if item.get("tipo") == "LOTACAO"
                and (item.get("unidadeSaude") or {}).get("cnes") == cnes
                and (item.get("cbo") or {}).get("cbo2002") == cbo2002
            ),
            None,
        )
        if access is None:
            raise PecClientError(
                f"authenticated user has no assignment for CNES {cnes}, CBO {cbo2002}"
            )
        self.select_access(access["id"])
        return access

    def request_password_reset_token(self, cpf: str) -> str:
        data = self.execute(
            REQUEST_PASSWORD_RESET,
            {"input": {"usuario": cpf}},
        )
        value = data.get("solicitarRedefinicaoSenha", {}).get("value")
        if not isinstance(value, str) or "/" not in value:
            raise PecClientError(f"PEC returned no password-reset link for {cpf}")
        return value.rstrip("/").rsplit("/", 1)[-1]

    def reset_password(self, cpf: str, token: str, password: str) -> None:
        data = self.execute(
            RESET_PASSWORD,
            {"input": {"usuario": cpf, "token": token, "novaSenha": password}},
        )
        if data.get("redefinirSenha") is not True:
            raise PecClientError(f"PEC did not confirm the password reset for {cpf}")

    def municipality_id_by_ibge(self, ibge: str, *, query: str) -> str:
        data = self.execute(
            MUNICIPALITIES,
            {
                "input": {
                    "query": query,
                    "pageParams": {
                        "size": 50,
                        "fetchPageInfo": False,
                        "sort": ["nome"],
                    },
                }
            },
        )
        matches = [
            item
            for item in data.get("municipios", {}).get("content") or ()
            if item.get("ibge") == ibge
        ]
        if len(matches) != 1:
            raise PecClientError(
                f"expected one municipality for IBGE {ibge}, found {len(matches)}"
            )
        return str(matches[0]["id"])

    def citizen_by_cpf(self, cpf: str) -> dict[str, Any] | None:
        data = self.execute(CITIZENS_BY_DOCUMENTS, {"filtro": {"cpfSet": [cpf]}})
        citizens = data.get("cidadaosByDocumentos") or []
        if len(citizens) > 1:
            raise PecClientError(f"PEC returned duplicate citizens for CPF {cpf}")
        return citizens[0] if citizens else None

    def save_citizen(self, input_data: dict[str, Any]) -> dict[str, Any]:
        citizen = self.execute(SAVE_CITIZEN, {"input": input_data}).get("salvarCidadao")
        if not isinstance(citizen, dict) or not citizen.get("id"):
            raise PecClientError("PEC did not return the saved citizen")
        return citizen

    def save_attendance(self, citizen_id: str | int) -> dict[str, Any]:
        attendance = self.execute(
            SAVE_ATTENDANCE,
            {"input": {"cidadao": str(citizen_id), "tiposServico": []}},
        ).get("salvarAtendimento")
        if not isinstance(attendance, dict) or not attendance.get("id"):
            raise PecClientError("PEC did not return the saved attendance")
        return attendance

    def start_individual_attendance(
        self,
        attendance_id: str | int,
    ) -> dict[str, Any]:
        attendance = self.execute(
            START_INDIVIDUAL_ATTENDANCE,
            {"atendimento": str(attendance_id)},
        ).get("realizarAtendimentoIndividual")
        if not isinstance(attendance, dict) or not attendance.get(
            "atendimentoProfissional", {}
        ).get("id"):
            raise PecClientError("PEC did not start the individual attendance")
        return attendance

    def automatic_procedure_id(self, code: str) -> str:
        procedures = (
            self.execute(AUTOMATIC_PROCEDURES).get("procedimentosAutomaticos") or []
        )
        matches = [item for item in procedures if item.get("codigo") == code]
        if len(matches) != 1:
            raise PecClientError(
                f"expected one automatic procedure {code}, found {len(matches)}"
            )
        return str(matches[0]["id"])

    def procedure_id(self, codes: tuple[str, ...]) -> str:
        """Resolve one active procedure from a tuple of natural codes.

        Consumers of the demo data resolve HbA1c, foot assessment, cytology and
        mammography by natural code because the internal ids differ between
        catalogs.  The factory must do the same, and must fail loudly when the
        restored catalog carries none of the accepted codes.
        """
        if not codes:
            raise PecClientError("at least one natural procedure code is required")
        procedures = (
            self.execute(PROCEDURES_BY_CODES, {"codigos": list(codes)}).get(
                "procedimentosByCodigos"
            )
            or []
        )
        by_code = {
            str(item.get("codigo")): item
            for item in procedures
            if item.get("ativo") is not False
        }
        for code in codes:
            match = by_code.get(code)
            if match:
                return str(match["id"])
        raise PecClientError(
            "no active procedure found for any of the natural codes "
            f"{', '.join(codes)}"
        )

    def immunobiological_id(self, name: str, *, search: str) -> str:
        """Resolve one immunobiological by its exact catalog name.

        ``search`` narrows the server-side query; ``name`` must then match one
        catalog entry exactly, so a partial name can never silently resolve to
        a neighbouring product.
        """
        data = self.execute(
            IMMUNOBIOLOGICALS,
            {
                "input": {
                    "query": search,
                    "pageParams": {"size": 200, "fetchPageInfo": False},
                    "semRegras": True,
                }
            },
        )
        return str(
            _single_exact_match(
                (data.get("imunobiologicos") or {}).get("content") or [],
                name,
                field="nome",
                label="immunobiological",
            )["id"]
        )

    def immunobiological_dose_id(
        self,
        acronym: str,
        *,
        immunobiological_id: str,
    ) -> str:
        """Resolve one dose of a given immunobiological by its exact acronym."""
        data = self.execute(
            IMMUNOBIOLOGICAL_DOSES,
            {
                "input": {
                    "query": "",
                    "pageParams": {"size": 200, "fetchPageInfo": False},
                    "imunobiologicoIds": [int(immunobiological_id)],
                    "semRegras": True,
                }
            },
        )
        return str(
            _single_exact_match(
                (data.get("doseImunobiologicoVacinacao") or {}).get("content") or [],
                acronym,
                field="sigla",
                label="immunobiological dose",
            )["id"]
        )

    def ciap_id(
        self,
        code: str,
        *,
        sex: str,
        age: int,
    ) -> str:
        data = self.execute(
            CIAPS,
            {
                "input": {
                    "query": code,
                    "pageParams": {"size": 50, "fetchPageInfo": False},
                    "sexo": sex,
                    "capitulosExcluidos": ["PROCEDIMENTOS"],
                    "excluirCIAPsDAB": True,
                    "idadeCidadaoEmAnos": age,
                }
            },
        )
        matches = [
            item
            for item in data.get("ciaps", {}).get("content") or []
            if item.get("codigo") == code
        ]
        if len(matches) != 1:
            raise PecClientError(
                f"expected one permitted CIAP {code}, found {len(matches)}"
            )
        return str(matches[0]["id"])

    def cid10_id(
        self,
        code: str,
        *,
        sex: str,
        age: int,
    ) -> str:
        normalized_code = code.replace(".", "").replace("-", "").upper()
        data = self.execute(
            CIDS,
            {
                "input": {
                    "query": normalized_code,
                    "sexo": sex,
                    "idadeCidadaoEmAnos": age,
                    "pageParams": {"size": 50, "fetchPageInfo": False},
                }
            },
        )
        matches = [
            item
            for item in data.get("cids", {}).get("content") or []
            if (
                str(item.get("codigo") or "").replace(".", "").replace("-", "").upper()
                == normalized_code
            )
        ]
        if len(matches) != 1:
            raise PecClientError(
                f"expected one permitted CID-10 {code}, found {len(matches)}"
            )
        return str(matches[0]["id"])

    def medication(
        self,
        query: str,
        *,
        concentration: str | None = None,
    ) -> dict[str, Any]:
        """Resolve one active catalog medication, preferring an exact principle."""
        data = self.execute(
            MEDICATIONS,
            {
                "input": {
                    "query": query,
                    "pageParams": {"size": 50, "fetchPageInfo": False},
                }
            },
        )
        content = [
            item
            for item in data.get("medicamentosCatmat", {}).get("content") or []
            if item.get("ativo") and (item.get("medicamento") or {}).get("id")
        ]
        normalized = query.casefold().strip()
        exact = [
            item
            for item in content
            if normalized
            in {
                str((item.get("principioAtivo") or {}).get("nome") or "")
                .casefold()
                .strip(),
                str((item.get("medicamento") or {}).get("principioAtivo") or "")
                .casefold()
                .strip(),
            }
        ]
        matches = exact or content
        if concentration:
            concentration_matches = [
                item
                for item in matches
                if str(
                    (item.get("medicamento") or {}).get("concentracao") or ""
                ).casefold()
                == concentration.casefold()
            ]
            matches = concentration_matches or matches
        if not matches:
            raise PecClientError(f"no active catalog medication found for {query}")
        # Stable ordering keeps repeated factory builds deterministic.
        return sorted(matches, key=lambda item: int(item["id"]))[0]

    def medication_application_id(self, query: str) -> str:
        data = self.execute(
            MEDICATION_APPLICATIONS,
            {
                "input": {
                    "query": query,
                    "pageParams": {"size": 50, "fetchPageInfo": False},
                }
            },
        )
        content = data.get("aplicacoesMedicamento", {}).get("content") or []
        normalized = query.casefold().strip()
        matches = [
            item
            for item in content
            if normalized == str(item.get("nome") or "").casefold().strip()
        ]
        if len(matches) != 1:
            raise PecClientError(
                f"expected one medication application for {query}, found {len(matches)}"
            )
        return str(matches[0]["id"])

    def dose_unit_id(self, query: str) -> str:
        data = self.execute(
            DOSE_UNITS,
            {
                "input": {
                    "query": query,
                    "pageParams": {"size": 50, "fetchPageInfo": False},
                }
            },
        )
        content = data.get("unidadesMedida", {}).get("content") or []
        normalized = query.casefold().strip()
        matches = [
            item
            for item in content
            if normalized
            in {
                str(item.get("nome") or "").casefold().strip(),
                str(item.get("nomePlural") or "").casefold().strip(),
            }
        ]
        if len(matches) != 1:
            raise PecClientError(
                f"expected one dose unit for {query}, found {len(matches)}"
            )
        return str(matches[0]["id"])

    def active_problem_by_cid(
        self,
        *,
        medical_record_id: str | int,
        cid10_id: str | int,
        ciap_id: str | int | None = None,
    ) -> dict[str, Any] | None:
        """Find an open problem by its coding pair.

        A problem opened with both a CIAP-2 and a CID-10 — a pregnancy, for
        instance — is only found when both codes are supplied.
        """
        problem = self.execute(
            PROBLEM_BY_CID,
            {
                "input": {
                    "prontuarioId": str(medical_record_id),
                    "cidId": str(cid10_id),
                    **({"ciapId": str(ciap_id)} if ciap_id else {}),
                    "situacoes": ["ATIVO", "LATENTE"],
                }
            },
        ).get("problemaByCiapCid")
        if problem is not None and (
            not isinstance(problem, dict) or not problem.get("id")
        ):
            raise PecClientError("PEC returned an invalid active problem")
        return problem

    def save_individual_attendance(
        self,
        input_data: dict[str, Any],
    ) -> dict[str, Any]:
        result = self.execute(
            SAVE_INDIVIDUAL_ATTENDANCE,
            {"input": input_data},
        ).get("salvarAtendimentoIndividual")
        if not isinstance(result, dict) or not result.get("atendProf", {}).get("id"):
            raise PecClientError("PEC did not finalize the individual attendance")
        return result

    def individual_attendance(
        self,
        attendance_professional_id: str | int,
    ) -> dict[str, Any]:
        attendance = self.execute(
            INDIVIDUAL_ATTENDANCE,
            {"id": str(attendance_professional_id)},
        ).get("atendimentoIndividual")
        if not isinstance(attendance, dict) or not attendance.get("id"):
            raise PecClientError(
                f"PEC returned no professional attendance {attendance_professional_id}"
            )
        return attendance

    def _xsrf_token(self) -> str:
        cookie = next(
            (item for item in self.cookies if item.name == "XSRF-TOKEN"),
            None,
        )
        if cookie is None:
            raise PecClientError("PEC session has no XSRF token")
        return unquote(cookie.value)

    def upload_cnes(self, archive_path: Path, municipality_id: str | int) -> None:
        """Upload a generated CNES archive through PEC's official REST endpoint."""
        try:
            archive = archive_path.read_bytes()
        except OSError as error:
            raise PecClientError(f"could not read CNES archive: {error}") from error
        boundary = f"pec-demo-{uuid4().hex}"
        filename = archive_path.name.replace('"', "")
        body = (
            (
                f"--{boundary}\r\n"
                f'Content-Disposition: form-data; name="file"; filename="{filename}"\r\n'
                "Content-Type: application/zip\r\n\r\n"
            ).encode()
            + archive
            + f"\r\n--{boundary}--\r\n".encode()
        )
        request = Request(
            f"{self.base_url}/api/cnes/{int(municipality_id)}",
            data=body,
            headers={
                "Accept": "application/json",
                "Content-Type": f"multipart/form-data; boundary={boundary}",
                "X-XSRF-TOKEN": self._xsrf_token(),
                "Api-Consumer-Id": "ESUS_WEB_CLIENT",
                "User-Agent": "pec-demo-factory/0.1",
            },
            method="POST",
        )
        try:
            with self.opener.open(request, timeout=self.timeout) as response:
                if response.status != 200:
                    raise PecClientError(f"CNES upload returned HTTP {response.status}")
        except HTTPError as error:
            detail = error.read().decode("utf-8", errors="replace")
            raise PecClientError(
                f"CNES upload failed with HTTP {error.code}: {detail}"
            ) from error
        except (URLError, TimeoutError) as error:
            raise PecClientError(f"CNES upload failed: {error}") from error

    def cnes_imports(self, municipality_id: str | int) -> tuple[dict[str, Any], ...]:
        municipality = int(municipality_id)
        operation = GraphQLOperation(
            "ImportacoesCnesDemo",
            f"""
            query ImportacoesCnesDemo {{
              importacoesCnes(input: {{
                municipioId: {municipality}
                pageParams: {{ size: 100, fetchPageInfo: false }}
              }}) {{
                content {{
                  id
                  unidadesSaudeNovas
                  unidadesSaudeAtualizadas
                  equipesNovas
                  equipesAtualizadas
                  profissionaisNovos
                  profissionaisAtualizados
                  lotacoesNovas
                  lotacoesAtualizadas
                  processo {{ id status }}
                }}
              }}
            }}
            """,
        )
        content = self.execute(operation).get("importacoesCnes", {}).get("content")
        if not isinstance(content, list):
            raise PecClientError("PEC returned no CNES import list")
        return tuple(content)

    def import_cnes_and_wait(
        self,
        archive_path: Path,
        *,
        municipality_id: str | int,
        timeout: float = 300.0,
        poll_interval: float = 2.0,
    ) -> dict[str, Any]:
        """Upload CNES and wait until PEC reports the new async process complete."""
        previous_ids = {str(item["id"]) for item in self.cnes_imports(municipality_id)}
        self.upload_cnes(archive_path, municipality_id)
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            imports = self.cnes_imports(municipality_id)
            current = next(
                (item for item in imports if str(item.get("id")) not in previous_ids),
                None,
            )
            if current is not None:
                status = (current.get("processo") or {}).get("status")
                if status == "CONCLUIDO":
                    return current
                if status not in (None, "EM_EXECUCAO"):
                    raise PecClientError(
                        f"CNES import {current.get('id')} ended with status {status}"
                    )
            time.sleep(poll_interval)
        raise PecClientError("timed out waiting for the CNES import")
