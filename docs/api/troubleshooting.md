# Troubleshooting — Boleto CNAB API

> **Versão:** 1.5.0

Este guia ajuda a resolver problemas comuns ao usar a API.

## Índice

- [Logging](#logging)
- [Deploy no Render.com](#deploy-no-rendercom)
- [Erros Comuns — Boletos](#erros-comuns--boletos)
- [Erros Comuns — Remessa CNAB](#erros-comuns--remessa-cnab)
- [Erros Comuns — Retorno CNAB](#erros-comuns--retorno-cnab)
- [Erros Comuns — OFX](#erros-comuns--ofx)
- [Checklist de Debug](#checklist-de-debug)

## Logging

A API produz logs estruturados em JSON via `RequestLogger` middleware:

```json
{"event":"request_start","method":"POST","path":"/api/ofx/parse","timestamp":"2026-04-09T12:00:00.000+0000"}
{"event":"request_end","method":"POST","path":"/api/ofx/parse","status":201,"duration_ms":4.69,"timestamp":"..."}
```

Erros são logados via `ErrorHandler`:

```
2026-04-09T12:00:00.000+0000 [ERROR] [400] ValidationError: Parâmetro inválido - file is missing
```

## Deploy no Render.com

### Logs não aparecem no dashboard do Render

**Causa:** Em ambientes containerizados, o Ruby bufferiza `stdout/stderr` em blocos. Os logs só aparecem quando o buffer enche, o que pode demorar muito ou nunca acontecer em baixo volume.

**Solução (já aplicada a partir da v1.3.0):** O projeto força `$stdout.sync = true` e `$stderr.sync = true` em 3 pontos:
- `config.ru` (entry point do Rack)
- `config/puma.rb` (antes do Puma bootar)
- `lib/boleto_api.rb` (quando a aplicação é carregada)

Além disso, `log_requests true` está habilitado no Puma para logar cada request automaticamente.

**Verificação local:**
```ruby
require 'boleto_api'
BoletoApi.logger.info 'teste'
puts $stdout.sync  # deve imprimir 'true'
```

**Se ainda assim não aparecer:**
1. Verifique que está usando a v1.3.0+ (`cat VERSION`)
2. Force um rebuild da imagem no Render (Manual Deploy → Clear build cache & deploy)
3. No dashboard do Render, clique em "Logs" e role para cima (Render mostra últimas 1000 linhas)

### HTTP 429 — Too Many Requests (cold start)

**Causa:** Isto **não é rate limiting da API** — a API Grape não possui rate limiting. O 429 vem do próprio **Render.com free tier**:

1. **Cold start (sleep mode):** Após 15 minutos de inatividade, o Render suspende o serviço. A primeira request pode demorar 30-60s para acordar.
2. **Durante o wake up, requests subsequentes podem receber 429 ou 503** enquanto o serviço se inicializa.
3. Se o cliente envia múltiplas requests em paralelo ou em sequência rápida, as primeiras acordam o serviço e as seguintes podem receber 429 enquanto o wake está em progresso.

**Exemplo no log do cliente:**
```
ERROR ... Erro BRCobranca: 429 - Too Many Requests
ERROR ... Erro BRCobranca: 429 - Too Many Requests  (480ms depois)
```

**Soluções:**

| Opção | Custo | Descrição |
|-------|-------|-----------|
| **1. Retry com backoff no cliente** | Grátis | Implementar retry exponencial (1s, 2s, 4s, 8s) até 4 tentativas |
| **2. Ping service (manter acordado)** | Grátis | Usar [cron-job.org](https://cron-job.org) ou [UptimeRobot](https://uptimerobot.com) para pingar `/api/health` a cada **10 minutos** (14 min fica no limite do sleep de 15 min). Há também o workflow `.github/workflows/keepalive.yml` |
| **3. Upgrade para Starter ($7/mês)** | Pago | Elimina sleep mode e aumenta RAM para 2GB |

**Exemplo de retry em Python (no cliente):**

```python
import time
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

session = requests.Session()
retry = Retry(
    total=4,
    backoff_factor=1,           # 1s, 2s, 4s, 8s
    status_forcelist=[429, 500, 502, 503, 504],
    allowed_methods=['GET', 'POST']
)
session.mount('https://', HTTPAdapter(max_retries=retry))

# Primeira chamada acorda o servidor
response = session.get('https://boleto-cnab-api.onrender.com/api/health', timeout=60)
```

**Exemplo de ping service (cron-job.org):**
- URL: `https://seu-service.onrender.com/api/health`
- Intervalo: a cada 10 minutos
- Método: GET
- Timeout: 30s

## Erros Comuns — Boletos

### 1. `type is missing`

**Causa:** Endpoint `/api/boleto` (GET) requer 3 parâmetros obrigatórios:
- `bank` — Nome do banco (`banco_brasil`, `sicoob`, etc)
- `type` — Formato de saída (`pdf`, `jpg`, `png`, `tif`)
- `data` — JSON com os dados do boleto

**Response (400):**
```json
{"error": "Parâmetro inválido", "details": "type is missing", "type": "ValidationError"}
```

**Solução:**
```python
response = requests.get(
    f"{API_URL}/api/boleto",
    params={
        "bank": "sicoob",
        "type": "pdf",
        "data": json.dumps(boleto_data)
    }
)
```

### 2. JSON inválido

**Response (400):**
```json
{"error": "JSON inválido", "details": "unexpected token at '{'", "type": "JSON::ParserError"}
```

**Solução:** Use aspas duplas no JSON. Em Python, use `json.dumps()`.

### 3. Campos obrigatórios ausentes

**Response (400):**
```json
{
  "error": "Dados do boleto inválidos",
  "validation_errors": {
    "nosso_numero": ["não pode ficar em branco"],
    "agencia": ["não é um número"]
  },
  "hint": "Verifique se todos os campos obrigatórios estão preenchidos"
}
```

**Solução:** Use `/api/boleto/validate` antes de gerar o PDF. Veja [fields/all-banks.md](../fields/all-banks.md) para campos obrigatórios por banco.

### 4. `numero_documento` vs `documento_numero`

- **`nosso_numero`** — Obrigatório, faz parte do código de barras
- **`numero_documento`** — Nome usado pela API (controle interno da empresa)
- **`documento_numero`** — Nome interno da gem BRCobranca (**não usar** diretamente na API)

A API converte `numero_documento` → `documento_numero` automaticamente.

```python
# ✅ Correto
boleto_data = {
    "numero_documento": "NF-12345",
    "nosso_numero": "1234567",
}
```

### 5. Linha digitável vazia

**Causa:** Falta `nosso_numero` ou outros campos obrigatórios.

**Debug:**
```python
# Validar antes de gerar
validate = requests.get(
    f"{API_URL}/api/boleto/validate",
    params={"bank": "sicoob", "data": json.dumps(boleto_data)}
)
print(validate.json())
```

### 6. `aceite` / `especie_documento` em branco

**Comportamento:** campos com valor padrão (`aceite`, `especie_documento`,
`especie`, `moeda`, `local_pagamento`) enviados **em branco** (`""`) caem
automaticamente no default do brcobrança (`aceite='S'`, `especie_documento='DM'`,
`especie='R$'`, `moeda='9'`). Não é mais necessário omitir o campo — vazio e
ausente têm o mesmo efeito. Para usar outro valor, basta enviá-lo preenchido.

## Erros Comuns — Remessa CNAB

### 1. `wrong number of arguments`

**Causa (corrigido em v1.3.0):** Passagem incorreta de keyword arguments para `Brcobranca::Remessa.criar`. Se você ver esse erro em uma versão antiga, atualize para v1.3.0+.

### 2. Formato CNAB incorreto

**Response (400):**
```json
{"error": "Erro ao gerar remessa", "validation_errors": ["Formato '240' não suportado. Use: cnab240, cnab400"]}
```

**Solução:** Use `cnab240` ou `cnab400` (não apenas `240` ou `400`) no parâmetro `type`.

### 3. Pagamentos devem ser objetos

**Causa:** Envio de array vazio ou com formato incorreto.

**Solução:** Cada pagamento no array deve conter:
```json
{
  "nosso_numero": "123456789",
  "data_vencimento": "2025/12/31",
  "valor": 1500.00,
  "sacado": "João da Silva",
  "sacado_documento": "12345678900"
}
```

### 4. Campos obrigatórios no cabeçalho da remessa

Alguns bancos exigem campos específicos:

| Banco | Campo obrigatório |
|-------|-------------------|
| Sicoob (CNAB 240) | `convenio`, `modalidade` (o `variacao` é do boleto e é ignorado na remessa) |
| Banco do Brasil | `convenio` (4-7 dígitos) |
| Itaú | `carteira` |

Consulte [fields/all-banks.md](../fields/all-banks.md).

### 5. Remessa PIX — banco não suportado

**Response (400):**
```json
{"error": "Parâmetro inválido", "details": "Remessa PIX não disponível para banco 'banrisul' com formato 'cnab400'."}
```

**Solução:** Verifique a tabela de suporte PIX em [api/pix.md](./pix.md). Nem todo banco suporta PIX em todos os formatos CNAB.

### 6. Sicoob Layout 810

Para usar o layout alternativo onde o cliente calcula o DV, envie no payload da remessa Sicoob CNAB240:

```json
{"versao_layout_arquivo_opcao": "810", ...}
```

O valor padrão é `"081"`. O campo passa direto para a gem sem necessidade de configuração adicional na API.

### 7. Campos não suportados pela classe de remessa são ignorados

**Comportamento:** um campo que existe no **boleto** mas **não** na classe de
remessa do banco é **ignorado** (não gera erro). Exemplo: `variacao` é usado no
boleto Sicoob, mas não existe na remessa **CNAB 240** do Sicoob — enviar `variacao`
no payload CNAB 240 não quebra a geração. O mesmo vale para campos extras dentro
de cada `pagamento` (ex.: `cedente` vazado do nível de remessa): são descartados
em vez de causar `500`. Campos **obrigatórios** ausentes continuam retornando erro
de validação normalmente.

## Erros Comuns — Retorno CNAB

### 1. Banco ou tipo não encontrado

**Response (400):**
```json
{"error": "Banco ou tipo não encontrado", "details": "Classe de retorno não encontrada para banco 'xyz' e tipo 'cnab400'"}
```

**Solução:** Verifique se o banco suporta o tipo CNAB em [fields/all-banks.md](../fields/all-banks.md).

### 2. Arquivo vazio ou corrompido

**Debug:** Verifique tamanho do arquivo e primeiras linhas:
```bash
wc -l retorno.ret
head -3 retorno.ret
```

Arquivos CNAB 400 têm linhas de 400 caracteres; CNAB 240 tem 240 caracteres.

## Erros Comuns — OFX

### 1. Arquivo OFX inválido

**Response (400):**
```json
{"erro": "Arquivo OFX inválido ou não reconhecido: <detalhes>"}
```

**Causa:** Arquivo não é um OFX válido ou está corrompido.

**Solução:**
- Confirme que é um arquivo `.ofx` (não `.ret` que é CNAB de retorno)
- Abra em um editor e verifique se começa com `OFXHEADER:` (v1) ou `<?xml` (v2)
- Tente abrir em um visualizador OFX (Money, GnuCash, etc)

### 2. `file is missing`

**Response (400):**
```json
{"error": "Parâmetro inválido", "details": "file is missing", "type": "ValidationError"}
```

**Causa:** Campo `file` não enviado ou nome errado.

**Solução:**
```bash
# ✅ Correto
curl -X POST http://localhost:9292/api/ofx/parse -F "file=@extrato.ofx"

# ❌ Errado (campo errado)
curl -X POST http://localhost:9292/api/ofx/parse -F "data=@extrato.ofx"
```

### 3. `nosso_numero_extraido` sempre null

**Causa:** Banco não reconhecido ou memo sem sequência numérica adequada.

**Debug:**
```python
response = requests.post(
    f"{API_URL}/api/ofx/parse",
    files={'file': open('extrato.ofx', 'rb')}
)
data = response.json()

# Confirme que o banco foi reconhecido
print(f"Banco: {data['banco']}")  # {'org': 'SICOOB', 'fid': '756'}

# Veja os memos
for tx in data['transacoes']:
    print(f"memo: '{tx['memo']}' → {tx['nosso_numero_extraido']}")
```

Veja [ofx-parsing.md](./ofx-parsing.md) para os padrões regex de cada banco.

### 4. Caracteres com encoding errado (`�`, `?`)

**Causa:** Arquivo original tem encoding diferente de Latin-1 ou UTF-8.

O service tenta automaticamente:
1. UTF-8 (se válido)
2. Latin-1 → UTF-8 (padrão de bancos brasileiros)
3. ASCII-8BIT com replace (fallback)

Se ainda assim houver problemas, reporte um issue com arquivo de exemplo.

## Checklist de Debug

### Boleto não gera

1. [ ] Todos os 3 parâmetros (`bank`, `type`, `data`) estão sendo enviados?
2. [ ] JSON é válido (use `json.dumps()`)?
3. [ ] Usou `/api/boleto/validate` primeiro?
4. [ ] Campo `nosso_numero` está presente?
5. [ ] `data_vencimento` está no formato `YYYY/MM/DD`?
6. [ ] Consultou os campos obrigatórios em [fields/all-banks.md](../fields/all-banks.md)?

### Remessa não gera

1. [ ] `type` é `cnab240` ou `cnab400` (não apenas números)?
2. [ ] Array `pagamentos` tem pelo menos 1 item?
3. [ ] Cada pagamento tem `nosso_numero`, `data_vencimento`, `valor`, `sacado`, `sacado_documento`?
4. [ ] Banco suporta o tipo CNAB? (Bradesco não suporta CNAB240)

### OFX não parseia

1. [ ] Arquivo é `.ofx` válido (v1 SGML ou v2 XML)?
2. [ ] Enviou via `multipart/form-data` com campo `file`?
3. [ ] Verificou que o banco foi reconhecido (`banco.org` no response)?
4. [ ] Confirmou encoding do arquivo?

## Suporte

- **Documentação:** [docs/README.md](../README.md)
- **Campos por banco:** [docs/fields/all-banks.md](../fields/all-banks.md)
- **OpenAPI Spec:** [docs/openapi.yaml](../openapi.yaml)
- **Issues:** https://github.com/Maxwbh/boleto_cnab_api/issues

---

**Mantido por:** Maxwell da Silva Oliveira ([@maxwbh](https://github.com/maxwbh)) - M&S do Brasil LTDA
