# BRCobrança — Gem Utilizada

> **Versão atual usada pelo projeto:** `12.10.3` (master @ `e555745`)
> **Repositório:** [github.com/Maxwbh/brcobranca](https://github.com/Maxwbh/brcobranca)

Fork mantido por Maxwell da Silva Oliveira ([@maxwbh](https://github.com/maxwbh)) do projeto original [kivanio/brcobranca](https://github.com/kivanio/brcobranca), com melhorias específicas para uso em APIs REST e suporte ampliado a bancos brasileiros.

## Instalação (Gemfile)

```ruby
gem 'brcobranca', git: 'https://github.com/maxwbh/brcobranca.git'
```

## Histórico de Versões do Fork

| Versão | Data | Principais mudanças |
|--------|------|---------------------|
| **12.10.3** | 2026-06-17 | Corrige o template **PrawnCarne**: adiciona o `autoload` de `PrawnCarne`/`PrawnTema` em `lib/brcobranca.rb` e o método `PrawnTema.texto_logo_banco`, restaurando o carnê 3-vias A4 sem GhostScript (`template=carne`/`lote_carne`) |
| **12.10.2** | 2026-06-14 | `Brcobranca::Bancos` com registro/remoção de bancos em runtime (`registrar`, `classe_boleto/remessa/pix`); bancos customizados em `todos`/`find`/`as_json`. Fix menor de gemspec |
| **12.10.1** | 2026-06-12 | Template **PrawnCarne** (carnê 1 pág./3 vias A4), **PrawnTema** (logo/cor/rodapé), **marca d'água** antifraude e **fontes TTF** (UTF-8). Fixes de PIX/QR (sobreposição, nível M BACEN). Normalização de remessa também para BB CNAB 240/400 |
| **12.9.0** | 2026-06-12 | Remessa Sicoob CNAB400: setters normalizam `carteira` (`rjust 2`) e `convenio` (`rjust 9`), corrigindo as validações que falhavam quando o boleto gerava mas a remessa não |
| **12.8.0** | 2026-05-28 | Novos campos PIX no boleto: `chave_pix`, `tipo_chave_pix`, `txid`. `dados_pix` expandido com `qrcode_disponivel` |
| **12.7.1** | 2026-05-28 | Fix compatibilidade rghost 0.9.9 |
| **12.7.0** | 2026-04-08 / 2026-04-20 | Suporte completo a **Banco C6 (336)** CNAB 400 (remessa + retorno + boleto) + PIX para 6 bancos; módulo `Brcobranca::Bancos` (registro centralizado de capacidades), carteiras por banco, extras (Sicoob cart 9/layout 810) |
| **12.6.0** | 2026-01-03 | Métodos de validação seguros (`valido?`, `to_hash_seguro`) — Fase 2 |
| **12.5.0** | — | `Brcobranca::Retorno.parse` (factory com auto-detecção), `pagamento.to_hash` |
| **12.4.0** | — | `Brcobranca::Remessa.criar` (factory), `remessa.to_hash` |
| **12.3.0** | — | Validações seguras via ActiveModel, mensagens melhoradas |
| **12.2.0** | — | `to_hash`, `as_json`, `to_json`, `dados_entrada`, `dados_calculados`, `dados_pix` |
| **12.1.x** | — | Módulo de formatação de campos + docs Rails |
| **12.0.x** | 2025-11 | Reestruturação da documentação, suporte a Ruby 3.4 |

## Bancos Suportados (18)

| Código | Banco | Classe | Boleto | CNAB 400 | CNAB 240 | PIX |
|--------|-------|--------|:------:|:--------:|:--------:|:---:|
| 001 | Banco do Brasil | `BancoBrasil` | ✅ | ✅ | ✅ | ✅ |
| 004 | Banco do Nordeste | `BancoNordeste` | ✅ | ✅ | — | — |
| 021 | Banestes | `Banestes` | ✅ | — | — | — |
| 033 | Santander | `Santander` | ✅ | ✅ | ✅ | ✅ |
| 041 | Banrisul | `Banrisul` | ✅ | ✅ | — | — |
| 070 | Banco de Brasília | `BancoBrasilia` | ✅ | ✅ | — | — |
| 085 | Ailos | `Ailos` | ✅ | — | ✅ | — |
| 097 | Credisis | `Credisis` | ✅ | ✅ | — | — |
| 104 | Caixa | `Caixa` | ✅ | — | ✅ | ✅ |
| 136 | Unicred | `Unicred` | ✅ | ✅ | ✅ | — |
| 237 | Bradesco | `Bradesco` | ✅ | ✅ | — | ✅ |
| **336** | **Banco C6** | **`BancoC6`** | ✅ | ✅ | — | ✅ |
| 341 | Itaú | `Itau` | ✅ | ✅ | — | ✅ |
| 399 | HSBC | `Hsbc` | ✅ | — | — | — |
| 422 | Safra | `Safra` | ✅ | — | — | — |
| 745 | Citibank | `Citibank` | ✅ | ✅ | — | — |
| 748 | Sicredi | `Sicredi` | ✅ | — | ✅ | ✅ |
| 756 | Sicoob | `Sicoob` | ✅ | ✅ | ✅ | ✅ |

> Novidades v1.3.0 (boleto_cnab_api): adição de **Banco C6** em `SUPPORTED_BANKS` e `CNAB400_BANKS`.

## API Moderna da Gem (v12.5+)

### `boleto.to_hash`

Retorna hash completo com dados de entrada + calculados (ideal para responses de API):

```ruby
boleto = Brcobranca::Boleto::BancoBrasil.new(dados)
hash = boleto.to_hash
# => {
#   convenio: "...", moeda: "9", carteira: "18",
#   codigo_barras: "00191...", linha_digitavel: "00191.23456...",
#   nosso_numero_formatado: "00000123456-X", nosso_numero_dv: "X",
#   agencia_conta_boleto: "3073 / 12345678-0",
#   pix: nil | { emv: "...", qrcode_png: "<base64>" }
# }
```

### `boleto.dados_calculados`

Apenas os dados **derivados** (sem os campos de entrada):

```ruby
boleto.dados_calculados
# => { banco, banco_dv, agencia_dv, nosso_numero_dv,
#      codigo_barras, linha_digitavel, ... }
```

### `boleto.dados_entrada`

Apenas os dados **enviados** pelo cliente (sem derivados):

```ruby
boleto.dados_entrada
# => { agencia, conta_corrente, convenio, valor, ... }
```

### `boleto.dados_pix`

Dados do PIX híbrido (apenas em bancos com suporte):

```ruby
boleto.dados_pix
# => { emv: "00020126...", qrcode_base64: "..." }
```

### `boleto.valido?`

Validação que **retorna boolean** (não lança exceção) e popula `errors`:

```ruby
boleto.valido?  # => true | false
boleto.errors.messages  # => { nosso_numero: ["não pode estar em branco"] }
```

### `boleto.to_hash_seguro`

Hash com dados sensíveis mascarados (CPF/CNPJ parcial) — útil para logs:

```ruby
boleto.to_hash_seguro
# => { sacado_documento: "123***89-00", documento_cedente: "12***/0001-00", ... }
```

### Factories — `Brcobranca::Remessa.criar`

Cria remessa com detecção automática de banco/formato:

```ruby
remessa = Brcobranca::Remessa.criar(
  banco: 'banco_brasil',
  formato: 'cnab400',
  pagamentos: [pagamento1, pagamento2],
  agencia: '3073',
  convenio: '01234567',
  # ... demais campos
)
remessa.valid?         # => true | false
remessa.gera_arquivo   # => String binário CNAB
remessa.to_hash        # => Hash estruturado
```

### Factories — `Brcobranca::Retorno.parse`

Parseia retorno com auto-detecção de layout CNAB:

```ruby
pagamentos = Brcobranca::Retorno.parse(
  banco: 'banco_brasil',
  arquivo: file   # File, StringIO ou path
)
# => Array<Brcobranca::Retorno::RetornoXxx>
pagamentos.first.to_hash
# => { nosso_numero, codigo_ocorrencia, valor_pago, data_credito, ... }
```

## PIX Híbrido (v12.7.0+)

Bancos com suporte a PIX embutido no boleto via **PixMixin**:

- ✅ Banco do Brasil (001)
- ✅ Bradesco (237)
- ✅ Itaú (341)
- ✅ Sicoob (756)
- ✅ Caixa (104)
- ✅ Banco C6 (336)
- ✅ Santander (033) — suporte original
- ✅ Sicredi (748)

**Como usar:**

```ruby
boleto = Brcobranca::Boleto::Sicoob.new(dados.merge(
  emv: '00020126580014br.gov.bcb.pix...',  # payload EMV do PIX
  pix_label: 'Escaneie para pagar via PIX'
))

# O PDF gerado terá QR Code do PIX + linha digitável tradicional
pdf = boleto.to_pdf
```

A API também retorna o objeto `pix` em `/api/boleto/data` quando o boleto é híbrido.

## Template Alternativo: PrawnBolepix

A partir de v12.6+, existe alternativa ao Ghostscript (rghost) usando **Prawn**:

- Vantagens: Ruby puro, sem dependência de `gs` binário
- Requer gems: `prawn`, `rqrcode`, `chunky_png`
- Ideal para: containers minimalistas sem Ghostscript

Desde a v1.4.0 o `boleto_cnab_api` usa **Prawn por padrão** (`BOLETO_TEMPLATE=prawn` na imagem principal, sem GhostScript); a variante com rghost fica em `Dockerfile.rghost`. O template `carne` (3 vias A4) também é Prawn.

## Mapeamento de Campos

### Campos comuns a todos os bancos

| Campo na API | Campo na gem | Obrigatório |
|--------------|--------------|-------------|
| `agencia` | `agencia` | ✅ |
| `conta_corrente` | `conta_corrente` | ✅ |
| `nosso_numero` | `nosso_numero` | ✅ |
| `cedente` | `cedente` | ✅ |
| `documento_cedente` | `documento_cedente` | ✅ |
| `sacado` | `sacado` | ✅ |
| `sacado_documento` | `sacado_documento` | ✅ |
| `valor` | `valor` | ✅ |
| `data_vencimento` | `data_vencimento` | ✅ |
| `numero_documento` | `documento_numero` | ⚠️ **alias** |
| `convenio` | `convenio` | depende do banco |
| `carteira` | `carteira` | depende do banco |

> **Nota:** A API converte automaticamente `numero_documento` → `documento_numero` e filtra campos não suportados por banco (ex: `digito_conta` no Bradesco).

### Campos específicos por banco

#### Banco do Brasil (001)

```ruby
convenio       # obrigatório (4 a 8 dígitos)
carteira       # padrão: '18'
codigo_servico # opcional
```

Tamanho do `nosso_numero` conforme convênio:
- 4 dígitos → nosso_numero máx 7 dígitos
- 6 dígitos → nosso_numero máx 5 ou 17 dígitos
- 7 dígitos → nosso_numero máx 10 dígitos
- 8 dígitos → nosso_numero máx 9 dígitos

#### Sicoob (756)

```ruby
convenio    # obrigatório
carteira    # padrão: '1', também aceita '9' (contrato)
variacao    # obrigatório (2 dígitos, ex: '01')
modalidade  # padrão: '01'
```

**Restrições:**
- `aceite` deve ser `'N'`
- `especie_documento` deve ser enviado (padrão: `'DM'`)
- Novidade v12.7.0: **Carteira 9** com número de contrato
- Novidade v12.7.0: **Layout 810** onde o cliente calcula próprio DV

#### Banco C6 (336) — NOVO em v12.7.0

```ruby
convenio   # obrigatório
carteira   # valores válidos: '10' ou '20'
# digito_conta NÃO é aceito (filtrado automaticamente pela API)
```

**Observações:**
- CNAB 400 suportado (remessa + retorno)
- CNAB 240 ainda **não** disponível
- PIX híbrido suportado
- Registro online via API oficial do C6: **integrado no gateway Python** (`boleto-api-python`, provider `c6` — ver [c6-rest.md](./c6-rest.md)); aguarda homologação no portal C6 Developers (`C6_REGISTERED_READY`)

#### Caixa (104)

```ruby
convenio     # obrigatório
carteira     # valores válidos: '1' ou '2'
digito_conta # obrigatório
```

## Validações

### Formato de datas

A API aceita múltiplos formatos e converte para `Date`:

```
'YYYY/MM/DD'   → '2025/12/31'
'DD/MM/YYYY'   → '31/12/2025'
'YYYY-MM-DD'   → '2025-12-31'
Date object    → direto
```

### Campos numéricos

Aceitos como string ou número:

- `convenio`, `agencia`, `conta_corrente`, `nosso_numero`
- `valor` (float ou string com ponto decimal)

## Fluxo de Processamento

```
Cliente HTTP
  │ { "numero_documento": "...", "valor": 100.00, ... }
  ▼
BoletoApi::Endpoints
  │
  ▼
BoletoApi::Services::BoletoService.create(bank, values)
  │
  ├─► FieldMapper.map_boleto(values)
  │   • numero_documento → documento_numero
  │   • data_* (string) → Date
  │
  ├─► filter_supported_attributes(klass, mapped)
  │   • remove campos não aceitos pelo banco
  │   • (ex: digito_conta para Bradesco/C6)
  │
  ▼
Brcobranca::Boleto::Xxx.new(filtered_values)
  │
  ├─► boleto.valido?         # ActiveModel validation
  ├─► boleto.to_hash          # dados completos
  ├─► boleto.dados_calculados # código de barras, linha digitável
  └─► boleto.to_pdf / to_png / to_jpg / to_tif
```

## Erros Comuns

### `undefined method 'X=' for instance of Boleto::Y`

**Causa:** Campo não suportado por este banco.

**Solução (automática na API):** O `BoletoService.create` filtra campos não aceitos antes de passar para a gem. Se ainda acontecer, algum campo novo foi adicionado sem ser filtrado — reportar issue.

### `Carteira não é uma carteira válida. Utilize: X, Y`

**Causa:** Cada banco aceita só certos valores de carteira.

**Valores comuns:**
- Banco do Brasil: `'18'` (padrão)
- Sicoob: `'1'`, `'9'`
- Bradesco: `'09'`, `'28'`
- Itaú: `'109'`, `'175'`, `'180'`, `'174'`
- Caixa: `'1'`, `'2'` (não aceita `'SR'`)
- Banco C6: `'10'`, `'20'`

### `Nosso numero deve ter no máximo X dígitos`

**Causa:** Cada banco tem limite próprio, geralmente depende do convênio.

**Solução:** Consultar manual técnico do banco ou `docs/fields/all-banks.md`.

### `aceite` inválido para Sicoob

**Causa:** Sicoob exige `aceite='N'`. Enviar `'S'` dá erro de validação.

## Repositórios e Referências

- **Gem (fork):** https://github.com/Maxwbh/brcobranca
- **Gem (upstream):** https://github.com/kivanio/brcobranca
- **API (este projeto):** https://github.com/Maxwbh/boleto_cnab_api
- **Documentação de campos:** [docs/fields/README.md](../fields/README.md)
- **Compatibilidade por banco:** [docs/fields/all-banks.md](../fields/all-banks.md)

---

**Última atualização:** 2026-06-17
**Mantenedor:** Maxwell da Silva Oliveira ([@maxwbh](https://github.com/maxwbh)) — M&S do Brasil LTDA
