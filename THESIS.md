# Where Hermes Agent surprises its operators

Seven reproducible behaviors of the webhook gateway, the skills index, the config writers and the terminal environment, tested against pinned image digests.

| | |
| --- | --- |
| Author | Israel Ortiz |
| Version | 1.0.0, 2026-11-15 |
| Subject | [Hermes Agent](https://github.com/NousResearch/hermes-agent) by Nous Research, official Docker image, tags v2026.8.13 to v0.23.1 |
| Licenses | Prose CC-BY-4.0 ([LICENSE](LICENSE)); code MIT ([LICENSE-CODE](LICENSE-CODE)) |
| How to cite | [CITATION.cff](CITATION.cff) |

Independent work. Not affiliated with, endorsed by, or reviewed by Nous Research.

## Abstract

Hermes Agent is an open-source agent runtime that operators run as a long-lived gateway, often triggered by webhooks from other systems. Several of its behaviors differ from what its documentation leads an operator to expect, and they fail silently: a skill that is never offered, a second skill that is never loaded, a signed delivery that is refused, a config file that loses its comments. This work isolates seven such behaviors, states each as a falsifiable hypothesis, and tests it with a short script against official Hermes images pinned by registry digest, with a local stub in place of the language model. Every script ran in public CI on every tag its entry names; all 23 entry and tag pairs matched the hypothesis, and the transcripts of that run are committed with the text. Three behaviors are present on every tested tag, including the newest (v0.23.1); four were fixed upstream at a tag this work identifies. For each, the cause is traced to pinned source lines and a workaround is given with its cost. Six of the seven were also observed on the author's production install. The main recommendation is that a webhook route should be treated as its own platform: it has no skills index, loads one forced skill, and on older tags shares one deduplication map with every other route.

## Declaration

I set the scope and the rules of this work, operated the Hermes install it draws on, and chose what to publish.

Most of this repository was written by an AI coding agent (Claude, through Claude Code). It read the upstream source and documentation, wrote the harness, the repro scripts, the Chatwoot relay and the text, ran every repro locally, dispatched every CI run, and, with my permission, ran the read-only field observations on my install. A second, independent AI review checked the claims against their cited sources before release, and its findings were fixed.

I reviewed entry E1 against my own experience operating Hermes. The field observations compare every other entry with my install, but I have not reviewed each of those entries line by line, and I did not review the harness code line by line. The confidence of every entry comes from the CI run linked in it, not from my review.

Commits carry no AI trailers, by my choice. This declaration is the disclosure.

## Contents

1. [Introduction](#1-introduction)
2. [Background](#2-background)
3. [Method](#3-method)
4. [Results](#4-results)
5. [Discussion](#5-discussion)
6. [Threats to validity](#6-threats-to-validity)
7. [Conclusion and future work](#7-conclusion-and-future-work)
8. [References](#references)
9. [Appendices](#appendices)

## 1. Introduction

### 1.1 Problem

An operator who runs Hermes Agent as a gateway configures it through `config.yaml`, skills on disk and webhook routes, and reads the documentation to learn what each setting does. Some behaviors differ from that reading. They rarely raise an error: the gateway answers, the run completes, and the difference shows up later as an agent that did not know something, or a delivery that did nothing. Each such behavior costs an operator hours to find, and the same hours again for the next operator, because the finding stays in a private note or a chat thread.

Write-ups of such behaviors are hard to trust and go stale. They rarely say which version they describe, rarely ship a way to check, and are not revisited when the software changes.

### 1.2 Research questions

- **RQ1.** Which behaviors of the Hermes webhook gateway, skills index, config writers and terminal environment contradict what an operator would expect from the documentation?
- **RQ2.** On which published image tags is each behavior present, and at which tag did it change?
- **RQ3.** Which workaround holds on the affected tags, and at what cost?

### 1.3 Contributions

1. Seven entries, each a falsifiable hypothesis with a repro script, the tags where it holds and where it does not, the cause at pinned source lines, and a workaround ([chapter 4](#4-results)).
2. A harness that runs each script against an official image pinned by digest, without model credentials, and classes every run as `match`, `behavior-changed` or `repro-error`, so that a broken harness is never read as a behavior ([chapter 3](#3-method)).
3. Committed evidence: the results and transcripts of every CI run cited, with checksums, so the evidence outlives the CI provider's retention ([Appendix E](#appendices)).
4. A guide and a stdlib-only relay for sending Chatwoot webhooks to a Hermes route without giving the relay a secret ([Appendix A](#appendices)).
5. A weekly check that reruns every entry against the newest stable release and opens an issue when a result changes.

### 1.4 Scope

The subject is the official Docker image, `nousresearch/hermes-agent`, at seven tags from v2026.8.13 (2026-08-13) to v0.23.1. pip, Nix and desktop installs are out of scope and may differ. Model behavior is out of scope: the repros check what the gateway puts in front of the model, not what a model does with it. Security vulnerabilities are out of scope and go to upstream privately ([SECURITY.md](SECURITY.md)).

## 2. Background

### 2.1 The image and its tags

The image boots through s6 and a stage2 hook, which runs a config schema migration before the gateway starts. Its `hermes` command drops to the `hermes` user, uid 10000. Upstream changed its tag scheme in October 2026: the date-based tags (v2026.8.13, v2026.9.21, v2026.9.24) are older than the semver tags (v0.21.6, published 2026-10-08, to v0.23.1). "v0.21.6 or later" is therefore newer than every v2026 tag. [harness/images.json](harness/images.json) lists the pinned tags in release order with their publication dates.

### 2.2 The webhook gateway

With `WEBHOOK_ENABLED`, the gateway listens for HTTP deliveries on port 8644 and dispatches each to a route under `platforms.webhook.extra.routes`. A route has a secret, a prompt template that renders the payload into the agent's first message, and optionally `toolsets` and `skills`. Signatures are checked per provider: GitHub's `X-Hub-Signature-256`, and a generic V2 scheme, HMAC-SHA256 over `"{timestamp}.{body}"` with a 300-second window. A delivery id is remembered so that retries run once.

### 2.3 Skills and the skills index

A skill is a directory with a `SKILL.md`. On chat platforms the system prompt carries a skills index, one line per skill with its name and a cut description, and the model loads a skill's body with `skill_view` when the line matches the task. A webhook route can instead force skills by name with `skills:`; their bodies are injected into the message.

### 2.4 Config writers

`config.yaml` is written by `hermes config set`, by features such as enabling a plugin, and by the boot-time schema migration. Operators annotate the file by hand.

### 2.5 The terminal tool's environment

The terminal tool runs commands through bash. Its environment is captured from a login shell, so `/etc/profile` applies.

### 2.6 Chatwoot webhooks

Chatwoot, an open-source support inbox, signs outgoing webhooks from v4.11.2 with the same MAC as Hermes' V2 scheme, under its own header names. Hermes has no Chatwoot support of its own.

## 3. Method

### 3.1 Selecting behaviors

Candidates came from the author's operation of a production install and from upstream issues. A candidate became an entry only if it was (a) a difference between the documentation, or a reasonable reading of it, and the observed behavior; (b) testable without model credentials; and (c) not a security vulnerability. Candidates that upstream already documents clearly became short pointers instead ([Appendix B](#appendices)). Numbers E5, E8 and E10 to E13 were cut, deferred or made pointers, which is why the entry numbers have gaps.

### 3.2 Pinning

Every tag is pinned to its registry index digest in [harness/images.json](harness/images.json), and [harness/resolve_digest.py](harness/resolve_digest.py) verifies the manifest body against its digest before adding a pin. A re-pushed tag cannot change a result. Every source link points at a 40-character commit, never at a branch.

### 3.3 The repro contract

Each entry ships `repro.sh`, at most 30 lines, which names no tag and receives the pinned image from the harness. It prints the raw values it measures as `EVIDENCE` lines and ends with exactly one `OBSERVED=<token>` line, such as `empty-present-present`. The entry's `expect.json` gives the token the hypothesis predicts for each tag. The full contract is in [docs/entry-format.md](docs/entry-format.md) ([Appendix C](#appendices)).

### 3.4 Stub model and real gateway

Repros that need a run boot the real gateway from the pinned image and point its model at [harness/stub_model.py](harness/stub_model.py), a local OpenAI-compatible server that answers every request and records it. A repro then signs a delivery with [harness/sign.py](harness/sign.py), posts it, and reads what the gateway sent to the model. No external network or credential is involved.

### 3.5 Classification

[harness/run_repro.py](harness/run_repro.py) classes each run: `match` when the token equals the prediction, `behavior-changed` when it differs, and `repro-error` when the script fails, times out or prints no single token. Only `match` supports a hypothesis. A `repro-error` is never read as a behavior.

### 3.6 Verification in CI

The `repro` workflow runs every entry on GitHub-hosted runners against each tag in its `expect.json`, after a smoke test of the gateway and the Chatwoot relay on the oldest and newest tag. [harness/stamp.py](harness/stamp.py) then writes each matching result into the entry's `verified_on` and its Runs table, with the digest and run link. An entry is `reproduced` only when every predicted tag matched in a stamped run; until then it is `source-verified`.

### 3.7 Evidence retention

GitHub keeps this repository's artifacts and logs for 90 days at most. So `stamp.py` also copies each cited run's results and transcripts into `evidence/<run-id>/`, with the run's commit and trigger and a `SHA256SUMS` file. Every Runs table links to its transcripts.

### 3.8 Field observations

Each entry was also compared with the author's production install of v2026.8.13, with read-only commands. These are reported separately in each entry under Field observation, record counts and versions only, and are not evidence a reader can rerun ([Appendix E](#appendices)).

### 3.9 Source reading

Causes come from reading the source at the tagged commits. The text keeps the two apart: what was read is described as source reading, and only what a run printed is described as observed.

### 3.10 Watching upstream

Every week, [watch-upstream.yml](.github/workflows/watch-upstream.yml) runs every entry against the newest stable release and opens or updates an issue when a result changes.

## 4. Results

All seven hypotheses held on every tag tested. CI run [43665652222](https://github.com/binaryme/hermes-agent-casebook/actions/runs/43665652222) matched all 23 entry and tag pairs; its results and transcripts are in [evidence/43665652222](evidence/43665652222/README.md).

| Entry | Behavior | Present on | Absent from | Token where present |
| --- | --- | --- | --- | --- |
| [E1](entries/webhook-no-skills-index/README.md) | Webhook runs have no skills index | v2026.8.13, v0.23.1 | none tested | `empty-present-present` |
| [E2](entries/webhook-first-skill-only/README.md) | A route's `skills:` loads only the first resolvable skill | v2026.8.13, v0.23.1 | none tested | `alpha-only-beta-only` |
| [E3](entries/chatwoot-signature-v2/README.md) | Chatwoot's signature is refused unless its headers are mapped | v2026.8.13, v0.23.1 | none tested | `401-202-401-401` |
| [E4](entries/skill-description-cut/README.md) | The index cuts descriptions at 60 characters | v2026.8.13 to v0.22.5 (hard cut) | v0.22.6, v0.23.1 cut at a word | `hard-cut` |
| [E6](entries/config-write-drops-comments/README.md) | `config set` and the boot migration drop comments | v2026.8.13, v2026.9.21 | v2026.9.24 | `set-lost-boot-lost` |
| [E7](entries/login-shell-path/README.md) | The login shell loses the image's Python | v2026.8.13, v0.22.5 | v0.22.6, v0.23.1 | `venv-lost` |
| [E9](entries/webhook-cross-route-dedup/README.md) | One delivery id runs on only one of two routes | v2026.8.13, v2026.9.24 | v0.21.6 | `duplicate` |

Each section below states the result. The entry it links to is the full section: observation, hypothesis, method, runs, analysis, recommendation, related work and threats to validity.

### 4.1 E1: webhook runs have no skills index

The system prompt builds the index only when a skill tool is among the run's tools, and the default webhook toolset has none. Adding the `skills` toolset, to the platform or to one route, restores it, but also gives the route `skill_manage`, which lets text in an outside payload ask the agent to write a persistent skill. Forcing skills with `skills:` avoids that. No upstream report was found. [Entry](entries/webhook-no-skills-index/README.md).

### 4.2 E2: only the first listed skill is loaded

A route that lists several skills injects the first that resolves and drops the rest silently; a missing first name shifts which one loads. On the author's install, a route listing three skills never delivered the second or third in three months. Upstream pull request #139223 loads every listed skill and was unmerged when searched. [Entry](entries/webhook-first-skill-only/README.md).

### 4.3 E3: Chatwoot's signature needs mapping

Chatwoot and Hermes compute the same MAC, but Hermes reads it from other header names and without the `sha256=` prefix, so every raw Chatwoot delivery gets 401. Mapping the headers gives 202, and a changed body and a stale timestamp are still refused. [Appendix A](guides/chatwoot/README.md) gives a relay that maps them without holding the secret. [Entry](entries/chatwoot-signature-v2/README.md).

### 4.4 E4: descriptions are cut at 60 characters

The index line shows at most 60 characters of a description: up to v0.22.5 at a fixed count, from v0.22.6 at a word boundary. Trigger words placed later never reach the model. [Entry](entries/skill-description-cut/README.md).

### 4.5 E6: config writers drop comments

Before v2026.9.24, both `hermes config set` and the boot-time schema migration rewrite `config.yaml` through a plain YAML dump; the migration also adds default comment blocks the operator did not write. From v2026.9.24, one comment-preserving writer is used. [Entry](entries/config-write-drops-comments/README.md).

### 4.6 E7: the login shell loses the image's Python

Before v0.22.6, `/etc/profile` resets `PATH` in the login shell the terminal tool uses, so `python3` is the system interpreter without Hermes' modules. v0.22.6 restores the path in `/etc/profile.d`. [Entry](entries/login-shell-path/README.md).

### 4.7 E9: routes share one deduplication map

Up to v2026.9.24, a delivery id is remembered across all routes for an hour, so GitHub's single delivery id for two hooks runs one route and drops the other; which one wins depends on timing and route scripts. v0.21.6 keys the map per profile and route. [Entry](entries/webhook-cross-route-dedup/README.md).

### 4.8 Field observations

On the author's install, six of the seven behaviors were seen outside the harness: an empty webhook index beside a 95-skill CLI index (E1), a three-skill route that delivered only its first skill (E2), 18 of 19 descriptions longer than the cut (E4), a config file with no comments left (E6), the login shell resolving the system interpreter (E7), and 60 dropped duplicate deliveries in five days until one hook was removed (E9). E3 was not compared on the install. [Appendix E.2](evidence/field/2026-11-14.md).

## 5. Discussion

### 5.1 A webhook route is its own platform

Three of the seven entries (E1, E2, E9) come from the same assumption: that a webhook route behaves like a chat session triggered by HTTP. It does not. It has no skills index, it loads one forced skill, and on older tags its delivery ids share state with every other route. E3 adds that its signature schemes are provider-specific. An operator should configure each route as if it were a separate platform: decide its tools, force the one skill it needs, give it its own hook, and test it with a signed request before relying on it.

### 5.2 Writers that drop operator state

E6 shows a class rather than one bug: any component that parses and re-dumps a file loses what the parser does not keep. Until a writer is known to round-trip, the annotated copy belongs outside the data volume, under version control, and the file on the volume should be treated as generated.

### 5.3 Silent failures

None of the seven behaviors produces an error an operator would notice. E3 logs a warning that reads like a wrong secret; E2 logs nothing when a later skill is dropped; E1, E4, E6 and E7 log nothing at all. This is why they cost time, and why each entry gives the one observable check (a `prompt-size` count, a status code, a grep) that tells an operator which case they are in.

### 5.4 What to change first

On any tag: give each webhook route exactly one forced skill, or merge the skills it needs (E2); weigh `skill_manage` before adding the `skills` toolset to a route that renders outside text (E1); put trigger words in the first 55 characters of every description (E4); map Chatwoot's headers or use the relay (E3). On older tags, upgrading removes E4's hard cut, E6, E7 and E9; v0.22.6 or later covers all four.

## 6. Threats to validity

The classification follows the usual split for empirical software engineering [W1].

**Construct validity.** A token reduces a behavior to a few words, and a repro could print the predicted token for the wrong reason. Each repro prints the raw values behind its token, and the committed transcripts let a reader check that the token follows from them. The stub model replaces a language model, so the repros measure what reaches the model, not whether a model would use it.

**Internal validity.** A harness bug could pass for a behavior. Failures are classed `repro-error` and never stamped; most repros test contrasting cases in one run, such as E3's four requests or E1's three configurations, or run on tags where the behavior differs, so a harness that always printed the same answer would not match; and the gateway is the real one from the pinned image, not a reimplementation.

**External validity.** Only the official Docker image was tested, at seven tags, with minimal configurations. Other install methods, other configurations, and tags between the pinned ones may behave differently. A repro shows that a behavior is present on the listed tags; it does not show its absence anywhere else. The field observations come from one install.

**Reliability.** Images are pinned by digest, runs are public, and their evidence is committed with checksums, so a rerun on the same digests should give the same tokens. Line references are pinned to commits and drift on `main`.

**Authorship.** Most of this work was written by an AI agent ([Declaration](#declaration)). A second AI review checked the claims against their sources, and every claim of observation is backed by a CI transcript, but a reader should weigh the causes, which are source reading, accordingly. Corrections are taken through [issues](https://github.com/binaryme/hermes-agent-casebook/issues/new/choose) and recorded in the [changelog](CHANGELOG.md).

## 7. Conclusion and future work

**RQ1.** Seven behaviors contradict a reasonable reading of the documentation: four in the webhook gateway (E1, E2, E3, E9), one in the skills index (E4), one in the config writers (E6) and one in the terminal environment (E7).

**RQ2.** E1, E2 and E3 are present on every tested tag, including v0.23.1. E9 changed at v0.21.6, E6 at v2026.9.24, E7 at v0.22.6, and E4 moved from a hard cut to a word-boundary cut at v0.22.6.

**RQ3.** Every entry gives a workaround that held on its affected tags, and states its cost: the `skills` toolset for E1 brings `skill_manage`; one skill per route for E2 means merging skills; a relay for E3 is one more process; for E6, E7 and E9, upgrading is the fix and the alternatives each need care.

Future work: report E1 and E3 upstream and follow E2's pull request; extend the pinned tags as upstream releases; test the pip install; and add entries for the deferred candidates, E5 among them. The weekly watch will show when a fix lands.

## References

Upstream source links in the entries are pinned to commits; the references below are the ones this document cites directly.

- [H1] Nous Research, "Hermes Agent," GitHub repository. <https://github.com/NousResearch/hermes-agent>
- [H2] Hermes Agent v0.23.1 source, commit 3b421578. <https://github.com/NousResearch/hermes-agent/tree/3b421578588243f920886e6fe79a6faa87ea026e>
- [H3] Hermes Agent v2026.8.13 source, commit f80f453a. <https://github.com/NousResearch/hermes-agent/tree/f80f453ae0679347e38abc917c7f94f717bf96c5>
- [H4] Hermes Agent, `agent/system_prompt.py` L307-L311 at v0.23.1 (E1). <https://github.com/NousResearch/hermes-agent/blob/3b421578588243f920886e6fe79a6faa87ea026e/agent/system_prompt.py#L307-L311>
- [H5] Hermes Agent, pull request #139223, load every skill listed on a webhook route (E2). <https://github.com/NousResearch/hermes-agent/pull/139223>
- [H6] Hermes Agent, `gateway/platforms/webhook.py` L886-L901 at v0.23.1, V2 signature check (E3). <https://github.com/NousResearch/hermes-agent/blob/3b421578588243f920886e6fe79a6faa87ea026e/gateway/platforms/webhook.py#L886-L901>
- [H7] Hermes Agent, issues #50698, #92554, #63039 and #107511, config comments (E6). <https://github.com/NousResearch/hermes-agent/issues/50698>
- [H8] Hermes Agent, `docker/profile-hermes-path.sh` at v0.22.6 (E7). <https://github.com/NousResearch/hermes-agent/blob/f0d94882e89ab8d4098b5bb2f166adfb9ee0a0ab/docker/profile-hermes-path.sh>
- [H9] Hermes Agent, commit 30f556d0, per-route delivery identity (E9). <https://github.com/NousResearch/hermes-agent/commit/30f556d094dba84905a677b9b23ffcdef19c087e>
- [C1] Chatwoot, `lib/webhooks/trigger.rb` L44-L52 at v4.11.2 (E3). <https://github.com/chatwoot/chatwoot/blob/19683fae74f4d747b332b1fe6e9628da5f7e523d/lib/webhooks/trigger.rb#L44-L52>
- [W1] C. Wohlin, P. Runeson, M. Höst, M. C. Ohlsson, B. Regnell and A. Wesslén, *Experimentation in Software Engineering*. Berlin, Heidelberg: Springer, 2012.
- [S1] ISO 7144:1986, *Documentation: Presentation of theses and similar documents*. International Organization for Standardization. The layout of this document follows its front matter, body and back matter.

## Appendices

- **Appendix A. Chatwoot integration guide.** [guides/chatwoot/README.md](guides/chatwoot/README.md), with the relay in [guides/chatwoot/relay/](guides/chatwoot/relay/).
- **Appendix B. Pointers.** [POINTERS.md](POINTERS.md): documented behaviors that still surprise operators, each a short note with pinned links.
- **Appendix C. Entry format.** [docs/entry-format.md](docs/entry-format.md): the entry format, the repro contract and the rules CI enforces.
- **Appendix D. Reproducing a result.** With Docker and Python 3 with PyYAML: `python3 harness/run_repro.py --entry <slug> --tag <tag>` runs one entry against one pinned image and writes its result and transcript under `results/`; `--all-tags` runs every tag the entry predicts. `make test` runs the harness's unit tests. A local run is never stamped; only CI runs are evidence.
- **Appendix E. Evidence.** [evidence/](evidence/README.md): E.1, the results and transcripts of the cited CI runs; E.2, the [field observations](evidence/field/2026-11-14.md).
- **Index.** [INDEX.md](INDEX.md), generated from the entries' front matter.
