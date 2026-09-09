# frozen_string_literal: true

# Local exercise of the AWS Lambda handler (lib/lambda_function.rb) without
# Docker or Lambda: builds API Gateway proxy events for every endpoint and
# calls lambda_handler directly. The assertions reuse the same upstream
# BRCobranca fixtures as test/curl_tests.sh.
#
# Usage:
#   bundle exec ruby scripts/lambda_local_test.rb
#
# On Termux/Android (where rghost does not auto-detect ghostscript) pass the
# binary explicitly:
#   GHOSTSCRIPT_PATH=/data/data/com.termux/files/usr/bin/gs \
#     bundle exec ruby scripts/lambda_local_test.rb

lib = File.expand_path('../lib', __dir__)
$LOAD_PATH.unshift(lib) unless $LOAD_PATH.include?(lib)

require 'base64'
require 'json'
require 'shellwords'

# Termux-only helper: rghost's platform detection does not know
# "linux-android"; GHOSTSCRIPT_PATH is only ever read here, never from the
# app itself (in the Alpine/Lambda images ghostscript is found normally).
if ENV['GHOSTSCRIPT_PATH']
  require 'rghost'
  RGhost::Config::GS[:path] = ENV['GHOSTSCRIPT_PATH']
end

require 'lambda_function'

@failures = 0

def check(desc)
  yield
  puts "PASS: #{desc}"
rescue StandardError => e
  puts "FAIL: #{desc}"
  puts "      #{e.class}: #{e.message}"
  e.backtrace.first(6).each { |l| puts "      #{l}" }
  @failures += 1
end

def assert_eq(desc, expected, actual)
  if actual == expected
    puts "PASS: #{desc}"
  else
    puts "FAIL: #{desc}"
    puts "      expected: #{expected.inspect}"
    puts "      actual:   #{actual.inspect}"
    @failures += 1
  end
end

# --- event builders -------------------------------------------------------

def get_event(path, query)
  {
    'httpMethod' => 'GET',
    'path' => path,
    'queryStringParameters' => query,
    'headers' => { 'host' => 'lambda.example', 'x-forwarded-proto' => 'https' },
    'isBase64Encoded' => false
  }
end

def multipart_event(path, fields, files)
  boundary = "----BoletoCnabApi#{rand(1_000_000)}"
  body = +''
  fields.each do |name, value|
    body << "--#{boundary}\r\n"
    body << "Content-Disposition: form-data; name=\"#{name}\"\r\n\r\n"
    body << "#{value}\r\n"
  end
  files.each do |name, filename, content|
    body << "--#{boundary}\r\n"
    body << "Content-Disposition: form-data; name=\"#{name}\"; filename=\"#{filename}\"\r\n"
    body << "Content-Type: application/octet-stream\r\n\r\n"
    body << content << "\r\n"
  end
  body << "--#{boundary}--\r\n"

  {
    'httpMethod' => 'POST',
    'path' => path,
    'headers' => {
      'host' => 'lambda.example',
      'x-forwarded-proto' => 'https',
      'content-type' => "multipart/form-data; boundary=#{boundary}"
    },
    'body' => Base64.strict_encode64(body),
    'isBase64Encoded' => true
  }
end

# --- fixtures (same data as test/curl_tests.sh) ----------------------------

BOLETO_ITAU_DATA = {
  'valor' => 5.0,
  'cedente' => 'Kivanio Barbosa',
  'documento_cedente' => '12345678912',
  'sacado' => 'Claudio Pozzebom',
  'sacado_documento' => '12345678900',
  'agencia' => '0810',
  'conta_corrente' => '53678',
  'convenio' => 12_387,
  'nosso_numero' => '12345678',
  'data_vencimento' => '2026/12/31',
  'data_documento' => '2026/09/01',
  'data_processamento' => '2026/09/01'
}.freeze

BOLETO_CAIXA_DATA = {
  'valor' => 10.00,
  'cedente' => 'PREFEITURA MUNICIPAL DE VILHENA',
  'documento_cedente' => '04092706000181',
  'sacado' => 'João Paulo Barbosa',
  'sacado_documento' => '77777777777',
  'agencia' => '1825',
  'conta_corrente' => '0000528',
  'convenio' => '245274',
  'nosso_numero' => '000000000000001'
}.freeze

