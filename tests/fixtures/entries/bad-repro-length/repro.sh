#!/usr/bin/env bash
set -euo pipefail
source "$HARNESS/lib.sh"
require_env HERMES_IMAGE FIXTURES
if hermes_shell 'test -d /opt/data'; then
  observed present
else
  observed empty
fi
echo step-0
echo step-1
echo step-2
echo step-3
echo step-4
echo step-5
echo step-6
echo step-7
echo step-8
echo step-9
echo step-10
echo step-11
echo step-12
echo step-13
echo step-14
echo step-15
echo step-16
echo step-17
echo step-18
echo step-19
echo step-20
echo step-21
echo step-22
echo step-23
echo step-24
echo step-25
echo step-26
echo step-27
echo step-28
echo step-29
