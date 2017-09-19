# boleto API

O projeto de gestão de boletos, remessas e retornos bancarios https://github.com/kivanio/brcobranca é muito bem feito, bem testado e mantido.

E interessante poder usar o projeto brcobranca a partir de outras linguagens na forma de uma micro-serviço REST. Mais especificamente, a [Akretion](http://www.akretion.com) que é a empresa que lidera a localização do Odoo no Brasil desde 2009 https://github.com/OCA/l10n-brazil e co-criou a fundação OCA usa esse projeto para gerenciar boletos a partir do ERP Odoo (feito em Python).

# Como testar

```
git clone https://github.com/akretion/boleto_api.git
cd boleto_api
docker build -t akretion/boleto_api .
docker run -ti -p 9292:9292 akretion/boleto_api
```

Depois usar o navegador, ou CURL para testar o API assim que documentado no codigo https://github.com/akretion/boleto_api/blob/master/lib/boleto_api.rb

Por examplo, para imprimir uma lista de boletos é preciso criar um arquivo temporario com os boletos em formato json e depois fazer um POST do arquivo:
```
echo '[{"valor":5.0,"cedente":"Kivanio Barbosa","documento_cedente":"12345678912","sacado":"Claudio Pozzebom","sacado_documento":"12345678900","agencia":"0810","conta_corrente":"53678","convenio":12387,"numero_documento":"12345678","bank":"itau"},{"valor": 10.00,"cedente": "PREFEITURA MUNICIPAL DE VILHENA","documento_cedente": "04092706000181","sacado": "João Paulo Barbosa","sacado_documento": "77777777777","agencia": "1825","conta_corrente": "0000528","convenio": "245274","numero_documento": "000000000000001","bank":"caixa"}]' > /tmp/boletos_data.json
curl -X POST -F type=pdf -F 'data=@/tmp/boletos_data.json' localhost:9292/api/boleto/multi > /tmp/boletos.pdf
```
Vc pode então conferir os boletos gerados no arquivo ```/tmp/boletos.pdf```

Nota: campos de datas devem estar no formato YYYY/MM/DD
