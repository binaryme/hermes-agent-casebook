#!/usr/bin/env bash
set -euo pipefail
source "$HARNESS/lib.sh"
source "$HARNESS/gateway.sh"

index_state() {
    mkdir -p "$WORK/$1"
    cp -R "$FIXTURES/skills" "$WORK/$1/skills"
    cp "$FIXTURES/$1.yaml" "$WORK/$1/config.yaml"
    hermes_exec_data "$WORK/$1" prompt-size --json --platform webhook 2>/dev/null >"$WORK/$1.out"
    python3 -c 'import json, sys; t = open(sys.argv[1]).read(); d = json.loads(t[t.index("{\n"):]); i = d["skills_index"]; n = [s["name"] for s in d["skills_breakdown"]]; print("present" if i["chars"] else "empty", i["chars"], len(n), "casebook-marker" in n)' "$WORK/$1.out" >"$WORK/$1.state"
    evidence "$1: prompt-size --platform webhook skills_index state, chars, skills listed, marker listed: $(cat "$WORK/$1.state")"
    cut -d' ' -f1 "$WORK/$1.state"
}

default=$(index_state default)
platform=$(index_state platform-skills)

cp -R "$FIXTURES/gateway" "$WORK/gateway"
cp -R "$FIXTURES/skills" "$WORK/gateway/skills"
gateway_up "$WORK/gateway"
status=$(post_v2 with-skills "$FIXTURES/payload.json" casebook-placeholder-secret)
evidence "route with-skills: POST status $status"
test "$status" = 202
stub_wait 2 120 || stub_wait 1 5
matching=$(stub_texts_matching casebook-marker)
route=empty
[ -z "$matching" ] || route=present
evidence "route with-skills: $(stub_count) model requests recorded; casebook-marker lines: $(echo "$matching" | grep -m 3 casebook-marker | cut -c 1-200 | tr '\n' '|')"
observed "$default-$platform-$route"
