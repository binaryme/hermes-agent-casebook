#!/usr/bin/env bash
set -euo pipefail
source "$HARNESS/lib.sh"

mkdir -p "$WORK/data"
cp -R "$FIXTURES/skills" "$WORK/data/skills"
hermes_exec_data "$WORK/data" prompt-size --json --platform cli 2>/dev/null >"$WORK/prompt-size.out"
shown=$(python3 - "$WORK/prompt-size.out" <<'PY'
import json, sys
text = open(sys.argv[1]).read()
skills = {s["name"]: s["index_line_bytes"] for s in json.loads(text[text.index("{\n"):])["skills_breakdown"]}
print(skills["casebook-trims"] - skills["casebook-short"] + 40)
PY
)
if [ "$shown" -eq 60 ]; then
    observed hard-cut
elif [ "$shown" -lt 60 ]; then
    observed word-cut
else
    observed not-cut
fi
