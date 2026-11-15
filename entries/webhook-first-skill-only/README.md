---
id: E2
slug: webhook-first-skill-only
title: Don't list several skills on a webhook route and expect them all to load
kind: gotcha
status: open
affected:
- v2026.8.13
- v2026.9.21
- v2026.9.24
- v0.21.6
- v0.22.5
- v0.22.6
- v0.23.1
not_affected: []
fixed_in: null
upstream:
- https://github.com/NousResearch/hermes-agent/pull/139223
- https://github.com/NousResearch/hermes-agent/issues/124447
evidence:
- https://github.com/NousResearch/hermes-agent/blob/3b421578588243f920886e6fe79a6faa87ea026e/gateway/platforms/webhook.py#L649-L665
- https://github.com/NousResearch/hermes-agent/blob/3b421578588243f920886e6fe79a6faa87ea026e/website/docs/user-guide/messaging/webhooks.md?plain=1#L87
- https://github.com/NousResearch/hermes-agent/blob/f80f453ae0679347e38abc917c7f94f717bf96c5/gateway/platforms/webhook.py#L806-L829
repro: entries/webhook-first-skill-only/repro.sh
needs_credentials: false
confidence: reproduced
verified_on:
- tag: v2026.8.13
  digest: sha256:68e15ae2a6d894d0ccbd9f8aacbbe13d4d28fa5dc9b6a303970b67bb2499b1a6
  date: '2026-11-15'
  observed: alpha-only-beta-only
  run: https://github.com/binaryme/hermes-agent-casebook/actions/runs/43668393761
- tag: v2026.9.21
  digest: sha256:6bece0644e29a347e5ae17db43c36938c86f171c6f5e0cef18aa2075d331f3a3
  date: '2026-11-15'
  observed: alpha-only-beta-only
  run: https://github.com/binaryme/hermes-agent-casebook/actions/runs/43668393761
- tag: v2026.9.24
  digest: sha256:fca358f12efd65bfaaca05884166f15c0e2788375ca30d77061ac1ebc96452b7
  date: '2026-11-15'
  observed: alpha-only-beta-only
  run: https://github.com/binaryme/hermes-agent-casebook/actions/runs/43668393761
- tag: v0.21.6
  digest: sha256:55e192fba0cd4fde61142abbff5adeacff40efdb482ccd0ff877924bd274f909
  date: '2026-11-15'
  observed: alpha-only-beta-only
  run: https://github.com/binaryme/hermes-agent-casebook/actions/runs/43668393761
- tag: v0.22.5
  digest: sha256:9c5561579f3ffdf333401797094ac3a743738d6c25d40f4331c7bf77b694238d
  date: '2026-11-15'
  observed: alpha-only-beta-only
  run: https://github.com/binaryme/hermes-agent-casebook/actions/runs/43668393761
- tag: v0.22.6
  digest: sha256:d27689bc6e8581ec884a7227c9101fdaebf6c853cff8859020dac14f21452b4d
  date: '2026-11-15'
  observed: alpha-only-beta-only
  run: https://github.com/binaryme/hermes-agent-casebook/actions/runs/43668393761
- tag: v0.23.1
  digest: sha256:276d44685c65c0cb2a25f190b63c65c8906f9dc76486fb1c05ae71b5826bda08
  date: '2026-11-15'
  observed: alpha-only-beta-only
  run: https://github.com/binaryme/hermes-agent-casebook/actions/runs/43668393761
last_reviewed: '2026-11-14'
limits: The repro checks which skill bodies reach the model's input, not how a model would act on them. It covers list values only; scalar values are the separate bug in issue 124447.
credits:
- joibaremetal, who opened upstream pull request 139223 with a fix
---

## Observation

A route lists two skills under `skills:`. The agent follows the first one and ignores the second. If the first name is misspelled or missing, the second loads instead, so the route works until someone fixes the typo. If you track skill usage, every skill after the first on a route shows no use at all.

## Hypothesis

When a webhook route lists several skills under `skills:`, only the first name that resolves to an installed skill is injected into the message. The hypothesis is falsified if a route that lists two installed skills injects both, or if a route whose first name is missing injects nothing.

## Method

`repro.sh` boots a gateway with two marker skills, `casebook-alpha` (body contains `ALPHA-7Q`) and `casebook-beta` (`BETA-7Q`), and two routes:

| Route | `skills:` |
| --- | --- |
| `both-listed` | `[casebook-alpha, casebook-beta]` |
| `first-missing` | `[casebook-missing, casebook-beta]` |

It sends one signed request to each route and checks which markers reached the stub model in that route's requests. It prints `OBSERVED=<both-listed>-<first-missing>`, each part `alpha-only`, `beta-only`, `both` or `none`.

## Results

### Runs

