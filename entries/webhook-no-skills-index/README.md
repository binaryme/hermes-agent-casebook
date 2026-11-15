---
id: E1
slug: webhook-no-skills-index
title: Don't expect webhook runs to discover skills without the skills toolset
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
- https://github.com/NousResearch/hermes-agent/issues/156206
- https://github.com/NousResearch/hermes-agent/pull/156218
evidence:
- https://github.com/NousResearch/hermes-agent/blob/3b421578588243f920886e6fe79a6faa87ea026e/agent/system_prompt.py#L307-L311
- https://github.com/NousResearch/hermes-agent/blob/3b421578588243f920886e6fe79a6faa87ea026e/toolsets.py#L39
- https://github.com/NousResearch/hermes-agent/blob/3b421578588243f920886e6fe79a6faa87ea026e/toolsets.py#L99-L103
- https://github.com/NousResearch/hermes-agent/blob/3b421578588243f920886e6fe79a6faa87ea026e/toolsets.py#L221
- https://github.com/NousResearch/hermes-agent/blob/3b421578588243f920886e6fe79a6faa87ea026e/gateway/platforms/webhook.py#L396-L409
- https://github.com/NousResearch/hermes-agent/blob/3b421578588243f920886e6fe79a6faa87ea026e/gateway/run_turn.py#L435-L451
- https://github.com/NousResearch/hermes-agent/blob/f80f453ae0679347e38abc917c7f94f717bf96c5/agent/system_prompt.py#L412-L413
- https://github.com/NousResearch/hermes-agent/blob/f80f453ae0679347e38abc917c7f94f717bf96c5/toolsets.py#L97-L102
- https://github.com/NousResearch/hermes-agent/blob/f80f453ae0679347e38abc917c7f94f717bf96c5/toolsets.py#L640-L644
repro: entries/webhook-no-skills-index/repro.sh
needs_credentials: false
confidence: reproduced
verified_on:
- tag: v2026.8.13
  digest: sha256:68e15ae2a6d894d0ccbd9f8aacbbe13d4d28fa5dc9b6a303970b67bb2499b1a6
  date: '2026-11-15'
  observed: empty-present-present
  run: https://github.com/binaryme/hermes-agent-casebook/actions/runs/43668393761
- tag: v2026.9.21
  digest: sha256:6bece0644e29a347e5ae17db43c36938c86f171c6f5e0cef18aa2075d331f3a3
  date: '2026-11-15'
  observed: empty-present-present
  run: https://github.com/binaryme/hermes-agent-casebook/actions/runs/43668393761
- tag: v2026.9.24
  digest: sha256:fca358f12efd65bfaaca05884166f15c0e2788375ca30d77061ac1ebc96452b7
  date: '2026-11-15'
  observed: empty-present-present
  run: https://github.com/binaryme/hermes-agent-casebook/actions/runs/43668393761
- tag: v0.21.6
  digest: sha256:55e192fba0cd4fde61142abbff5adeacff40efdb482ccd0ff877924bd274f909
  date: '2026-11-15'
  observed: empty-present-present
  run: https://github.com/binaryme/hermes-agent-casebook/actions/runs/43668393761
- tag: v0.22.5
  digest: sha256:9c5561579f3ffdf333401797094ac3a743738d6c25d40f4331c7bf77b694238d
  date: '2026-11-15'
  observed: empty-present-present
  run: https://github.com/binaryme/hermes-agent-casebook/actions/runs/43668393761
- tag: v0.22.6
  digest: sha256:d27689bc6e8581ec884a7227c9101fdaebf6c853cff8859020dac14f21452b4d
  date: '2026-11-15'
  observed: empty-present-present
  run: https://github.com/binaryme/hermes-agent-casebook/actions/runs/43668393761
- tag: v0.23.1
  digest: sha256:276d44685c65c0cb2a25f190b63c65c8906f9dc76486fb1c05ae71b5826bda08
  date: '2026-11-15'
  observed: empty-present-present
  run: https://github.com/binaryme/hermes-agent-casebook/actions/runs/43668393761
last_reviewed: '2026-11-14'
limits: The repro checks whether the skills index is built, not whether a model would pick a skill from it. The workaround's effect on skill_manage was read in the source, not exercised.
credits: []
---

## Observation

You add a skill to the skills directory, and a webhook-triggered run behaves as if it does not exist. The same skill shows up in a CLI session. Nothing in the logs says the index was skipped.

