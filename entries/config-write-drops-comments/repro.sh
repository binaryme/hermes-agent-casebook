#!/usr/bin/env bash
set -euo pipefail
source "$HARNESS/lib.sh"

mkdir -p "$WORK/data"
printf '%s\n' '# Operator notes, kept by hand.' 'agent:' '  # Keep runs short on this host.' '  max_turns: 30' >"$WORK/data/config.yaml"
chmod 0777 "$WORK/data"
chmod 0666 "$WORK/data/config.yaml"
before=$(grep -c '^ *#' "$WORK/data/config.yaml")

in_image() {
    hermes_docker_run -v "$WORK/data:/opt/data" --entrypoint "$1" "$HERMES_IMAGE" "${@:2}"
}
if ! in_image hermes config set agent.max_turns 42 >"$WORK/set.out" 2>&1; then
    cat "$WORK/set.out" >&2
    exit 1
fi
in_image cat /opt/data/config.yaml >"$WORK/after.yaml"
grep -q 'max_turns: 42' "$WORK/after.yaml" || { echo "config set did not write the value" >&2; cat "$WORK/after.yaml" >&2; exit 1; }
after=$(grep -c '^ *#' "$WORK/after.yaml" || true)
echo "comment lines before: $before, after: $after" >&2

if [ "$after" -eq "$before" ]; then
    observed comments-kept
elif [ "$after" -eq 0 ]; then
    observed comments-lost
else
    observed comments-partial
fi
