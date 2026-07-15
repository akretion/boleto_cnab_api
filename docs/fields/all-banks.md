# Todos os Bancos Suportados - Validação Completa

> Status de compatibilidade e particularidades de cada banco

## 📋 Bancos Testados e Validados

| Banco | Código | Status | Método Seguro | PDF | Remessa | Observações |
|-------|--------|--------|---------------|-----|---------|-------------|
| **Banco do Brasil** | 001 | ✅ | ✅ | ✅ | CNAB400 + CNAB240 | Todos os métodos disponíveis |
| **Sicoob** | 756 | ✅ | ✅ | ✅ | CNAB240 | `linha_digitavel` pode ser `null` via `/data`; `variacao` **não** vai na remessa |
| **Bradesco** | 237 | ✅ | ✅ | ✅ | CNAB400 | Requer `digito_conta` |
| **Itaú** | 341 | ✅ | ✅ | ✅ | CNAB400 | Suporta múltiplas carteiras |
| **Caixa Econômica** | 104 | ✅ | ✅ | ✅ | CNAB240 | Convenio obrigatório |
| **Santander** | 033 | ✅ | ✅ | ✅ | CNAB400 + CNAB240 | `nosso_numero` até 7 dígitos |
| **Banco C6** | 336 | ✅ | ✅ | ✅ | CNAB400 | Carteira `'10'` ou `'20'`; remessa exige `codigo_beneficiario` |

### Outros Bancos Suportados

| Banco | Código | Status |
|-------|--------|--------|
| Sicredi | 748 | ✅ |
| Banrisul | 041 | ✅ |
| Banestes | 021 | ✅ |
| BRB | 070 | ✅ |
| Unicred | 136 | ✅ |
| Ailos | 085 | ✅ |
| Credisis | 097 | ✅ |
| Safra | 422 | ✅ |
| Banco do Nordeste | 004 | ✅ |
| HSBC | 399 | ⚠️ (descontinuado) |
| Citibank | 745 | ⚠️ (descontinuado) |

---

## 🏦 Detalhes por Banco

### 1. Banco do Brasil (001)

**Status:** ✅ Totalmente suportado

**Campos Específicos:**
```json
{
  "convenio": "01234567",     // OBRIGATÓRIO (4-8 dígitos)
  "carteira": "18",           // Padrão: 18
  "nosso_numero": "123"       // Tamanho varia com convenio
}
```

**Particularidades:**
- ✅ `linha_digitavel` disponível
- ✅ `codigo_barras` disponível
- ✅ `nosso_numero_dv` disponível
- ✅ Todos os métodos funcionam

**Tamanho do nosso_numero:**
- Convênio 4 dígitos → max 7 dígitos
- Convênio 6 dígitos → max 5 ou 17 dígitos
- Convênio 7 dígitos → max 10 dígitos
- Convênio 8 dígitos → max 9 dígitos

---

### 2. Sicoob (756)

**Status:** ✅ Suportado com ressalvas

**Campos Específicos:**
```json
{
  "convenio": "229385",       // OBRIGATÓRIO
  "carteira": "1",            // Padrão: 1
  "variacao": "01",           // OBRIGATÓRIO
  "modalidade": "01",         // Padrão: 01
  "aceite": "N",              // DEVE ser 'N' (não 'S')
  "especie_documento": "DM"   // OBRIGATÓRIO
}
```

**Particularidades:**
- ⚠️ `linha_digitavel` pode retornar `null` via `/api/boleto/data`
- ✅ `codigo_barras` disponível sempre
- ✅ `nosso_numero_dv` disponível
- ✅ PDF funciona perfeitamente (linha digitável aparece no PDF)

**Importante:**
```javascript
// ❌ ERRADO para Sicoob
{ "aceite": "S" }

// ✅ CORRETO para Sicoob
{ "aceite": "N" }
```

---

### 3. Bradesco (237)

**Status:** ✅ Totalmente suportado

**Campos Específicos:**
```json
{
  "agencia": "1234",
  "conta_corrente": "567890",
  "digito_conta": "1",        // OBRIGATÓRIO para Bradesco
  "carteira": "09",           // 09, 02, 03, etc
  "nosso_numero": "12345"
}
```

**Particularidades:**
- ✅ Todos os métodos disponíveis
- ⚠️ Requer `digito_conta` explícito
- ✅ Suporta múltiplas carteiras (09, 02, 03, 06, 25)

---

### 4. Itaú (341)

**Status:** ✅ Totalmente suportado

**Campos Específicos:**
```json
{
  "agencia": "0810",
  "conta_corrente": "53678",
  "carteira": "175",          // 175, 174, 104, 109, etc
  "nosso_numero": "12345678"
}
```

**Particularidades:**
- ✅ Todos os métodos disponíveis
- ✅ Suporta diversas carteiras
- ✅ `nosso_numero` até 8 dígitos

