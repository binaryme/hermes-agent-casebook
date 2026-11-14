#!/usr/bin/env bash
set -euo pipefail

GUIDE_DIR=$(cd "$(dirname "$0")" && pwd)
HARNESS=${HARNESS:-$(cd "$GUIDE_DIR/../../harness" && pwd)}
WORK=${WORK:-$(mktemp -d "${TMPDIR:-/tmp}/casebook-chatwoot.XXXXXX")}
export HARNESS WORK
source "$HARNESS/lib.sh"
source "$HARNESS/gateway.sh"
require_env HERMES_IMAGE

SECRET=casebook-placeholder-secret
RELAY_PID=
mkdir -p "$WORK/data"
cat >"$WORK/data/config.yaml" <<EOF
platforms:
  webhook:
    enabled: true
    extra:
      routes:
        chatwoot:
          secret: $SECRET
          prompt: "Reply with one word."
EOF
printf '{"event":"message_created","id":1,"content":"Hello from example.com"}' >"$WORK/payload.json"
cp "$WORK/payload.json" "$WORK/tampered.json"
printf ' ' >>"$WORK/tampered.json"

stop_all() {
    if [ -n "$RELAY_PID" ]; then
        kill "$RELAY_PID" 2>/dev/null || true
        wait "$RELAY_PID" 2>/dev/null || true
    fi
    gateway_down
}

gateway_up "$WORK/data"
trap stop_all EXIT
trap 'stop_all; exit 143' TERM
trap 'stop_all; exit 130' INT

RELAY_PORT=$(python3 -c 'import socket; s = socket.socket(); s.bind(("127.0.0.1", 0)); print(s.getsockname()[1])')
python3 "$GUIDE_DIR/relay/relay.py" --host 127.0.0.1 --port "$RELAY_PORT" \
    --upstream "$GATEWAY_URL/webhooks/chatwoot" 2>"$WORK/relay.log" &
RELAY_PID=$!
RELAY_URL="http://127.0.0.1:$RELAY_PORT"
waited=0
until curl -fsS --max-time 2 "$RELAY_URL/health" >/dev/null 2>&1; do
    if [ "$waited" -ge 10 ]; then
        echo "relay did not start" >&2
        cat "$WORK/relay.log" >&2
        exit 1
    fi
    sleep 1
    waited=$((waited + 1))
done

send_through_relay() {
    local signed=$1
    local sent=$2
    local header_args=()
    local line
    python3 "$HARNESS/sign.py" chatwoot "$SECRET" "$signed" >"$WORK/headers.txt"
    while IFS= read -r line; do
        header_args+=(-H "$line")
    done <"$WORK/headers.txt"
    curl -sS -o "$WORK/last-response.json" -w '%{http_code}' --max-time 30 \
        -X POST -H "Content-Type: application/json" "${header_args[@]}" \
        --data-binary "@$sent" "$RELAY_URL/"
}

signed=$(send_through_relay "$WORK/payload.json" "$WORK/payload.json")
tampered=$(send_through_relay "$WORK/payload.json" "$WORK/tampered.json")
unsigned=$(curl -sS -o "$WORK/unsigned.json" -w '%{http_code}' --max-time 30 -X POST \
    -H "Content-Type: application/json" --data-binary "@$WORK/payload.json" "$RELAY_URL/")
grep -q 'missing Chatwoot signature' "$WORK/unsigned.json" || unsigned="$unsigned-not-from-relay"
echo "through the relay: signed $signed, tampered $tampered, unsigned $unsigned" >&2

if [ "$signed" = 202 ] && [ "$tampered" = 401 ] && [ "$unsigned" = 401 ]; then
    observed relay-ok
else
    observed "relay-$signed-$tampered-$unsigned"
fi
