require 'brcobranca'
require 'grape'


module BoletoApi

  def self.get_boleto(bank, values)
   clazz = Object.const_get("Brcobranca::Boleto::#{bank.camelize}")
   date_fields = %w[data_documento data_vencimento data_processamento]
   date_fields.each do |date_field|
      values[date_field] = Date.parse(values[date_field]) if values[date_field]
    end
    clazz.new(values)
  end

  def self.get_pagamento(values)
   date_fields = %w[data_vencimento data_emissao data_desconto data_segundo_desconto data_multa]
   date_fields.each do |date_field|
      values[date_field] = Date.parse(values[date_field]) if values[date_field]
    end
   values['data_vencimento'] ||= Date.current
   Brcobranca::Remessa::Pagamento.new(values)
  end

  class Server < Grape::API
    version 'v1', using: :header, vendor: 'Akretion'
    format :json
    prefix :api

    resource :boleto do

      desc 'Validate boleto data'
      # example of invalid attributes:
      # http://localhost:9292/api/boleto/validate?bank=itau&data=%7B%22valor%22:0.0,%22documento_cedente%22:%2212345678912%22,%22sacado%22:%22Claudio%20Pozzebom%22,%22sacado_documento%22:%2212345678900%22,%22conta_corrente%22:%2253678%22,%22convenio%22:12387,%22numero_documento%22:%2212345678%22%7D
      # boleto fields are listed here: https://github.com/kivanio/brcobranca/blob/master/lib/brcobranca/boleto/base.rb
      params do
        requires :bank, type: String, desc: 'Bank'
        requires :data, type: String, desc: 'Boleto data as a stringified json'
      end
      get :validate do
        values = JSON.parse(params[:data])
        boleto = BoletoApi.get_boleto(params[:bank], values)
        if boleto.valid?
          true
        else
          error!(boleto.errors.messages, 400)
        end
      end

      desc 'Generates boleto nosso_numero'
      # TODO do we also need an API endpoint for nosso_numero_dv?
      # example with Itau boleto with data from https://github.com/kivanio/brcobranca/blob/master/spec/brcobranca/boleto/itau_spec.rb:
      # http://localhost:9292/api/boleto/nosso_numero?bank=itau&data=%7B%22valor%22:0.0,%22cedente%22:%22Kivanio%20Barbosa%22,%22documento_cedente%22:%2212345678912%22,%22sacado%22:%22Claudio%20Pozzebom%22,%22sacado_documento%22:%2212345678900%22,%22agencia%22:%220810%22,%22conta_corrente%22:%2253678%22,%22convenio%22:12387,%22numero_documento%22:%2212345678%22%7D
      # boleto fields are listed here: https://github.com/kivanio/brcobranca/blob/master/lib/brcobranca/boleto/base.rb
      params do
        requires :bank, type: String, desc: 'Bank'
        requires :data, type: String, desc: 'Boleto data as a stringified json'
      end
      get :nosso_numero do
        values = JSON.parse(params[:data])
        boleto = BoletoApi.get_boleto(params[:bank], values)
        if boleto.valid?
          boleto.nosso_numero_boleto
        else
          error!(boleto.errors.messages, 400)
        end
      end

      desc 'Return a bolato image or pdf'
      # example of valid Itau boleto with data from https://github.com/kivanio/brcobranca/blob/master/spec/brcobranca/boleto/itau_spec.rb
      # http://localhost:9292/api/boleto?type=pdf&bank=itau&data=%7B%22valor%22:0.0,%22cedente%22:%22Kivanio%20Barbosa%22,%22documento_cedente%22:%2212345678912%22,%22sacado%22:%22Claudio%20Pozzebom%22,%22sacado_documento%22:%2212345678900%22,%22agencia%22:%220810%22,%22conta_corrente%22:%2253678%22,%22convenio%22:12387,%22numero_documento%22:%2212345678%22%7D
      # boleto fields are listed here: https://github.com/kivanio/brcobranca/blob/master/lib/brcobranca/boleto/base.rb
      params do
        requires :bank, type: String, desc: 'Bank'
        requires :type, type: String, desc: 'Type: pdf|jpg|png|tif'
        requires :data, type: String, desc: 'Boleto data as a stringified json'
      end
      get do
        values = JSON.parse(params[:data])
        boleto = BoletoApi.get_boleto(params[:bank], values)
        if boleto.valid?
          content_type "application/#{params[:type]}"
          header['Content-Disposition'] = "attachment; filename=boleto-#{params[:bank]}.#{params[:type]}"
          env['api.format'] = :binary
          boleto.send("to_#{params[:type]}".to_sym)
        else
          error!(boleto.errors.messages, 400)
        end
      end

      desc 'Return the image or pdf of a collection of boletos'
      # example of valid Itau boleto with data from https://github.com/kivanio/brcobranca/blob/master/spec/brcobranca/boleto/itau_spec.rb
      # and https://github.com/kivanio/brcobranca/blob/master/spec/brcobranca/boleto/caixa_spec.rb
      # echo '[{"valor":5.0,"cedente":"Kivanio Barbosa","documento_cedente":"12345678912","sacado":"Claudio Pozzebom","sacado_documento":"12345678900","agencia":"0810","conta_corrente":"53678","convenio":12387,"numero_documento":"12345678","bank":"itau"},{"valor": 10.00,"cedente": "PREFEITURA MUNICIPAL DE VILHENA","documento_cedente": "04092706000181","sacado": "João Paulo Barbosa","sacado_documento": "77777777777","agencia": "1825","conta_corrente": "0000528","convenio": "245274","numero_documento": "000000000000001","bank":"caixa"}]' > /tmp/boletos_data.json
      # curl -X POST -F type=pdf -F 'data=@/tmp/boletos_data.json' localhost:9292/api/boleto/multi > /tmp/boletos.pdf
      # boleto fields are listed here: https://github.com/kivanio/brcobranca/blob/master/lib/brcobranca/boleto/base.rb
      params do
        requires :type, type: String, desc: 'Type: pdf|jpg|png|tif'
        requires :data, type: File, desc: 'json of the list of boletos, including the "bank" key'
      end
      post :multi do
        values = JSON.parse(params[:data][:tempfile].read())
      	boletos = []
        errors = []
        values.each do |boleto_values|
          bank = "Brcobranca::Boleto::#{boleto_values.delete('bank').camelize}"
          boleto = BoletoApi.get_boleto(bank, boleto_values)
          if boleto.valid?
            boletos << boleto
          else
            errors << boleto.errors.messages
          end
        end
        if errors.empty?
          content_type "application/#{params[:type]}"
          header['Content-Disposition'] = "attachment; filename=boletos-#{params[:bank]}.#{params[:type]}"
          env['api.format'] = :binary
          Brcobranca::Boleto::Base.lote(boletos, formato: params[:type].to_sym)
        else
          error!(errors, 400)
        end
      end
    end

    resource :remessa do
      # example with data from https://github.com/kivanio/brcobranca/blob/master/spec/brcobranca/remessa/cnab400/itau_spec.rb
      # echo '{"carteira": "123","agencia": "1234","conta_corrente": "12345","digito_conta": "1","empresa_mae": "SOCIEDADE BRASILEIRA DE ZOOLOGIA LTDA","documento_cedente": "12345678910","pagamentos":[{"valor": 199.9,"data_vencimento": "Thu, 15 Jun 2017","nosso_numero": 123,"documento_sacado": "12345678901","nome_sacado": "PABLO DIEGO JOSÉ FRANCISCO DE PAULA JUAN NEPOMUCENO MARÍA DE LOS REMEDIOS CIPRIANO DE LA SANTÍSSIMA TRINIDAD RUIZ Y PICASSO","endereco_sacado": "RUA RIO GRANDE DO SUL São paulo Minas caçapa da silva junior","bairro_sacado": "São josé dos quatro apostolos magros","cep_sacado": "12345678","cidade_sacado": "Santa rita de cássia maria da silva","uf_sacado": "SP"}]}' > /tmp/remessa_data.json
      # curl -X POST -F type=cnab400 -F bank=itau -F 'data=@/tmp/remessa_data.json' localhost:9292/api/remessa
      # generic remessa fields are: https://github.com/kivanio/brcobranca/blob/master/lib/brcobranca/remessa/base.rb
      # cnab240 have these extra fields: https://github.com/kivanio/brcobranca/blob/master/lib/brcobranca/remessa/cnab240/base.rb
      # cnab400 have these extra fields: https://github.com/kivanio/brcobranca/blob/master/lib/brcobranca/remessa/cnab400/base.rb
      # the 'pagamentos'  items have these fields: https://github.com/kivanio/brcobranca/blob/master/lib/brcobranca/remessa/pagamento.rb
      params do
        requires :bank, type: String, desc: 'Bank'
        requires :type, type: String, desc: 'Type: cnab400|cnab240'
        requires :data, type: File, desc: 'json of the list of pagamentos'
      end
      post do
        values = JSON.parse(params[:data][:tempfile].read())
        pagamentos = []
      	errors = []
        values['pagamentos'].each do |pagamento_values|
          pagamento = BoletoApi.get_pagamento(pagamento_values)
          if pagamento.valid?
            pagamentos << pagamento
          else
            errors << pagamento.errors.messages
          end
        end
        if errors.empty?
          values[:pagamentos] = pagamentos
          clazz = Object.const_get("Brcobranca::Remessa::#{params[:type].camelize}::#{params[:bank].camelize}")
          remessa = clazz.new(values)
          if remessa.valid?
            env['api.format'] = :binary
            remessa.gera_arquivo()
          else
            [remessa.errors.messages] + errors
          end
        else
          error!(errors, 400)
        end
      end
    end

    # to avoid returning Ruby objects, we will read the payments fields from https://github.com/kivanio/brcobranca/blob/master/lib/brcobranca/retorno/base.rb
    RETORNO_FIELDS = [:codigo_registro,:codigo_ocorrencia,:data_ocorrencia,:agencia_com_dv,:agencia_sem_dv,:cedente_com_dv,:convenio,:nosso_numero,:codigo_ocorrencia,:data_ocorrencia,:tipo_cobranca,:tipo_cobranca_anterior,:natureza_recebimento,:carteira_variacao,:desconto,:iof,:carteira,:comando,:data_liquidacao,:data_vencimento,:valor_titulo,:banco_recebedor,:agencia_recebedora_com_dv,:especie_documento,:data_ocorrencia,:data_credito,:valor_tarifa,:outras_despesas,:juros_desconto,:iof_desconto,:valor_abatimento,:desconto_concedito,:valor_recebido,:juros_mora,:outros_recebimento,:abatimento_nao_aproveitado,:valor_lancamento,:indicativo_lancamento,:indicador_valor,:valor_ajuste,:sequencial,:arquivo,:outros_recebimento,:motivo_ocorrencia,:documento_numero]
    resource :retorno do
      # example:
      # wget -O /tmp/CNAB400ITAU.RET https://raw.githubusercontent.com/kivanio/brcobranca/master/spec/arquivos/CNAB400ITAU.RET
      # curl -X POST -F type=cnab400 -F bank=itau -F 'data=@/tmp/CNAB400ITAU.RET.txt' localhost:9292/api/retorno
      # the returned payment items have these fields: https://github.com/kivanio/brcobranca/blob/master/lib/brcobranca/retorno/base.rb
      params do
        requires :bank, type: String, desc: 'Bank'
        requires :type, type: String, desc: 'Type: cnab400|cnab240'
        requires :data, type: File, desc: 'txt of the retorno file'
      end
      post do
        data = params[:data][:tempfile]
        clazz = Object.const_get("Brcobranca::Retorno::#{params[:type].camelize}::#{params[:bank].camelize}")
        pagamentos = clazz.load_lines(data)
        pagamentos.map! do |p|
          Hash[RETORNO_FIELDS.map{|sym| [sym, p.send(sym)]}]
        end
        JSON.generate(pagamentos)
      end
    end
  end
end
