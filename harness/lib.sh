#!/usr/bin/env bash
set -euo pipefail

require_env() {
    local name
    local missing=0
    for name in "$@"; do
        if [ -z "${!name:-}" ]; then
            echo "required environment variable is not set: $name" >&2
            missing=1
        fi
    done
    return "$missing"
}

CASEBOOK_LABEL=casebook=repro

hermes_docker_run() {
    local network=(--network none)
    if [ "${HERMES_EXEC_NETWORK:-}" = "1" ]; then
        network=()
    fi
    docker run --rm --label "$CASEBOOK_LABEL" ${network[@]+"${network[@]}"} "$@"
}

hermes_exec() {
    require_env HERMES_IMAGE
    hermes_docker_run "$HERMES_IMAGE" "$@"
}

hermes_exec_data() {
    require_env HERMES_IMAGE
    local host_dir=$1
    shift
    hermes_docker_run -v "$host_dir:/opt/data" "$HERMES_IMAGE" "$@"
}

hermes_shell() {
    require_env HERMES_IMAGE
    hermes_docker_run --entrypoint bash "$HERMES_IMAGE" -c "$1"
}

hermes_login_shell() {
    require_env HERMES_IMAGE
    hermes_docker_run --entrypoint bash "$HERMES_IMAGE" -l -c "$1"
}

observed() {
    local token=${1:-}
    if ! [[ "$token" =~ ^[a-z0-9]+(-[a-z0-9]+)*$ ]]; then
        echo "observed token must be lowercase kebab-case: '$token'" >&2
        return 1
    fi
    printf 'OBSERVED=%s\n' "$token"
}