# --- helpers ---------------------------------------------------------------

# Run the handler and return the parsed response (body kept as raw string;
# callers JSON.parse it when the endpoint is expected to return JSON).
def invoke(event)
  LambdaFunction.lambda_handler(event: event, context: nil)
end

def json_body(response)
  JSON.parse(response['body'])
end

# --- tests -----------------------------------------------------------------

puts '== Boleto =='

response = invoke(get_event('/api/boleto/validate', 'bank' => 'itau', 'data' => JSON.generate(BOLETO_ITAU_DATA)))
assert_eq('validate returns true for valid itau boleto', 200, response['statusCode'])
assert_eq('validate body is true', true, json_body(response))

invalid = BOLETO_ITAU_DATA.merge('agencia' => '12345')
response = invoke(get_event('/api/boleto/validate', 'bank' => 'itau', 'data' => JSON.generate(invalid)))
assert_eq('validate returns 400 for invalid boleto (5-digit agencia)', 400, response['statusCode'])

response = invoke(get_event('/api/boleto/nosso_numero', 'bank' => 'itau', 'data' => JSON.generate(BOLETO_ITAU_DATA)))
assert_eq('nosso_numero for itau boleto', 200, response['statusCode'])
assert_eq('nosso_numero value', '175/12345678-4', json_body(response))

response = invoke(get_event('/api/boleto', 'bank' => 'itau', 'type' => 'pdf', 'data' => JSON.generate(BOLETO_ITAU_DATA)))
assert_eq('single itau boleto served as PDF', 200, response['statusCode'])
assert_eq('PDF is base64-encoded', true, response['isBase64Encoded'])
pdf = Base64.strict_decode64(response['body'])
assert_eq('PDF magic bytes', '%PDF', pdf[0, 4])
check('single itau boleto PDF is non-empty') { raise 'too small' if pdf.bytesize < 10_000 }

response = invoke(get_event('/api/boleto', 'bank' => 'caixa', 'type' => 'png', 'data' => JSON.generate(BOLETO_CAIXA_DATA)))
assert_eq('single caixa boleto served as PNG', 200, response['statusCode'])
assert_eq('PNG is base64-encoded', true, response['isBase64Encoded'])
png = Base64.strict_decode64(response['body'])
assert_eq('PNG magic bytes', "\x89PNG".b, png[0, 4])

boletos = [BOLETO_ITAU_DATA.merge('bank' => 'itau'), BOLETO_CAIXA_DATA.merge('bank' => 'caixa')]
response = invoke(multipart_event('/api/boleto/multi', { 'type' => 'pdf' }, [['data', 'boletos_data.json', JSON.generate(boletos)]]))
assert_eq('multi boletos served as PDF', 201, response['statusCode'])
check('multi boletos PDF is a valid non-empty PDF') do
  multi_pdf = Base64.strict_decode64(response['body'])
  raise 'bad magic bytes' unless multi_pdf[0, 4] == '%PDF'
  raise 'too small' if multi_pdf.bytesize < 10_000
end

puts '== Remessa =='

remessa_data = {
  'carteira' => '123',
  'agencia' => '1234',
  'conta_corrente' => '12345',
  'digito_conta' => '1',
  'empresa_mae' => 'SOCIEDADE BRASILEIRA GNU LTDA',
  'documento_cedente' => '12345678910',
  'pagamentos' => [{
    'valor' => 199.9,
    'data_vencimento' => '2026/06/15',
    'nosso_numero' => 123,
    'documento' => 6969,
    'documento_sacado' => '12345678901',
    'nome_sacado' => 'PABLO DIEGO JOSE FRANCISCO DE PAULA JUAN NEPOMUCENO MARIA DE LOS REMEDIOS CIPRIANO DE LA SANTISSIMA TRINIDAD RUIZ Y PICASSO',
    'endereco_sacado' => 'RUA RIO GRANDE DO SUL Sao paulo Minas cacapa da silva junior',
    'bairro_sacado' => 'Sao jose dos quatro apostolos magros',
    'cep_sacado' => '12345678',
    'cidade_sacado' => 'Santa rita de cassia maria da silva',
    'uf_sacado' => 'SP'
  }]
}

