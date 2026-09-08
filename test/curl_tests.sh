#!/usr/bin/env bash
# Basic curl-based smoke tests for the boleto_cnab_api REST service.
#
# Usage:
#   ./curl_tests.sh [BASE_URL]     # default: http://localhost:9292
#
# Exit code is non-zero if any check fails.
#
# The test payloads below reproduce the exact data used by the upstream
# BRCobranca RSpec suite (https://github.com/kivanio/brcobranca), so the
# assertions remain meaningful (expected nosso_numero, barcode layout,
# CNAB line lengths, etc.) instead of just checking for HTTP 200.
set -u
BASE_URL="${1:-http://localhost:9292}"
API="$BASE_URL/api"
FAILURES=0
export WORK=$(mktemp -d)
trap 'rm -rf "$WORK"' EXIT

check() {
    local desc="$1"; shift
    local out
    if out=$("$@" 2>&1); then
        echo "PASS: $desc"
    else
        echo "FAIL: $desc"
        if [ -n "$out" ]; then
            printf '%s\n' "$out" | sed 's/^/      /'
        fi
        FAILURES=$((FAILURES + 1))
    fi
}

check_eq() {
    local desc="$1" expected="$2" actual="$3"
    if [ "$actual" = "$expected" ]; then
        echo "PASS: $desc"
    else
        echo "FAIL: $desc"
        echo "      expected: $expected"
        echo "      actual:   $actual"
        FAILURES=$((FAILURES + 1))
    fi
}

echo "== Boleto =="
# Data from https://github.com/kivanio/brcobranca/blob/master/spec/brcobranca/boleto/itau_spec.rb
BOLETO_ITAU_DATA='{"valor":5.0,"cedente":"Kivanio Barbosa","documento_cedente":"12345678912","sacado":"Claudio Pozzebom","sacado_documento":"12345678900","agencia":"0810","conta_corrente":"53678","convenio":12387,"nosso_numero":"12345678","data_vencimento":"2026/12/31","data_documento":"2026/09/01","data_processamento":"2026/09/01"}'

# Data from https://github.com/kivanio/brcobranca/blob/master/spec/brcobranca/boleto/caixa_spec.rb
BOLETO_CAIXA_DATA='{"valor":10.00,"cedente":"PREFEITURA MUNICIPAL DE VILHENA","documento_cedente":"04092706000181","sacado":"João Paulo Barbosa","sacado_documento":"77777777777","agencia":"1825","conta_corrente":"0000528","convenio":"245274","nosso_numero":"000000000000001"}'

# /api/boleto/validate: valid data -> body true
VALIDATE=$(curl -sS -G "$API/boleto/validate" --data-urlencode "bank=itau" --data-urlencode "data=$BOLETO_ITAU_DATA")
check_eq "validate returns true for valid itau boleto" "true" "$VALIDATE"

# /api/boleto/validate: invalid data -> 400 + error messages
# 5-digit agencia is the upstream spec's own invalid case ("Agencia deve ter
# 4 dígitos."); blank values would NOT fail because brcobranca left-pads them
HTTP_CODE=$(curl -sS -o "$WORK/invalid.json" -w '%{http_code}' -G "$API/boleto/validate" \
    --data-urlencode 'bank=itau' \
    --data-urlencode 'data={"valor":0.0,"cedente":"Kivanio Barbosa","documento_cedente":"12345678912","sacado":"Claudio Pozzebom","sacado_documento":"12345678900","agencia":"12345","conta_corrente":"53678","convenio":12387,"nosso_numero":"12345678"}')
check_eq "validate returns HTTP 400 for invalid boleto (5-digit agencia, per upstream spec)" "400" "$HTTP_CODE"
check "validate error body mentions the invalid fields" bash -c 'grep -qi "agencia" "$WORK/invalid.json" || { cat "$WORK/invalid.json"; exit 1; }'

# /api/boleto/nosso_numero: upstream spec expects 175/12345678-4
# (carteira 175 default; formula: carteira/nosso_numero-nosso_numero_dv)
NN=$(curl -sS -G "$API/boleto/nosso_numero" --data-urlencode "bank=itau" --data-urlencode "data=$BOLETO_ITAU_DATA")
check_eq "nosso_numero for itau boleto (carteira/numero-dv)" '"175/12345678-4"' "$NN"

