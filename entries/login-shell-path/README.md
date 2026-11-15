---
id: E7
slug: login-shell-path
title: Use v0.22.6 or later before relying on the image's Python from the terminal tool
kind: check-your-version
status: fixed
affected:
- v2026.8.13
- v2026.9.21
- v2026.9.24
- v0.21.6
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
confidence: reproduced
verified_on:
- tag: v2026.8.13
  digest: sha256:68e15ae2a6d894d0ccbd9f8aacbbe13d4d28fa5dc9b6a303970b67bb2499b1a6
  date: '2026-11-15'
  observed: venv-lost
  run: https://github.com/binaryme/hermes-agent-casebook/actions/runs/43668393761
- tag: v2026.9.21
  digest: sha256:6bece0644e29a347e5ae17db43c36938c86f171c6f5e0cef18aa2075d331f3a3
  date: '2026-11-15'
  observed: venv-lost
  run: https://github.com/binaryme/hermes-agent-casebook/actions/runs/43668393761
- tag: v2026.9.24
  digest: sha256:fca358f12efd65bfaaca05884166f15c0e2788375ca30d77061ac1ebc96452b7
  date: '2026-11-15'
  observed: venv-lost
  run: https://github.com/binaryme/hermes-agent-casebook/actions/runs/43668393761
- tag: v0.21.6
  digest: sha256:55e192fba0cd4fde61142abbff5adeacff40efdb482ccd0ff877924bd274f909
  date: '2026-11-15'
  observed: venv-lost
  run: https://github.com/binaryme/hermes-agent-casebook/actions/runs/43668393761
- tag: v0.22.5
  digest: sha256:9c5561579f3ffdf333401797094ac3a743738d6c25d40f4331c7bf77b694238d
  date: '2026-11-15'
  observed: venv-lost
  run: https://github.com/binaryme/hermes-agent-casebook/actions/runs/43668393761
- tag: v0.22.6
  digest: sha256:d27689bc6e8581ec884a7227c9101fdaebf6c853cff8859020dac14f21452b4d
  date: '2026-11-15'
  observed: venv-kept
  run: https://github.com/binaryme/hermes-agent-casebook/actions/runs/43668393761
- tag: v0.23.1
  digest: sha256:276d44685c65c0cb2a25f190b63c65c8906f9dc76486fb1c05ae71b5826bda08
  date: '2026-11-15'
  observed: venv-kept
  run: https://github.com/binaryme/hermes-agent-casebook/actions/runs/43668393761
last_reviewed: '2026-11-14'
limits: The repro runs the two shells as root through a bash entrypoint, not through the terminal tool itself. It shows which python3 a login shell finds, not every tool that depends on it.
credits: []
---

## Observation

The agent runs a command through the terminal tool that imports a module Hermes itself depends on, such as `yaml` or `mcp`, and gets `ModuleNotFoundError`. The same command works in `docker exec <container> python3 ...`. The agent may then report that it changed a file when the script that should have changed it failed.

## Hypothesis

Before v0.22.6, a login shell in the image resolves `python3` outside the image's virtual environment, while a non-login shell resolves it inside. The hypothesis is falsified if the login shell finds the venv interpreter on an affected tag, or misses it on a fixed one.

## Method

`repro.sh` runs `command -v python3` in the image twice: in `bash -c`, and in `bash -l -c`, the login shell the terminal tool uses. It fails as a repro error if the non-login shell does not find the image's virtualenv, and otherwise prints `venv-kept` when the login shell also finds it, or `venv-lost` when it does not.

## Results

### Runs

