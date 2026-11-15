---
id: E6
slug: config-write-drops-comments
title: Use v2026.9.24 or later before letting Hermes write a commented config.yaml
kind: check-your-version
status: fixed
affected:
- v2026.8.13
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
- https://github.com/NousResearch/hermes-agent/blob/f80f453ae0679347e38abc917c7f94f717bf96c5/hermes_cli/config.py#L5277
- https://github.com/NousResearch/hermes-agent/blob/f80f453ae0679347e38abc917c7f94f717bf96c5/utils.py#L475-L535
- https://github.com/NousResearch/hermes-agent/blob/d337b736aa1e8ebecfab043842d13e4a2d2f48a3/hermes_cli/config.py#L3411-L3414
- https://github.com/NousResearch/hermes-agent/blob/d337b736aa1e8ebecfab043842d13e4a2d2f48a3/hermes_cli/config.py#L1305-L1310
- https://github.com/NousResearch/hermes-agent/blob/d337b736aa1e8ebecfab043842d13e4a2d2f48a3/hermes_cli/config.py#L2372-L2410
- https://github.com/NousResearch/hermes-agent/blob/d337b736aa1e8ebecfab043842d13e4a2d2f48a3/utils.py#L417-L426
- https://github.com/NousResearch/hermes-agent/blob/d337b736aa1e8ebecfab043842d13e4a2d2f48a3/docker/stage2-hook.sh#L623-L632
- https://github.com/NousResearch/hermes-agent/blob/d337b736aa1e8ebecfab043842d13e4a2d2f48a3/scripts/docker_config_migrate.py#L45-L52
- https://github.com/NousResearch/hermes-agent/blob/f97608f178d1ffeca59860195ab7da295f7c8e5f/hermes_cli/config.py#L3447-L3450
- https://github.com/NousResearch/hermes-agent/blob/f97608f178d1ffeca59860195ab7da295f7c8e5f/hermes_cli/config.py#L2016-L2020
repro: entries/config-write-drops-comments/repro.sh
needs_credentials: false
confidence: reproduced
verified_on:
- tag: v2026.8.13
  digest: sha256:68e15ae2a6d894d0ccbd9f8aacbbe13d4d28fa5dc9b6a303970b67bb2499b1a6
  date: '2026-11-14'
  observed: set-lost-boot-lost
  run: https://github.com/binaryme/hermes-agent-casebook/actions/runs/43544045802
- tag: v2026.9.21
  digest: sha256:6bece0644e29a347e5ae17db43c36938c86f171c6f5e0cef18aa2075d331f3a3
  date: '2026-11-14'
  observed: set-lost-boot-lost
  run: https://github.com/binaryme/hermes-agent-casebook/actions/runs/43544045802
- tag: v2026.9.24
  digest: sha256:fca358f12efd65bfaaca05884166f15c0e2788375ca30d77061ac1ebc96452b7
  date: '2026-11-14'
  observed: set-kept-boot-kept
  run: https://github.com/binaryme/hermes-agent-casebook/actions/runs/43544045802
last_reviewed: '2026-11-14'
limits: The repro exercises two writers, hermes config set and the boot-time schema migration from version 30. Other writers, such as enabling a plugin, were read in the source and not run.
credits: []
---

## Observation

You annotate `config.yaml` by hand: why a limit is set, which block is disabled and why. Then one of two things happens:

- you run `hermes config set`, or
- the container restarts after an image upgrade.

Every comment you wrote is gone. After the restart, the file may instead hold dozens of comment lines you never wrote: default boilerplate that replaced yours. Nothing warns you, and the values themselves are still right, so it is easy to notice weeks later.

## Hypothesis

Before v2026.9.24, both `hermes config set` and the boot-time schema migration rewrite `config.yaml` without the operator's comments, and from v2026.9.24 both keep them. The hypothesis is falsified if either writer keeps both comment lines on an affected tag, or drops one on v2026.9.24.

## Method

`repro.sh` writes a `config.yaml` with two comment lines at run time, so no file in this repository carries comment lines. It then checks two writers, each on its own copy:

1. `hermes config set agent.max_turns 42`, run directly, the same path as `docker exec <container> hermes config set`. It skips the image entrypoint, so the boot migration cannot interfere.
2. A normal boot through the image entrypoint, with `_config_version: 30` in the file, so the boot-time schema migration runs. The repro fails as a repro error if the version did not change.

The image's `hermes` command drops to the `hermes` user (uid 10000) before it writes. So the repro opens the data directory's permissions first, and reads the result back through a second container. For each writer it checks whether both original comment lines are still present, by exact text, so boilerplate comments added by the writer cannot pass for the operator's. It prints `set-<kept|lost>-boot-<kept|lost>`.

## Results

### Runs