# /api/boleto (single boleto)
HTTP_TYPE=$(curl -sS -o "$WORK/boleto_itau.pdf" -w '%{content_type}' -G "$API/boleto" \
    --data-urlencode "bank=itau" --data-urlencode "type=pdf" --data-urlencode "data=$BOLETO_ITAU_DATA")
check_eq "single itau boleto is served as PDF" "application/pdf" "$HTTP_TYPE"
check "single itau boleto PDF is a non-empty PDF (magic bytes)" bash -c "head -c 4 '$WORK/boleto_itau.pdf' | grep -q '%PDF' && test \$(stat -c %s '$WORK/boleto_itau.pdf') -gt 10000"

HTTP_TYPE=$(curl -sS -o "$WORK/boleto_caixa.png" -w '%{content_type}' -G "$API/boleto" \
    --data-urlencode "bank=caixa" --data-urlencode "type=png" --data-urlencode "data=$BOLETO_CAIXA_DATA")
check_eq "single caixa boleto is served as PNG" "image/png" "$HTTP_TYPE"
check "single caixa boleto PNG magic bytes" bash -c "head -c 4 '$WORK/boleto_caixa.png' | grep -qa 'PNG'"

# /api/boleto/multi: 2 boletos (itau + caixa) in one PDF
cat > "$WORK/boletos_data.json" <<EOF
[{"valor":5.0,"cedente":"Kivanio Barboza","documento_cedente":"12345678912","sacado":"Claudio Pozzebom","sacado_documento":"12345678900","agencia":"0810","conta_corrente":"53678","convenio":12387,"nosso_numero":"12345678","bank":"itau"},
{"valor":10.00,"cedente":"PREFEITURA MUNICIPAL DE VILHENA","documento_cedente":"04092706000181","sacado":"João Paulo Barbosa","sacado_documento":"77777777777","agencia":"1825","conta_corrente":"0000528","convenio":"245274","nosso_numero":"000000000000001","bank":"caixa"}]
EOF
HTTP_TYPE=$(curl -sS -o "$WORK/boletos.pdf" -w '%{content_type}' -X POST -F type=pdf -F "data=@$WORK/boletos_data.json" "$API/boleto/multi")
check_eq "multi boletos are served as PDF" "application/pdf" "$HTTP_TYPE"
check "multi boletos PDF is a non-empty PDF (magic bytes)" bash -c "head -c 4 '$WORK/boletos.pdf' | grep -q '%PDF' && test \$(stat -c %s '$WORK/boletos.pdf') -gt 10000"

echo "== Remessa =="
# Data from https://github.com/kivanio/brcobranca/blob/master/spec/brcobranca/remessa/cnab400/itau_spec.rb
cat > "$WORK/remessa_data.json" <<'EOF'
{"carteira": "123",
 "agencia": "1234",
 "conta_corrente": "12345",
 "digito_conta": "1",
 "empresa_mae": "SOCIEDADE BRASILEIRA GNU LTDA",
 "documento_cedente": "12345678910",
 "pagamentos": [{
     "valor": 199.9,
     "data_vencimento": "2026/06/15",
     "nosso_numero": 123,
     "documento": 6969,
     "documento_sacado": "12345678901",
     "nome_sacado": "PABLO DIEGO JOSÉ FRANCISCO DE PAULA JUAN NEPOMUCENO MARÍA DE LOS REMEDIOS CIPRIANO DE LA SANTÍSSIMA TRINIDAD RUIZ Y PICASSO",
     "endereco_sacado": "RUA RIO GRANDE DO SUL São paulo Minas caçapa da silva junior",
     "bairro_sacado": "São josé dos quatro apostolos magros",
     "cep_sacado": "12345678",
     "cidade_sacado": "Santa rita de cássia maria da silva",
     "uf_sacado": "SP"}]}
EOF
curl -sS -o "$WORK/remessa_cnab400.rem" -X POST -F type=cnab400 -F bank=itau -F "data=@$WORK/remessa_data.json" "$API/remessa"
check "remessa cnab400 itau generated" bash -c "grep -q '^01REMESSA' '$WORK/remessa_cnab400.rem' && test \$(stat -c %s '$WORK/remessa_cnab400.rem') -gt 400"
check "remessa cnab400 itau has 400-char lines" bash -c 'tr -d "\r" < "$WORK/remessa_cnab400.rem" | awk "/^02/ && length(\$0) != 400 {bad=1} END {exit bad}"'

