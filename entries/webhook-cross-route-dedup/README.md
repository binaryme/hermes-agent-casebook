---
id: E9
slug: webhook-cross-route-dedup
title: Use v0.21.6 or later before pointing two webhook routes at one GitHub event
kind: check-your-version
status: fixed
affected:
- v2026.8.13
- v2026.9.24
not_affected:
- v0.21.6
fixed_in: v0.21.6
upstream:
- https://github.com/NousResearch/hermes-agent/issues/7448
- https://github.com/NousResearch/hermes-agent/pull/130692
- https://github.com/NousResearch/hermes-agent/pull/129626
evidence:
- https://github.com/NousResearch/hermes-agent/blob/f80f453ae0679347e38abc917c7f94f717bf96c5/gateway/platforms/webhook.py#L451-L460
- https://github.com/NousResearch/hermes-agent/blob/f97608f178d1ffeca59860195ab7da295f7c8e5f/gateway/platforms/webhook.py#L603-L623
- https://github.com/NousResearch/hermes-agent/blob/f97608f178d1ffeca59860195ab7da295f7c8e5f/gateway/platforms/webhook.py#L316-L325
- https://github.com/NousResearch/hermes-agent/blob/f97608f178d1ffeca59860195ab7da295f7c8e5f/gateway/platforms/webhook.py#L620-L623
- https://github.com/NousResearch/hermes-agent/blob/818c13be1dc4fd28987e1e881a9408224afd4535/gateway/platforms/webhook.py#L74-L84
- https://github.com/NousResearch/hermes-agent/blob/818c13be1dc4fd28987e1e881a9408224afd4535/gateway/platforms/webhook.py#L357-L366
repro: entries/webhook-cross-route-dedup/repro.sh
needs_credentials: false
confidence: reproduced
verified_on:
- tag: v2026.8.13
  digest: sha256:68e15ae2a6d894d0ccbd9f8aacbbe13d4d28fa5dc9b6a303970b67bb2499b1a6
  date: '2026-11-14'
  observed: duplicate
  run: https://github.com/binaryme/hermes-agent-casebook/actions/runs/43544045802
- tag: v2026.9.24
  digest: sha256:fca358f12efd65bfaaca05884166f15c0e2788375ca30d77061ac1ebc96452b7
  date: '2026-11-14'
  observed: duplicate
  run: https://github.com/binaryme/hermes-agent-casebook/actions/runs/43544045802
- tag: v0.21.6
  digest: sha256:55e192fba0cd4fde61142abbff5adeacff40efdb482ccd0ff877924bd274f909
  date: '2026-11-14'
  observed: both-accepted
  run: https://github.com/binaryme/hermes-agent-casebook/actions/runs/43544045802
last_reviewed: '2026-11-14'
limits: The repro sends the two deliveries one after the other from one client, not from GitHub. It does not cover routes with a script, where the winner can change from event to event.
credits:
- frogGuaGuaGuaGua, who reported the bug upstream in issue 7448
- Froraut, who wrote the first fix in pull request 129626
- kshitijk4poor, who landed it in pull request 130692
---

## Symptom

You add two GitHub webhooks for the same event, each to its own Hermes route, for example one that posts a notice and one that reviews pull requests. Each event runs on only one of them, and over time the split between the two can look uneven. The one that loses answers `200 {"status": "duplicate"}`, so GitHub shows the delivery as successful, and the gateway logs only `Skipping duplicate delivery`.

## Verified on

