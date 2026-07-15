from __future__ import annotations

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from app.core.vault import CredentialNotFound
from app.providers.c6 import ProcessamentoPendente
from app.routers import (bancos, bolepix, carne, cobranca, conciliacao, credenciais,
                         extrato, pix, pix_automatico, webhook_banco, webhooks)

TAGS = [
    {"name": "bancos", "description": "Catálogo de bancos, capacidades reais (introspecção) e esquema de credenciais por banco."},
    {"name": "credenciais", "description": "Tokenização zero-knowledge: cadastre as credenciais do banco UMA vez e use o token `bapi_` nas demais chamadas."},
    {"name": "cobranca", "description": "Boleto: emitir, consultar, alterar, PDF e baixar — REST (banco) ou CNAB offline (engine Ruby), conforme `provider`."},
    {"name": "carne", "description": "Carnê 3-vias A4 (registra N parcelas e monta o PDF no engine)."},
    {"name": "pix", "description": "Pix BACEN: cob/cobv, revisão, listas, lote e Pix RECEBIDOS (conciliação). Dialeto idêntico em todos os bancos."},
    {"name": "bolepix", "description": "Boleto híbrido online com QR Pix EVP embutido (exclusivo C6, /v2/bank_slips)."},
    {"name": "pix-automatico", "description": "Débito recorrente via Pix (BACEN): recorrência, autorização do pagador, cobranças do ciclo e retentativa. O agendamento de cada cobrança fica no produto consumidor."},
    {"name": "conciliacao", "description": "Recebíveis e transações C6 Pay (extrato da adquirência)."},
    {"name": "extrato", "description": "Extrato da conta PJ (C6 /v1/statement; Sicoob conta-corrente v4 — mensal)."},
    {"name": "config", "description": "Configurações NO banco: URL de webhook (boleto e Pix por chave)."},
    {"name": "webhooks", "description": "ENTRADA de notificações dos bancos → evento normalizado → push assinado (HMAC) ao consumidor dono do tenant."},
    {"name": "health", "description": "Sonda de disponibilidade."},
]

app = FastAPI(
    title="Boleto-API (Python)",
    version="0.6.0",
    openapi_tags=TAGS,
    description=(
        "Gateway de cobrança multi-banco (C6/Sicoob) + proxy ao engine brcobrança (Ruby).\n\n"
        "**Produto standalone** consumido por múltiplos sistemas; escopo por `tenant_id`.\n\n"
        "**Push de eventos (saída, não é um path desta API):** ao receber o webhook do "
        "banco, o gateway envia o evento normalizado (`WebhookEvent`) por `POST` ao "
        "consumidor dono do tenant, assinado em `X-Signature: sha256=<hmac_sha256(secret, "
        "raw_body)>`. Destino por tenant via `SUB__<tenant>__URL/SECRET`, com fallback "
        "global `EVENT_WEBHOOK_URL/SECRET`.\n\n"
        "**Respostas `dict` (passthrough):** rotas Pix/Pix Automático/extrato/conciliação "
        "devolvem o corpo do banco como veio (padrão BACEN/documentação do banco), sem "
        "re-tipagem — o contrato é o do banco; o gateway normaliza autenticação, "
        "multi-tenant e erros."
    ),
)

app.include_router(bancos.router)
app.include_router(credenciais.router)
app.include_router(cobranca.router)
app.include_router(carne.router)
app.include_router(pix.router)
app.include_router(bolepix.router)
app.include_router(conciliacao.router)
app.include_router(extrato.router)
app.include_router(pix_automatico.router)
app.include_router(webhook_banco.router)
app.include_router(webhook_banco.pix_router)
app.include_router(webhooks.router)


@app.exception_handler(ProcessamentoPendente)
async def _processamento_pendente(request: Request, exc: ProcessamentoPendente) -> JSONResponse:
    # Registro assincrono na CIP ainda em curso — o chamador re-tenta.
    return JSONResponse(status_code=409, content={"detail": str(exc)})


@app.exception_handler(CredentialNotFound)
async def _credential_not_found(request: Request, exc: CredentialNotFound) -> JSONResponse:
    # Tenant/provider não provisionado no cofre — erro de configuração, não 500.
    return JSONResponse(
        status_code=424,
        content={"detail": "credenciais do tenant/provider ausentes no cofre"},
    )


@app.get("/health", tags=["health"])
def health() -> dict[str, str]:
    """Sonda de disponibilidade do gateway (não toca nos bancos)."""
    return {"status": "ok"}