## Hypothesis

A webhook run's system prompt has no skills index unless the run's tools include `skills_list`, `skill_view` or `skill_manage`, and adding the `skills` toolset, for the platform or for one route, restores it. The hypothesis is falsified if the default webhook prompt, as `hermes prompt-size --platform webhook` builds it, lists the marker skill, or if either workaround leaves it out of the prompt or of a real gateway run.

## Method

`repro.sh` puts one marker skill, `casebook-marker`, in the data directory and checks three cases:

1. `hermes prompt-size --json --platform webhook` with an empty config, offline. It reads `skills_index.chars`.
2. The same command with `platform_toolsets.webhook: [hermes-webhook, skills]`.
3. A real gateway with a route whose `toolsets` is `[hermes-webhook, skills]`, the configuration recommended below. It sends one signed request and greps the request the stub model received for the marker skill.

It prints `OBSERVED=<default>-<platform workaround>-<route workaround>`, each part `empty` or `present`.

## Results

### Runs

| Tag | Observed | Date | Digest | Run | Transcript |
| --- | --- | --- | --- | --- | --- |
| v2026.8.13 | `empty-present-present` | 2026-11-15 | `sha256:68e15ae2a6d8` | [run](https://github.com/binaryme/hermes-agent-casebook/actions/runs/43668393761) | [log](../../evidence/43668393761/webhook-no-skills-index/v2026.8.13.log) |
| v2026.9.21 | `empty-present-present` | 2026-11-15 | `sha256:6bece0644e29` | [run](https://github.com/binaryme/hermes-agent-casebook/actions/runs/43668393761) | [log](../../evidence/43668393761/webhook-no-skills-index/v2026.9.21.log) |
| v2026.9.24 | `empty-present-present` | 2026-11-15 | `sha256:fca358f12efd` | [run](https://github.com/binaryme/hermes-agent-casebook/actions/runs/43668393761) | [log](../../evidence/43668393761/webhook-no-skills-index/v2026.9.24.log) |
| v0.21.6 | `empty-present-present` | 2026-11-15 | `sha256:55e192fba0cd` | [run](https://github.com/binaryme/hermes-agent-casebook/actions/runs/43668393761) | [log](../../evidence/43668393761/webhook-no-skills-index/v0.21.6.log) |
| v0.22.5 | `empty-present-present` | 2026-11-15 | `sha256:9c5561579f3f` | [run](https://github.com/binaryme/hermes-agent-casebook/actions/runs/43668393761) | [log](../../evidence/43668393761/webhook-no-skills-index/v0.22.5.log) |
| v0.22.6 | `empty-present-present` | 2026-11-15 | `sha256:d27689bc6e85` | [run](https://github.com/binaryme/hermes-agent-casebook/actions/runs/43668393761) | [log](../../evidence/43668393761/webhook-no-skills-index/v0.22.6.log) |
| v0.23.1 | `empty-present-present` | 2026-11-15 | `sha256:276d44685c65` | [run](https://github.com/binaryme/hermes-agent-casebook/actions/runs/43668393761) | [log](../../evidence/43668393761/webhook-no-skills-index/v0.23.1.log) |

### Expected and observed

| Case | What an operator expects | Observed |
| --- | --- | --- |
| Default webhook toolset | the index lists `casebook-marker` | `empty` |
| `platform_toolsets.webhook` adds `skills` | listed | `present` |
| Route `toolsets: [hermes-webhook, skills]` | listed | `present` |

`expect.json` records `empty-present-present` on all seven pinned tags.

### Field observation

On the author's own install (the official Docker image, v2026.8.13, in production since August 2026), read on 2026-11-14 with read-only commands. This is not reproducible by a reader and is not part of the CI evidence; it shows the behavior outside the harness. [Appendix E](../../evidence/field/2026-11-14.md) lists the commands. Statements marked *operator's account* come from the operator, not from a command.

- `hermes prompt-size --platform cli` lists 95 skills in a 9,794-character index; `--platform webhook` on the same install gives a 0-character index.
- Every webhook route that needs a skill names it under `skills:`; no route and no platform setting adds the `skills` toolset. That is the workaround without `skill_manage`.
- Two skills on the install have `created_by: agent` in the usage file: the agent wrote them itself, on a platform that has the skill tools (operator's account). A skill the agent writes is persistent and is offered to every platform afterwards, which is the risk the recommendation weighs.

## Analysis

The system prompt builds the skills index only when one of `skills_list`, `skill_view` or `skill_manage` is among the run's tools, and returns an empty string otherwise ([v0.23.1 system_prompt.py L307-L311](https://github.com/NousResearch/hermes-agent/blob/3b421578588243f920886e6fe79a6faa87ea026e/agent/system_prompt.py#L307-L311); the same check at [v2026.8.13 L412-L413](https://github.com/NousResearch/hermes-agent/blob/f80f453ae0679347e38abc917c7f94f717bf96c5/agent/system_prompt.py#L412-L413)).

The default webhook toolset, `hermes-webhook`, is `web_search`, `web_extract`, `vision_analyze` and `clarify` ([v0.23.1 toolsets.py L39](https://github.com/NousResearch/hermes-agent/blob/3b421578588243f920886e6fe79a6faa87ea026e/toolsets.py#L39) and [L221](https://github.com/NousResearch/hermes-agent/blob/3b421578588243f920886e6fe79a6faa87ea026e/toolsets.py#L221)). None of the three skill tools is in it, so a webhook run never gets an index. Skills a route lists under `skills:` are still injected into the message. That path does not depend on the index.

## Recommendation

Add the `skills` toolset, either for every webhook route:

```yaml
platform_toolsets:
  webhook:
    - hermes-webhook
    - skills
```

or for one route, remembering that a route's `toolsets` replaces the platform default rather than adding to it: the gateway puts the route's list in place of `platform_toolsets.webhook` for that run ([v0.23.1 run_turn.py L435-L451](https://github.com/NousResearch/hermes-agent/blob/3b421578588243f920886e6fe79a6faa87ea026e/gateway/run_turn.py#L435-L451); the route lookup is [webhook.py L396-L409](https://github.com/NousResearch/hermes-agent/blob/3b421578588243f920886e6fe79a6faa87ea026e/gateway/platforms/webhook.py#L396-L409), and the docs say "replaces" in [webhooks.md L88](https://github.com/NousResearch/hermes-agent/blob/3b421578588243f920886e6fe79a6faa87ea026e/website/docs/user-guide/messaging/webhooks.md?plain=1#L88)). Keep `hermes-webhook` in the list, or the route loses the default web tools:

```yaml
platforms:
  webhook:
    extra:
      routes:
        my-route:
          toolsets: [hermes-webhook, skills]
```

Weigh this before you do it. The `skills` toolset is `skills_list`, `skill_view` and `skill_manage` ([v0.23.1 toolsets.py L99-L103](https://github.com/NousResearch/hermes-agent/blob/3b421578588243f920886e6fe79a6faa87ea026e/toolsets.py#L99-L103)). `skill_manage` creates and edits skills. A webhook route usually renders payload text from an outside sender into the prompt. With this toolset, text injected into that payload can ask the agent to write a persistent skill, which later runs on every platform will load.

If the route only ever needs a fixed set of skills, list them under the route's `skills:` instead and leave the toolset alone. That avoids `skill_manage`. Read [E2](../webhook-first-skill-only/README.md) first: only the first resolvable name in that list is injected.

## Related work

No earlier upstream issue or pull request was found on 2026-11-13 or on 2026-11-15, when the search was repeated over issues and pull requests in every state and over the source on `main`. Searched for webhook together with `skills_list`, `skill_view`, "skills index", "skills toolset" and `platform_toolsets`.

The author reported it on 2026-11-15:

- [#156206](https://github.com/NousResearch/hermes-agent/issues/156206), open: the missing documentation, with this entry's repro.
- [#156218](https://github.com/NousResearch/hermes-agent/pull/156218), open: a subsection of the webhooks guide that says when a webhook run gets a skills index, and that the `skills` toolset includes `skill_manage`.

## Threats to validity

Reproduced in CI on all seven pinned tags, v2026.8.13 to v0.23.1, on 2026-11-15 ([run 43668393761](https://github.com/binaryme/hermes-agent-casebook/actions/runs/43668393761); transcripts in [evidence/43668393761](../../evidence/43668393761/README.md)), each against the digest pinned in `harness/images.json`. The causes are source-verified at the linked lines. The repro shows that the index is built or not. It does not show which skill a model would choose from it, and it does not exercise `skill_manage`.
