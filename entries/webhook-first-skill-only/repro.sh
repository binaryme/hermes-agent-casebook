#!/usr/bin/env bash
set -euo pipefail
source "$HARNESS/lib.sh"
source "$HARNESS/gateway.sh"

texts_for() {
    local i=0
    while [ "$i" -lt "$(stub_count)" ]; do
        if stub_text "$i" | grep -q "$1"; then stub_text "$i"; fi
        i=$((i + 1))
    done
}

injected() {
    local text alpha=0 beta=0
    text=$(texts_for "$1")
    echo "$text" | grep -q ALPHA-7Q && alpha=1
    echo "$text" | grep -q BETA-7Q && beta=1
    case "$alpha$beta" in 10) echo alpha-only ;; 01) echo beta-only ;; 11) echo both ;; *) echo none ;; esac
}

cp -R "$FIXTURES/data" "$WORK/data"
gateway_up "$WORK/data"
test "$(post_v2 both-listed "$FIXTURES/payload.json" casebook-placeholder-secret)" = 202
test "$(post_v2 first-missing "$FIXTURES/payload.json" casebook-placeholder-secret)" = 202
waited=0
until [ -n "$(texts_for ROUTE-BOTH)" ] && [ -n "$(texts_for ROUTE-MISSING)" ] || [ "$waited" -ge 120 ]; do sleep 2; waited=$((waited + 2)); done
observed "$(injected ROUTE-BOTH)-$(injected ROUTE-MISSING)"
