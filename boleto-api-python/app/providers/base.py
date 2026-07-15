# Interface comum a todos os providers (porte do BaseProvider Ruby).
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from app.schemas import Cobranca, CobrancaOut, ConciliacaoOut, PixCobranca, PixCobrancaOut, WebhookEvent


class BankProvider(ABC):
    def __init__(self, *, account_config: dict[str, Any], credentials: dict[str, Any]) -> None:
        self.account_config = account_config
        self.credentials = credentials  # do cofre; em memória, não persiste

    @abstractmethod
    def registrar(self, cobranca: Cobranca) -> CobrancaOut: ...

    @abstractmethod
    def consultar(self, cobranca_id: str) -> CobrancaOut: ...

    @abstractmethod
    def baixar(self, cobranca_id: str) -> CobrancaOut: ...

    def normalizar_webhook(self, headers: dict[str, str], body: dict[str, Any]) -> WebhookEvent:
        raise NotImplementedError

    # --- capacidades opcionais (nem todo provider tem) ------------------------
    # Os routers checam com hasattr/try antes de expor; brcobrança (offline) não
    # implementa nenhuma delas.

    def pdf(self, cobranca_id: str) -> CobrancaOut:
        """PDF do boleto registrado, quando o banco fornece."""
        raise NotImplementedError

    def alterar(self, cobranca_id: str, campos: dict[str, Any]) -> CobrancaOut:
        """Alteração online do boleto emitido, quando o banco suporta."""
        raise NotImplementedError

    def criar_pix(self, pix: PixCobranca) -> PixCobrancaOut:
        """Cobrança Pix dinâmica (cob/cobv BACEN)."""
        raise NotImplementedError

    def consultar_pix(self, txid: str) -> PixCobrancaOut:
        raise NotImplementedError

    def listar_recebiveis(self, *, start_date: str, end_date: str, page: int, size: int) -> ConciliacaoOut:
        raise NotImplementedError

    def listar_transacoes(self, *, start_date: str, end_date: str, page: int, size: int) -> ConciliacaoOut:
        raise NotImplementedError
