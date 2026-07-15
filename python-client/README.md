# Boleto CNAB Client - Python

>  **Versão:** 1.4.1 (cliente pip) | **API:** 1.5.0 | **Python:** 3.8+

Cliente Python oficial para a API de geração de Boletos Bancários Brasileiros.

[![Python Version](https://img.shields.io/badge/python-3.8%2B-blue)](https://www.python.org/downloads/)
[![License](https://img.shields.io/badge/license-MIT-green)](../LICENSE)
[![Version](https://img.shields.io/badge/version-1.4.1-green)](./boleto_cnab_client/__init__.py)

## 📋 Características

- ✅ Interface Pythonic simples e intuitiva
- ✅ Suporte para 18 bancos brasileiros
- ✅ Retry automático com backoff exponencial
- ✅ **TypedDict** para tipagem estática
- ✅ Type hints completos
- ✅ Tratamento de erros robusto
- ✅ Validação de dados antes da geração
- ✅ Geração de PDF e imagens
- ✅ Logging configurável
- ✅ Sessão HTTP reutilizável
- ✅ Testes pytest completos (44 testes)

## 🏦 Bancos Suportados

| Banco | Código | Status |
|-------|--------|--------|
| Banco do Brasil | 001 | ✅ |
| Sicoob | 756 | ✅ |
| Bradesco | 237 | ✅ |
| Itaú | 341 | ✅ |
| Caixa Econômica | 104 | ✅ |
| Santander | 033 | ✅ |
| Sicredi | 748 | ✅ |
| Banrisul | 041 | ✅ |
| **Banco C6** | **336** | ✅ (novo em v1.3.0) |
| + 9 outros | — | ✅ |

Veja [docs/fields/all-banks.md](../docs/fields/all-banks.md) para lista completa.

## 📦 Instalação

### Via pip (recomendado)

```bash
pip install boleto-cnab-client
```

### Via repositório

```bash
git clone https://github.com/Maxwbh/boleto_cnab_api.git
cd boleto_cnab_api/python-client
pip install -e .
```

### Para desenvolvimento

```bash
pip install -e ".[dev]"
```

## 🚀 Início Rápido

### 1. Importar o cliente

```python
from boleto_cnab_client import BoletoClient

# Conectar à API local
client = BoletoClient('http://localhost:9292')

# Ou conectar à API em produção
client = BoletoClient('https://sua-api.onrender.com')
```

### 2. Validar dados do boleto

```python
# Dados do boleto
dados = {
    "cedente": "Minha Empresa LTDA",
    "documento_cedente": "12345678000100",
    "sacado": "João da Silva",
    "sacado_documento": "12345678900",
    "agencia": "3073",
    "conta_corrente": "12345678",
    "convenio": "01234567",
    "carteira": "18",
    "nosso_numero": "123",
    "valor": 150.00,
    "data_vencimento": "2025/12/31"
}

# Validar antes de gerar
try:
    resultado = client.validate('banco_brasil', dados)
    if resultado['valid']:
        print("✅ Dados válidos!")
    else:
        print(f"❌ Erros: {resultado['errors']}")
except Exception as e:
    print(f"Erro: {e}")
```

### 3. Obter dados completos do boleto

```python
# Obter código de barras, linha digitável, etc.
response = client.get_boleto_data('banco_brasil', dados)

print(f"Nosso Número: {response.nosso_numero}")
print(f"Código de Barras: {response.codigo_barras}")
print(f"Linha Digitável: {response.linha_digitavel}")
```

### 4. Gerar PDF do boleto

```python
# Gerar PDF
pdf_bytes = client.generate_boleto('banco_brasil', dados, file_type='pdf')

# Salvar em arquivo
with open('boleto.pdf', 'wb') as f:
    f.write(pdf_bytes)

print("✅ PDF gerado com sucesso!")
```

## 📖 Exemplos Completos

### Exemplo 1: Banco do Brasil

```python
from boleto_cnab_client import BoletoClient, BoletoValidationError

client = BoletoClient('http://localhost:9292')

dados_bb = {
    "cedente": "Empresa Teste LTDA",
    "documento_cedente": "12345678000100",
    "sacado": "João da Silva",
    "sacado_documento": "12345678900",
    "sacado_endereco": "Rua Teste, 100, Centro, São Paulo, SP, CEP 01000000",
    "agencia": "3073",
    "conta_corrente": "12345678",
    "convenio": "01234567",  # OBRIGATÓRIO para BB
    "carteira": "18",
    "nosso_numero": "123",
    "numero_documento": "CTR-2025-001",
    "valor": 1500.00,
    "data_vencimento": "2025/12/31",
    "data_documento": "2025/11/27",
    "especie_documento": "DM",
    "aceite": "N",
    "local_pagamento": "Pagavel em qualquer banco ate o vencimento",
    "instrucao1": "Não receber após o vencimento"
}

try:
    # 1. Validar
    validation = client.validate('banco_brasil', dados_bb)
    print(f"Validação: {validation['valid']}")

    # 2. Obter dados
    boleto = client.get_boleto_data('banco_brasil', dados_bb)
    print(f"Código de Barras: {boleto.codigo_barras}")
    print(f"Linha Digitável: {boleto.linha_digitavel}")

    # 3. Gerar PDF
    pdf = client.generate_boleto('banco_brasil', dados_bb)
    with open('boleto_bb.pdf', 'wb') as f:
        f.write(pdf)

    print("✅ Sucesso!")

except BoletoValidationError as e:
    print(f"❌ Erro de validação: {e}")
except Exception as e:
    print(f"❌ Erro: {e}")
```

### Exemplo 2: Sicoob

```python
dados_sicoob = {
    "cedente": "Cooperativa Teste",
    "documento_cedente": "98765432000100",
    "sacado": "Maria Santos",
    "sacado_documento": "98765432100",
    "sacado_endereco": "Av. Principal, 50, Bairro, Rio de Janeiro, RJ, CEP 20000000",
    "agencia": "4327",
    "conta_corrente": "417270",
    "carteira": "1",
    "variacao": "01",  # OBRIGATÓRIO para Sicoob
    "convenio": "229385",  # OBRIGATÓRIO para Sicoob
    "nosso_numero": "7890",
    "numero_documento": "NF-2025-1234",
    "valor": 2500.00,
    "data_vencimento": "2025/12/31",
    "data_documento": "2025/11/27",
    "especie_documento": "DM",
    "aceite": "N",  # DEVE ser 'N' para Sicoob
    "local_pagamento": "Pagavel em qualquer banco ate o vencimento",
    "instrucao1": "Não receber após 30 dias"
}

# Gerar PDF
pdf = client.generate_boleto('sicoob', dados_sicoob)
with open('boleto_sicoob.pdf', 'wb') as f:
    f.write(pdf)

print("✅ Boleto Sicoob gerado!")
```

### Exemplo 3: Tratamento de Erros

```python
from boleto_cnab_client import (
    BoletoClient,
    BoletoValidationError,
    BoletoConnectionError,
    BoletoTimeoutError
)

client = BoletoClient('http://localhost:9292', timeout=10, retries=3)

try:
    boleto = client.get_boleto_data('banco_brasil', dados)

except BoletoValidationError as e:
    print(f"Dados inválidos: {e}")
    print(f"Detalhes: {e.details}")

except BoletoConnectionError as e:
    print(f"Erro de conexão: {e}")

except BoletoTimeoutError as e:
    print(f"Timeout: {e}")

except Exception as e:
    print(f"Erro inesperado: {e}")
```

### Exemplo 4: Usando Modelos de Dados

```python
from boleto_cnab_client import BoletoClient
from boleto_cnab_client.models import BoletoData

# Criar objeto BoletoData
boleto_data = BoletoData(
    cedente="Minha Empresa",
    documento_cedente="12345678000100",
    sacado="João da Silva",
    sacado_documento="12345678900",
    agencia="3073",
    conta_corrente="12345678",
    convenio="01234567",
    carteira="18",
    nosso_numero="123",
    valor=150.00,
    data_vencimento="2025/12/31"
)

# Converter para dicionário
dados_dict = boleto_data.to_dict()

client = BoletoClient('http://localhost:9292')
pdf = client.generate_boleto('banco_brasil', dados_dict)
```

### Exemplo 5: Health Check

```python
client = BoletoClient('http://localhost:9292')

try:
    status = client.health_check()
    print(f"Status: {status['status']}")
    print(f"Mensagem: {status['message']}")
except Exception as e:
    print(f"API não está disponível: {e}")
```

## 🔧 Configuração Avançada

### Timeout e Retries

```python
# Configurar timeout e número de retries
client = BoletoClient(
    base_url='http://localhost:9292',
    timeout=30,  # 30 segundos
    retries=5    # 5 tentativas
)
```

### Logging

```python
import logging

# Configurar logging
logging.basicConfig(level=logging.DEBUG)

client = BoletoClient('http://localhost:9292')
# Agora você verá logs detalhados das requisições
```

### Sessão HTTP Customizada

```python
import requests
from boleto_cnab_client import BoletoClient

# Criar sessão customizada
session = requests.Session()
session.headers.update({'User-Agent': 'MeuApp/1.0'})

client = BoletoClient('http://localhost:9292')
client.session = session
```

## 📚 Documentação de Campos

### Campos Obrigatórios (Todos os Bancos)

| Campo | Tipo | Descrição |
|-------|------|-----------|
| `cedente` | string | Nome da empresa/pessoa que está emitindo o boleto |
| `documento_cedente` | string | CNPJ ou CPF do cedente |
| `sacado` | string | Nome do pagador |
| `sacado_documento` | string | CPF ou CNPJ do pagador |
| `agencia` | string | Número da agência |
| `conta_corrente` | string | Número da conta corrente |
| `nosso_numero` | string | Número do boleto (único) |
| `valor` | float | Valor do boleto em reais |
| `data_vencimento` | string | Data de vencimento (YYYY/MM/DD) |

### Campos Específicos por Banco

#### Banco do Brasil (001)
- `convenio`: OBRIGATÓRIO (4-8 dígitos)
- `carteira`: Padrão "18"

#### Sicoob (756)
- `convenio`: OBRIGATÓRIO
- `variacao`: OBRIGATÓRIO
- `aceite`: DEVE ser "N" (não "S")
- `especie_documento`: OBRIGATÓRIO ("DM")

#### Bradesco (237)
- `digito_conta`: OBRIGATÓRIO
- `carteira`: Ex: "09"

#### Caixa (104)
- `convenio`: OBRIGATÓRIO
- `digito_conta`: OBRIGATÓRIO
- `nosso_numero`: 15 dígitos (preencher com zeros)

Consulte a [documentação completa](../docs/fields/) para detalhes de todos os bancos.

## ⚠️ Notas Importantes

### linha_digitavel no Sicoob

O campo `linha_digitavel` pode retornar `None` no Sicoob quando usando `get_boleto_data()`. Isso NÃO é um bug. A linha digitável sempre aparece corretamente no PDF gerado.

```python
boleto = client.get_boleto_data('sicoob', dados)
if boleto.linha_digitavel:
    print(f"Linha Digitável: {boleto.linha_digitavel}")
else:
    print("Linha digitável não disponível via /data, mas estará no PDF")
```

### numero_documento vs documento_numero

A API faz mapeamento automático. Você pode usar `numero_documento` no cliente:

```python
dados = {
    "numero_documento": "NF-2025-001",  # Cliente usa este
    # API converte automaticamente para 'documento_numero'
}
```

## 🧪 Testes

```bash
# Instalar dependências de desenvolvimento
pip install -e ".[dev]"

# Executar testes
pytest

# Com cobertura
pytest --cov=boleto_cnab_client

# Testes específicos
pytest tests/test_client.py -v
```

## 🤝 Contribuindo

Contribuições são bem-vindas! Por favor:

1. Fork o repositório
2. Crie uma branch para sua feature (`git checkout -b feature/nova-feature`)
3. Commit suas mudanças (`git commit -am 'Adiciona nova feature'`)
4. Push para a branch (`git push origin feature/nova-feature`)
5. Abra um Pull Request

## 📝 Changelog

Veja [CHANGELOG.md](../CHANGELOG.md) para histórico de versões.

## 📄 Licença

Este projeto está licenciado sob a Licença MIT - veja o arquivo [LICENSE](../LICENSE) para detalhes.

## 🔗 Links Úteis

- [Documentação da API](../docs/api/)
- [Documentação de Campos](../docs/fields/)
- [Exemplos](../examples/)
- [Repositório GitHub](https://github.com/Maxwbh/boleto_cnab_api)
- [Issues](https://github.com/Maxwbh/boleto_cnab_api/issues)

## 👨‍💻 Autor

**Maxwell da Silva Oliveira**
- GitHub: [@Maxwbh](https://github.com/Maxwbh)
- Email: maxwbh@gmail.com

## 🙏 Agradecimentos

Este cliente utiliza a API Boleto CNAB, que por sua vez usa a gem [BRCobranca](https://github.com/Maxwbh/brcobranca) para geração de boletos bancários brasileiros.

## 📄 Parsing de Extratos OFX (v1.2.0+)

O endpoint `POST /api/ofx/parse` permite parsear extratos bancários OFX.
O cliente Python ainda não possui um método helper dedicado, mas pode ser usado via `requests`:

```python
import requests

with open('extrato.ofx', 'rb') as f:
    response = requests.post(
        'http://localhost:9292/api/ofx/parse',
        files={'file': f},
        data={'somente_creditos': 'true'}  # opcional
    )

data = response.json()
print(f"Banco: {data['banco']['org']}")
print(f"Total de créditos: {data['resumo']['soma_creditos']}")

for tx in data['transacoes']:
    nn = tx.get('nosso_numero_extraido')
    if nn:
        print(f"  {tx['data']} R$ {tx['valor']:.2f} nosso_numero={nn}")
```

Veja [docs/api/ofx-parsing.md](../docs/api/ofx-parsing.md) para detalhes do endpoint e [docs/openapi.yaml](../docs/openapi.yaml) para o schema completo.

---

**Versão:** 1.4.1 (cliente) / API 1.5.0

### Novidades v1.3.0

- Suporte ao **Banco C6 (336)** — basta usar `bank='banco_c6'` com carteira `'10'` ou `'20'`
- PIX híbrido documentado (8 bancos) — adicione `emv` ao payload
- brcobranca atualizado para v12.6.1

### Novidades v1.2.0

- Endpoint `POST /api/ofx/parse` para parsing de extratos OFX
- Extração automática de `nosso_numero` por banco
- Fix: `RetryError` tratado como `BoletoAPIError` no client

### Novidades v1.1.0

- TypedDict para tipagem estática (`BoletoDataDict`, `BoletoResponseDict`)
- Testes pytest completos
- `pyproject.toml` (PEP 517/518)
- Compatibilidade com Python 3.8+ via `typing_extensions`
