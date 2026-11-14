#!/usr/bin/env bash
set -euo pipefail
source "$HARNESS/lib.sh"

config="$WORK/data/config.yaml"
mkdir -p "$WORK/data"
printf '%s\n' '# Operator notes, kept by hand.' 'agent:' '  # Keep runs short on this host.' '  max_turns: 30' >"$config"
before=$(grep -c '^ *#' "$config")

if ! hermes_docker_run -v "$WORK/data:/opt/data" --entrypoint hermes "$HERMES_IMAGE" config set agent.max_turns 42 >"$WORK/set.out" 2>&1; then
    cat "$WORK/set.out" >&2
    exit 1
fi
grep -q 'max_turns: 42' "$config" || { echo "config set did not write the value" >&2; cat "$config" >&2; exit 1; }
after=$(grep -c '^ *#' "$config" || true)
echo "comment lines before: $before, after: $after" >&2

if [ "$after" -eq "$before" ]; then
    observed comments-kept
elif [ "$after" -eq 0 ]; then
    observed comments-lost
else
    observed comments-partial
fi
