# Schemas canônicos (pydantic v2) — contrato estável que os consumidores usam.
#
# O mesmo shape serve qualquer provider (C6, Sicoob, brcobrança offline). Cada
# provider traduz para o seu banco; a resposta volta normalizada.
from __future__ import annotations

from decimal import Decimal
from datetime import date, datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field, field_validator


class Provider(str, Enum):
    """Provider de cobrança. `brcobranca` = offline/CNAB (engine Ruby)."""

    brcobranca = "brcobranca"
    c6 = "c6"
    sicoob = "sicoob"


class Status(str, Enum):
    """Status normalizado da cobrança (igual para qualquer banco)."""

    registrado = "registrado"
    pendente = "pendente"
    liquidado = "liquidado"
    baixado = "baixado"
    expirado = "expirado"
    erro = "erro"


class Pagador(BaseModel):
    nome: str = Field(description="Nome do pagador", examples=["Fulano de Tal"])
    documento: str = Field(description="CPF ou CNPJ (só dígitos)", examples=["12345678901"])
    endereco: dict[str, Any] | None = Field(default=None, description="Endereço do pagador (opcional)")


class Cobranca(BaseModel):
    valor: Decimal = Field(description="Valor da cobrança", examples=["1000.00"])
    vencimento: date = Field(description="Data de vencimento (ISO)", examples=["2026-07-10"])
    nosso_numero: str | None = Field(default=None, description="Nosso número (opcional; o banco pode atribuir)")
    seu_numero: str | None = Field(default=None, description="Seu número / identificador do emissor (opcional)")
    pagador: Pagador
    multa: dict[str, Any] | None = Field(default=None, description="Regras de multa (opcional)")
    juros: dict[str, Any] | None = Field(default=None, description="Regras de juros (opcional)")
    desconto: dict[str, Any] | None = Field(default=None, description="Regras de desconto (opcional)")


class CobrancaIn(BaseModel):
    tenant_id: str = Field(description="Identificador do tenant (resolve credenciais no cofre)", examples=["empresa_123"])
    provider: Provider = Field(
        default=Provider.brcobranca,
        description="Roteamento: `c6` = API REST do banco; vazio/omitido = brcobrança (CNAB offline).",
    )
    account_config: dict[str, Any] = Field(
        default_factory=dict,
        description=(
            "Blob por provider (não unificado de propósito). "
            "c6: {agencia, conta, convenio}; "
            "sicoob: {cooperativa, conta, numeroCliente, codigoModalidade}."
        ),
    )
    cobranca: Cobranca
    credentials: dict[str, Any] | None = Field(
        default=None,
        description=(
            "Credenciais do banco enviadas NO REQUEST (client_id, client_secret, "
            "pfx_base64, pfx_password). Usadas só em memória, nunca persistidas. "
            "Se omitidas, caem no cofre do servidor (VAULT__*)."
        ),
    )

    @field_validator("provider", mode="before")
    @classmethod
    def _provider_vazio_vira_brcobranca(cls, v: Any) -> Any:
        # Contrato: provider vazio/None/omitido roteia para o método antigo (CNAB).
        return Provider.brcobranca if v in (None, "") else v


class CobrancaOut(BaseModel):
    """Resposta normalizada — mesmo shape para qualquer provider."""

    id: str | None = Field(default=None, description="Id da cobrança no banco (nosso número/txid)")
    status: Status
    linha_digitavel: str | None = None
    codigo_barras: str | None = None
    pix_copia_cola: str | None = Field(default=None, description="PIX copia-e-cola (EMV), quando híbrido")
    pdf_base64: str | None = Field(default=None, description="PDF do boleto em base64, quando disponível")
    raw: dict[str, Any] | None = Field(default=None, description="Resposta crua do banco (debug)")


# --- PIX dinâmico (só providers REST; brcobrança não emite cobrança Pix) -----


class PixCobranca(BaseModel):
    """Cobrança Pix dinâmica (padrão BACEN: cob imediata ou cobv com vencimento)."""

    valor: Decimal = Field(description="Valor original da cobrança", examples=["10.00"])
    chave: str | None = Field(
        default=None,
        description="Chave Pix do recebedor. Se omitida, usa `account_config.chave_pix`.",
    )
    txid: str | None = Field(
        default=None,
        description="Txid ([a-zA-Z0-9]{26,35}). Obrigatório na cobv; na cob o banco gera.",
    )
    expiracao_segundos: int = Field(
        default=3600, description="Validade da cob imediata, em segundos (ignorado na cobv)."
    )
    data_vencimento: date | None = Field(
        default=None,
        description="Se presente, emite cobv (cobrança com vencimento) em vez de cob imediata.",
    )
    validade_apos_vencimento: int = Field(
        default=30, description="Dias corridos em que a cobv ainda pode ser paga após o vencimento."
    )
    devedor: Pagador | None = Field(default=None, description="Devedor (obrigatório na cobv)")
    descricao: str | None = Field(default=None, description="solicitacaoPagador (texto ao pagador)")


