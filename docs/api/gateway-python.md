# Boleto-API Gateway (Python) — Referência da API

> Gateway de cobrança multi-banco (`boleto-api-python/`, FastAPI, v0.6.0).
> Spec viva: `GET /docs` (Swagger) e `GET /openapi.json` com a app rodando;
> versionada em [`boleto-api-python/openapi.json`](../../boleto-api-python/openapi.json).
>
> Não confundir com a **API Ruby** (engine BrCobrança, `/api/*` — ver
> [docs/openapi.yaml](../openapi.yaml)). Papéis em
> [separacao-3-produtos.md](../development/separacao-3-produtos.md).

## Conceitos

- **`tenant_id`** — escopo de cada conta/cliente (multi-tenant).
- **`provider`** — roteamento: `c6` = API REST do banco; **vazio/omitido** ou
  `brcobranca` = CNAB offline (engine Ruby). Pix e conciliação exigem provider
  REST (senão **422**).
- **Credenciais** (ordem de precedência):
  1. `Authorization: Bearer bapi_...` — token do `/credenciais` (recomendado);
  2. `credentials` no corpo (POSTs) ou header `X-Bank-Credentials`
     (JSON base64, GET/DELETE) — stateless, só memória;
  3. cofre do servidor `VAULT__<tenant>__<provider>__*` (env, fallback).

## 🏦 Descoberta: `GET /bancos`

Lista os bancos/providers, suas **capacidades reais** (introspectadas do código —
nunca desatualiza) e o contrato único de autenticação:

```bash
curl http://localhost:8000/bancos
# → {"autenticacao_api": {...},
#    "bancos": [
#      {"id": "c6", "codigo_banco": "336", "tipo": "rest",
#       "capacidades": ["boleto", "boleto_alteracao", "boleto_pdf", "bolepix",
#                       "pix", "pix_recebidos", "pix_automatico", "extrato",
#                       "conciliacao_cartao", "webhook_banco", ...]},
#      {"id": "sicoob", "codigo_banco": "756", "tipo": "rest", ...},
#      {"id": "brcobranca", "tipo": "offline", "bancos_cnab": [18 bancos]}]}
```

Antes de chamar qualquer operação, o sistema consumidor pode checar se o banco
do tenant suporta a capacidade (ex.: `bolepix` é exclusivo do C6).

## 🔐 Autenticação — mecanismo único da API, esquema próprio por banco

O **mecanismo da API é o mesmo para todos os bancos** (é ele que o consumidor
integra uma única vez):

1. `POST /credenciais` **recebe os parâmetros do banco** (cada banco tem o seu
   esquema), processa e **armazena cifrado** (zero-knowledge) → devolve o token
   `bapi_` (única vez);
2. **Todas as demais chamadas** autenticam com `Authorization: Bearer bapi_...`
   — a API valida o token e usa as credenciais do banco internamente;
3. `DELETE /credenciais` revoga.

O **esquema de credenciais é próprio de cada banco** — o campo `credentials` é
livre e o `GET /bancos` documenta o esquema vigente:

| Banco | `credentials` (esquema próprio) |
|---|---|
| **C6** | `client_id`, `client_secret`, `pfx_base64`, `pfx_password` (mTLS obrigatório) |
| **Sicoob** | `client_id` + `access_token` (sandbox) · `client_id`, `client_secret`, `pfx_base64`, `pfx_password`, `scopes?` (produção) |

> Banco novo com outro esquema? O consumidor não muda nada: continua enviando o
> dict de credenciais daquele banco no `POST /credenciais` e usando o `bapi_`.

## Códigos de erro comuns

| Código | Quando |
|---|---|
| 401 | token `bapi_` inválido/revogado; webhook com token errado |
| 403 | token de outro tenant/provider |
| 422 | contrato inválido (provider offline em rota REST, chave Pix ausente, header malformado) |
| 424 | tenant sem credenciais (nem request, nem token, nem cofre) |
| 409 | registro em processamento no banco (CIP) — re-tente em instantes |

---

## 🔑 Credenciais (tokenização)

