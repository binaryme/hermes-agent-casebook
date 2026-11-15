#!/usr/bin/env bash
set -euo pipefail
source "$HARNESS/lib.sh"

prepare() {
    mkdir -p "$WORK/$1"
    printf '%s\n' '# Operator notes, kept by hand.' 'agent:' '  # Keep runs short on this host.' '  max_turns: 30' "$2" >"$WORK/$1/config.yaml"
    chmod 0777 "$WORK/$1"
    chmod 0666 "$WORK/$1/config.yaml"
}
in_image() {
    local dir=$1 entrypoint=$2
    shift 2
    hermes_docker_run -v "$WORK/$dir:/opt/data" --entrypoint "$entrypoint" "$HERMES_IMAGE" "$@"
}
comments_after() {
    in_image "$1" cat /opt/data/config.yaml >"$WORK/$1.after"
    grep -q "$2" "$WORK/$1.after" || { echo "$1: the write did not happen" >&2; cat "$WORK/$1.after" >&2; exit 1; }
    evidence "$1: config.yaml after the write: $(wc -l <"$WORK/$1.after" | tr -d ' ') lines, $(grep -c '^ *#' "$WORK/$1.after" || true) comment lines, $(grep -m 1 '^_config_version:' "$WORK/$1.after" || echo 'no _config_version'); first lines: $(head -n 12 "$WORK/$1.after" | tr '\n' '|')"
    if grep -qF '# Operator notes, kept by hand.' "$WORK/$1.after" && grep -qF '# Keep runs short on this host.' "$WORK/$1.after"; then echo kept; else echo lost; fi
}

prepare set ''
evidence "config.yaml before each write: $(tr '\n' '|' <"$WORK/set/config.yaml")"
in_image set hermes config set agent.max_turns 42 >"$WORK/set.out" 2>&1 || { cat "$WORK/set.out" >&2; exit 1; }
set_result=$(comments_after set 'max_turns: 42')

prepare boot '_config_version: 30'
hermes_exec_data "$WORK/boot" --version >"$WORK/boot.out" 2>&1 || { cat "$WORK/boot.out" >&2; exit 1; }
boot_result=$(comments_after boot '_config_version: ')
evidence "boot: config files left in the data directory: $(in_image boot find /opt/data -name 'config.yaml*' 2>/dev/null | sort | tr '\n' ' ')"
grep -q '^_config_version: 30$' "$WORK/boot.after" && { echo "the boot did not migrate the config" >&2; exit 1; }
observed "set-$set_result-boot-$boot_result"
