#!/usr/bin/env bash
set -euo pipefail
source "$HARNESS/lib.sh"
source "$HARNESS/gateway.sh"

index_state() {
    mkdir -p "$WORK/$1"
    cp -R "$FIXTURES/skills" "$WORK/$1/skills"
    cp "$FIXTURES/$1.yaml" "$WORK/$1/config.yaml"
    hermes_exec_data "$WORK/$1" prompt-size --json --platform webhook 2>/dev/null >"$WORK/$1.out"
    python3 -c 'import json, sys; t = open(sys.argv[1]).read(); d = json.loads(t[t.index("{\n"):]); print("present" if d["skills_index"]["chars"] else "empty")' "$WORK/$1.out"
}

default=$(index_state default)
platform=$(index_state platform-skills)

cp -R "$FIXTURES/gateway" "$WORK/gateway"
cp -R "$FIXTURES/skills" "$WORK/gateway/skills"
gateway_up "$WORK/gateway"
test "$(post_v2 with-skills "$FIXTURES/payload.json" casebook-placeholder-secret)" = 202
stub_wait 2 120 || stub_wait 1 5
route=empty
i=0
while [ "$i" -lt "$(stub_count)" ]; do
    if stub_text "$i" | grep -q 'casebook-marker'; then route=present; fi
    i=$((i + 1))
done
observed "$default-$platform-$route"