class PixCobrancaIn(BaseModel):
    tenant_id: str = Field(description="Identificador do tenant", examples=["empresa_123"])
    provider: Provider = Field(
        default=Provider.c6,
        description="Provider REST com Pix dinâmico (brcobrança não suporta).",
    )
    account_config: dict[str, Any] = Field(
        default_factory=dict, description="Blob por provider. c6: {chave_pix, ...}"
    )
    pix: PixCobranca
    credentials: dict[str, Any] | None = Field(
        default=None,
        description=(
            "Credenciais do banco enviadas NO REQUEST (client_id, client_secret, "
            "pfx_base64, pfx_password). Só em memória; fallback: cofre VAULT__*."
        ),
    )


class PixCobrancaOut(BaseModel):
    """Resposta normalizada da cobrança Pix."""

    txid: str | None = None
    status: Status
    pix_copia_cola: str | None = Field(default=None, description="Payload EMV (copia-e-cola)")
    location: str | None = Field(default=None, description="URL do payload (loc.location)")
    expira_em: datetime | None = None
    raw: dict[str, Any] | None = None


# --- Bolepix (boleto híbrido online com Pix EVP — C6 /v2/bank_slips) ----------


class BolepixCobranca(BaseModel):
    valor: Decimal = Field(description="Valor da cobrança", examples=["99.90"])
    vencimento: date
    descricao: str = Field(description="Descrição da cobrança (obrigatória no Bolepix)")
    pagador: Pagador = Field(description="endereco: {address|logradouro+numero, neighborhood|bairro, city, state, zip_code}")
    external_reference_id: str | None = Field(
        default=None, description="^[A-Z0-9]{26}$ — gerado automaticamente se omitido"
    )
    chave_pix: str | None = Field(default=None, description="Chave EVP; default: account_config.chave_pix")
    nosso_numero: str | None = None
    instrucoes: list[str] | None = None
    dias_apos_vencimento: int | None = Field(default=None, description="days_after_due_date")


class BolepixIn(BaseModel):
    tenant_id: str
    provider: Provider = Provider.c6
    account_config: dict[str, Any] = Field(default_factory=dict)
    bolepix: BolepixCobranca
    credentials: dict[str, Any] | None = None


# --- Pix lote de cobv -----------------------------------------------------------


class LoteCobvIn(BaseModel):
    tenant_id: str
    provider: Provider = Provider.c6
    account_config: dict[str, Any] = Field(default_factory=dict)
    descricao: str
    cobrancas: list[PixCobranca] = Field(description="Cada item exige txid e data_vencimento")
    credentials: dict[str, Any] | None = None


# --- Pix Automático (BACEN: rec / solicrec / cobr) --------------------------------


class Recorrencia(BaseModel):
    """Vínculo de recorrência (Pix Automático) — o 'contrato de cobrança'."""

    contrato: str = Field(description="Identificador do contrato no recebedor", examples=["CT-2026-001"])
    objeto: str | None = Field(default=None, description="Descrição do objeto do contrato", examples=["Aluguel Apto 101"])
    devedor: Pagador
    periodicidade: str = Field(description="SEMANAL | MENSAL | TRIMESTRAL | SEMESTRAL | ANUAL", examples=["MENSAL"])
    data_inicial: date
    data_final: date | None = None
    valor_fixo: Decimal | None = Field(default=None, description="valorRec — cobranças de valor fixo")
    valor_minimo: Decimal | None = Field(default=None, description="valorMinimoRecebedor — valor variável")
    politica_retentativa: str = Field(default="PERMITE_3R_7D", description="NAO_PERMITE | PERMITE_3R_7D")
    loc: int | None = Field(default=None, description="Id de locrec p/ adesão via QR (Jornada 2)")
    txid_ativacao: str | None = Field(default=None, description="ativacao.dadosJornada.txid (Jornadas 3/4)")
    extras: dict[str, Any] | None = Field(default=None, description="Campos BACEN adicionais (merge no payload)")


