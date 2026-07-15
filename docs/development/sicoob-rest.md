# Sicoob — Integração REST (boleto v3, Pix BACEN)

> Implementada no gateway Python (`boleto-api-python`), provider `sicoob`.
> Fontes: [Portal Developers Sicoob](https://developers.sicoob.com.br/portal/),
> doc Postman oficial da Cobrança v3 e integrações de mercado. A documentação
> oficial do Sicoob é notoriamente incompleta — itens "a confirmar" fecham na
> homologação (mesmo processo feito com o C6).

## Autenticação

| Item | Valor |
|---|---|
| Fluxo | OAuth2 `client_credentials` + **scopes** + **mTLS** |
| Token | `https://auth.sicoob.com.br/auth/realms/cooperado/protocol/openid-connect/token` |
| Certificado | PFX cadastrado no portal (produção: e-CNPJ ICP-Brasil) |
| Peculiaridade | header **`client_id` em toda request** |
| Sandbox | `https://sandbox.sicoob.com.br/sicoob/sandbox` — token estático do portal, **sem mTLS** (aponte com `SICOOB_BASE_URL`/`SICOOB_AUTH_URL`) |

Scopes usados (pedidos no token): `cobranca_boletos_incluir/consultar/baixa`,
`cob.*`, `cobv.*`, `lotecobv.*`, `pix.*`, `webhook.*`, `payloadlocation.*`.
Conta corrente (extrato mensal — implementado): `cco_extrato`, `cco_saldo`.

## Superfície

| Operação | Sicoob | Endpoint do gateway |
|---|---|---|
| Emitir boleto | `POST /cobranca-bancaria/v3/boletos` (**v3** — v2 descontinuada em 2025) | `POST /cobranca` |
| Consultar boleto | `GET /v3/boletos?numeroCliente&codigoModalidade&nossoNumero` | `GET /cobranca/{id}` |
| Segunda via (PDF) | consulta com `gerarPdf=true` | `GET /cobranca/{id}/pdf` |
| Baixar | comando de baixa (a confirmar rota exata) | `DELETE /cobranca/{id}` |
| **Pix (BACEN)** | `/pix/api/v2` — **mesmo dialeto do C6** | `/pix`, `/pix/{txid}`, `PATCH`, listas, `/pix/lote/*` |
| Extrato conta-corrente | `GET /conta-corrente/v4/extrato/{mes}/{ano}` (mensal) | `GET /extrato` |
| Webhook Pix | BACEN (`/webhook`, push com array `pix`) | `POST /webhooks/sicoob[/{tenant}]` |

**Boleto híbrido:** com chave Pix vinculada à conta, a emissão v3 já devolve
`pixCopiaECola` (QR no boleto) — normalizado em `CobrancaOut.pix_copia_cola`.

## Pix Automático, recebidos e webhook por chave (BACEN, compartilhado)

Implementados no dialeto BACEN compartilhado (`bacen_pix.py`) — valem para C6 e
Sicoob: **Pix Automático** (`/pix-automatico/*`: rec, solicrec, locrec, cobr,
retentativa, webhookrec/cobr — o agendamento de cada cobrança fica no produto
consumidor), **Pix recebidos** (`/pix/recebidos`, devoluções) e **webhook por
chave** (`/config/webhook-pix`).

## Coesão com o C6 (arquitetura)

O Pix é **padronizado pelo BACEN** — o gateway implementa o dialeto UMA vez em
`app/providers/bacen_pix.py` (`BacenPixMixin`) e cada provider define só o
prefixo: C6 `/v2/pix`, Sicoob `/pix/api/v2`. Cob, cobv, revisão (PATCH),
listas e lote funcionam idênticos nos dois bancos (e em qualquer banco futuro).
O mesmo valerá para o **Pix Automático** (`/rec`, `/solicrec`, `/cobr`).

## Conciliação

- **Pix:** webhook BACEN (tempo real) → push assinado ao consumidor.
- **Boleto:** o Sicoob não tem webhook de boleto — conciliação por **polling**
  (`GET /cobranca/{id}`). O agendamento do polling fica no **produto
  consumidor** — o gateway é interface de consumo (stateless), por decisão
  de arquitetura.

## Autenticação (mecanismo único da API)

Cada banco tem seu **próprio esquema** de credenciais, mas o mecanismo da API é
o mesmo: `POST /credenciais` recebe os parâmetros deste banco, armazena cifrado
(zero-knowledge) e devolve o token `bapi_`; as demais chamadas validam pelo
`Authorization: Bearer bapi_...`. Esquema vigente por banco: `GET /bancos`.

## account_config (por tenant)

`{numeroCliente, codigoModalidade (1), numeroContaCorrente, chave_pix, ...}`
Credenciais: mesmos 3 modos do C6 (Bearer `bapi_` / request / cofre `VAULT__`).

## Validado no SANDBOX oficial (mock do portal)

Com o token estático do portal (`SICOOB_SANDBOX_TOKEN`/`_CLIENT_ID`), o e2e
(`tests/test_sandbox_sicoob.py`) validou:

- **Consulta de boleto** (`GET /v3/boletos`): 200 com o contrato completo
  (`resultado{linhaDigitavel, codigoBarras, ...}`) — confirma o mapeamento.
- **Segunda via**: rota dedicada `GET /v3/boletos/segunda-via` (descoberta no
  sandbox; o provider usa essa rota).
- **Pix**: `POST /cob` 200 — o Sicoob devolve **`brcode`** (não
  `pixCopiaECola`); normalizado no `_pix_out` compartilhado.
- **Pix recebidos** (`GET /pix`): 200 `{parametros, pix[]}` — mesmo dialeto
  BACEN do C6 ✔.
- **Pix Automático** (`POST /rec`): 200 no sandbox — PA validado nos DOIS
  bancos.
- **Limitação do mock**: o `POST /v3/boletos` (emissão) devolve um **400
  enlatado** (`{"mensagens":[{"mensagem":"string"...}]}`) para qualquer
  payload — comportamento do simulador, não do contrato; a emissão real fecha
  na homologação com a cooperativa.

## A confirmar na homologação (produção)

1. Emissão real (`POST /v3/boletos`) — mock do sandbox não valida payload.
2. Rota/verbo exatos da **baixa** v3.
3. Campos mínimos aceitos pela cooperativa (varia por config da conta).
4. Webhook de movimentação de boleto (se a v3 expuser, substitui o polling).
