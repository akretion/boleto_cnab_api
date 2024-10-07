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
GET /boleto/get
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
        requires :data, type: File, desc: 'json of the list of pagamentos'

# Transformar um arquivo de Retorno CNAB 240 ou CNAB 400 em JSON:
POST /retorno
        requires :bank, type: String, desc: 'Bank'
        requires :type, type: String, desc: 'Type: cnab400|cnab240'
        requires :data, type: File, desc: 'txt of the retorno file'
```

Nota: os campos datas devem estar no formato YYYY/MM/DD

O API está documentado com mais detalhes no código aqui: https://github.com/akretion/boleto_cnab_api/blob/master/lib/boleto_api.rb

# Como rodar o micro-serviço

```bash
docker run -p 9292:9292 ghcr.io/akretion/boleto_cnab_api
```

# Exemplos de como consumir o serviço usando sua linguagem preferida:

## Bash

Por exemplo, para imprimir uma lista de Boletos é preciso criar um arquivo temporario com os Boletos em formato JSON e depois fazer um POST do arquivo:
```bash
echo '[{"valor":5.0,"cedente":"Kivanio Barbosa","documento_cedente":"12345678912","sacado":"Claudio Pozzebom",
"sacado_documento":"12345678900","agencia":"0810","conta_corrente":"53678","convenio":12387,"nosso_numero":"12345678","bank":"itau"},
{"valor": 10.00,"cedente": "PREFEITURA MUNICIPAL DE VILHENA","documento_cedente": "04092706000181","sacado": "João Paulo Barbosa",
"sacado_documento": "77777777777","agencia": "1825","conta_corrente": "0000528","convenio": "245274","nosso_numero": "000000000000001","bank":"caixa"}]'\
> /tmp/boletos_data.json
curl -X POST -F type=pdf -F 'data=@/tmp/boletos_data.json' localhost:9292/api/boleto/multi > /tmp/boletos.pdf
```
Você pode então conferir os Boletos gerados no arquivo ```/tmp/boletos.pdf```

## Python

```
TODO
```
(Ver os exemplos nos módulos Odoo: https://github.com/OCA/l10n-brazil/tree/14.0/l10n_br_account_payment_brcobranca)

## Java

```
TODO (contribuições bem vindas)
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
