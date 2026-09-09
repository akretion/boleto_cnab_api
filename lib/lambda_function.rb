# frozen_string_literal: true

# AWS Lambda handler for the boleto_cnab_api Grape app.
#
# Translates an API Gateway "proxy integration" event into a Rack env,
# runs the existing Grape app through it, and returns the API Gateway
# response (binary responses base64-encoded with isBase64Encoded=true).
#
# In the Lambda container image the gem/app code lives under /var/task,
# RUBYLIB=/var/task/lib and the Runtime Interface Client (RIC) is pointed
# at this file via `CMD ["lambda_function.lambda_handler"]`.
#
# The exact same handler is exercised without Lambda by
# scripts/lambda_local_test.rb (a plain `lambda_handler(event:, context:)`
# call), which is also what CI runs inside the built image.

require 'base64'
require 'json'
require 'stringio'

# In the Lambda container the Runtime Interface Client does a bare
# `require 'lambda_function'` (no `bundle exec`), so activate the Gemfile to
# make brcobranca & co. resolvable from vendor/bundle. Idempotent when the
# process is already running under bundler (e.g. scripts/lambda_local_test.rb).
begin
  require 'bundler/setup'
rescue LoadError
  # no bundler available — gems must already be on the load path
end

lib_dir = __dir__ # this file lives in lib/, next to boleto_api.rb
$LOAD_PATH.unshift(lib_dir) unless $LOAD_PATH.include?(lib_dir)
require 'boleto_api'

module LambdaFunction
  module_function

  # Headers that should stay in the top-level Rack slots rather than HTTP_*.
  RACK_SPECIAL = %w[CONTENT_TYPE CONTENT_LENGTH].freeze

  def build_env(event)
    body = event['body'].to_s
    body = Base64.decode64(body) if event['isBase64Encoded']

    headers = event['headers'] || {}
    query = event['queryStringParameters'] || {}

    env = {
      'REQUEST_METHOD' => event['httpMethod'],
      'PATH_INFO' => event['path'] || '/',
      'QUERY_STRING' => Rack::Utils.build_query(query),
      'SCRIPT_NAME' => '',
      'SERVER_NAME' => headers['host'] || 'lambda',
      'SERVER_PORT' => (headers['x-forwarded-port'] || '443').to_s,
      'SERVER_PROTOCOL' => 'HTTP/1.1',
      'rack.input' => StringIO.new(body.b),
      'rack.errors' => $stderr,
      'rack.version' => Rack::VERSION,
      'rack.url_scheme' => headers['x-forwarded-proto'] || 'https'
    }

    headers.each do |key, value|
      name = key.upcase.tr('-', '_')
      next if name == 'HOST'
      if RACK_SPECIAL.include?(name)
        env[name] = value
      else
        env["HTTP_#{name}"] = value
      end
    end

    # rack.input must always match the actual body size (Rack::Multipart relies
    # on it); override any client-supplied value.
    env['CONTENT_LENGTH'] = body.bytesize.to_s

    env
  end

  def lambda_handler(event:, context:)
    env = build_env(event)
    status, headers, body = BoletoApi::Server.call(env)

    body_str = +''
    if body.respond_to?(:each)
      body.each { |chunk| body_str << chunk }
    else
      body_str = body.to_s
    end
    body_str = body_str.b

    binary = binary_response?(headers)
    response = {
      'statusCode' => status,
      'headers' => stringify_headers(headers)
    }
    if binary
      response['body'] = Base64.strict_encode64(body_str)
      response['isBase64Encoded'] = true
    else
      response['body'] = body_str.force_encoding(Encoding::UTF_8)
    end
    response
  end

  def stringify_headers(headers)
    headers.each_with_object({}) do |(key, value), hash|
      hash[key.to_s] = value.to_s
    end
  end

  def binary_response?(headers)
    content_type = nil
    headers.each do |key, value|
      content_type = value.to_s if key.to_s.downcase == 'content-type'
    end
    # endpoints that set env['api.format'] = :binary without an explicit
    # content_type (e.g. /remessa) yield an empty one — still binary bytes
    return true if content_type.nil? || content_type.empty?

    content_type.match?(%r{application/pdf|image/|application/octet-stream})
  end
end