class RecorrenciaIn(BaseModel):
    tenant_id: str
    provider: Provider = Provider.c6
    account_config: dict[str, Any] = Field(default_factory=dict)
    recorrencia: Recorrencia
    credentials: dict[str, Any] | None = None


class CobrancaRecorrente(BaseModel):
    """Uma cobrança do ciclo (cobr) — agendar >= 2 dias antes do vencimento.
    O agendamento é responsabilidade do produto consumidor (gateway stateless)."""

    id_rec: str = Field(description="idRec da recorrência aprovada")
    valor: Decimal
    data_vencimento: date
    info_adicional: str | None = None
    extras: dict[str, Any] | None = None


class CobrancaRecorrenteIn(BaseModel):
    tenant_id: str
    provider: Provider = Provider.c6
    account_config: dict[str, Any] = Field(default_factory=dict)
    cobranca: CobrancaRecorrente
    credentials: dict[str, Any] | None = None


class SolicitacaoRecorrenciaIn(BaseModel):
    """solicrec — pedido de autorização enviado ao app do pagador (Jornada 1)."""

    tenant_id: str
    provider: Provider = Provider.c6
    account_config: dict[str, Any] = Field(default_factory=dict)
    dados: dict[str, Any] = Field(description="Payload BACEN da solicrec (idRec, ...)")
    credentials: dict[str, Any] | None = None


# --- Cadastro de webhook no banco ------------------------------------------------


class WebhookBancoIn(BaseModel):
    tenant_id: str
    provider: Provider = Provider.c6
    url: str = Field(description="URL pública que o banco chamará (ex: https://.../webhooks/c6/{tenant})")
    service: str = Field(default="BANK_SLIP", description="BANK_SLIP | CHECKOUT")
    credentials: dict[str, Any] | None = None


# --- Tokenização de credenciais ----------------------------------------------


class CredencialIn(BaseModel):
    """Cadastro de credenciais do banco — devolve um token opaco (única vez)."""

    tenant_id: str = Field(description="Tenant dono destas credenciais", examples=["empresa_123"])
    provider: Provider = Field(description="Banco/provider destas credenciais (ex: c6)")
    credentials: dict[str, Any] = Field(
        description="client_id, client_secret, pfx_base64, pfx_password (cifradas em repouso; "
                    "chave derivada do token — o servidor não decifra sozinho)"
    )


class CredencialOut(BaseModel):
    token: str = Field(description="Token opaco (bapi_...) — exibido UMA única vez; guarde-o. "
                                   "Use nas demais rotas via Authorization: Bearer")
    tenant_id: str
    provider: Provider


# --- Conciliação (C6 Pay statement) ------------------------------------------


class ConciliacaoOut(BaseModel):
    """Página de recebíveis/transações — itens crus do banco + paginação."""

    page: int | None = None
    last_page: int | None = None
    total_items: int | None = None
    items: list[dict[str, Any]] = Field(default_factory=list)


class WebhookEvent(BaseModel):
    """Evento normalizado de pagamento — também o corpo do push aos consumidores."""

    event: str = Field(description="Tipo do evento", examples=["cobranca.atualizada", "pix.recebido"])
    id: str | None = Field(default=None, description="Id da cobrança / txid")
    status: Status | None = None
    paid_at: datetime | None = Field(default=None, description="Data/hora do pagamento, se liquidado")
    valor: Decimal | None = Field(default=None, description="Valor pago, se aplicável")
    raw: dict[str, Any] | None = None


class CarneIn(BaseModel):
    tenant_id: str = Field(description="Identificador do tenant", examples=["empresa_123"])
    provider: Provider
    account_config: dict[str, Any] = Field(default_factory=dict, description="Blob por provider (ver CobrancaIn)")
    bank: str = Field(description="Nome brcobrança para renderizar o carnê", examples=["banco_c6"])
    parcelas: list[Cobranca] = Field(description="Parcelas do carnê (registradas individualmente)")
    credentials: dict[str, Any] | None = Field(
        default=None,
        description="Credenciais do banco no request (só memória; fallback: cofre VAULT__*).",
    )


class CarneOut(BaseModel):
    carne_pdf_base64: str | None = Field(default=None, description="PDF do carnê 3-vias em base64")
    cobrancas: list[CobrancaOut] = Field(default_factory=list, description="Cobranças registradas (uma por parcela)")
