#!/usr/bin/env bash
set -euo pipefail
source "$HARNESS/lib.sh"

plain=$(hermes_shell 'command -v python3' 2>/dev/null | tail -n 1)
login=$(hermes_login_shell 'command -v python3 || echo none' 2>/dev/null | tail -n 1)
evidence "bash -c: python3 is $plain; bash -l -c: python3 is $login"
evidence "bash -l -c PATH: $(hermes_login_shell 'echo "$PATH"' 2>/dev/null | tail -n 1)"

case "$plain" in
    /opt/hermes/.venv/*) ;;
    *) echo "the non-login shell does not use the image venv: $plain" >&2; exit 1 ;;
esac
case "$login" in
    /opt/hermes/.venv/*) observed venv-kept ;;
    *) observed venv-lost ;;
esac
