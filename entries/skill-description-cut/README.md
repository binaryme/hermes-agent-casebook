---
id: E4
slug: skill-description-cut
title: Keep a skill description within 60 characters, trigger words first
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
- https://github.com/NousResearch/hermes-agent/issues/13944
- https://github.com/NousResearch/hermes-agent/issues/46024
- https://github.com/NousResearch/hermes-agent/issues/84195
- https://github.com/NousResearch/hermes-agent/issues/150523
evidence:
- https://github.com/NousResearch/hermes-agent/blob/f80f453ae0679347e38abc917c7f94f717bf96c5/agent/skill_utils.py#L849
- https://github.com/NousResearch/hermes-agent/blob/f80f453ae0679347e38abc917c7f94f717bf96c5/agent/skill_utils.py#L864
- https://github.com/NousResearch/hermes-agent/blob/bf0203a794a07aac3ff764972ab9087baa4e4f4e/agent/skill_utils.py#L848-L851
- https://github.com/NousResearch/hermes-agent/blob/f0d94882e89ab8d4098b5bb2f166adfb9ee0a0ab/agent/skill_utils.py#L853-L861
- https://github.com/NousResearch/hermes-agent/blob/3b421578588243f920886e6fe79a6faa87ea026e/agent/skill_utils.py#L843-L865
- https://github.com/NousResearch/hermes-agent/blob/3b421578588243f920886e6fe79a6faa87ea026e/tools/skill_manager_tool.py#L172-L183
repro: entries/skill-description-cut/repro.sh
needs_credentials: false
confidence: source-verified
verified_on: []
last_reviewed: '2026-11-14'
limits: The repro measures the length of the description shown in the index, not whether a model picks the skill. Skills registered by plugins are listed differently and are not covered.
credits:
- hermes-field-notes by itpartypattaya, which lists the 57-character cut as a pitfall (https://github.com/itpartypattaya/hermes-field-notes/blob/d40bdbd2fad06c01cfa2d4314680c155e6ba71cb/skills/hermes-field-notes/references/known-pitfalls.md)
---

## Symptom

You write a careful `description:` with every phrase that should make the agent load the skill, and the agent still does not load it when one of those phrases comes up. The skills index in the system prompt shows only the start of the description, followed by `...`. The model sees nothing past that point until it has already decided to open the skill.

## Verified on

No CI run has been recorded yet. Every statement below is source reading.

## Reproduce

`repro.sh` adds two skills with names of the same length and runs `hermes prompt-size --json` offline:

| Skill | Description length |
| --- | --- |
| `casebook-short` | 40, never cut |
| `casebook-trims` | 75: `Rotate the webhook signing secret of every configured inbound route at once`, whose 57th character falls inside `inbound` |

The difference between the two index lines, plus 40, is the length of the description the index shows. The repro prints `hard-cut` for exactly 60 (57 characters and `...`), `word-cut` for exactly 56 (`Rotate the webhook signing secret of every configured` and `...`), `not-cut` for 75, and `shown-<length>` for anything else.

## Expected vs actual

| Tag | Index shows | Token |
| --- | --- | --- |
| v2026.8.13 to v0.22.5 | `Rotate the webhook signing secret of every configured inb...` | `hard-cut` |
| v0.22.6, v0.23.1 | `Rotate the webhook signing secret of every configured...` | `word-cut` |

## Cause

`SKILL_PROMPT_DESC_LIMIT` is 60 on every pinned tag. Up to v0.22.5 a longer description becomes its first 57 characters plus `...`, mid-word if need be ([v2026.8.13 L849](https://github.com/NousResearch/hermes-agent/blob/f80f453ae0679347e38abc917c7f94f717bf96c5/agent/skill_utils.py#L849) and [L864](https://github.com/NousResearch/hermes-agent/blob/f80f453ae0679347e38abc917c7f94f717bf96c5/agent/skill_utils.py#L864); [v0.22.5 L848-L851](https://github.com/NousResearch/hermes-agent/blob/bf0203a794a07aac3ff764972ab9087baa4e4f4e/agent/skill_utils.py#L848-L851)).

From v0.22.6, `clip_skill_description` cuts at the last whitespace within the first 58 characters, strips trailing punctuation and adds `...` ([v0.22.6 L853-L861](https://github.com/NousResearch/hermes-agent/blob/f0d94882e89ab8d4098b5bb2f166adfb9ee0a0ab/agent/skill_utils.py#L853-L861); unchanged at [v0.23.1 L846-L865](https://github.com/NousResearch/hermes-agent/blob/3b421578588243f920886e6fe79a6faa87ea026e/agent/skill_utils.py#L846-L865)). The index never shows half a word any more, but it can show much less than 57 characters: the whole word that crosses the budget is dropped, and a single word longer than the budget is still cut hard. On v0.23.1, `skill_manage` also refuses a new description longer than the limit ([skill_manager_tool.py L172-L183](https://github.com/NousResearch/hermes-agent/blob/3b421578588243f920886e6fe79a6faa87ea026e/tools/skill_manager_tool.py#L172-L183)).

## Workaround

- Keep `description:` at 60 characters or fewer. A description that fits is never cut, on any tag, and from v0.23.1 `skill_manage` refuses anything longer.
- Put the noun and the verb a real message would contain at the very start, in case a longer description from an older skill is still cut.
- Put everything else (scope, caveats, examples) in the skill body, which the model reads after it opens the skill.
- Check a description's length before you ship it: `python3 -c 'import sys; print(len(sys.argv[1]))' "<description>"`.

## Upstream status

The limit is a design choice: on v0.23.1 the comment above it says shipped skills are held to it, so only legacy or hand-edited skills ever reach the clipping code ([skill_utils.py L843-L846](https://github.com/NousResearch/hermes-agent/blob/3b421578588243f920886e6fe79a6faa87ea026e/agent/skill_utils.py#L843-L846)). [#13944](https://github.com/NousResearch/hermes-agent/issues/13944) was closed on 2026-04-26. Three requests to relax it or make it configurable were open on 2026-11-13: [#46024](https://github.com/NousResearch/hermes-agent/issues/46024), [#84195](https://github.com/NousResearch/hermes-agent/issues/84195) and [#150523](https://github.com/NousResearch/hermes-agent/issues/150523). The mid-word cut changed to a word-boundary cut in v0.22.6, which is why this entry is `fixed` with `fixed_in: v0.22.6` even though the limit itself stays.

## Confidence and limits

CI-PENDING. The repro measures what the index shows, not what a model does with it. Skills registered by plugins are listed with their full description, which hermes-field-notes reports for 0.21.6 and later; that path is not covered here.
