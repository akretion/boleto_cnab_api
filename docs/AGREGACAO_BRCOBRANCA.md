# Agregação dos repositórios da gem BRCobranca (git-aggregator)

Este projeto **não** consome a BRCobranca direto do GitHub. A gem vem de um
repositório **agregado** em `vendor/brcobranca/`, gerado com
[acsone/git-aggregator](https://github.com/acsone/git-aggregator) (a mesma
ferramenta que o Odoo/OCA usa para juntar branches de vários remotes em um
único branch consolidado).

Fontes agregadas:

| remote     | URL                                          | ref                            |
|------------|----------------------------------------------|--------------------------------|
| `kivanio`  | https://github.com/kivanio/brcobranca.git    | `master` (upstream)            |
| `akretion` | https://github.com/akretion/brcobranca.git   | `IMP-split_payment_ibs_cbs`    |

O branch `master` do repositório agregado contém o upstream **mais** o commit
do fork (Split Payment IBS/CBS), com o histórico dos dois concatenado.

## Por que não basta `gem 'brcobranca', git: '...', branch: '...'`

O `Gemfile` aceita **um** remote e **uma** ref por gem. Um `git:` source
clona exatamente aquela URL e aquele branch — não existe sintaxe de bundler
para "upstream A + fork B". Para combinar dois repositórios/refs é preciso
materializar a combinação em um repositório git de verdade antes do
`bundle install`. É isso que o `gitaggregate.yaml` faz.

## Estado atual das duas fontes (30/10/2026)

