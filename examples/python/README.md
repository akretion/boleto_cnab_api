# Exemplos Python - Cliente Boleto CNAB

Exemplos práticos de uso do cliente Python para geração de boletos bancários.

## 📋 Pré-requisitos

### 1. Instalar o cliente Python

```bash
# Via pip (quando publicado)
pip install boleto-cnab-client

# Ou via repositório local
cd python-client
pip install -e .
```

### 2. Iniciar a API

```bash
# Usando Docker Compose (recomendado)
docker-compose up -d

# Ou usando Docker direto
docker build -t boleto-api .
docker run -p 9292:9292 boleto-api

# Ou localmente com Ruby
bundle install
bundle exec rackup -p 9292
```

### 3. Verificar se a API está rodando

```bash
curl http://localhost:9292/api/health
# Deve retornar: {"status":"OK","timestamp":"..."}
```

## 🚀 Exemplos Disponíveis

### 1. exemplo_basico.py

**Nível:** Iniciante

Demonstra o fluxo completo básico:
- Conexão com a API
- Health check
- Validação de dados
- Obtenção de dados do boleto
- Geração de PDF

**Como executar:**
```bash
python examples/python/exemplo_basico.py
```

**Saída esperada:**
```
✅ API Status: ok
🔍 Validando dados do boleto...
✅ Dados válidos!
📊 Obtendo dados do boleto...
✅ Nosso Número: 123
✅ Código de Barras: 00190000000000000000...
✅ Linha Digitável: 00190.00009 00000.000000...
📄 Gerando PDF do boleto...
✅ PDF salvo em: boleto_exemplo.pdf
🎉 Boleto gerado com sucesso!
```

**Arquivo gerado:** `boleto_exemplo.pdf`

---

### 2. exemplo_sicoob.py

**Nível:** Intermediário

Demonstra particularidades do Sicoob:
- Campos obrigatórios específicos (variacao, convenio)
- Campo aceite deve ser 'N'
- linha_digitavel pode retornar None via API (mas aparece no PDF)

**Como executar:**
```bash
python examples/python/exemplo_sicoob.py
```

**Pontos importantes:**
- ⚠️ Campo `variacao` é OBRIGATÓRIO
- ⚠️ Campo `convenio` é OBRIGATÓRIO
- ⚠️ Campo `aceite` DEVE ser 'N'
- ⚠️ `linha_digitavel` pode ser None via /data (mas está no PDF)

**Arquivo gerado:** `boleto_sicoob.pdf`

---

### 3. exemplo_multiplos_bancos.py

**Nível:** Intermediário

Demonstra geração de boletos para múltiplos bancos:
- Banco do Brasil (001)
- Sicoob (756)
- Bradesco (237)
- Itaú (341)
- Caixa (104)
- Santander (033)

**Como executar:**
```bash
python examples/python/exemplo_multiplos_bancos.py
```

**Saída esperada:**
```
🏦 Gerando boletos para múltiplos bancos
📄 Gerando boleto: BANCO_BRASIL
✅ PDF salvo: boleto_banco_brasil.pdf
📄 Gerando boleto: SICOOB
✅ PDF salvo: boleto_sicoob.pdf
...
🎉 Processamento concluído!
```

**Arquivos gerados:**
- `boleto_banco_brasil.pdf`
- `boleto_sicoob.pdf`
- `boleto_bradesco.pdf`
- `boleto_itau.pdf`
- `boleto_caixa.pdf`
- `boleto_santander.pdf`

---

### 4. exemplo_tratamento_erros.py

**Nível:** Avançado

Demonstra tratamento robusto de erros:
- Erros de validação (`BoletoValidationError`)
- Erros de conexão (`BoletoConnectionError`)
- Timeouts (`BoletoTimeoutError`)
- Retry automático
- Campos específicos por banco

**Como executar:**
```bash
python examples/python/exemplo_tratamento_erros.py
```

**Cenários cobertos:**
1. Dados inválidos (campos faltando)
2. API não disponível (conexão falha)
3. Retry automático (tentativas múltiplas)
4. Campos específicos do banco (ex: variacao no Sicoob)
5. Tratamento completo (todos os passos com error handling)

**Ideal para:**
- Ambientes de produção
- Integração com sistemas críticos
- Logging e monitoramento

---

## 🔧 Configurações Comuns

### Timeout e Retries

```python
from boleto_cnab_client import BoletoClient

# Configuração para produção
client = BoletoClient(
    base_url='https://sua-api.onrender.com',
    timeout=30,  # 30 segundos
    retries=5    # 5 tentativas com backoff exponencial
)
```

### Logging Detalhado

```python
import logging

# Ver todas as requisições HTTP
logging.basicConfig(level=logging.DEBUG)

# Ou apenas INFO
logging.basicConfig(level=logging.INFO)
```