### `POST /credenciais`
Cadastra credenciais do banco e devolve um **token opaco** (única vez).
Zero-knowledge: cifradas com AES-256-GCM cuja chave é derivada **do próprio
token** (HKDF-SHA256) — o servidor guarda só o SHA-256 do token e não decifra
sozinho. Storage: Postgres/Supabase (`SUPABASE_DB_URL`/`DATABASE_URL`, schema
próprio `boleto_api`) ou SQLite local.

```bash
curl -X POST http://localhost:8000/credenciais \
  -H 'Content-Type: application/json' \
  -d '{
    "tenant_id": "empresa_123",
    "provider": "c6",
    "credentials": {
      "client_id": "...", "client_secret": "...",
      "pfx_base64": "...", "pfx_password": "..."
    }
  }'
# 201 → {"token": "bapi_kJx...", "tenant_id": "empresa_123", "provider": "c6"}
#   guarde o token: ele não é recuperável (o servidor não o armazena)
```

### `DELETE /credenciais`
Revoga o token **imediatamente** (apaga o registro cifrado).

```bash
curl -X DELETE http://localhost:8000/credenciais \
  -H 'Authorization: Bearer bapi_kJx...'
# 204 | 401 se o token não existir
```

---

## 🧾 Cobrança (boleto)

### `POST /cobranca`
Registra a cobrança no provider. Com `provider=c6` (e `C6_REGISTERED_READY=true`)
usa a API REST do banco; senão renderiza offline no engine Ruby.

```bash
curl -X POST http://localhost:8000/cobranca \
  -H 'Authorization: Bearer bapi_kJx...' \
  -H 'Content-Type: application/json' \
  -d '{
    "tenant_id": "empresa_123",
    "provider": "c6",
    "account_config": {"billing_scheme": "21"},
    "cobranca": {
      "valor": "1500.00",
      "vencimento": "2026-08-31",
      "seu_numero": "FAT001",
      "nosso_numero": "123",
      "pagador": {
        "nome": "José da Silva",
        "documento": "12345678901",
        "endereco": {"street": "Av. Nove de Julho", "number": 123,
                     "city": "São Paulo", "state": "SP", "zip_code": "01000000"}
      }
    }
  }'
# 200 → {"id": "01J3...", "status": "registrado",
#        "linha_digitavel": "33690.00009 ...", "codigo_barras": "3369...",
#        "pix_copia_cola": null, "pdf_base64": null, "raw": {...}}
```

### `GET /cobranca/{id}?tenant_id=&provider=`
Consulta o status normalizado (`registrado|pendente|liquidado|baixado|expirado|erro`).

### `GET /cobranca/{id}/pdf?tenant_id=&provider=`
PDF do boleto registrado (C6 devolve `pdf_base64`). Provider offline → 422.

### `PUT /cobranca/{id}?tenant_id=&provider=`
Altera boleto emitido — corpo com os campos C6 (`amount`, `due_date`,
`discount`, `interest`, `fine`). Registro em processamento na CIP → **409**
(re-tente em instantes).

### `DELETE /cobranca/{id}?tenant_id=&provider=`
Baixa/cancela (C6: `PUT /bank_slips/{id}/cancel`, 204 no banco).

> Nas rotas GET/DELETE, credenciais via `Authorization: Bearer bapi_...` ou
> header `X-Bank-Credentials: <base64(JSON)>`.

---

## 📚 Carnê

### `POST /carne`
Registra N parcelas no provider e monta o carnê 3-vias A4 (PDF) no engine.
Corpo: `{tenant_id, provider, account_config, bank, parcelas: [Cobranca...],
credentials?}` → `{carne_pdf_base64, cobrancas: [...]}`.

---

## ⚡ Pix dinâmico (BACEN) — só providers REST

### `POST /pix` — cob imediata
```bash
curl -X POST http://localhost:8000/pix \
  -H 'Authorization: Bearer bapi_kJx...' \
  -H 'Content-Type: application/json' \
  -d '{
    "tenant_id": "empresa_123",
    "provider": "c6",
    "account_config": {"chave_pix": "financeiro@empresa.com"},
    "pix": {"valor": "97.50", "expiracao_segundos": 3600, "descricao": "Pedido 42"}
  }'
# 200 → {"txid": "9d36b84f...", "status": "registrado",
#        "pix_copia_cola": "00020126...", "location": "pix.example.com/qr/..."}
```