| Tag | Observed | Date | Digest | Run |
| --- | --- | --- | --- | --- |
| v2026.8.13 | `set-lost-boot-lost` | 2026-11-14 | `sha256:68e15ae2a6d8` | [run](https://github.com/binaryme/hermes-agent-casebook/actions/runs/43544045802) |
| v2026.9.21 | `set-lost-boot-lost` | 2026-11-14 | `sha256:6bece0644e29` | [run](https://github.com/binaryme/hermes-agent-casebook/actions/runs/43544045802) |
| v2026.9.24 | `set-kept-boot-kept` | 2026-11-14 | `sha256:fca358f12efd` | [run](https://github.com/binaryme/hermes-agent-casebook/actions/runs/43544045802) |

### Expected and observed

| Tag | `config set` | Boot migration | Token |
| --- | --- | --- | --- |
| v2026.8.13, v2026.9.21 | comments lost | comments lost | `set-lost-boot-lost` |
| v2026.9.24 | kept | kept | `set-kept-boot-kept` |

In local runs on 2026-11-13 and 2026-11-14 the boot migrated the file from schema 30 to 34 on v2026.8.13, to 45 on v2026.9.21 and to 46 on v2026.9.24. On v2026.9.21 it left 36 comment lines of default boilerplate in place of the two original ones. These counts are from local runs, not from the repro.

## Analysis

On v2026.8.13 and v2026.9.21, `config set` writes the raw user config through `atomic_yaml_write` ([v2026.8.13 config.py L5277](https://github.com/NousResearch/hermes-agent/blob/f80f453ae0679347e38abc917c7f94f717bf96c5/hermes_cli/config.py#L5277); [v2026.9.21 L3411-L3414](https://github.com/NousResearch/hermes-agent/blob/d337b736aa1e8ebecfab043842d13e4a2d2f48a3/hermes_cli/config.py#L3411-L3414)). That function is a plain PyYAML `yaml.dump` of the parsed data ([v2026.8.13 utils.py L475-L535](https://github.com/NousResearch/hermes-agent/blob/f80f453ae0679347e38abc917c7f94f717bf96c5/utils.py#L475-L535); [v2026.9.21 L417-L426](https://github.com/NousResearch/hermes-agent/blob/d337b736aa1e8ebecfab043842d13e4a2d2f48a3/utils.py#L417-L426)). Parsing drops comments, so the dump has none of yours. A comment-preserving ruamel writer already existed in v2026.9.21's `utils.py`, but `config set` did not use it.

The boot migration is a second writer. The image's stage2 hook runs `scripts/docker_config_migrate.py` whenever `config.yaml` exists ([stage2-hook.sh L623-L632](https://github.com/NousResearch/hermes-agent/blob/d337b736aa1e8ebecfab043842d13e4a2d2f48a3/docker/stage2-hook.sh#L623-L632)). That script does nothing in three cases ([docker_config_migrate.py L45-L52](https://github.com/NousResearch/hermes-agent/blob/d337b736aa1e8ebecfab043842d13e4a2d2f48a3/scripts/docker_config_migrate.py#L45-L52)):

- `HERMES_SKIP_CONFIG_MIGRATION` is set;
- the config is already at the image's schema version;
- the config is older than the version-12 support floor.

Otherwise it migrates. On v2026.9.21 the migration persists through `save_config` ([L1305-L1310](https://github.com/NousResearch/hermes-agent/blob/d337b736aa1e8ebecfab043842d13e4a2d2f48a3/hermes_cli/config.py#L1305-L1310)), which writes with the same `atomic_yaml_write` and appends commented default sections ([L2372-L2410](https://github.com/NousResearch/hermes-agent/blob/d337b736aa1e8ebecfab043842d13e4a2d2f48a3/hermes_cli/config.py#L2372-L2410)). Every image upgrade that raises the schema version therefore rewrites your file.

From v2026.9.24, `_write_user_config` calls `atomic_config_write` ([config.py L3447-L3450](https://github.com/NousResearch/hermes-agent/blob/f97608f178d1ffeca59860195ab7da295f7c8e5f/hermes_cli/config.py#L3447-L3450)). Its docstring calls it "THE config.yaml writer", comment-preserving through a ruamel round-trip, and says `save_config`, `config set` and migrations all go through it ([L2016-L2020](https://github.com/NousResearch/hermes-agent/blob/f97608f178d1ffeca59860195ab7da295f7c8e5f/hermes_cli/config.py#L2016-L2020)).

## Recommendation

- Upgrade to v2026.9.24 or later before you let anything write the config.
- On v2026.9.21 or earlier, set `HERMES_SKIP_CONFIG_MIGRATION=1` on the container, so an image upgrade does not rewrite the file at boot. Run migrations yourself, after taking a copy.
- On those versions, also keep the annotated copy outside the data volume, under version control, and treat `config.yaml` on the volume as generated. Diff the two after every `config set`, plugin enable or upgrade.
- Edit the file by parsing and dumping it yourself, never by text replacement, and expect the comments to go either way until you upgrade.
- After a boot that migrated, the previous file is kept as a backup. On v2026.8.13 the local run left it next to the config as `config.yaml.bak-<timestamp>`; on v2026.9.21 and v2026.9.24 it was under `backups/config/` as `config.yaml.pre-docker-migrate.<timestamp>`.

## Related work

Fixed. Issues [#50698](https://github.com/NousResearch/hermes-agent/issues/50698), [#92554](https://github.com/NousResearch/hermes-agent/issues/92554), [#63039](https://github.com/NousResearch/hermes-agent/issues/63039) and [#107511](https://github.com/NousResearch/hermes-agent/issues/107511) were all closed on 2026-09-22, between v2026.9.21 and v2026.9.24.

## Threats to validity

Reproduced in CI on v2026.8.13, v2026.9.21 and v2026.9.24 on 2026-11-14 ([run 43544045802](https://github.com/binaryme/hermes-agent-casebook/actions/runs/43544045802)), each against the digest pinned in `harness/images.json`. The causes are source-verified at the linked lines. Two writers are exercised: `config set`, and a boot migration from schema version 30. Other writers, such as enabling a plugin, are source reading only.