| Tag | Observed | Date | Digest | Run |
| --- | --- | --- | --- | --- |
| v2026.8.13 | `duplicate` | 2026-11-14 | `sha256:68e15ae2a6d8` | [run](https://github.com/binaryme/hermes-agent-casebook/actions/runs/43544045802) |
| v2026.9.24 | `duplicate` | 2026-11-14 | `sha256:fca358f12efd` | [run](https://github.com/binaryme/hermes-agent-casebook/actions/runs/43544045802) |
| v0.21.6 | `both-accepted` | 2026-11-14 | `sha256:55e192fba0cd` | [run](https://github.com/binaryme/hermes-agent-casebook/actions/runs/43544045802) |

## Reproduce

`repro.sh` boots a gateway with two routes, `notify` and `review`, both accepting `push` with the same secret. It posts one GitHub-signed payload to `notify` and then the same payload with the same `X-GitHub-Delivery` id to `review`, the way GitHub does when two hooks fire on one event. It prints `duplicate` when the second route answers 200 with `"duplicate"`, `both-accepted` when it answers 202, and `second-<status>` otherwise. A first route that does not answer 202 is a repro error.

## Expected vs actual

| Tag | `review` answers | Token |
| --- | --- | --- |
| v2026.8.13, v2026.9.24 | `200 {"status": "duplicate"}` | `duplicate` |
| v0.21.6 | `202 accepted` | `both-accepted` |

## Cause

Up to v2026.9.24 the gateway remembers deliveries in one map keyed by the delivery id alone ([v2026.9.24 webhook.py L316-L325](https://github.com/NousResearch/hermes-agent/blob/f97608f178d1ffeca59860195ab7da295f7c8e5f/gateway/platforms/webhook.py#L316-L325); the same at [v2026.8.13 L451-L460](https://github.com/NousResearch/hermes-agent/blob/f80f453ae0679347e38abc917c7f94f717bf96c5/gateway/platforms/webhook.py#L451-L460)), and a second request with a known id gets `200 {"status": "duplicate"}` ([L620-L623](https://github.com/NousResearch/hermes-agent/blob/f97608f178d1ffeca59860195ab7da295f7c8e5f/gateway/platforms/webhook.py#L620-L623)). GitHub sends the same `X-GitHub-Delivery` to every hook subscribed to the event, so one route runs and the other is dropped, every time.

It is not a narrow timing race: the id stays remembered for an hour, so the second request is dropped however late it comes. What varies is which route wins. It is whichever request reaches the deduplication check first, and a route `script` runs before that check ([L603-L623](https://github.com/NousResearch/hermes-agent/blob/f97608f178d1ffeca59860195ab7da295f7c8e5f/gateway/platforms/webhook.py#L603-L623)), so a route with a slow script can lose even when its request arrived first. That is why the split between two routes can look random.

v0.21.6 keys the map on a `_WebhookDeliveryIdentity` of profile, route and delivery id ([v0.21.6 webhook.py L74-L84](https://github.com/NousResearch/hermes-agent/blob/818c13be1dc4fd28987e1e881a9408224afd4535/gateway/platforms/webhook.py#L74-L84) and [L357-L366](https://github.com/NousResearch/hermes-agent/blob/818c13be1dc4fd28987e1e881a9408224afd4535/gateway/platforms/webhook.py#L357-L366)), so each route deduplicates only its own retries. The change is commit [30f556d0](https://github.com/NousResearch/hermes-agent/commit/30f556d094dba84905a677b9b23ffcdef19c087e), dated 2026-10-01.

Upstream switched tag schemes between these releases: v0.21.6 was published on 2026-10-08, after v2026.9.24 (2026-09-24). "v0.21.6 or later" includes every v0.22 and v0.23 release.

## Workaround

- Upgrade to v0.21.6 or later.
- On an older image, use one GitHub hook and one route per event, and let that one route do both jobs.
- Or give the second hook a different event filter, so the two routes never share a delivery.

## Upstream status

Fixed. Issue [#7448](https://github.com/NousResearch/hermes-agent/issues/7448), "Webhook idempotency is keyed only by delivery ID, so the second route is skipped in valid multi-route fan-out", was opened on 2026-04-10. Pull request [#130692](https://github.com/NousResearch/hermes-agent/pull/130692) fixed it, salvaging [#129626](https://github.com/NousResearch/hermes-agent/pull/129626), and was merged on 2026-10-01; the fix ships in v0.21.6.

## Confidence and limits

Reproduced in CI on v2026.8.13, v2026.9.24 and v0.21.6 on 2026-11-14 ([run 43544045802](https://github.com/binaryme/hermes-agent-casebook/actions/runs/43544045802)), each against the digest pinned in `harness/images.json`. The causes are source-verified at the linked lines. The deliveries come from the repro, not from GitHub, and routes with a `script` are not covered.
