$: << File.join(File.dirname(__FILE__), "/lib")
require 'boleto_api'
run BoletoApi::Server
