---
id: E7
slug: login-shell-path
title: Use v0.22.6 or later before relying on the image's Python from the terminal tool
kind: check-your-version
status: fixed
affected:
- v2026.8.13
- v0.22.5
not_affected:
- v0.22.6
- v0.23.1
fixed_in: v0.22.6
upstream:
- https://github.com/NousResearch/hermes-agent/issues/56634
evidence:
- https://github.com/NousResearch/hermes-agent/blob/f80f453ae0679347e38abc917c7f94f717bf96c5/tools/environments/base.py#L703-L707
- https://github.com/NousResearch/hermes-agent/blob/f0d94882e89ab8d4098b5bb2f166adfb9ee0a0ab/docker/profile-hermes-path.sh
- https://github.com/NousResearch/hermes-agent/blob/f0d94882e89ab8d4098b5bb2f166adfb9ee0a0ab/Dockerfile#L531
repro: entries/login-shell-path/repro.sh
needs_credentials: false
confidence: source-verified
verified_on: []
last_reviewed: '2026-11-14'
limits: The repro runs the two shells as root through a bash entrypoint, not through the terminal tool itself. It shows which python3 a login shell finds, not every tool that depends on it.
credits: []
---

## Symptom

The agent runs a command through the terminal tool that imports a module Hermes itself depends on, such as `yaml` or `mcp`, and gets `ModuleNotFoundError`. The same command works in `docker exec <container> python3 ...`. The agent may then report that it changed a file when the script that should have changed it failed.

## Verified on

No CI run has been recorded yet. Every statement below is source reading.

## Reproduce

`repro.sh` runs `command -v python3` in the image twice: in `bash -c`, and in `bash -l -c`, the login shell the terminal tool uses. It fails as a repro error if the non-login shell does not find the image's virtualenv, and otherwise prints `venv-kept` when the login shell also finds it, or `venv-lost` when it does not.

## Expected vs actual

| Tag | `bash -l -c 'command -v python3'` | Token |
| --- | --- | --- |
| v2026.8.13, v0.22.5 | `/usr/bin/python3`, without the image's packages | `venv-lost` |
| v0.22.6, v0.23.1 | `/opt/hermes/.venv/bin/python3` | `venv-kept` |

A local run on v2026.8.13 on 2026-11-13 also showed the login `PATH` as `/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin` and `python3 -c "import yaml"` failing with `ModuleNotFoundError: No module named 'yaml'`.

## Cause

The image puts its virtualenv first in `PATH` through the Dockerfile's `ENV`. The terminal tool captures its environment from a login shell ([v2026.8.13 base.py L703-L707](https://github.com/NousResearch/hermes-agent/blob/f80f453ae0679347e38abc917c7f94f717bf96c5/tools/environments/base.py#L703-L707)). On the Debian base, `/etc/profile` sets `PATH` from scratch for every login shell, so the virtualenv directories disappear and `python3` resolves to the system interpreter, which has none of Hermes' dependencies.

v0.22.6 adds `/etc/profile.d/hermes.sh`, which puts `/opt/data/.local/bin`, `/opt/hermes/.venv/bin` and `/opt/hermes/bin` back after `/etc/profile` runs ([profile-hermes-path.sh](https://github.com/NousResearch/hermes-agent/blob/f0d94882e89ab8d4098b5bb2f166adfb9ee0a0ab/docker/profile-hermes-path.sh), installed by [Dockerfile L531](https://github.com/NousResearch/hermes-agent/blob/f0d94882e89ab8d4098b5bb2f166adfb9ee0a0ab/Dockerfile#L531)). The v0.22.5 Dockerfile has no such step.

## Workaround

- Upgrade to v0.22.6 or later.
- On an older image, call the interpreter by its full path, `/opt/hermes/.venv/bin/python3`, in commands the agent runs, for example in a skill that tells it how to edit a file.
- Or install the one module you need for the system interpreter into the data volume, for example with `uv pip install --python /usr/bin/python3 --target /opt/data/.local/lib/python3.<minor>/site-packages pyyaml`. An operator used this in production because it survives redeploys without changing `PATH`; it is not exercised here, and it is a second copy of the module to keep current.

## Upstream status

Fixed. Issue [#56634](https://github.com/NousResearch/hermes-agent/issues/56634) ("terminal tool's bash -l session snapshot loses venv PATH on Debian-based images") was closed on 2026-10-29, and the fix ships in v0.22.6.

## Confidence and limits

CI-PENDING. The repro runs both shells as root through a bash entrypoint. The terminal tool runs as the `hermes` user, and `/etc/profile` resets `PATH` for every user, so the result is the same, but the terminal tool itself is not exercised.
