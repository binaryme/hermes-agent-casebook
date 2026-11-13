#!/usr/bin/env bash
set -euo pipefail
# explains the next line
source "$HARNESS/lib.sh"
require_env HERMES_IMAGE FIXTURES
if hermes_shell 'test -d /opt/data'; then
  observed present
else
  observed empty
fi