- `kivanio/master` = `9e28ee2` ([REFACTOR] Elimina duplicacao no template
  bolepix e no retorno CNAB 240 (#285), 28/08/2026)
- `akretion/IMP-split_payment_ibs_cbs` = `be91efb` = **exatamente um commit
  em cima** de `9e28ee2`

Ou seja: **hoje a agregação é um fast-forward** e produz `be91efb` — o mesmo
conteúdo que o `git:` source do fork já entregava. O ganho aparece quando
`kivanio/master` avançar: a agregação passa a criar um commit de merge
(upstream novo + patch do fork) em vez de exigir rebase manual do fork.

## Como (re)gerar

```sh
gitaggregate -c gitaggregate.yaml              # cria/atualiza vendor/brcobranca
gitaggregate -c gitaggregate.yaml --no-color   # idem, sem cores (CI/logs)
```

Requisitos:

- `gitaggregate` instalado (`pipx install git-aggregator`, testado com 4.1);
- identidade git configurada (`git config user.name` / `user.email`): quando há
  divergência o git-aggregator cria um **commit de merge**.

Conferir o resultado:

```sh
git -C vendor/brcobranca log --oneline --graph -5
git -C vendor/brcobranca merge-base --is-ancestor <sha-do-upstream> HEAD && echo ok
```

### Armadilha: o branch alvo tem que ser o PRIMEIRO item de `merges`

O git-aggregator faz `git reset --hard` para o **primeiro** `merges` e depois
`git pull` dos demais. Se `kivanio master` não estiver na lista, o resultado é
apenas o fork e **os commits novos do upstream são perdidos silenciosamente**
(o comando sai com sucesso). Por isso o YAML lista o upstream primeiro:

```yaml
  target: kivanio master
  merges:
    - kivanio master
    - akretion IMP-split_payment_ibs_cbs
```

Testado com um upstream simulado que avançou um commit:

- sem divergência de conteúdo → commit de merge com os dois pais
  (`fd8d9b1` upstream + `be91efb` fork), arquivos do split payment presentes;
- com divergência no mesmo trecho de `lib/brcobranca/remessa/cnab240/base.rb`
  → `gitaggregate` sai != 0 e deixa `UU lib/brcobranca/remessa/cnab240/base.rb`
  no repo agregado.

### Resolver conflito

```sh
cd vendor/brcobranca
git status                      # arquivos UU
# editar, testar (rspec da própria gem) e:
git add -A && git commit
gitaggregate -c gitaggregate.yaml   # reexecuta em cima do merge resolvido
```

Se `gitaggregate` reclamar de repositório sujo, use `-f` (ou commite/limpe
antes).

## Integração com a imagem

- `Gemfile`: `gem 'brcobranca', path: 'vendor/brcobranca'` (source `PATH` no
  `Gemfile.lock`, versão continua `13.0.0`).
- `Dockerfile`: `COPY vendor/brcobranca/ ./vendor/brcobranca/` **antes** do
  `bundle install` (com `:path` o diretório precisa existir na hora do
  install). `git` saiu das dependências de build: não há mais gem git-sourced.
- `.dockerignore`: exclui `vendor/brcobranca/{.git,docs,spec,.github,...}` —
  só `lib/` (14MB) e o gemspec entram no contexto; `.git` (46MB) e `docs/`
  (48MB) ficam de fora.
- `.gitignore`: `vendor/` não é versionado (é artefato gerado, ~60MB). O
  checkout existe localmente e o Docker o copia mesmo assim (docker não lê
  `.gitignore`).
- `Gemfile.lock` foi regenerado na imagem `alpine:3.24` com `bundler 4.0.19`
  (mesma combinação do Dockerfile). Único diff vs. a versão anterior:
  seção `GIT` → `PATH`.

O checkout agregado é um clone **completo** do kivanio (todos os blobs), então
pode ser publicado (`git push`) se um dia for necessário. Quando o
git-aggregator cria o diretório do zero ele usa clone parcial
(`--filter=blob:none`); nesse caso, para publicar:

```sh
git -C vendor/brcobranca fetch --refetch --filter=blob:limit=1g origin
```

## CI (.github/workflows/ci.yml)

Como `vendor/` é gitignored, o workflow agrega antes do build, com a mesma
ferramenta e o mesmo YAML:

```yaml
      - name: Install git-aggregator
        run: pip install git-aggregator
      - name: Aggregate BRCobranca (kivanio master + akretion IMP-split_payment_ibs_cbs)
        run: |
          git config --global user.name "github-actions[bot]"
          git config --global user.email "github-actions[bot]@users.noreply.github.com"
          gitaggregate -c gitaggregate.yaml --no-color
```

Também vale para rodar `test_run.py` localmente: rode o `gitaggregate` antes do
`pytest` (ele faz `docker build`).

## Regenerar o `Gemfile.lock`

O lock tem que ser gerado com a mesma combinação do Dockerfile
(`alpine:3.24` + `bundler 4.0.19`), senão a seção `BUNDLED WITH` e as
checksums divergem e o build em modo `frozen` falha:

```sh
mkdir -p /tmp/locktool && cat > /tmp/locktool/Dockerfile <<'EOF'
FROM alpine:3.24
RUN apk add --no-cache build-base ruby-dev \
    && gem install bundler:4.0.19 --no-document
EOF
docker build -t boleto-toolchain -f /tmp/locktool/Dockerfile /tmp/locktool
docker run --rm -u "$(id -u):$(id -g)" \
    -e HOME=/tmp -e GEM_HOME=/tmp/gems -e GEM_PATH=/tmp/gems \
    -e PATH=/tmp/gems/bin:/usr/local/bin:/usr/bin:/bin \
    -v "$PWD":/app -w /app boleto-toolchain \
    sh -c 'gem install bundler:4.0.19 --no-document >/dev/null && bundle lock'
```

## Alternativa: publicar o branch agregado e voltar para `git:` source

Se preferir manter o `Gemfile.lock` com seção `GIT` (sem `vendor/`):

```sh
git -C vendor/brcobranca push <remote-com-permissao> master:aggregated-split-payment
```

e no `Gemfile`:

```ruby
gem 'brcobranca', git: 'https://github.com/<fork>/brcobranca.git',
                  branch: 'aggregated-split-payment'
```

Depois `bundle lock` (a seção `GIT` volta, com `revision:` apontando para o
merge commit). Nesse modo a imagem volta a precisar de `git` no estágio de
build.

PR do Split Payment:

* https://github.com/kivanio/brcobranca/pull/294
