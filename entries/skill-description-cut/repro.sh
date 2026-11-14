#!/usr/bin/env bash
set -euo pipefail
source "$HARNESS/lib.sh"

mkdir -p "$WORK/data"
cp -R "$FIXTURES/skills" "$WORK/data/skills"
hermes_exec_data "$WORK/data" prompt-size --json --platform cli 2>"$WORK/prompt-size.err" >"$WORK/prompt-size.out" || { tail -n 20 "$WORK/prompt-size.err" >&2; exit 1; }
shown=$(python3 - "$WORK/prompt-size.out" <<'PY'
import json, sys
text = open(sys.argv[1]).read()
skills = {s["name"]: s["index_line_bytes"] for s in json.loads(text[text.index("{\n"):])["skills_breakdown"]}
print(skills["casebook-trims"] - skills["casebook-short"] + 40)
PY
)
case "$shown" in
    60) observed hard-cut ;;
    56) observed word-cut ;;
    75) observed not-cut ;;
    *) observed "shown-$shown" ;;
esac
