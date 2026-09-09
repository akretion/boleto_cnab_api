require 'rack/auth/basic'

# Optional API key authentication middleware.
#
# Enabled by setting the API_KEYS environment variable (comma-separated keys).
# When API_KEYS is unset the service stays open (previous behavior).
#
# Two ways to pass the key:
#   * X-Api-Key header — the same header AWS API Gateway uses for its API
#     keys, so a client (e.g. Odoo) configured with it works unchanged
#     against both a self-hosted container and the AWS-hosted service.
#   * HTTP Basic auth — any username, the key as password
#     (handy for curl -u and browsers).
class ApiKeyAuth
  def initialize(app, keys)
    @app = app
    @keys = keys
  end

  def call(env)
    key = env['HTTP_X_API_KEY']
    if key.nil? || key.empty?
      auth = Rack::Auth::Basic::Request.new(env)
      key = auth.credentials.last if auth.provided? && auth.basic?
    end

    return @app.call(env) if key && @keys.any? { |known| key_match?(known, key) }

    [
      401,
      {
        'content-type' => 'application/json',
        'www-authenticate' => 'Basic realm="boleto_cnab_api"'
      },
      ['{"error":"missing or invalid API key"}']
    ]
  end

  private

  def key_match?(known, given)
    known.bytesize == given.bytesize && Rack::Utils.secure_compare(known, given)
  end
end
