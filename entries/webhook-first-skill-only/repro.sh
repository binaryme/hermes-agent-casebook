#!/usr/bin/env bash
set -euo pipefail
source "$HARNESS/lib.sh"
source "$HARNESS/gateway.sh"

injected() {
    local text alpha=0 beta=0
    text=$(stub_texts_matching "$1")
    echo "$text" | grep -q ALPHA-7Q && alpha=1
    echo "$text" | grep -q BETA-7Q && beta=1
    evidence "$1: skill markers in the model request: ALPHA-7Q=$alpha BETA-7Q=$beta; lines: $(echo "$text" | grep -E 'ALPHA-7Q|BETA-7Q' | cut -c 1-160 | tr '\n' '|')"
    case "$alpha$beta" in 10) echo alpha-only ;; 01) echo beta-only ;; 11) echo both ;; *) echo none ;; esac
}

cp -R "$FIXTURES/data" "$WORK/data"
gateway_up "$WORK/data"
both=$(post_v2 both-listed "$FIXTURES/payload.json" casebook-placeholder-secret)
missing=$(post_v2 first-missing "$FIXTURES/payload.json" casebook-placeholder-secret)
evidence "POST status: both-listed $both, first-missing $missing"
test "$both" = 202
test "$missing" = 202
waited=0
until [ -n "$(stub_texts_matching ROUTE-BOTH)" ] && [ -n "$(stub_texts_matching ROUTE-MISSING)" ]; do
    [ "$waited" -lt 120 ] || { echo "a route's request never reached the stub model" >&2; exit 1; }
    sleep 2
    waited=$((waited + 2))
done
observed "$(injected ROUTE-BOTH)-$(injected ROUTE-MISSING)"