### `POST /pix` — cobv (com vencimento)
Inclua `data_vencimento`, `txid` (26–35 alfanuméricos) e `devedor` **com
endereço** (`logradouro/cidade/uf/cep` — exigência BACEN):

```json
"pix": {
  "valor": "150.00", "txid": "FATURA2026080100000000000001",
  "data_vencimento": "2026-08-31", "validade_apos_vencimento": 30,
  "devedor": {"nome": "José", "documento": "12345678901",
              "endereco": {"logradouro": "Rua X, 1", "cidade": "Recife",
                           "uf": "PE", "cep": "50000000"}}
}
```

### `GET /pix/{txid}?tenant_id=&provider=c6[&vencimento=true]`
Status: `ATIVA→registrado`, `CONCLUIDA→liquidado`, `REMOVIDA_*→baixado`.
`vencimento=true` consulta cobv.

### `PATCH /pix/{txid}?tenant_id=[&vencimento=true]`
Revisa a cobrança (BACEN): corpo com `valor`, `solicitacaoPagador`, `calendario`…

### `GET /pix?tenant_id=&inicio=&fim=[&vencimento=true]`
Lista cobranças do período (RFC3339: `2026-07-15T00:00:00Z`).

### Lote de cobv
`PUT /pix/lote/{id}` (corpo: `{descricao, cobrancas:[{txid, valor,
data_vencimento, devedor…}]}`) · `GET /pix/lote/{id}` · `GET /pix/lotes?inicio=&fim=`.

---

## 🧾⚡ Bolepix — boleto híbrido online (C6 v2)

### `POST /bolepix`
Emite boleto **com QR Pix EVP embutido**, direto no banco (idempotente por
`external_reference_id`, 26 chars A-Z0-9 — gerado se omitido):

```bash
curl -X POST http://localhost:8000/bolepix \
  -H 'Authorization: Bearer bapi_kJx...' -H 'Content-Type: application/json' \
  -d '{
    "tenant_id": "empresa_123", "provider": "c6",
    "account_config": {"chave_pix": "<chave EVP>", "billing_scheme": "21"},
    "bolepix": {
      "valor": "99.90", "vencimento": "2026-08-31", "descricao": "Pedido 42",
      "pagador": {"nome": "José", "documento": "12345678901",
                  "endereco": {"address": "Av. Nove de Julho, 100",
                               "neighborhood": "Centro", "city": "São Paulo",
                               "state": "SP", "zip_code": "01000000"}}
    }
  }'
# 201 → linha digitável + código de barras + pix_copia_cola (QR EVP)
```

### `GET /bolepix/{ext_ref}` · `GET /bolepix/{ext_ref}/pdf` · `DELETE /bolepix/{ext_ref}`
Consulta, PDF (base64) e cancelamento (**409** enquanto a CIP processa).

---

## 🏦 Extrato e configuração

### `GET /extrato?tenant_id=&start_date=&end_date=`
Movimentações da conta PJ no período.

### `POST /config/webhook-banco`
Registra no banco a URL que receberá notificações
(`{tenant_id, provider, url, service: BANK_SLIP|CHECKOUT}`); `GET`/`DELETE`
com `?service=` consultam/removem.

---

## 📊 Conciliação (C6 Pay)

### `GET /conciliacao/recebiveis` · `GET /conciliacao/transacoes`
Query: `tenant_id`, `start_date`, `end_date` (máx. 60 dias), `provider=c6`,
`page` (default 1), `size` (default 50, máx. 100).

```bash
curl "http://localhost:8000/conciliacao/recebiveis?tenant_id=empresa_123&start_date=2026-07-01&end_date=2026-07-31" \
  -H 'Authorization: Bearer bapi_kJx...'
# 200 → {"page": 1, "last_page": 3, "total_items": 120, "items": [{...}]}
```

---