response = invoke(multipart_event('/api/remessa', { 'bank' => 'itau', 'type' => 'cnab400' }, [['data', 'remessa_data.json', JSON.generate(remessa_data)]]))
assert_eq('remessa cnab400 itau status', 201, response['statusCode'])
rem400 = Base64.strict_decode64(response['body'])
check('remessa cnab400 itau generated') { raise 'bad header' unless rem400.start_with?('01REMESSA') && rem400.bytesize > 400 }
check('remessa cnab400 itau has 400-char lines') do
  lines = rem400.delete("\r").split("\n")
  raise 'bad line length' if lines.any? { |l| l.start_with?('02') && l.bytesize != 400 }
end

remessa240_data = {
  'empresa_mae' => 'EMPRESA TESTE LTDA',
  'documento_cedente' => '28254225000193',
  'agencia' => '1234',
  'conta_corrente' => '12345',
  'carteira' => '175',
  'sequencial_remessa' => '1',
  'pagamentos' => [{
    'valor' => 123.45,
    'data_vencimento' => '2026/06/15',
    'nosso_numero' => 12_345_678,
    'documento' => 9999,
    'documento_sacado' => '12345679',
    'nome_sacado' => 'PABLO DIEGO JOSE FRANCISCO DE PAULA JUAN NEPOMUCENO MARIA DE LOS REMEDIOS CIPRIANO DE LA SANTISSIMA TRINIDAD RUIZ Y PICASSO',
    'endereco_sacado' => 'RUA RIO GRANDE DO SUL Sao paulo Minas cacapa da silva junior',
    'bairro_sacado' => 'Sao jose dos quatro apostolos magros',
    'cep_sacado' => '12345678',
    'cidade_sacado' => 'Santa rita de cassia maria da silva',
    'uf_sacado' => 'SP',
    'numero' => '123',
    'codigo_baixa' => '3',
    'dias_baixa' => '0'
  }]
}

response = invoke(multipart_event('/api/remessa', { 'bank' => 'itau', 'type' => 'cnab240' }, [['data', 'remessa_data_cnab240.json', JSON.generate(remessa240_data)]]))
if response['statusCode'] == 201
  rem240 = Base64.strict_decode64(response['body'])
  check('remessa cnab240 itau generated') { raise 'bad header' unless rem240.start_with?('341') && rem240.bytesize > 1400 }
  check('remessa cnab240 itau 240-char CRLF lines') { raise 'bad CRLF' unless rem240[240, 2] == "\r\n" }
else
  puts "SKIP: remessa cnab240 itau (HTTP #{response['statusCode']}) requires BRCobranca >= 13.0.0"
end

puts '== Retorno =='

retorno_file = File.expand_path('retorno.tmp', __dir__)
begin
  system("wget -q -O #{Shellwords.escape(retorno_file)} https://raw.githubusercontent.com/kivanio/brcobranca/master/spec/arquivos/CNAB400ITAU.RET") or raise 'wget failed'
  retorno = File.binread(retorno_file)
  response = invoke(multipart_event('/api/retorno', { 'bank' => 'itau', 'type' => 'cnab400' }, [['data', 'CNAB400ITAU.RET', retorno]]))
  assert_eq('retorno cnab400 itau status', 201, response['statusCode'])
  payments = json_body(response)
  assert_eq('retorno cnab400 itau returns 53 pagamentos', 53, payments.length)
  assert_eq('retorno first nosso_numero', '00000011', payments[0]['nosso_numero'])
  assert_eq('retorno first codigo_ocorrencia', '06', payments[0]['codigo_ocorrencia'])
ensure
  File.delete(retorno_file) if File.exist?(retorno_file)
end

puts
if @failures.zero?
  puts 'ALL LAMBDA HANDLER CHECKS PASSED'
else
  puts "#{@failures} CHECK(S) FAILED"
  exit 1
end
