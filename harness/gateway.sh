#!/usr/bin/env bash
set -euo pipefail

GATEWAY_BOOT_TIMEOUT=${GATEWAY_BOOT_TIMEOUT:-180}
STUB_START_TIMEOUT=10
WEBHOOK_CONTAINER_PORT=8644
GATEWAY_CID=
STUB_PID=

stub_bind_host() {
    if [ "$(uname -s)" = "Linux" ]; then
        docker network inspect bridge --format '{{(index .IPAM.Config 0).Gateway}}'
    else
        echo 127.0.0.1
    fi
}

start_stub() {
    local port_file="$WORK/stub.port"
    local waited=0
    STUB_LOG="$WORK/stub.jsonl"
    rm -f "$port_file"
    python3 "$HARNESS/stub_model.py" serve --host "$(stub_bind_host)" --log "$STUB_LOG" --port-file "$port_file" >"$WORK/stub.out" 2>&1 &
    STUB_PID=$!
    while [ ! -s "$port_file" ]; do
        if [ "$waited" -ge "$STUB_START_TIMEOUT" ] || ! kill -0 "$STUB_PID" 2>/dev/null; then
            echo "stub model did not start" >&2
            cat "$WORK/stub.out" >&2
            return 1
        fi
        sleep 1
        waited=$((waited + 1))
    done
    STUB_PORT=$(cat "$port_file")
    export STUB_LOG STUB_PID STUB_PORT
}

write_stub_model_config() {
    local config="$1/config.yaml"
    if [ -f "$config" ] && grep -Eq '^(model|database):' "$config"; then
        echo "fixture config must not set model or database; gateway_up writes them" >&2
        return 1
    fi
    cat >>"$config" <<EOF
model:
  provider: custom
  base_url: http://host.docker.internal:$STUB_PORT/v1
  default: casebook-stub
  api_key: casebook-placeholder-key
  context_length: 200000
database:
  journal_mode: delete
EOF
}

gateway_healthy() {
    curl -fsS --max-time 5 "$GATEWAY_URL/health" 2>/dev/null | grep -Eq '"platform": *"webhook"'
}

gateway_up() {
    require_env HERMES_IMAGE HARNESS WORK
    local data_dir
    local waited=0
    data_dir=$(cd "$1" && pwd)
    trap gateway_down EXIT
    trap 'gateway_down; exit 143' TERM
    trap 'gateway_down; exit 130' INT
    start_stub
    write_stub_model_config "$data_dir"
    GATEWAY_CID=$(docker run -d \
        --name "casebook-gw-$$-$RANDOM" \
        --label "$CASEBOOK_LABEL" \
        --add-host host.docker.internal:host-gateway \
        -e WEBHOOK_ENABLED=true \
        -e WEBHOOK_PORT="$WEBHOOK_CONTAINER_PORT" \
        -p "127.0.0.1::$WEBHOOK_CONTAINER_PORT" \
        -v "$data_dir:/opt/data" \
        "$HERMES_IMAGE" gateway run)
    GATEWAY_URL="http://$(docker port "$GATEWAY_CID" "$WEBHOOK_CONTAINER_PORT/tcp" | head -n 1)"
    export GATEWAY_CID GATEWAY_URL
    until gateway_healthy; do
        if [ "$waited" -ge "$GATEWAY_BOOT_TIMEOUT" ]; then
            echo "gateway did not report webhook health within ${GATEWAY_BOOT_TIMEOUT}s" >&2
            docker logs --tail 60 "$GATEWAY_CID" >&2 2>&1 || true
            return 1
        fi
        sleep 2
        waited=$((waited + 2))
    done
}

gateway_logs() {
    if [ -n "$GATEWAY_CID" ]; then
        docker logs "$GATEWAY_CID" 2>&1
    fi
}

gateway_down() {
    if [ -n "$GATEWAY_CID" ]; then
        docker rm -f "$GATEWAY_CID" >/dev/null 2>&1 || true
        GATEWAY_CID=
    fi
    if [ -n "$STUB_PID" ]; then
        kill "$STUB_PID" 2>/dev/null || true
        wait "$STUB_PID" 2>/dev/null || true
        STUB_PID=
    fi
}

post_signed() {
    local url=$1
    local payload=$2
    shift 2
    local header_args=()
    local line
    while IFS= read -r line; do
        header_args+=(-H "$line")
    done < <(python3 "$HARNESS/sign.py" "$@")
    curl -sS -o "$WORK/last-response.json" -w '%{http_code}' --max-time 30 \
        -X POST -H "Content-Type: application/json" \
        ${header_args[@]+"${header_args[@]}"} \
        --data-binary "@$payload" "$url"
}

post_v2() {
    post_signed "$GATEWAY_URL/webhooks/$1" "$2" v2 "$3" "$2"
}

post_github() {
    post_signed "$GATEWAY_URL/webhooks/$1" "$2" github "$3" "$2" --delivery-id "$4" --event "${5:-push}"
}

post_chatwoot() {
    local route=$1
    local payload=$2
    local secret=$3
    local mode=$4
    local stale
    case "$mode" in
        raw) post_signed "$GATEWAY_URL/webhooks/$route" "$payload" chatwoot "$secret" "$payload" ;;
        mapped) post_signed "$GATEWAY_URL/webhooks/$route" "$payload" chatwoot-mapped "$secret" "$payload" ;;
        tampered)
            cp "$payload" "$WORK/tampered.json"
            printf ' ' >>"$WORK/tampered.json"
            post_tampered "$GATEWAY_URL/webhooks/$route" "$payload" "$WORK/tampered.json" "$secret"
            ;;
        stale)
            stale=$(( $(date +%s) - 900 ))
            post_signed "$GATEWAY_URL/webhooks/$route" "$payload" chatwoot-mapped "$secret" "$payload" --timestamp "$stale"
            ;;
        *)
            echo "unknown chatwoot mode: $mode" >&2
            return 2
            ;;
    esac
}

post_tampered() {
    local url=$1
    local signed_payload=$2
    local sent_payload=$3
    local secret=$4
    local header_args=()
    local line
    while IFS= read -r line; do
        header_args+=(-H "$line")
    done < <(python3 "$HARNESS/sign.py" chatwoot-mapped "$secret" "$signed_payload")
    curl -sS -o "$WORK/last-response.json" -w '%{http_code}' --max-time 30 \
        -X POST -H "Content-Type: application/json" \
        "${header_args[@]}" --data-binary "@$sent_payload" "$url"
}

stub_count() {
    python3 "$HARNESS/stub_model.py" count --log "$STUB_LOG"
}

stub_wait() {
    local count=$1
    local timeout=$2
    local waited=0
    until [ "$(stub_count)" -ge "$count" ]; do
        if [ "$waited" -ge "$timeout" ]; then
            return 1
        fi
        sleep 1
        waited=$((waited + 1))
    done
}

stub_text() {
    python3 "$HARNESS/stub_model.py" text --log "$STUB_LOG" "$1"
}