**Carteiras suportadas:**
- 175 - Sem registro
- 174 - Sem registro
- 104, 109, 112 - Com registro

---

### 5. Caixa Econômica Federal (104)

**Status:** ✅ Totalmente suportado

**Campos Específicos:**
```json
{
  "agencia": "1825",
  "conta_corrente": "0000528",
  "digito_conta": "6",        // OBRIGATÓRIO
  "carteira": "1",            // '1' ou '2' (nao aceita 'SR', 'RG')
  "convenio": "245274",       // OBRIGATÓRIO
  "nosso_numero": "000000000000001"  // 15 dígitos
}
```

**Particularidades:**
- ✅ Todos os métodos disponíveis
- ⚠️ `nosso_numero` com 15 dígitos (preencher com zeros)
- ✅ Local de pagamento: "Preferencialmente nas casas lotéricas"

---

### 6. Santander (033)

**Status:** ✅ Totalmente suportado

**Campos Específicos:**
```json
{
  "agencia": "1234",
  "conta_corrente": "9876543",
  "digito_conta": "2",
  "carteira": "102",          // 101, 102, 201, etc
  "nosso_numero": "12345678901234567890"  // Até 7 dígitos
}
```

**Particularidades:**
- ✅ Todos os métodos disponíveis
- ✅ `nosso_numero` aceita até **7 dígitos**
- ✅ Múltiplas carteiras suportadas

---

### 7. Banco C6 (336) — desde v1.3.0

**Status:** ✅ Totalmente suportado (brcobranca v12.7.0+)

#### 7.1 Boleto (GET /api/boleto)

**Campos Específicos:**
```json
{
  "agencia": "0001",
  "conta_corrente": "1234567",
  "convenio": "100",
  "carteira": "10",           // APENAS '10' ou '20'
  "nosso_numero": "12345678"
}
```

**Particularidades:**
- ✅ Todos os métodos disponíveis (código de barras, linha digitável, nosso_numero formatado)
- ✅ PIX híbrido suportado (campo `emv` + `pix_label`)
- ✅ Templates suportados: `prawn`, `carne`
- ❌ CNAB 240 **NÃO** suportado
- ⚠️ Campo `digito_conta` é **filtrado automaticamente** pela API (gem não aceita)
- ⚠️ Carteira deve ser exatamente `'10'` ou `'20'` — outros valores retornam HTTP 400

**Exemplo completo de boleto:**
```python
dados_c6 = {
    "cedente": "Empresa C6 LTDA",
    "documento_cedente": "33445566000177",
    "sacado": "Pedro Almeida",
    "sacado_documento": "33344455566",
    "sacado_endereco": "Av. Faria Lima, 1500, Itaim Bibi, São Paulo, SP, CEP 04538133",
    "agencia": "0001",
    "conta_corrente": "1234567",
    "carteira": "10",
    "convenio": "100",
    "nosso_numero": "12345678",
    "numero_documento": "INV-2026-001",
    "valor": 2750.00,
    "data_vencimento": "2026/12/31",
    "aceite": "N"
}

requests.get(f"{API_URL}/api/boleto", params={
    "bank": "banco_c6", "type": "pdf", "data": json.dumps(dados_c6)
})
```

#### 7.2 Remessa CNAB 400 (POST /api/remessa)

> **Atenção:** O payload de remessa usa campos **diferentes** dos de boleto.

**Campos específicos da remessa C6:**
```json
{
  "empresa_mae": "Empresa C6 LTDA",
  "documento_cedente": "33445566000177",
  "agencia": "0001",
  "conta_corrente": "1234567",
  "digito_conta": "0",
  "carteira": "10",
  "codigo_beneficiario": "0012345678",   // ⚠️ OBRIGATÓRIO na remessa
  "pagamentos": [...]
}
```

- ✅ `codigo_beneficiario` — código do cedente fornecido pelo C6 (até 10 dígitos)
- ❌ `convenio` — **NÃO** deve ser enviado na remessa (campo não existe na classe de remessa)
- ❌ CNAB 240 — não suportado para C6

**Campos do pagamento (remessa C6):**
```json
{
  "nosso_numero": "12345678",
  "data_vencimento": "2026/12/31",
  "valor": 1500.00,
  "nome_sacado": "Joao da Silva",        // ⚠️ nome_sacado (não sacado)
  "documento_sacado": "12345678900",    // ⚠️ documento_sacado (não sacado_documento)
  "endereco_sacado": "Rua Teste, 100",
  "bairro_sacado": "Centro",
  "cep_sacado": "01000000",
  "cidade_sacado": "Sao Paulo",
  "uf_sacado": "SP"
}
```

---

## 🔧 Compatibilidade dos Métodos

### Métodos Garantidos (Todos os Bancos)

