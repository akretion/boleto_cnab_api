# Política de Segurança

## 🔒 Versões Suportadas

Mantemos ativamente as seguintes versões:

| Versão | Suportada          | Observação |
| ------ | ------------------ | ---------- |
| 1.5.x  | ✅ Sim             | Atual (recomendada) |
| 1.4.x  | ⚠️ Críticas apenas | Migre para 1.5.x |
| 1.3.x  | ⚠️ Críticas apenas | Migre para 1.5.x |
| < 1.3  | ❌ Não             | Descontinuada |

## 🐛 Reportando uma Vulnerabilidade

A segurança do Boleto CNAB API é levada muito a sério. Se você descobrir uma vulnerabilidade de segurança, por favor:

### ⚠️ NÃO abra uma issue pública

Vulnerabilidades de segurança devem ser reportadas de forma privada.

### ✅ Processo de Reporte

1. **Envie um e-mail para:** maxwbh@gmail.com
   - Assunto: `[SECURITY] Vulnerabilidade em Boleto CNAB API`

2. **Inclua as seguintes informações:**
   - Tipo de vulnerabilidade (ex: SQL injection, XSS, etc.)
   - Localização do código afetado (arquivo e linha)
   - Passos para reproduzir
   - Impacto potencial
   - Possível correção (se souber)
   - Sua informação de contato

3. **Exemplo de reporte:**
   ```
   Assunto: [SECURITY] Vulnerabilidade em Boleto CNAB API

   Tipo: Command Injection
   Localização: lib/boleto_api.rb:123
   Versão afetada: 1.3.0

   Descrição:
   O parâmetro 'nosso_numero' não é sanitizado antes de ser
   usado em um comando shell, permitindo command injection.

   Reprodução:
   1. POST /api/boleto
   2. nosso_numero="; rm -rf /"
   3. Comando malicioso é executado

   Impacto:
   Execução arbitrária de código no servidor

   Possível correção:
   Sanitizar o parâmetro antes de usar
   ```

### 📅 Tempo de Resposta

- **Confirmação inicial:** Dentro de 48 horas
- **Análise da vulnerabilidade:** Dentro de 7 dias
- **Correção e patch:** Varia conforme criticidade
  - Crítico: < 7 dias
  - Alto: < 14 dias
  - Médio: < 30 dias
  - Baixo: < 60 dias

### 🔐 Processo de Correção

1. Confirmaremos o recebimento do seu reporte
2. Investigaremos e validaremos a vulnerabilidade
3. Desenvolveremos uma correção
4. Lançaremos um patch de segurança
5. Publicaremos um security advisory (se crítico)
6. Creditaremos você na correção (se desejar)

## 🛡️ Práticas de Segurança

### Para Usuários da API

**Proteção de Dados Sensíveis:**
- ❌ Nunca commite arquivos `.env` com credenciais
- ❌ Nunca logue dados completos de boletos em produção
- ✅ Use variáveis de ambiente para configurações sensíveis
- ✅ Implemente rate limiting no seu proxy/gateway
- ✅ Use HTTPS em produção

**Validação de Dados:**
```python
# ✅ BOM: Validar entrada do usuário
def gerar_boleto(dados):
    if not validar_cpf(dados['sacado_documento']):
        raise ValueError("CPF inválido")
    # ...

# ❌ RUIM: Confiar cegamente em dados do usuário
def gerar_boleto(dados):
    # usar dados diretamente sem validação
```

**Deploy Seguro:**
- ✅ Use Docker com imagem base oficial e atualizada
- ✅ Execute a aplicação com usuário não-root
- ✅ Limite recursos (CPU, memória)
- ✅ Configure firewall apropriadamente
- ❌ Não exponha porta do container diretamente

### Para Desenvolvedores

**Evite Vulnerabilidades Comuns:**

1. **SQL Injection** - Não aplicável (não usa SQL diretamente)

2. **Command Injection:**
   ```ruby
   # ❌ RUIM: Concatenar strings em comandos shell
   `convert #{params[:file]} output.pdf`

   # ✅ BOM: Usar arrays de argumentos
   system('convert', params[:file], 'output.pdf')
   ```

3. **Path Traversal:**
   ```ruby
   # ❌ RUIM: Usar input diretamente em paths
   File.read(params[:filename])

   # ✅ BOM: Validar e sanitizar
   filename = File.basename(params[:filename])
   File.read(File.join(SAFE_DIR, filename))
   ```

4. **XSS** - Não aplicável (API REST sem frontend)

5. **Information Disclosure:**
   ```ruby
   # ❌ RUIM: Retornar stack trace completo
   rescue => e
     { error: e.backtrace }

   # ✅ BOM: Retornar mensagem genérica
   rescue => e
     logger.error(e.backtrace)
     { error: "Erro interno" }
   ```

6. **DoS (Denial of Service):**
   ```ruby
   # ✅ BOM: Limitar tamanho de upload
   use Rack::Protection::JsonCsrf
   use Rack::BodyProxy::MaxLength, max_length: 1_000_000
   ```

## 📋 Dependências

### Auditoria de Dependências

Verificamos regularmente dependências com:

```bash
# Ruby
bundle audit check --update

# Python
pip-audit
```

### Atualização de Dependências

- Dependências críticas: Atualizadas imediatamente
- Dependências de segurança: Dentro de 7 dias
- Dependências menores: Revisão mensal

### Dependências Conhecidas

**Ruby:**
- `grape` - Framework da API
- `brcobranca` - Geração de boletos
- Ver `Gemfile` para lista completa

**Python Cliente:**
- `requests` - Cliente HTTP
- Ver `python-client/requirements.txt`

## 🔍 Auditoria de Segurança

Este projeto:
- ✅ Não armazena dados de cartão de crédito
- ✅ Não processa pagamentos diretamente
- ✅ Gera apenas PDFs de boletos (não executa transações)
- ✅ É stateless (não mantém sessões)
- ✅ Não acessa bancos de dados externos
- ✅ Usa imagem Docker Alpine minimalista

## 📚 Recursos de Segurança

- [OWASP Top 10](https://owasp.org/www-project-top-ten/)
- [Ruby on Rails Security Guide](https://guides.rubyonrails.org/security.html)
- [Docker Security Best Practices](https://docs.docker.com/develop/security-best-practices/)
- [CWE - Common Weakness Enumeration](https://cwe.mitre.org/)

## 🏆 Hall of Fame

Agradecemos aos seguintes pesquisadores de segurança que reportaram vulnerabilidades responsavelmente:

*(Nenhum reporte até o momento - seja o primeiro!)*

---

**Obrigado por ajudar a manter o Boleto CNAB API seguro!**

Para questões gerais (não relacionadas a segurança), por favor use as [issues do GitHub](https://github.com/Maxwbh/boleto_cnab_api/issues).
