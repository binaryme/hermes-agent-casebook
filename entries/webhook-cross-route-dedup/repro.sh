#!/usr/bin/env bash
set -euo pipefail
source "$HARNESS/lib.sh"
source "$HARNESS/gateway.sh"

cp -R "$FIXTURES/data" "$WORK/data"
gateway_up "$WORK/data"
delivery="casebook-$(date +%s)-$$"
first=$(post_github notify "$FIXTURES/payload.json" casebook-placeholder-secret "$delivery" push)
second=$(post_github review "$FIXTURES/payload.json" casebook-placeholder-secret "$delivery" push)
evidence "same X-GitHub-Delivery to two routes: notify status $first, review status $second, review body $(head -c 200 "$WORK/last-response.json")"

if [ "$first" != 202 ]; then
    echo "the first route did not accept the delivery" >&2
    exit 1
fi
if [ "$second" = 200 ] && grep -q '"duplicate"' "$WORK/last-response.json"; then
    observed duplicate
elif [ "$second" = 202 ]; then
    observed both-accepted
else
    observed "second-$second"
fi
