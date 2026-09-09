# frozen_string_literal: true

# Generates docs/openapi.json from the live Grape API definition,
# without booting a server (uses a Rack mock request).
#
# Usage:
#   bundle exec ruby scripts/generate_openapi.rb
#
# The generated file is published as interactive documentation by the
# GitHub Pages site in docs/ (see docs/index.html).

$LOAD_PATH << File.expand_path('../lib', __dir__)

require 'boleto_api'
require 'rack/mock'
require 'json'
require 'fileutils'

response = Rack::MockRequest.new(BoletoApi::Server).get('/api/swagger_doc')
abort "swagger_doc endpoint failed: HTTP #{response.status}\n#{response.body}" unless response.status == 200

spec = JSON.parse(response.body)
# no public default server: the service is self-hosted, so a static "host"
# (the mock request's example.org) would only mislead the docs readers
spec.delete('host')

output = File.expand_path('../docs/openapi.json', __dir__)
FileUtils.mkdir_p(File.dirname(output))
File.write(output, "#{JSON.pretty_generate(spec)}\n")
puts "wrote #{output}"