| Método | Disponibilidade | Observação |
|--------|-----------------|------------|
| `nosso_numero_formatado` | ✅ 100% | Valor impresso no boleto |
| `codigo_barras` | ✅ 100% | Sempre disponível |
| `valid?` | ✅ 100% | Validação sempre funciona |
| `to_pdf` | ✅ 100% | Geração de PDF sempre funciona |

### Métodos com Proteção (Podem ser null)

| Método | API Response | Proteção | Observação |
|--------|--------------|----------|------------|
| `linha_digitavel` | `respond_to?` | ✅ | Pode ser `null` no Sicoob via /data |
| `nosso_numero_dv` | `rescue nil` | ✅ | Geralmente disponível |
| `agencia_conta_boleto` | `rescue nil` | ✅ | Formatação de agência/conta |
| `codigo_barras_segunda_parte` | `rescue nil` | ✅ | Depende do banco |
| `valor_documento` | `rescue valor` | ✅ | Fallback para `valor` |

---

## 🧪 Testes Automatizados

### Executar Testes de Todos os Bancos

```bash
# Todos os testes (incluindo multi-bank)
bundle exec rspec

# Apenas testes de múltiplos bancos
bundle exec rspec spec/all_banks_spec.rb

# Com output detalhado
bundle exec rspec spec/all_banks_spec.rb --format documentation
```

### Cobertura dos Testes

Os testes validam:
- ✅ Validação de dados (`/api/boleto/validate`)
- ✅ Retorno de dados (`/api/boleto/data`)
- ✅ Geração de nosso_numero (`/api/boleto/nosso_numero`)
- ✅ Geração de PDF (`/api/boleto`)
- ✅ Mapeamento de campos (`numero_documento` ↔ `documento_numero`)
- ✅ Resiliência a erros (`NoMethodError` não deve ocorrer)

---

## ⚠️ Notas Importantes

### 1. linha_digitavel no Sicoob

O método `linha_digitavel` pode não estar disponível diretamente no Sicoob quando usando `/api/boleto/data`. Isso **NÃO é um bug**, mas uma limitação da implementação da gem.

**Soluções:**
- ✅ Usar `/api/boleto` (PDF) — linha digitável aparece no PDF
- ✅ Aceitar `null` no response de `/api/boleto/data`
- ✅ Usar `codigo_barras` que está sempre disponível

### 2. numero_documento vs documento_numero

A API faz **mapeamento automático**:
```javascript
// Cliente envia
{ "numero_documento": "NF-2025-001" }

// API converte para
{ "documento_numero": "NF-2025-001" }

// Gem recebe correto
boleto.documento_numero  // ✅
```

### 3. Campos de Boleto ≠ Campos de Remessa

> **Atenção:** Os campos do payload de **boleto** e de **remessa** são diferentes!

| Contexto | Campo do sacado | Campo do documento |
|----------|-----------------|--------------------|
| **Boleto** (`GET /api/boleto`) | `sacado` | `sacado_documento` |
| **Remessa** (`POST /api/remessa`) | `nome_sacado` | `documento_sacado` |

### 4. Campos Específicos por Banco — Remessa

| Banco | Formato | Campos obrigatórios extras | Campos que NÃO vão na remessa |
|-------|---------|---------------------------|-------------------------------|
| Banco do Brasil | CNAB400 + CNAB240 | `convenio`, `carteira`, `variacao_carteira` | — |
| Sicoob | CNAB240 | `convenio`, `carteira` | `variacao` |
| Bradesco | CNAB400 | `carteira`, `digito_conta` | — |
| Caixa | CNAB240 | `convenio`, `digito_conta` | — |
| Santander | CNAB400 + CNAB240 | `digito_conta` | — |
| **Banco C6** | **CNAB400** | `carteira`, `codigo_beneficiario` | `convenio` |

---

## 📊 Resumo de Compatibilidade

| Recurso | BB | Sicoob | Bradesco | Itaú | Caixa | Santander |
|---------|----|----|----------|------|-------|-----------|
| Validação | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| PDF | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| Dados completos | ✅ | ⚠️ | ✅ | ✅ | ✅ | ✅ |
| linha_digitavel | ✅ | ⚠️ | ✅ | ✅ | ✅ | ✅ |
| codigo_barras | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |

**Legenda:**
- ✅ = Totalmente suportado
- ⚠️ = Suportado com ressalvas (ver observações)

---

## 🔗 Referências

- [Documentação de Campos](./README.md)
- [Exemplos Práticos](../../examples/python/README.md)
- [Detalhes Técnicos](../development/brcobranca-fork.md)
- [Gem BRCobranca](https://github.com/Maxwbh/brcobranca)

---

**Última atualização:** 2026-06-28
**Testes:** ✅ Validado na prática com Docker local — boletos PDF e remessas CNAB gerados com sucesso
**API:** Compatível com tratamento seguro de métodos