## 🔔 Webhooks (entrada) e push de eventos (saída)

### `POST /webhooks/{banco}` · `POST /webhooks/{banco}/{tenant_id}`
URL que você cadastra **no banco**. Com `WEBHOOK_TOKEN__<BANCO>` configurado,
exige `?token=...` (ou header `x-webhook-token`) — divergiu, **401**.

O evento é normalizado (`WebhookEvent`) e **empurrado por POST assinado**
(`X-Signature: sha256=<hmac_sha256(secret, body)>`) ao consumidor dono do
tenant (`SUB__<tenant>__URL/SECRET`) ou ao destino global
(`EVENT_WEBHOOK_URL/SECRET`).

### `GET /health`
`{"status": "ok"}`.

---

## 🚀 Exemplos de utilização por banco

O fluxo é o MESMO para qualquer banco — muda apenas `provider`, as credenciais
e o `account_config`. Copie e ajuste.

### C6 Bank (336) — produção/sandbox mTLS

```bash
GW=http://localhost:8000

# 1. Cadastra credenciais UMA vez → token
TOKEN=$(curl -s -X POST $GW/credenciais -H 'Content-Type: application/json' -d '{
  "tenant_id": "empresa_123", "provider": "c6",
  "credentials": {"client_id": "<uuid do portal>", "client_secret": "<secret>",
                   "pfx_base64": "<base64 do .pfx>", "pfx_password": "<senha>"}
}' | jq -r .token)

# 2. Boleto registrado (carteira 21 sandbox / 15 produção)
curl -s -X POST $GW/cobranca -H "Authorization: Bearer $TOKEN" \
  -H 'Content-Type: application/json' -d '{
  "tenant_id": "empresa_123", "provider": "c6",
  "account_config": {"billing_scheme": "21"},
  "cobranca": {"valor": "1500.00", "vencimento": "2026-08-31", "seu_numero": "FAT001",
    "pagador": {"nome": "José da Silva", "documento": "12345678901",
      "endereco": {"street": "Av. Nove de Julho", "number": 123,
                   "city": "São Paulo", "state": "SP", "zip_code": "01000000"}}}}'

# 3. Bolepix (boleto + QR Pix EVP embutido) — exclusivo C6
curl -s -X POST $GW/bolepix -H "Authorization: Bearer $TOKEN" \
  -H 'Content-Type: application/json' -d '{
  "tenant_id": "empresa_123", "provider": "c6",
  "account_config": {"chave_pix": "<chave EVP>", "billing_scheme": "21"},
  "bolepix": {"valor": "99.90", "vencimento": "2026-08-31", "descricao": "Pedido 42",
    "pagador": {"nome": "José", "documento": "12345678901",
      "endereco": {"address": "Av. Nove de Julho, 100", "neighborhood": "Centro",
                   "city": "São Paulo", "state": "SP", "zip_code": "01000000"}}}}'

# 4. Pix imediato + conciliação de recebidos
curl -s -X POST $GW/pix -H "Authorization: Bearer $TOKEN" -H 'Content-Type: application/json' \
  -d '{"tenant_id": "empresa_123", "provider": "c6",
       "account_config": {"chave_pix": "<chave>"}, "pix": {"valor": "97.50"}}'
curl -s "$GW/pix/recebidos?tenant_id=empresa_123&provider=c6&inicio=2026-07-01T00:00:00Z&fim=2026-07-31T23:59:59Z" \
  -H "Authorization: Bearer $TOKEN"
```

### Sicoob (756) — sandbox com token estático (sem mTLS)