### URL da API

```python
# Desenvolvimento local
client = BoletoClient('http://localhost:9292')

# Produção (Render)
client = BoletoClient('https://boleto-cnab-api.onrender.com')

# Staging
client = BoletoClient('https://boleto-api-staging.onrender.com')
```

## 📚 Dados de Teste por Banco

### Banco do Brasil (001)

```python
{
    "agencia": "3073",
    "conta_corrente": "12345678",
    "convenio": "01234567",  # OBRIGATÓRIO (4-8 dígitos)
    "carteira": "18",
    "nosso_numero": "123"
}
```

### Sicoob (756)

```python
{
    "agencia": "4327",
    "conta_corrente": "417270",
    "carteira": "1",
    "variacao": "01",  # OBRIGATÓRIO
    "convenio": "229385",  # OBRIGATÓRIO
    "aceite": "N",  # DEVE ser 'N'
    "nosso_numero": "7890"
}
```

### Bradesco (237)

```python
{
    "agencia": "1234",
    "conta_corrente": "123456",
    "digito_conta": "7",  # OBRIGATÓRIO
    "carteira": "09",
    "nosso_numero": "12345"
}
```

### Itaú (341)

```python
{
    "agencia": "0057",
    "conta_corrente": "12345",
    "digito_conta": "6",
    "carteira": "175",
    "nosso_numero": "12345678"
}
```

### Caixa (104)

```python
{
    "agencia": "1565",
    "conta_corrente": "123456789",
    "digito_conta": "1",      # OBRIGATÓRIO
    "convenio": "654321",     # OBRIGATÓRIO
    "carteira": "1",          # '1' ou '2' (não aceita 'RG', 'SR', etc)
    "nosso_numero": "500000000000000"  # 15 dígitos
}
```

### Santander (033)

```python
{
    "agencia": "0001",
    "conta_corrente": "1234567",
    "digito_conta": "8",
    "carteira": "102",
    "convenio": "1234567",    # OBRIGATÓRIO
    "nosso_numero": "12345678"
}
```

### Banco C6 (336) — novo em v1.3.0

```python
{
    "agencia": "0001",
    "conta_corrente": "1234567",
    "carteira": "10",         # APENAS '10' ou '20'
    "convenio": "100",        # OBRIGATÓRIO
    "nosso_numero": "12345678"
    # NÃO envie digito_conta (a API filtra automaticamente)
}
```

## ⚠️ Problemas Comuns

### 1. Erro: "API não disponível"

**Causa:** API não está rodando

**Solução:**
```bash
docker-compose up -d
# ou
bundle exec rackup -p 9292
```

### 2. Erro: "Dados inválidos"

**Causa:** Campos obrigatórios faltando

**Solução:** Consulte a documentação do banco específico em `docs/fields/`

### 3. Erro: "linha_digitavel is None" (Sicoob)

**Causa:** Comportamento esperado do Sicoob via endpoint /data

**Solução:** A linha digitável sempre aparece no PDF gerado. Use `generate_boleto()` para obter o PDF completo.

### 4. Erro: "numero_documento not found"

**Causa:** A API usa `documento_numero` internamente

**Solução:** Use `numero_documento` no cliente - a conversão é automática:
```python
dados = {
    "numero_documento": "NF-001",  # ✅ Funciona!
    # A API converte automaticamente para documento_numero
}
```

### 5. Erro: "Connection timeout"

**Causa:** API lenta ou timeout muito curto

**Solução:**
```python
client = BoletoClient(
    'http://localhost:9292',
    timeout=60,  # Aumentar timeout
    retries=5    # Mais tentativas
)
```

## 📖 Próximos Passos

1. **Leia a documentação completa:**
   - [Documentação da API](../../docs/api/)
   - [Documentação de Campos](../../docs/fields/)
   - [README do Cliente Python](../../python-client/README.md)

2. **Execute os exemplos:**
   ```bash
   python examples/python/exemplo_basico.py
   python examples/python/exemplo_sicoob.py
   python examples/python/exemplo_multiplos_bancos.py
   python examples/python/exemplo_tratamento_erros.py
   ```

3. **Adapte para seu uso:**
   - Substitua dados de teste por dados reais
   - Ajuste configurações de timeout/retry
   - Adicione logging customizado
   - Integre com seu sistema

## 🤝 Contribuindo

Quer adicionar um exemplo? Por favor:

1. Crie um arquivo `exemplo_seu_caso.py`
2. Adicione comentários explicativos
3. Documente neste README
4. Teste antes de commitar
5. Abra um Pull Request

## 📝 Licença

MIT License - veja [LICENSE](../../LICENSE)

---

**Última atualização:** 2026-06-17
**Versão:** 1.5.0