# Data from https://github.com/kivanio/brcobranca/blob/master/spec/brcobranca/remessa/cnab240/itau_spec.rb
cat > "$WORK/remessa_data_cnab240.json" <<'EOF'
{"empresa_mae": "EMPRESA TESTE LTDA",
 "documento_cedente": "28254225000193",
 "agencia": "1234",
 "conta_corrente": "12345",
 "carteira": "175",
 "sequencial_remessa": "1",
 "pagamentos": [{
     "valor": 123.45,
     "data_vencimento": "2026/06/15",
     "nosso_numero": 12345678,
     "documento": 9999,
     "documento_sacado": "12345679",
     "nome_sacado": "PABLO DIEGO JOSÉ FRANCISCO DE PAULA JUAN NEPOMUCENO MARÍA DE LOS REMEDIOS CIPRIANO DE LA SANTÍSSIMA TRINIDAD RUIZ Y PICASSO",
     "endereco_sacado": "RUA RIO GRANDE DO SUL São paulo Minas caçapa da silva junior",
     "bairro_sacado": "São josé dos quatro apostolos magros",
     "cep_sacado": "12345678",
     "cidade_sacado": "Santa rita de cássia maria da silva",
     "uf_sacado": "SP",
     "numero": "123",
     "codigo_baixa": "3",
     "dias_baixa": "0"}]}
EOF
curl -sS -o "$WORK/remessa_cnab240.rem" -w '%{http_code}' -X POST -F type=cnab240 -F bank=itau -F "data=@$WORK/remessa_data_cnab240.json" "$API/remessa" > "$WORK/cnab240_code"
HTTP_CODE=$(cat "$WORK/cnab240_code")
case "$HTTP_CODE" in
  2*)
    check "remessa cnab240 itau generated" bash -c "test \$(head -c 3 '$WORK/remessa_cnab240.rem') = '341' && test \$(stat -c %s '$WORK/remessa_cnab240.rem') -gt 1400"
    check "remessa cnab240 itau has 240-char lines with CRLF endings" bash -c 'test "$(head -c 242 "$WORK/remessa_cnab240.rem" | tail -c 2)" = "$(printf "\r\n")" && test "$(sed -n "2p" "$WORK/remessa_cnab240.rem" | tr -d "\r" | wc -c)" = 241'
    ;;
  *)
    # Itau CNAB240 remessa support was only added in BRCobranca 13.0.0;
    # images built from BRCobranca 12 reply with an error here, so we skip.
    echo "SKIP: remessa cnab240 itau (HTTP $HTTP_CODE) requires BRCobranca >= 13.0.0"
    ;;
esac

echo "== Retorno =="
# Fixture from https://github.com/kivanio/brcobranca/blob/master/spec/arquivos/CNAB400ITAU.RET
# (upstream spec: 53 payments, first one with nosso_numero '00000011', agencia_com_dv
# '0730', cedente_com_dv '035110', valor_recebido '0000000003790', codigo_ocorrencia '06')
curl -sS -o "$WORK/CNAB400ITAU.RET" https://raw.githubusercontent.com/kivanio/brcobranca/master/spec/arquivos/CNAB400ITAU.RET
HTTP_CODE=$(curl -sS -o "$WORK/retorno.json" -w '%{http_code}' -X POST -F type=cnab400 -F bank=itau -F "data=@$WORK/CNAB400ITAU.RET" "$API/retorno")
check_eq "retorno cnab400 itau replies HTTP 201" "201" "$HTTP_CODE"
check "retorno cnab400 itau returns 53 pagamentos (header line ignored)" \
    bash -c 'jq -e "type == \"array\" and length == 53" "$WORK/retorno.json" || { head -c 2000 "$WORK/retorno.json"; exit 1; }'
check "retorno cnab400 itau first pagamento fields (per upstream spec)" \
    bash -c 'jq -e "(.[0].nosso_numero == \"00000011\") and (.[0].agencia_com_dv == \"0730\") and (.[0].cedente_com_dv == \"035110\") and (.[0].valor_recebido == \"0000000003790\") and (.[0].codigo_ocorrencia == \"06\")" "$WORK/retorno.json" || { head -c 2000 "$WORK/retorno.json"; exit 1; }'

echo
if [ "$FAILURES" -eq 0 ]; then
    echo "ALL CHECKS PASSED ($BASE_URL)"
else
    echo "$FAILURES CHECK(S) FAILED ($BASE_URL)"
    exit 1
fi
