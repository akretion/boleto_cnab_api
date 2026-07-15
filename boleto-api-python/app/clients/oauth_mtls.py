# Cliente HTTP genérico: OAuth2 client_credentials POR CIMA de mTLS.
#
# Serve C6 e Sicoob (mesma família). Diferenças absorvidas por parâmetro:
#   - scopes (Sicoob exige; C6 não)
#   - default_headers (Sicoob manda `client_id` em toda request)
#
# mTLS: o certificado do tenant vem como PKCS12 (.pfx) base64 + senha. Python/ssl
# não carrega PKCS12 direto — extraímos cert+key com `cryptography` e montamos um
# SSLContext em arquivos temporários (em memória/efêmeros), nunca persistidos.
from __future__ import annotations

import base64
import ssl
import tempfile
import time
from typing import Any

import httpx
from cryptography.hazmat.primitives.serialization import (
    Encoding,
    NoEncryption,
    PrivateFormat,
    pkcs12,
)


class OAuthMtlsClient:
    # cache de token em memória, por (client_id, base_url). Não é persistência
    # de credencial — só do access_token vivo.
    _token_cache: dict[tuple[str, str], dict[str, Any]] = {}

    def __init__(
        self,
        *,
        base_url: str,
        auth_url: str,
        client_id: str,
        client_secret: str,
        pfx_base64: str,
        pfx_password: str = "",
        scopes: list[str] | None = None,
        default_headers: dict[str, str] | None = None,
        timeout: float = 30.0,
        static_token: str = "",
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.auth_url = auth_url
        self.client_id = client_id
        self.client_secret = client_secret
        self.scopes = scopes or []
        # Sandbox de alguns bancos (ex.: Sicoob) usa token ESTÁTICO do portal,
        # sem o fluxo OAuth: se informado, token() o devolve direto.
        self.static_token = static_token
        self.default_headers = default_headers or {}
        self._ssl = self._build_ssl_context(pfx_base64, pfx_password)
        self._timeout = timeout

    # --- auth ---------------------------------------------------------------
    def token(self) -> str:
        if self.static_token:
            return self.static_token
        key = (self.client_id, self.base_url)
        cached = self._token_cache.get(key)
        if cached and cached["expires_at"] > time.time() + 30:
            return cached["access_token"]
        return self._authenticate()

    def _authenticate(self) -> str:
        data = {
            "grant_type": "client_credentials",
            "client_id": self.client_id,
            "client_secret": self.client_secret,
        }
        if self.scopes:
            data["scope"] = " ".join(self.scopes)
        with httpx.Client(verify=self._ssl, timeout=self._timeout) as c:
            r = c.post(self.auth_url, data=data)
            r.raise_for_status()
            body = r.json()
        access_token = body.get("access_token")
        if not access_token:
            raise RuntimeError("OAuth sem access_token")
        self._token_cache[(self.client_id, self.base_url)] = {
            "access_token": access_token,
            "expires_at": time.time() + int(body.get("expires_in", 300)),
        }
        return access_token

    # --- request ------------------------------------------------------------
    def request(
        self,
        method: str,
        path: str,
        json: Any = None,
        params: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        headers = {
            "Authorization": f"Bearer {self.token()}",
            "Content-Type": "application/json",
            **self.default_headers,
        }
        url = f"{self.base_url}{path}"
        with httpx.Client(verify=self._ssl, timeout=self._timeout) as c:
            r = c.request(method, url, json=json, params=params, headers=headers)
            r.raise_for_status()
            if not r.content:
                return {}
            try:
                return r.json()
            except ValueError:  # 2xx com corpo não-JSON (ex.: mocks de sandbox)
                return {"conteudo": r.text}

    # --- mTLS helper --------------------------------------------------------
    @staticmethod
    def _build_ssl_context(pfx_base64: str, pfx_password: str) -> ssl.SSLContext:
        ctx = ssl.create_default_context()
        if not pfx_base64:
            return ctx
        key, cert, _chain = pkcs12.load_key_and_certificates(
            base64.b64decode(pfx_base64),
            pfx_password.encode() if pfx_password else None,
        )
        # Arquivos efêmeros só para o load_cert_chain; removidos em seguida.
        with tempfile.NamedTemporaryFile(suffix=".pem") as cf, \
             tempfile.NamedTemporaryFile(suffix=".pem") as kf:
            cf.write(cert.public_bytes(Encoding.PEM))
            cf.flush()
            kf.write(key.private_bytes(Encoding.PEM, PrivateFormat.TraditionalOpenSSL, NoEncryption()))
            kf.flush()
            ctx.load_cert_chain(certfile=cf.name, keyfile=kf.name)
        return ctx
