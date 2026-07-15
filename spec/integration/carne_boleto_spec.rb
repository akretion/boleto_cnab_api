# frozen_string_literal: true

require 'spec_helper'

RSpec.describe 'Carnê e tema visual (templates Prawn)' do
  let(:fixtures) { JSON.parse(File.read('spec/fixtures/sample_data.json')) }
  let(:base) { fixtures['sicoob_valido'] }

  def pdf?(body)
    body.bytes[0..3] == [0x25, 0x50, 0x44, 0x46] # %PDF
  end

  describe 'template=carne' do
    it 'gera carnê em PDF para um boleto' do
      get '/api/boleto', { bank: 'sicoob', type: 'pdf', template: 'carne', data: base.to_json }

      expect(last_response.status).to eq(200)
      expect(pdf?(last_response.body)).to be(true)
    end

    it 'rejeita formato não-PDF para o carnê' do
      get '/api/boleto', { bank: 'sicoob', type: 'png', template: 'carne', data: base.to_json }

      expect(last_response.status).to eq(400)
    end

    it 'gera carnê em lote (3 vias por A4) via /multi' do
      boletos = [
        base.merge('bank' => 'sicoob', 'parcela_atual' => 1, 'total_parcelas' => 3),
        base.merge('bank' => 'sicoob', 'parcela_atual' => 2, 'total_parcelas' => 3),
        base.merge('bank' => 'sicoob', 'parcela_atual' => 3, 'total_parcelas' => 3)
      ]
      file = Rack::Test::UploadedFile.new(
        StringIO.new(boletos.to_json), 'application/json', original_filename: 'carne.json'
      )

      post '/api/boleto/multi', { type: 'pdf', template: 'carne', data: file }

      expect(last_response.status).to eq(200)
      expect(pdf?(last_response.body)).to be(true)
    end
  end

  describe 'tema visual no template prawn' do
    let(:tematizado) do
      base.merge(
        'cor_marca' => '006B3F',
        'marca_dagua' => 'CÓPIA - SEM VALOR FISCAL',
        'rodape_contato' => 'Empresa Lagoa Real • (71) 3333-0000',
        'parcela_atual' => 1,
        'total_parcelas' => 12
      )
    end

    it 'aceita campos de tema na validação (sem quebrar)' do
      get '/api/boleto/validate', { bank: 'sicoob', data: tematizado.to_json }

      expect(last_response.status).to eq(200)
      expect(JSON.parse(last_response.body)['valid']).to be(true)
    end

    it 'gera PDF prawn com campos de tema' do
      get '/api/boleto', { bank: 'sicoob', type: 'pdf', template: 'prawn', data: tematizado.to_json }

      expect(last_response.status).to eq(200)
      expect(pdf?(last_response.body)).to be(true)
    end
  end
end
