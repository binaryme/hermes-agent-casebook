#!/usr/bin/env bash
set -euo pipefail
source "$HARNESS/lib.sh"

plain=$(hermes_shell 'command -v python3' 2>/dev/null | tail -n 1)
login=$(hermes_login_shell 'command -v python3 || echo none' 2>/dev/null | tail -n 1)
echo "bash -c: $plain; bash -l -c: $login" >&2

case "$plain" in
    /opt/hermes/.venv/*) ;;
    *) echo "the non-login shell does not use the image venv: $plain" >&2; exit 1 ;;
esac
case "$login" in
    /opt/hermes/.venv/*) observed venv-kept ;;
    *) observed venv-lost ;;
esac