| Tag | Observed | Date | Digest | Run | Transcript |
| --- | --- | --- | --- | --- | --- |
| v2026.8.13 | `alpha-only-beta-only` | 2026-11-15 | `sha256:68e15ae2a6d8` | [run](https://github.com/binaryme/hermes-agent-casebook/actions/runs/43668393761) | [log](../../evidence/43668393761/webhook-first-skill-only/v2026.8.13.log) |
| v2026.9.21 | `alpha-only-beta-only` | 2026-11-15 | `sha256:6bece0644e29` | [run](https://github.com/binaryme/hermes-agent-casebook/actions/runs/43668393761) | [log](../../evidence/43668393761/webhook-first-skill-only/v2026.9.21.log) |
| v2026.9.24 | `alpha-only-beta-only` | 2026-11-15 | `sha256:fca358f12efd` | [run](https://github.com/binaryme/hermes-agent-casebook/actions/runs/43668393761) | [log](../../evidence/43668393761/webhook-first-skill-only/v2026.9.24.log) |
| v0.21.6 | `alpha-only-beta-only` | 2026-11-15 | `sha256:55e192fba0cd` | [run](https://github.com/binaryme/hermes-agent-casebook/actions/runs/43668393761) | [log](../../evidence/43668393761/webhook-first-skill-only/v0.21.6.log) |
| v0.22.5 | `alpha-only-beta-only` | 2026-11-15 | `sha256:9c5561579f3f` | [run](https://github.com/binaryme/hermes-agent-casebook/actions/runs/43668393761) | [log](../../evidence/43668393761/webhook-first-skill-only/v0.22.5.log) |
| v0.22.6 | `alpha-only-beta-only` | 2026-11-15 | `sha256:d27689bc6e85` | [run](https://github.com/binaryme/hermes-agent-casebook/actions/runs/43668393761) | [log](../../evidence/43668393761/webhook-first-skill-only/v0.22.6.log) |
| v0.23.1 | `alpha-only-beta-only` | 2026-11-15 | `sha256:276d44685c65` | [run](https://github.com/binaryme/hermes-agent-casebook/actions/runs/43668393761) | [log](../../evidence/43668393761/webhook-first-skill-only/v0.23.1.log) |

### Expected and observed

| Route | The docs suggest | Observed |
| --- | --- | --- |
| `both-listed` | `both` | `alpha-only` |
| `first-missing` | `beta-only` | `beta-only` |

The docs describe the field as a "List of skill names to load for the agent run" ([webhooks.md L87 at v0.23.1](https://github.com/NousResearch/hermes-agent/blob/3b421578588243f920886e6fe79a6faa87ea026e/website/docs/user-guide/messaging/webhooks.md?plain=1#L87)). `expect.json` records `alpha-only-beta-only` on all seven pinned tags.

### Field observation

On the author's own install (the official Docker image, v2026.8.13, in production since August 2026), read on 2026-11-14 with read-only commands. This is not reproducible by a reader and is not part of the CI evidence; it shows the behavior outside the harness. [Appendix E](../../evidence/field/2026-11-14.md) lists the commands. Statements marked *operator's account* come from the operator, not from a command.

- One route lists three skills under `skills:`. Across every session that route started in three months, the body of the first skill is in the injected message of 98% and the bodies of the second and third skills are in none.
- The usage counters agree: the first skill's uses are far above its views, as for a skill injected on nearly every run, while the other two have exactly as many uses as views, as for a skill only ever opened with `skill_view`. The operator had noticed that the second skill was rarely used and had not found why (operator's account).

## Analysis

`_apply_skills` walks the list and returns as soon as one name resolves to skill content; its docstring says "Inject the first matching skill" ([v0.23.1 webhook.py L649-L665](https://github.com/NousResearch/hermes-agent/blob/3b421578588243f920886e6fe79a6faa87ea026e/gateway/platforms/webhook.py#L649-L665)). Names that do not resolve are logged as `Skill '<name>' not found` and skipped, which is why a missing first name lets the second one through. v2026.8.13 has the same loop with a `break` after the first match ([v2026.8.13 webhook.py L806-L829](https://github.com/NousResearch/hermes-agent/blob/f80f453ae0679347e38abc917c7f94f717bf96c5/gateway/platforms/webhook.py#L806-L829)).

## Recommendation

- Put the skill that matters most first, and keep one skill per route until this is fixed.
- If a route needs the content of two skills, merge them into one skill.
- Watch the gateway log for `Skill '<name>' not found`. A typo in the first name silently changes which skill runs.

## Related work

Open. Pull request [#139223](https://github.com/NousResearch/hermes-agent/pull/139223), opened 2026-10-15, makes `_apply_skills` load every listed skill; it was open with no review comments on 2026-11-13. Issue [#124447](https://github.com/NousResearch/hermes-agent/issues/124447) is a related, separate bug: a scalar `skills:` value is iterated one character at a time.

## Threats to validity

Reproduced in CI on all seven pinned tags, v2026.8.13 to v0.23.1, on 2026-11-15 ([run 43668393761](https://github.com/binaryme/hermes-agent-casebook/actions/runs/43668393761); transcripts in [evidence/43668393761](../../evidence/43668393761/README.md)), each against the digest pinned in `harness/images.json`. The causes are source-verified at the linked lines. The repro inspects the model's input only. When pull request 139223 or another fix ships, the expected token for that tag becomes `both-beta-only`.
