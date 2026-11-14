---
id: E6
slug: config-write-drops-comments
title: Use v2026.9.24 or later before letting Hermes write a commented config.yaml
kind: check-your-version
status: fixed
affected:
  - v2026.9.21
not_affected:
  - v2026.9.24
fixed_in: v2026.9.24
upstream:
  - https://github.com/NousResearch/hermes-agent/issues/50698
  - https://github.com/NousResearch/hermes-agent/issues/92554
  - https://github.com/NousResearch/hermes-agent/issues/63039
  - https://github.com/NousResearch/hermes-agent/issues/107511
evidence:
  - https://github.com/NousResearch/hermes-agent/blob/d337b736aa1e8ebecfab043842d13e4a2d2f48a3/hermes_cli/config.py#L3411-L3414
  - https://github.com/NousResearch/hermes-agent/blob/d337b736aa1e8ebecfab043842d13e4a2d2f48a3/utils.py#L417-L426
  - https://github.com/NousResearch/hermes-agent/blob/f97608f178d1ffeca59860195ab7da295f7c8e5f/hermes_cli/config.py#L3447-L3450
  - https://github.com/NousResearch/hermes-agent/blob/f97608f178d1ffeca59860195ab7da295f7c8e5f/hermes_cli/config.py#L2016-L2020
  - https://github.com/NousResearch/hermes-agent/blob/d337b736aa1e8ebecfab043842d13e4a2d2f48a3/docker/stage2-hook.sh#L623-L632
  - https://github.com/NousResearch/hermes-agent/blob/d337b736aa1e8ebecfab043842d13e4a2d2f48a3/scripts/docker_config_migrate.py#L45-L52
repro: entries/config-write-drops-comments/repro.sh
needs_credentials: false
confidence: source-verified
verified_on: []
last_reviewed: 2026-11-13
limits: The repro exercises one write path, hermes config set. Other writers on v2026.9.21, and the boot-time schema migration, were read in the source and not run.
credits: []
---

## Symptom

You annotate `config.yaml` by hand: why a limit is set, which block is disabled and why. After one `hermes config set`, or anything else that writes the config, every comment is gone. Nothing warns you, and the values themselves are still right, so it is easy to notice weeks later.

## Verified on

No CI run has been recorded yet. Every statement below is source reading.

## Reproduce

`repro.sh` writes a `config.yaml` with two comment lines at run time, so no file in this repository carries comment lines, then runs `hermes config set agent.max_turns 42` in the image with the data directory mounted. It calls `hermes` directly instead of going through the image entrypoint, so the boot-time schema migration (see Cause) cannot be what writes the file. It checks that the value was written, then counts comment lines: `comments-kept` if both remain, `comments-lost` if none do, `comments-partial` otherwise.

## Expected vs actual

| Tag | Comment lines after `config set` | Token |
| --- | --- | --- |
| v2026.9.21 | 0 of 2 | `comments-lost` |
| v2026.9.24 | 2 of 2 | `comments-kept` |

## Cause

On v2026.9.21, `config set` writes the raw user config through `_write_user_config`, which calls `atomic_yaml_write` ([config.py L3411-L3414](https://github.com/NousResearch/hermes-agent/blob/d337b736aa1e8ebecfab043842d13e4a2d2f48a3/hermes_cli/config.py#L3411-L3414)), a plain PyYAML `yaml.dump` of the parsed data ([utils.py L417-L426](https://github.com/NousResearch/hermes-agent/blob/d337b736aa1e8ebecfab043842d13e4a2d2f48a3/utils.py#L417-L426)). Parsing drops comments, so the dump has none. A comment-preserving ruamel writer already existed in that release's `utils.py`, but `config set` did not use it.

From v2026.9.24, `_write_user_config` calls `atomic_config_write` ([config.py L3447-L3450](https://github.com/NousResearch/hermes-agent/blob/f97608f178d1ffeca59860195ab7da295f7c8e5f/hermes_cli/config.py#L3447-L3450)), described as "THE config.yaml writer: fail-closed ... and comment-preserving (ruamel round-trip merge of data onto the on-disk document)" ([L2016-L2020](https://github.com/NousResearch/hermes-agent/blob/f97608f178d1ffeca59860195ab7da295f7c8e5f/hermes_cli/config.py#L2016-L2020)).

A second writer runs at container boot. The image's stage2 hook runs `scripts/docker_config_migrate.py` whenever `config.yaml` exists ([stage2-hook.sh L623-L632](https://github.com/NousResearch/hermes-agent/blob/d337b736aa1e8ebecfab043842d13e4a2d2f48a3/docker/stage2-hook.sh#L623-L632)). It does nothing when `HERMES_SKIP_CONFIG_MIGRATION` is set or the config is already at the current schema version ([docker_config_migrate.py L45-L52](https://github.com/NousResearch/hermes-agent/blob/d337b736aa1e8ebecfab043842d13e4a2d2f48a3/scripts/docker_config_migrate.py#L45-L52)), and otherwise snapshots the config into `backups/config/` before migrating it. In local runs on 2026-11-13, booting each image once on the same two-comment config gave:

- v2026.9.21 refused to migrate a config with no `_config_version` ("predates version 12") and left both comments.
- v2026.9.24 migrated it from schema 0 to 46, wrote a `pre-docker-migrate` backup, and kept both comments.

## Workaround

- Upgrade to v2026.9.24 or later before you let anything write the config.
- On v2026.9.21 or earlier, keep the annotated copy outside the data volume, under version control, and treat `config.yaml` on the volume as generated. Diff the two after every `config set`, plugin enable or upgrade.
- Set `HERMES_SKIP_CONFIG_MIGRATION=1` if you want schema migrations to happen only when you run them yourself, and look in `backups/config/` after a boot that did migrate.

## Upstream status

Fixed. Issues [#50698](https://github.com/NousResearch/hermes-agent/issues/50698), [#92554](https://github.com/NousResearch/hermes-agent/issues/92554), [#63039](https://github.com/NousResearch/hermes-agent/issues/63039) and [#107511](https://github.com/NousResearch/hermes-agent/issues/107511) were all closed on 2026-09-22, between v2026.9.21 and v2026.9.24.

## Confidence and limits

Source-verified on v2026.9.21 and v2026.9.24. Local runs of `repro.sh` on 2026-11-13 printed `comments-lost` on v2026.9.21 and `comments-kept` on v2026.9.24; this becomes a stamped observation only once a CI run records it. Only `hermes config set` is exercised. Tags before v2026.9.21 are not pinned here, so the entry does not say where the behavior starts.