| Tag | Observed | Date | Digest | Run | Transcript |
| --- | --- | --- | --- | --- | --- |
| v2026.8.13 | `venv-lost` | 2026-11-15 | `sha256:68e15ae2a6d8` | [run](https://github.com/binaryme/hermes-agent-casebook/actions/runs/43668393761) | [log](../../evidence/43668393761/login-shell-path/v2026.8.13.log) |
| v2026.9.21 | `venv-lost` | 2026-11-15 | `sha256:6bece0644e29` | [run](https://github.com/binaryme/hermes-agent-casebook/actions/runs/43668393761) | [log](../../evidence/43668393761/login-shell-path/v2026.9.21.log) |
| v2026.9.24 | `venv-lost` | 2026-11-15 | `sha256:fca358f12efd` | [run](https://github.com/binaryme/hermes-agent-casebook/actions/runs/43668393761) | [log](../../evidence/43668393761/login-shell-path/v2026.9.24.log) |
| v0.21.6 | `venv-lost` | 2026-11-15 | `sha256:55e192fba0cd` | [run](https://github.com/binaryme/hermes-agent-casebook/actions/runs/43668393761) | [log](../../evidence/43668393761/login-shell-path/v0.21.6.log) |
| v0.22.5 | `venv-lost` | 2026-11-15 | `sha256:9c5561579f3f` | [run](https://github.com/binaryme/hermes-agent-casebook/actions/runs/43668393761) | [log](../../evidence/43668393761/login-shell-path/v0.22.5.log) |
| v0.22.6 | `venv-kept` | 2026-11-15 | `sha256:d27689bc6e85` | [run](https://github.com/binaryme/hermes-agent-casebook/actions/runs/43668393761) | [log](../../evidence/43668393761/login-shell-path/v0.22.6.log) |
| v0.23.1 | `venv-kept` | 2026-11-15 | `sha256:276d44685c65` | [run](https://github.com/binaryme/hermes-agent-casebook/actions/runs/43668393761) | [log](../../evidence/43668393761/login-shell-path/v0.23.1.log) |

### Expected and observed

| Tag | `bash -l -c 'command -v python3'` | Token |
| --- | --- | --- |
| v2026.8.13, v2026.9.21, v2026.9.24 | `/usr/bin/python3` | `venv-lost` |
| v0.21.6, v0.22.5 | `/usr/local/bin/python3` | `venv-lost` |
| v0.22.6, v0.23.1 | `/opt/hermes/.venv/bin/python3` | `venv-kept` |

The transcripts also show the login `PATH` on the affected tags, `/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin`, and whether the login shell's `python3` can import `openai`, a dependency only the image's virtualenv has: it cannot on the affected tags and can on v0.22.6 and v0.23.1. On v0.21.6 and v0.22.5 the login shell finds `/usr/local/bin/python3` instead of `/usr/bin/python3`; it is still not the virtualenv's interpreter. `import yaml` would be no probe across tags: in a local check, the v0.23.1 virtualenv itself has no PyYAML.

### Field observation

On the author's own install (the official Docker image, v2026.8.13, in production since August 2026), read on 2026-11-14 with read-only commands. This is not reproducible by a reader and is not part of the CI evidence; it shows the behavior outside the harness. [Appendix E](../../evidence/field/2026-11-14.md) lists the commands. Statements marked *operator's account* come from the operator, not from a command.

- In the running gateway, `bash -c 'command -v python3'` as the `hermes` user gives `/opt/hermes/.venv/bin/python3`, and `bash -l -c` gives `/usr/bin/python3`, as on v2026.8.13 in CI.
- The operator had installed PyYAML for the system interpreter into the data volume, with the `uv pip install --target` command in the recommendation (operator's account). In the login shell, `/usr/bin/python3` imports `yaml` from under `/opt/data`.

## Analysis

The image puts its virtualenv first in `PATH` through the Dockerfile's `ENV`. The terminal tool captures its environment from a login shell ([v2026.8.13 base.py L703-L707](https://github.com/NousResearch/hermes-agent/blob/f80f453ae0679347e38abc917c7f94f717bf96c5/tools/environments/base.py#L703-L707)). On the Debian base, `/etc/profile` sets `PATH` from scratch for every login shell, so the virtualenv directories disappear and `python3` resolves to the system interpreter, which has none of Hermes' dependencies.

v0.22.6 adds `/etc/profile.d/hermes.sh`, which puts `/opt/data/.local/bin`, `/opt/hermes/.venv/bin` and `/opt/hermes/bin` back after `/etc/profile` runs ([profile-hermes-path.sh](https://github.com/NousResearch/hermes-agent/blob/f0d94882e89ab8d4098b5bb2f166adfb9ee0a0ab/docker/profile-hermes-path.sh), installed by [Dockerfile L531](https://github.com/NousResearch/hermes-agent/blob/f0d94882e89ab8d4098b5bb2f166adfb9ee0a0ab/Dockerfile#L531)). The v0.22.5 Dockerfile has no such step.

## Recommendation

- Upgrade to v0.22.6 or later.
- On an older image, call the interpreter by its full path, `/opt/hermes/.venv/bin/python3`, in commands the agent runs, for example in a skill that tells it how to edit a file.
- Or install the one module you need for the system interpreter into the data volume, for example with `uv pip install --python /usr/bin/python3 --target /opt/data/.local/lib/python3.<minor>/site-packages pyyaml`, with `--python` set to what `bash -l -c 'command -v python3'` gives: `/usr/bin/python3` on the v2026 tags, `/usr/local/bin/python3` on v0.21.6 and v0.22.5. It survives redeploys without changing `PATH`. The repro does not exercise it; the field observation above shows it working on one v2026.8.13 install. It is a second copy of the module to keep current.

## Related work

Fixed. Issue [#56634](https://github.com/NousResearch/hermes-agent/issues/56634) ("terminal tool's bash -l session snapshot loses venv PATH on Debian-based images") was closed on 2026-10-29, and the fix ships in v0.22.6.

## Threats to validity

Reproduced in CI on all seven pinned tags, v2026.8.13 to v0.23.1, on 2026-11-15 ([run 43668393761](https://github.com/binaryme/hermes-agent-casebook/actions/runs/43668393761); transcripts in [evidence/43668393761](../../evidence/43668393761/README.md)), each against the digest pinned in `harness/images.json`. The causes are source-verified at the linked lines. The repro runs both shells as root through a bash entrypoint. The terminal tool runs as the `hermes` user, and `/etc/profile` resets `PATH` for every user, so the result is the same, but the terminal tool itself is not exercised. The field observation ran both shells as `hermes` in a running gateway and got the same result.