```bash
# 1. Credenciais do sandbox = client_id + access_token do portal (só isso!)
TOKEN=$(curl -s -X POST $GW/credenciais -H 'Content-Type: application/json' -d '{
  "tenant_id": "empresa_123", "provider": "sicoob",
  "credentials": {"client_id": "<client_id do portal>",
                   "access_token": "<token estático do portal>"}
}' | jq -r .token)
# produção: troque access_token por client_secret + pfx_base64/pfx_password
# e aponte SICOOB_BASE_URL para https://api.sicoob.com.br

# 2. Boleto v3 (numeroCliente/codigoModalidade da cooperativa)
curl -s -X POST $GW/cobranca -H "Authorization: Bearer $TOKEN" \
  -H 'Content-Type: application/json' -d '{
  "tenant_id": "empresa_123", "provider": "sicoob",
  "account_config": {"numeroCliente": 25546454, "codigoModalidade": 1},
  "cobranca": {"valor": "156.23", "vencimento": "2026-08-31", "seu_numero": "FAT001",
    "pagador": {"nome": "Marcelo dos Santos", "documento": "98765432185",
      "endereco": {"endereco": "Rua 87 Quadra 1", "bairro": "Setor Central",
                   "cidade": "Luziânia", "uf": "GO", "cep": "72360000"}}}}'
# resposta pode trazer pix_copia_cola (boleto híbrido, se a conta tem chave Pix)

# 3. Pix e conciliação — MESMAS chamadas do C6, só muda provider=sicoob
curl -s -X POST $GW/pix -H "Authorization: Bearer $TOKEN" -H 'Content-Type: application/json' \
  -d '{"tenant_id": "empresa_123", "provider": "sicoob",
       "account_config": {"chave_pix": "<chave>"}, "pix": {"valor": "10.00"}}'

# 4. Extrato conta-corrente (mensal no Sicoob)
curl -s "$GW/extrato?tenant_id=empresa_123&provider=sicoob&start_date=2026-07-01&end_date=2026-07-31" \
  -H "Authorization: Bearer $TOKEN"
```

### Pix Automático (débito recorrente) — idêntico nos dois bancos

```bash
# 1. Cria a recorrência (contrato de cobrança mensal)
curl -s -X POST $GW/pix-automatico/recorrencias -H "Authorization: Bearer $TOKEN" \
  -H 'Content-Type: application/json' -d '{
  "tenant_id": "empresa_123", "provider": "c6",
  "recorrencia": {"contrato": "CT-2026-001", "objeto": "Aluguel Apto 101",
    "devedor": {"nome": "José", "documento": "12345678901"},
    "periodicidade": "MENSAL", "data_inicial": "2026-08-01",
    "valor_fixo": "1500.00", "politica_retentativa": "PERMITE_3R_7D"}}'
# → idRec; o pagador autoriza pelo app (POST /solicitacoes) ou QR (POST /locations)

# 2. A cada ciclo, o SEU sistema agenda a parcela (>= 2 dias antes do vencimento)
curl -s -X PUT $GW/pix-automatico/cobrancas/TXID2026080100000000000001 \
  -H "Authorization: Bearer $TOKEN" -H 'Content-Type: application/json' -d '{
  "tenant_id": "empresa_123", "provider": "c6",
  "cobranca": {"id_rec": "<idRec>", "valor": "1500.00", "data_vencimento": "2026-08-05"}}'
# no vencimento o banco debita sozinho; o webhook avisa liquidação/falha
```

### Boleto offline (CNAB, 18 bancos) — sem credenciais de banco

```bash
# provider omitido/vazio → engine brcobrança (Ruby); bancos: GET /bancos
curl -s -X POST $GW/cobranca -H 'Content-Type: application/json' -d '{
  "tenant_id": "empresa_123",
  "account_config": {"bank": "itau", "agencia": "0810", "conta_corrente": "53678",
                      "carteira": "175", "convenio": "12345"},
  "cobranca": {"valor": "100.00", "vencimento": "2026-08-31", "nosso_numero": "123",
    "pagador": {"nome": "José", "documento": "12345678901"}}}'
```

## Fluxo típico de integração

```text
1. POST /credenciais            → guarda o bapi_ (por tenant+banco)
2. POST /cobranca | POST /pix   → emite (Bearer bapi_)
3. Banco notifica /webhooks/c6/{tenant} → push assinado ao seu sistema
4. GET /conciliacao/recebiveis  → bate o financeiro
5. DELETE /credenciais          → rotação/revogação quando precisar
```

Configuração completa (envs) no [README do gateway](../../boleto-api-python/README.md);
detalhes do C6 em [c6-rest.md](../development/c6-rest.md).
