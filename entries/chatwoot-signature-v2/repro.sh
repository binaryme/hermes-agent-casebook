#!/usr/bin/env bash
set -euo pipefail
source "$HARNESS/lib.sh"
source "$HARNESS/gateway.sh"

cp -R "$FIXTURES/data" "$WORK/data"
gateway_up "$WORK/data"
codes=
for mode in raw mapped tampered stale; do
    code=$(post_chatwoot chatwoot "$FIXTURES/payload.json" casebook-placeholder-secret "$mode")
    evidence "$mode: status $code, body $(head -c 200 "$WORK/last-response.json")"
    codes="$codes-$code"
done
evidence "gateway log lines about signatures: $(gateway_logs | grep -i 'signature' | cut -c 1-200 | tail -n 6 | tr '\n' '|')"
observed "${codes#-}"
