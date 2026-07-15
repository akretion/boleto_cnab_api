---
name: Bug Report
about: Reporte um bug para nos ajudar a melhorar
title: '[BUG] '
labels: bug
assignees: ''
---

## 🐛 Descrição do Bug

Uma descrição clara e concisa do que o bug é.

## 🔄 Passos para Reproduzir

1. Faça requisição para '...'
2. Com parâmetros '...'
3. Veja o erro '...'

## ✅ Comportamento Esperado

Uma descrição clara do que você esperava que acontecesse.

## ❌ Comportamento Atual

Uma descrição clara do que acontece atualmente.

## 📋 Informações do Ambiente

**API:**
- Versão: [ex: 1.0.0] (veja arquivo `VERSION`)
- Ambiente: [ex: Docker, local, Render]
- Ruby: [ex: 3.1.2]

**Cliente (se aplicável):**
- Cliente Python versão: [ex: 1.0.0]
- Python: [ex: 3.11.0]
- OS: [ex: Ubuntu 22.04, macOS 13.0]

**Banco:**
- Banco afetado: [ex: Banco do Brasil (001), Sicoob (756)]

## 📄 Logs

<details>
<summary>Logs de erro (clique para expandir)</summary>

```
Cole os logs aqui
```

</details>

## 💾 Exemplo de Requisição

<details>
<summary>Dados da requisição (clique para expandir)</summary>

```python
# Cole o código ou curl aqui
import requests

response = requests.get(
    "http://localhost:9292/api/boleto/data",
    params={
        "bank": "banco_brasil",
        "data": {...}
    }
)
```

</details>

## 📸 Screenshots

Se aplicável, adicione screenshots para ajudar a explicar seu problema.

## 🔍 Contexto Adicional

Adicione qualquer outro contexto sobre o problema aqui.

## ✔️ Checklist

- [ ] Verifiquei que não há issue similar aberta
- [ ] Testei com a versão mais recente
- [ ] Li a [documentação](../../docs/)
- [ ] Incluí logs de erro
- [ ] Incluí dados para reproduzir o problema
