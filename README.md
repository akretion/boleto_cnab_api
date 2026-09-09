# Sobre o projeto boleto_cnab_api

O projeto de gestão de Boletos, Remessas e Retornos Bancários https://github.com/kivanio/brcobranca é muito bem feito, bem testado e mantido.

É interessante poder usar o projeto BRCobranca (escrito em Ruby) a partir de outras linguagens na forma de um micro-serviço REST.
Mais especificamente, a [Akretion](http://www.akretion.com) que é a empresa que lidera a localização do Odoo no Brasil desde 2009 https://github.com/OCA/l10n-brazil e co-criou a fundação [OCA](https://odoo-community.org/) usa esse projeto para gerenciar Boletos, Remessas e Retornos a partir do ERP Odoo (feito em Python, módulo específico https://github.com/OCA/l10n-brazil/tree/14.0/l10n_br_account_payment_brcobranca).

A imagem usada no projeto é do OS [Alpine](https://hub.docker.com/_/alpine), o motivo é que por ser um Micro-Serviço quanto menor a imagem melhor e apesar de existir dentro das imagens [Ruby](https://hub.docker.com/_/ruby) tanto a opção Debian quanto Alpine a imagem criada a partir da versão "pura" acaba sendo menor( Ruby-Debian 746MB | Ruby-Alpine 565MB | Alpine 523MB ), existem diferenças entre o [Debian](https://pt.wikipedia.org/wiki/Debian) e o [Alpine](https://pt.wikipedia.org/wiki/Alpine_Linux) basicamente "na superfície" são alguns nomes de pacote e o instalador de pacotes, no Debian apt-get e no Alpine apk, outros comandos Linux são iguais, em caso de algum erro complexo o Debian pode acabar sendo usado.

# Funcionalidades

Imprime **Boletos**, gera arquivos de **Remessa** e lê os arquivos de **Retorno** nos formatos CNAB 240, CNAB 400 para os 16 principais bancos do Brasil (Banco do Brasil, Banco do Nordeste, Banestes, Santander, Banrisul, Banco de Brasília, Caixa, Bradesco, Itaú, HSBC, Sicredi, Sicoob, AILOS, Unicred, CREDISIS e Citibank). Mas o grande barato desse projeto é que fazemos isso com menos de 200 linhas de código! Já comparou quantas linhas de de código você tem que manter sozinho ou quase se for re-fazer na linguagem que você quer tudo que o BRCobranca já faz? Seriam dezenas de milhares de linhas e você nunca teria uma qualidade tão boa...

# API

```ruby
# Validar os dados de um Boleto:
GET /boleto/validate
        requires :bank, type: String, desc: 'Bank'
        requires :data, type: String, desc: 'Boleto data as a stringified json'

# Obter o nosso_numero de um Boleto:
GET /boleto/nosso_numero
        requires :bank, type: String, desc: 'Bank'
        requires :data, type: String, desc: 'Boleto data as a stringified json'

# Imprimir um Boleto apenas:
GET /boleto?type=pdf&bank=itau&data=<stringified json>
        requires :bank, type: String, desc: 'Bank'
        requires :type, type: String, desc: 'Type: pdf|jpg|png|tif'
        requires :data, type: String, desc: 'Boleto data as a stringified json'

# Imprimir uma lista de Boletos:
POST /boleto/multi
        requires :type, type: String, desc: 'Type: pdf|jpg|png|tif'
        requires :data, type: File, desc: 'json of the list of boletos, including the "bank" key'

# Gerir um arquivo de Remessa CNAB 240 ou CNAB 400:
POST /remessa
        requires :bank, type: String, desc: 'Bank'
        requires :type, type: String, desc: 'Type: cnab400|cnab240'
        requires :data, type: File, desc: 'json with the remessa fields, including a "pagamentos" list'
        # Obs: cada banco e cada formato (cnab400|cnab240) exige campos próprios,
        # veja os exemplos abaixo e a documentação da BRCobranca.

# Transformar um arquivo de Retorno CNAB 240 ou CNAB 400 em JSON:
POST /retorno
        requires :bank, type: String, desc: 'Bank'
        requires :type, type: String, desc: 'Type: cnab400|cnab240'
        requires :data, type: File, desc: 'txt of the retorno file'
```

Nota: os campos datas devem estar no formato YYYY/MM/DD (para o endpoint /remessa
também são aceitos os formatos de data aceitos pela Ruby "Date.parse", como "Thu, 15 Jun 2017").

Os campos de Boleto estão listados aqui: https://github.com/kivanio/brcobranca/blob/master/lib/brcobranca/boleto/base.rb
Os campos genéricos de Remessa estão listados aqui: https://github.com/kivanio/brcobranca/blob/master/lib/brcobranca/remessa/base.rb
Os campos de Retorno devolvidos em JSON estão listados aqui: https://github.com/kivanio/brcobranca/blob/master/lib/brcobranca/retorno/base.rb

A API está documentada com mais detalhes no código aqui: https://github.com/akretion/boleto_cnab_api/blob/master/lib/boleto_api.rb

# Documentação interativa (OpenAPI)

A API expõe a sua especificação OpenAPI (Swagger 2.0) em ```/api/swagger_doc```, gerada pelo [grape-swagger](https://github.com/ruby-grape/grape-swagger) a partir do próprio código, e serve uma documentação interativa com [Scalar](https://scalar.com) em ```/docs``` — suba o container e abra http://localhost:9292/docs para explorar e testar os endpoints (o "Try it" funciona por ser a mesma origem da API).

A mesma documentação é publicada no GitHub Pages: https://akretion.github.io/boleto_cnab_api/

O arquivo ```docs/openapi.json``` servido em ```/docs``` é um snapshot gerado a partir da API, sem precisar subir o servidor:

```bash
bundle exec ruby scripts/generate_openapi.rb
```

O CI verifica que esse arquivo nunca fica desatualizado em relação ao código.

# Como rodar o micro-serviço

```bash
docker run -p 9292:9292 ghcr.io/akretion/boleto_cnab_api
```

# Autenticação (opcional)

Por padrão o serviço não exige autenticação (adequado para rodar na mesma rede do ERP). Para proteger uma instância exposta, defina a variável de ambiente ```API_KEYS``` com uma ou mais chaves separadas por vírgula:

```bash
docker run -p 9292:9292 -e API_KEYS="chave-da-empresa-a,chave-da-empresa-b" ghcr.io/akretion/boleto_cnab_api
```

Com ```API_KEYS``` definida, todos os endpoints (```/api/*``` e ```/docs```) exigem a chave, que pode ser passada de duas formas:

1. **Header ```X-Api-Key```** — mesmo header usado pelas API keys do AWS API Gateway. Um cliente configurado assim (por exemplo o Odoo, módulo ```l10n_br_account_payment_brcobranca```) funciona sem alteração tanto contra um container auto-hospedado quanto contra um futuro serviço hospedado na AWS:

```bash
curl -G localhost:9292/api/boleto/validate -H 'X-Api-Key: chave-da-empresa-a' \
  --data-urlencode 'bank=itau' --data-urlencode 'data={...}'
```

2. **HTTP Basic auth** — qualquer usuário, a chave como senha (prático para curl e navegadores, por exemplo ao abrir a documentação em ```/docs```):

```bash
curl -G localhost:9292/api/boleto/validate -u qualquer-usuario:chave-da-empresa-a \
  --data-urlencode 'bank=itau' --data-urlencode 'data={...}'
```

Sem chave ou com chave inválida a resposta é ```401 {"error":"missing or invalid API key"}```. A comparação das chaves é feita em tempo constante.

# AWS Lambda (serverless)

Além do container Docker tradicional, o projeto pode ser empacotado como uma **imagem de container AWS Lambda** (```Dockerfile.lambda```), usando o mesmo código Grape sem alteração. O "handler" (```lib/lambda_function.rb```) traduz o evento do API Gateway (proxy integration) para um ambiente Rack, chama a aplicação e devolve a resposta no formato esperado pelo API Gateway — respostas binárias (PDF/PNG/remessa) saem em base64 com ```isBase64Encoded: true```.

Construir a imagem:

```bash
docker build -f Dockerfile.lambda -t boleto-cnab-lambda .
```

Testar localmente com o Runtime Interface Emulator (RIE), que já vem na imagem base — sem precisar de uma conta AWS:

```bash
docker run -p 9000:8080 boleto-cnab-lambda
python3 test/lambda_rie_smoke.py
```

Ou exercitar todos os endpoints direto contra o handler (sem Docker), reutilizando os mesmos fixtures da BRCobranca:

```bash
bundle exec ruby scripts/lambda_local_test.rb
```

O CI constrói a imagem Lambda, roda o harness completo dentro dela e faz um smoke test pelo RIE, garantindo que o empacotamento nunca quebre.

**Deploy na AWS (resumo):** a imagem é publicada no ECR e referenciada pela função Lambda; o API Gateway (REST API, para suportar usage plans/API keys) roteia para ela. A autenticação/throttling/quota por cliente ficam no API Gateway (usage plans), fora do código — e o header ```X-Api-Key``` aceito pela autenticação local (seção acima) é o mesmo usado pelas API keys do API Gateway, então um cliente funciona nos dois mundos. Limites a considerar: payload de até ~6 MB (10 MB para a resposta) no API Gateway e timeout de 29 s, então lotes grandes de ```/boleto/multi``` devem respeitar esses tetos.

# Exemplos de como consumir o serviço usando sua linguagem preferida:

## Bash

Os exemplos abaixo usam os mesmos dados da suíte de testes oficial da BRCobranca
(https://github.com/kivanio/brcobranca/tree/master/spec) e são exatamente os testes
executados no CI deste projeto (https://github.com/akretion/boleto_cnab_api/blob/master/test/curl_tests.sh).

Por exemplo, para validar os dados de um Boleto do Itaú:
```bash
curl -G localhost:9292/api/boleto/validate \
  --data-urlencode 'bank=itau' \
  --data-urlencode 'data={"valor":5.0,"cedente":"Kivanio Barbosa","documento_cedente":"12345678912","sacado":"Claudio Pozzebom","sacado_documento":"12345678900","agencia":"0810","conta_corrente":"53678","convenio":12387,"nosso_numero":"12345678","data_vencimento":"2026/12/31"}'
# => true
```

Para obter o nosso_numero formatado de um Boleto do Itaú:
```bash
curl -G localhost:9292/api/boleto/nosso_numero \
  --data-urlencode 'bank=itau' \
  --data-urlencode 'data={"valor":5.0,"cedente":"Kivanio Barbosa","documento_cedente":"12345678912","sacado":"Claudio Pozzebom","sacado_documento":"12345678900","agencia":"0810","conta_corrente":"53678","convenio":12387,"nosso_numero":"12345678"}'
# => "175/12345678-4"
```

Para imprimir um único Boleto (do Itaú em PDF ou da Caixa em PNG):
```bash
curl -G localhost:9292/api/boleto \
  --data-urlencode 'bank=itau' --data-urlencode 'type=pdf' \
  --data-urlencode 'data={"valor":5.0,"cedente":"Kivanio Barbosa","documento_cedente":"12345678912","sacado":"Claudio Pozzebom","sacado_documento":"12345678900","agencia":"0810","conta_corrente":"53678","convenio":12387,"nosso_numero":"12345678"}' \
  > /tmp/boleto_itau.pdf

curl -G localhost:9292/api/boleto \
  --data-urlencode 'bank=caixa' --data-urlencode 'type=png' \
  --data-urlencode 'data={"valor":10.00,"cedente":"PREFEITURA MUNICIPAL DE VILHENA","documento_cedente":"04092706000181","sacado":"João Paulo Barbosa","sacado_documento":"77777777777","agencia":"1825","conta_corrente":"0000528","convenio":"245274","nosso_numero":"000000000000001"}' \
  > /tmp/boleto_caixa.png
```

Para imprimir uma lista de Boletos é preciso criar um arquivo temporário com os Boletos em formato JSON e depois fazer um POST do arquivo:
```bash
echo '[{"valor":5.0,"cedente":"Kivanio Barbosa","documento_cedente":"12345678912","sacado":"Claudio Pozzebom",
"sacado_documento":"12345678900","agencia":"0810","conta_corrente":"53678","convenio":12387,"nosso_numero":"12345678","bank":"itau"},
{"valor": 10.00,"cedente": "PREFEITURA MUNICIPAL DE VILHENA","documento_cedente": "04092706000181","sacado": "João Paulo Barbosa",
"sacado_documento": "77777777777","agencia": "1825","conta_corrente": "0000528","convenio": "245274","nosso_numero": "000000000000001","bank":"caixa"}]'\
> /tmp/boletos_data.json
curl -X POST -F type=pdf -F 'data=@/tmp/boletos_data.json' localhost:9292/api/boleto/multi > /tmp/boletos.pdf
```
Você pode então conferir os Boletos gerados no arquivo ```/tmp/boletos.pdf```

Para gerir um arquivo de Remessa CNAB 400 do Itaú:
```bash
echo '{"carteira": "123","agencia": "1234","conta_corrente": "12345","digito_conta": "1","empresa_mae": "SOCIEDADE BRASILEIRA DE ZOOLOGIA LTDA","documento_cedente": "12345678910",
"pagamentos": [{"valor": 199.9,"data_vencimento": "2026/06/15","nosso_numero": 123,"documento": 6969,"documento_sacado": "12345678901",
"nome_sacado": "PABLO DIEGO JOSÉ FRANCISCO DE PAULA JUAN NEPOMUCENO MARÍA DE LOS REMEDIOS CIPRIANO DE LA SANTÍSSIMA TRINIDAD RUIZ Y PICASSO",
"endereco_sacado": "RUA RIO GRANDE DO SUL São paulo Minas caçapa da silva junior","bairro_sacado": "São josé dos quatro apostolos magros",
"cep_sacado": "12345678","cidade_sacado": "Santa rita de cássia maria da silva","uf_sacado": "SP"}]}' > /tmp/remessa_data.json
curl -X POST -F type=cnab400 -F bank=itau -F 'data=@/tmp/remessa_data.json' localhost:9292/api/remessa > /tmp/remessa_cnab400.rem
head -c 120 /tmp/remessa_cnab400.rem
# => 01REMESSA01COBRANCA...
```
Para o formato CNAB 240 os campos de conta mudam um pouco (sem "digito_conta", com "sequencial_remessa" e "carteira") e os pagamentos exigem campos como "numero" e "codigo_baixa", por exemplo:
```bash
echo '{"empresa_mae": "EMPRESA TESTE LTDA","documento_cedente": "28254225000193","agencia": "1234","conta_corrente": "12345","carteira": "175","sequencial_remessa": "1",
"pagamentos": [{"valor": 123.45,"data_vencimento": "2026/06/15","nosso_numero": 12345678,"documento": 9999,"documento_sacado": "12345678901",
"nome_sacado": "PABLO DIEGO JOSÉ FRANCISCO DE PAULA JUAN NEPOMUCENO MARÍA DE LOS REMEDIOS CIPRIANO DE LA SANTÍSSIMA TRINIDAD RUIZ Y PICASSO",
"endereco_sacado": "RUA RIO GRANDE DO SUL São paulo Minas caçapa da silva junior","bairro_sacado": "São josé dos quatro apostolos magros",
"cep_sacado": "12345678","cidade_sacado": "Santa rita de cássia maria da silva","uf_sacado": "SP","numero": "123","codigo_baixa": "3","dias_baixa": "0"}]}' > /tmp/remessa_data_cnab240.json
curl -X POST -F type=cnab240 -F bank=itau -F 'data=@/tmp/remessa_data_cnab240.json' localhost:9292/api/remessa > /tmp/remessa_cnab240.rem
```

Para ler um arquivo de Retorno CNAB 400 do Itaú:
```bash
wget -O /tmp/CNAB400ITAU.RET https://raw.githubusercontent.com/kivanio/brcobranca/master/spec/arquivos/CNAB400ITAU.RET
curl -X POST -F type=cnab400 -F bank=itau -F 'data=@/tmp/CNAB400ITAU.RET' localhost:9292/api/retorno
# => [{"codigo_registro":"1","codigo_ocorrencia":"06","nosso_numero":"00000011","valor_recebido":"0000000003790",...}, ...]
```

## Python

```python
import json
import requests

base_url = "http://localhost:9292/api"

# validar os dados de um Boleto
boleto_data = {
    "valor": 5.0,
    "cedente": "Kivanio Barbosa",
    "documento_cedente": "12345678912",
    "sacado": "Claudio Pozzebom",
    "sacado_documento": "12345678900",
    "agencia": "0810",
    "conta_corrente": "53678",
    "convenio": 12387,
    "nosso_numero": "12345678",
}
response = requests.get(
    f"{base_url}/boleto/validate",
    params={"bank": "itau", "data": json.dumps(boleto_data)},
)
assert response.json() is True

# imprimir o Boleto em PDF
response = requests.get(
    f"{base_url}/boleto",
    params={"bank": "itau", "type": "pdf", "data": json.dumps(boleto_data)},
)
with open("/tmp/boleto.pdf", "wb") as f:
    f.write(response.content)
```
(Ver os exemplos completos nos módulos Odoo: https://github.com/OCA/l10n-brazil/tree/14.0/l10n_br_account_payment_brcobranca)

## Java

```
TODO (contribuições bem vindas)
```

# Testes

O CI (https://github.com/akretion/boleto_cnab_api/blob/master/.github/workflows/ci.yml) constrói a imagem Docker, inicia o micro-serviço e roda contra ele uma suíte de testes "curl" (https://github.com/akretion/boleto_cnab_api/blob/master/test/curl_tests.sh) que cobre todos os endpoints da API: validação de Boleto, geração do nosso_numero, impressão de Boleto único e em lote (PDF/PNG), geração de Remessa CNAB 400 e CNAB 240 e leitura de Retorno CNAB 400. Os dados usados são os mesmos da suíte oficial da BRCobranca, então valores como o nosso_numero esperado ou o tamanho das linhas CNAB são verificados contra os valores esperados.

Para rodar os testes localmente contra um micro-serviço já em execução (por exemplo com ```docker run -p 9292:9292 ghcr.io/akretion/boleto_cnab_api```):

```bash
test/curl_tests.sh http://localhost:9292
```

Ou via pytest, que também constrói a imagem e inicia o container antes dos testes curl (requer Docker, pytest e requests):

```bash
pip install pytest requests
pytest -v test/test_run.py
```

## Testar alterações na imagem sem necessidade de commit

No arquivo Gemfile.lock é possível alterar o repositório e o commit específico que será usado na criação da imagem, o que é necessário durante uma correção, atualização ou implementação de um novo caso, um exemplo simples pode ser visto nesse PR https://github.com/akretion/boleto_cnab_api/pull/11/files , mas também é possível alterar o Dockerfile para criar uma imagem de teste onde seja possível editar os arquivos dentro do container (o que evita subir um commit desnecessário ou com erro), para isso no arquivo Dockerfile são feitas as seguintes alterações:

Instalar algum editor de texto, por exemplo VIM ou Nano (por padrão o VI já está instalado mas caracteres UTF-8 não são mostrados corretamente) e alterar o usuário **app** para o **root** para poder editar os arquivos
```bash
            git \
            ruby-dev \
+           vim \
+           nano \
         && rm -rf /var/cache/apk/* \
         ;

-USER app
+USER root
```

Criação da imagem
```bash
$ docker build -t akretion/boleto_cnab_api-teste .
```

Depois de iniciar a imagem podemos entrar dentro do container
```bash
Localizar o container ID

$ docker ps
CONTAINER ID   IMAGE                             COMMAND                  CREATED             STATUS             PORTS                                                 NAMES
1ea95da3a3c3   akretion/boleto_cnab_api-teste   "/bin/sh -c 'bundle …"   4 minutes ago   Up 4 minutes   0.0.0.0:9292->9292/tcp, :::9292->9292/tcp   eloquent_noether
```

Acessando o container (No Debian usa /bin/bash no Alpine /bin/sh)
```bash
$ docker exec -it <container-id> /bin/sh

O valor <container-id> varia, nesse exemplo o comando seria

$ docker exec -it 1ea95da3a3c3 /bin/sh
```

Dentro do container é preciso localizar a pasta onde está instalada a biblioteca, no exemplo é usado o comando **find** e a partir disso é possível realizar alterações necessárias
```bash
/usr/src/app # find /usr -name unicred.rb
/usr/lib/ruby/gems/3.3.0/bundler/gems/brcobranca-cd928e87554b/lib/brcobranca/retorno/cnab400/unicred.rb
/usr/lib/ruby/gems/3.3.0/bundler/gems/brcobranca-cd928e87554b/lib/brcobranca/remessa/cnab240/unicred.rb
/usr/lib/ruby/gems/3.3.0/bundler/gems/brcobranca-cd928e87554b/lib/brcobranca/remessa/cnab400/unicred.rb
```

A partir disso é possível realizar alterações necessárias, por exemplo verificar o valor de alguma variável "imprimindo" no LOG com o comando "puts" (algumas referencias https://www.dotnetperls.com/console-ruby https://www.rubyguides.com/2018/10/puts-vs-print/ http://ruby-for-beginners.rubymonstas.org/writing_methods/printing.html )
```bash
/usr/src/app # vim /usr/lib/ruby/gems/3.3.0/bundler/gems/brcobranca-cd928e87554b/lib/brcobranca/
boleto/unicred.rb

      def codigo_barras_segunda_parte
        puts "TESTE puts algum valor qualquer " + "#{agencia}"
        "#{agencia}#{conta_corrente}#{conta_corrente_dv}#{nosso_numero}#{nosso_numero_dv}"
      end
    end
```

Nesse exemplo ao criar um Boleto do UNICRED é possível ver no LOG o resultado do "puts"
```bash
$ docker logs -f 28f2881e4dd7
Puma starting in single mode...
* Puma version: 6.4.2 (ruby 3.3.3-p89) ("The Eagle of Durango")
*  Min threads: 0
*  Max threads: 5
*  Environment: development
*          PID: 1
* Listening on http://0.0.0.0:9292
Use Ctrl-C to stop
TESTE puts algum valor qualquer 1234
```

Se a imagem estiver sendo iniciada dentro de um **Docker Compose**, por exemplo por um projeto Odoo é possível ver o LOG usando:
```bash
$ docker logs -f 28f2881e4dd7
Puma starting in single mode...
* Puma version: 6.4.2 (ruby 3.3.3-p89) ("The Eagle of Durango")
*  Min threads: 0
*  Max threads: 5
*  Environment: development
*          PID: 1
* Listening on http://0.0.0.0:9292
Use Ctrl-C to stop
- Gracefully stopping, waiting for requests to finish
=== puma shutdown: 2024-07-05 19:50:05 +0000 ===
- Goodbye!
```

**IMPORTANTE:** por algum motivo as alterações dentro do container só tem efeito na primeira vez que o arquivo é Salvo, uma segunda alteração não tem efeito, isso pode ser algo referente ao comportamento da imagem, ou do Docker ou do Docker Compose, já que nos testes realizados esse container é iniciado e usado por outro container rodando o Odoo, é preciso investigar melhor para entender se isso é algo normal e já esperado ou se teria uma forma de corrigir, porque devido a isso para testar dessa forma está sendo necessário alterar uma vez e se for preciso fazer outra alteração sair do container fazer um kill e inicia-lo novamente.
