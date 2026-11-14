#!/usr/bin/env bash
set -euo pipefail
source "$HARNESS/lib.sh"
source "$HARNESS/gateway.sh"

cp -R "$FIXTURES/data" "$WORK/data"
gateway_up "$WORK/data"
codes=
for mode in raw mapped tampered stale; do
    codes="$codes-$(post_chatwoot chatwoot "$FIXTURES/payload.json" casebook-placeholder-secret "$mode")"
done
observed "${codes#-}"
