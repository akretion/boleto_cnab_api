# sobre o projeto boleto_cnab_api

O projeto de gestão de boletos, remessas e retornos bancarios https://github.com/kivanio/brcobranca é muito bem feito, bem testado e mantido.

E interessante poder usar o projeto brcobranca (escrito em Ruby) a partir de outras linguagens na forma de um micro-serviço REST.
Mais especificamente, a [Akretion](http://www.akretion.com) que é a empresa que lidera a localização do Odoo no Brasil desde 2009 https://github.com/OCA/l10n-brazil e co-criou a fundação OCA usa esse projeto para gerenciar boletos a partir do ERP Odoo (feito em Python).

# funcionalidades

Imprime *boletos*, gera arquivos de *remessa* e lê os arquivos de *retorno* nos formatos CNAB 240, CNAB 400 para os 15 principais bancos do Brasil (Banco do Brasil, Banco do Nordeste, Banco de Brasília, Banestes, Banrisul, Bradesco,Caixa, Citibank, HSBC, Itaú, Santander, Sicoob, Sicredi, UNICRED, CECRED, CREDISIS...)

# API

```ruby
# validar os dados de um boleto:
GET /boleto/validate
        requires :bank, type: String, desc: 'Bank'
        requires :data, type: String, desc: 'Boleto data as a stringified json'

# obter o nosso_numero de um boleto:
GET /boleto/nosso_numero
        requires :bank, type: String, desc: 'Bank'
        requires :data, type: String, desc: 'Boleto data as a stringified json'

# imprimir um boleto apenas:
GET /boleto/get
        requires :bank, type: String, desc: 'Bank'
        requires :type, type: String, desc: 'Type: pdf|jpg|png|tif'
        requires :data, type: String, desc: 'Boleto data as a stringified json'

# imprimir uma lista de boletos:
POST /boleto/multi
        requires :type, type: String, desc: 'Type: pdf|jpg|png|tif'
        requires :data, type: File, desc: 'json of the list of boletos, including the "bank" key'

# gerir um arquivo de remessa CNAB 240 ou CNAB 400:
POST /remessa
        requires :bank, type: String, desc: 'Bank'
        requires :type, type: String, desc: 'Type: cnab400|cnab240'
        requires :data, type: File, desc: 'json of the list of pagamentos'

# transformar um aqruivo de retorno CNAB 240 ou CNAB 400 em json:
POST /retorno
        requires :bank, type: String, desc: 'Bank'
        requires :type, type: String, desc: 'Type: cnab400|cnab240'
        requires :data, type: File, desc: 'txt of the retorno file'
 ```

Nota: os campos datas devem estar no formato YYYY/MM/DD

O API esta documentato com mais detalhes no codigo aqui: https://github.com/akretion/boleto_api/blob/master/lib/boleto_api.rb

# Como rodar o micro-serviço

```bash
git clone https://github.com/akretion/boleto_api.git
cd boleto_api
docker build -t akretion/boleto_api .
docker run -ti -p 9292:9292 akretion/boleto_api
```

# Examplos de como consumir o serviço usando sua linguagem preferida

## Bash

Por examplo, para imprimir uma lista de boletos é preciso criar um arquivo temporario com os boletos em formato json e depois fazer um POST do arquivo:
```bash
echo '[{"valor":5.0,"cedente":"Kivanio Barbosa","documento_cedente":"12345678912","sacado":"Claudio Pozzebom",\
"sacado_documento":"12345678900","agencia":"0810","conta_corrente":"53678","convenio":12387,"nosso_numero":"12345678","bank":"itau"},\
{"valor": 10.00,"cedente": "PREFEITURA MUNICIPAL DE VILHENA","documento_cedente": "04092706000181","sacado": "João Paulo Barbosa",\
"sacado_documento": "77777777777","agencia": "1825","conta_corrente": "0000528","convenio": "245274","nosso_numero": "000000000000001","bank":"caixa"}]'\
> /tmp/boletos_data.json
curl -X POST -F type=pdf -F 'data=@/tmp/boletos_data.json' localhost:9292/api/boleto/multi > /tmp/boletos.pdf
```
Vc pode então conferir os boletos gerados no arquivo ```/tmp/boletos.pdf```

## Python

```
TODO
```
(ver os examplos nos modulos Odoo: https://github.com/akretion/odoo-boleto-cnab)

## Java

```
TODO (contribuições bem vindas)
```
