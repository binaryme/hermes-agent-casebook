#!/usr/bin/env bash
set -euo pipefail

HARNESS=${HARNESS:-$(cd "$(dirname "$0")" && pwd)}
WORK=${WORK:-$(mktemp -d "${TMPDIR:-/tmp}/casebook-smoke.XXXXXX")}
export HARNESS WORK
source "$HARNESS/lib.sh"
source "$HARNESS/gateway.sh"
require_env HERMES_IMAGE

SECRET=casebook-smoke-placeholder-secret
mkdir -p "$WORK/data"
cat >"$WORK/data/config.yaml" <<EOF
platforms:
  webhook:
    enabled: true
    extra:
      routes:
        smoke:
          secret: $SECRET
          signature: generic
          prompt: "Reply with one word. Marker: SMOKE-7Q."
EOF
printf '{"event_type":"smoke","id":1}' >"$WORK/payload.json"

gateway_up "$WORK/data"
echo "health ok at $GATEWAY_URL" >&2
status=$(post_v2 smoke "$WORK/payload.json" "$SECRET")
echo "webhook answered HTTP $status: $(cat "$WORK/last-response.json")" >&2
if ! stub_wait 1 120; then
    echo "the stub model received no chat request" >&2
    gateway_logs | tail -n 60 >&2
    exit 1
fi
stub_text 0 | grep -q 'SMOKE-7Q' || { echo "the marker did not reach the model" >&2; exit 1; }
observed smoke-ok
