# frozen_string_literal: true

require 'spec_helper'
require 'base64'

# Testes de integração dos endpoints de renderização (engine BrCobrança)
# consumidos pelo Boleto-API (Python) via brcobranca_proxy.
#
# POST /api/render/boleto  -> dados + PDF base64
# POST /api/render/carne   -> PDF base64 multi-boleto (sem GhostScript)
# POST /api/render/remessa -> CNAB texto
RSpec.describe 'Render API', type: :integration do
  let(:boleto_data) do
    {
      'valor' => 100.0,
      'cedente' => 'Empresa X',
      'documento_cedente' => '12345678000123',
      'sacado' => 'Fulano',
      'sacado_documento' => '12345678901',
      'agencia' => '1234',
      'conta_corrente' => '12345',
      'carteira' => '175',
      'nosso_numero' => '1'
    }
  end

  def post_json(path, payload)
    post path, payload.to_json, 'CONTENT_TYPE' => 'application/json'
  end

  describe 'POST /api/render/boleto' do
    it 'retorna dados do boleto + PDF base64' do
      post_json('/api/render/boleto', { bank: 'itau', data: boleto_data })

      expect(last_response.status).to eq(201)
      body = JSON.parse(last_response.body)
      expect(body['linha_digitavel']).to be_a(String)
      expect(body['codigo_barras']).to be_a(String)
      expect(body['nosso_numero']).not_to be_nil
      expect(Base64.decode64(body['pdf_base64'])).to start_with('%PDF')
    end

    it 'retorna 400 para dados inválidos' do
      post_json('/api/render/boleto', { bank: 'itau', data: { 'valor' => 100.0 } })
      expect(last_response.status).to eq(400)
    end

    it 'retorna erro para banco não suportado' do
      post_json('/api/render/boleto', { bank: 'banco_inexistente', data: boleto_data })
      expect(last_response.status).to be >= 400
    end
  end

  describe 'POST /api/render/carne' do
    it 'gera carnê 3-vias A4 (template padrão carne) em PDF' do
      post_json('/api/render/carne', {
                  bank: 'itau',
                  boletos: [boleto_data.merge('nosso_numero' => '1'),
                            boleto_data.merge('nosso_numero' => '2'),
                            boleto_data.merge('nosso_numero' => '3')]
                })

      expect(last_response.status).to eq(201)
      body = JSON.parse(last_response.body)
      expect(Base64.decode64(body['pdf_base64'])).to start_with('%PDF')
    end

    it 'gera PDF multi-página com template prawn' do
      post_json('/api/render/carne', {
                  bank: 'itau', template: 'prawn',
                  boletos: [boleto_data.merge('nosso_numero' => '1'), boleto_data.merge('nosso_numero' => '2')]
                })

      expect(last_response.status).to eq(201)
      expect(Base64.decode64(JSON.parse(last_response.body)['pdf_base64'])).to start_with('%PDF')
    end
  end

  describe 'POST /api/render/remessa' do
    let(:remessa_data) do
      {
        'carteira' => '123', 'agencia' => '1234', 'conta_corrente' => '12345', 'digito_conta' => '1',
        'empresa_mae' => 'EMPRESA TESTE LTDA', 'documento_cedente' => '12345678910',
        'pagamentos' => [{
          'valor' => 199.90, 'data_vencimento' => '2026-07-15', 'nosso_numero' => 123,
          'documento_sacado' => '12345678901', 'nome_sacado' => 'Cliente Teste',
          'endereco_sacado' => 'Rua Teste, 123', 'bairro_sacado' => 'Centro',
          'cep_sacado' => '12345678', 'cidade_sacado' => 'Sao Paulo', 'uf_sacado' => 'SP'
        }]
      }
    end

    it 'gera o conteúdo CNAB' do
      post_json('/api/render/remessa', { bank: 'itau', type: 'cnab400', data: remessa_data })

      expect(last_response.status).to eq(201)
      body = JSON.parse(last_response.body)
      expect(body['cnab']).to include('REMESSA')
    end

    it 'retorna 400 para tipo CNAB inválido' do
      post_json('/api/render/remessa', { bank: 'itau', type: 'cnab999', data: remessa_data })
      expect(last_response.status).to eq(400)
    end
  end
end
