# Separação em 3 Produtos — decisão de topologia

> Documento autoritativo referenciado por `docs/ARCHITECTURE.md` e
> `boleto-api-python/README.md`.

Este repositório abriga **três produtos com papéis e versionamentos
independentes**. A colisão de nomes é histórica — o guia abaixo desfaz a
ambiguidade.

## Os 3 produtos

| # | Produto | Onde vive | Papel | Versão |
|---|---------|-----------|-------|--------|
| 1 | **BrCobrança Engine** (Ruby) | raiz do repo (`lib/`, nome legado `boleto_cnab_api`) | **Renderização e formato**: boleto PDF/PNG, carnê 3-vias, remessa/retorno CNAB 240/400, OFX, PIX-QR — 18 bancos, offline | `VERSION` / `BoletoApi::VERSION` (1.5.0) |
| 2 | **Boleto-API Gateway** (Python/FastAPI) | `boleto-api-python/` | **Cobrança online**: providers REST (C6, Sicoob), cofre de credenciais multi-tenant, webhooks, conciliação; faz proxy ao engine para o caminho offline | `app/main.py` (0.6.0) |
| 3 | **Cliente pip** (Python) | `python-client/` | SDK para consumir a API Ruby (`/api/*`) a partir de qualquer app Python | `boleto_cnab_client.__version__` (1.4.1) |

## Regras da separação

1. **O nome "Boleto-API" designa o gateway Python** (produto 2). O repo/módulo
   Ruby manter o nome `boleto_cnab_api` é legado — como produto, ele é o
   **engine BrCobrança**.
2. **Versionamento independente**: cada produto versiona o seu, na sua
   linguagem. Nenhum release acopla os dois.
3. **Fluxo de dependência** (uma direção só):
   `consumidores → gateway (2) → engine (1)`; o cliente pip (3) fala direto com
   o engine (1). O engine não conhece o gateway.
4. **Caminho registrado** (API do banco): resolvido inteiro no gateway (OAuth +
   mTLS + JSON) — o banco devolve linha digitável/PDF/QR, sem brcobrança.
   **Caminho offline** (CNAB): o gateway delega ao engine via `/api/render/*`.
5. **Extração futura**: o gateway deve virar repo próprio (`boleto-api`) quando
   sair do estágio atual; vive aqui temporariamente para versionar junto das
   decisões.

## Roteamento de provider (contrato do gateway)

| `provider` | Caminho |
|---|---|
| `c6` / `sicoob` (REST) | API do banco — boleto registrado, Pix dinâmico, Pix Automático, conciliação |
| vazio / omitido / `brcobranca` | engine Ruby (CNAB offline) — método clássico |

Detalhes da integração C6: [c6-rest.md](./c6-rest.md).
