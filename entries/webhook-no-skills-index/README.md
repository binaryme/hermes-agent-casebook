---
id: E1
slug: webhook-no-skills-index
title: Don't expect webhook runs to discover skills without the skills toolset
kind: gotcha
status: unreported
affected:
  - v2026.8.13
  - v0.23.1
not_affected: []
fixed_in: null
upstream: none-found
searched_on: 2026-11-13
evidence:
  - https://github.com/NousResearch/hermes-agent/blob/3b421578588243f920886e6fe79a6faa87ea026e/agent/system_prompt.py#L307-L311
  - https://github.com/NousResearch/hermes-agent/blob/3b421578588243f920886e6fe79a6faa87ea026e/toolsets.py#L39
  - https://github.com/NousResearch/hermes-agent/blob/3b421578588243f920886e6fe79a6faa87ea026e/toolsets.py#L99-L103
  - https://github.com/NousResearch/hermes-agent/blob/3b421578588243f920886e6fe79a6faa87ea026e/toolsets.py#L221
  - https://github.com/NousResearch/hermes-agent/blob/3b421578588243f920886e6fe79a6faa87ea026e/gateway/platforms/webhook.py#L396-L409
  - https://github.com/NousResearch/hermes-agent/blob/f80f453ae0679347e38abc917c7f94f717bf96c5/agent/system_prompt.py#L412-L413
  - https://github.com/NousResearch/hermes-agent/blob/f80f453ae0679347e38abc917c7f94f717bf96c5/toolsets.py#L97-L102
  - https://github.com/NousResearch/hermes-agent/blob/f80f453ae0679347e38abc917c7f94f717bf96c5/toolsets.py#L640-L644
repro: entries/webhook-no-skills-index/repro.sh
needs_credentials: false
confidence: source-verified
verified_on: []
last_reviewed: 2026-11-13
limits: The repro checks whether the skills index is built, not whether a model would pick a skill from it. The workaround's effect on skill_manage was read in the source, not exercised.
credits: []
---

## Symptom

You add a skill to the skills directory, and a webhook-triggered run behaves as if it does not exist. The same skill shows up in a CLI session. Nothing in the logs says the index was skipped.

## Verified on

No CI run has been recorded yet. Every statement below is source reading.

## Reproduce

`repro.sh` puts one marker skill, `casebook-marker`, in the data directory and checks three cases:

1. `hermes prompt-size --json --platform webhook` with an empty config, offline. It reads `skills_index.chars`.
2. The same command with `platform_toolsets.webhook: [hermes-webhook, skills]`.
3. A real gateway with a route whose `toolsets` is `[skills]`. It sends one signed request and greps the request the stub model received for the marker skill.

It prints `OBSERVED=<default>-<platform workaround>-<route workaround>`, each part `empty` or `present`.

## Expected vs actual

| Case | What an operator expects | What the source does |
| --- | --- | --- |
| Default webhook toolset | the index lists `casebook-marker` | `empty` |
| `platform_toolsets.webhook` adds `skills` | listed | `present` |
| Route `toolsets: [skills]` | listed | `present` |

`expect.json` records `empty-present-present` on v2026.8.13 and v0.23.1.

## Cause

The system prompt builds the skills index only when one of `skills_list`, `skill_view` or `skill_manage` is among the run's tools, and returns an empty string otherwise ([v0.23.1 system_prompt.py L307-L311](https://github.com/NousResearch/hermes-agent/blob/3b421578588243f920886e6fe79a6faa87ea026e/agent/system_prompt.py#L307-L311); the same check at [v2026.8.13 L412-L413](https://github.com/NousResearch/hermes-agent/blob/f80f453ae0679347e38abc917c7f94f717bf96c5/agent/system_prompt.py#L412-L413)).

The default webhook toolset, `hermes-webhook`, is `web_search`, `web_extract`, `vision_analyze` and `clarify` ([v0.23.1 toolsets.py L39](https://github.com/NousResearch/hermes-agent/blob/3b421578588243f920886e6fe79a6faa87ea026e/toolsets.py#L39) and [L221](https://github.com/NousResearch/hermes-agent/blob/3b421578588243f920886e6fe79a6faa87ea026e/toolsets.py#L221)). None of the three skill tools is in it, so a webhook run never gets an index. Skills a route lists under `skills:` are still injected into the message. That path does not depend on the index.

## Workaround

Add the `skills` toolset, either for every webhook route:

```yaml
platform_toolsets:
  webhook:
    - hermes-webhook
    - skills
```

or for one route, remembering that a route's `toolsets` replaces the platform default rather than adding to it ([v0.23.1 webhook.py L396-L409](https://github.com/NousResearch/hermes-agent/blob/3b421578588243f920886e6fe79a6faa87ea026e/gateway/platforms/webhook.py#L396-L409)):

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

## Upstream status

No upstream issue or pull request found on 2026-11-13. Searched for webhook together with `skills_list`, `skill_view`, "skills index", "skills toolset" and `platform_toolsets`.

## Confidence and limits

Source-verified on v2026.8.13 and v0.23.1. Local runs of `repro.sh` on 2026-11-13 printed `empty-present-present` on both tags; this becomes a stamped observation only once a CI run records it. The repro shows that the index is built or not. It does not show which skill a model would choose from it, and it does not exercise `skill_manage`.
