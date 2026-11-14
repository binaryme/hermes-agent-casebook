---
id: E9
slug: webhook-cross-route-dedup
title: Use v0.21.6 or later before pointing two webhook routes at one GitHub event
kind: check-your-version
status: fixed
affected:
  - v2026.9.24
not_affected:
  - v0.21.6
fixed_in: v0.21.6
upstream: none-found
searched_on: 2026-11-13
evidence:
  - https://github.com/NousResearch/hermes-agent/blob/f97608f178d1ffeca59860195ab7da295f7c8e5f/gateway/platforms/webhook.py#L316-L325
  - https://github.com/NousResearch/hermes-agent/blob/f97608f178d1ffeca59860195ab7da295f7c8e5f/gateway/platforms/webhook.py#L620-L623
  - https://github.com/NousResearch/hermes-agent/blob/818c13be1dc4fd28987e1e881a9408224afd4535/gateway/platforms/webhook.py#L74-L84
  - https://github.com/NousResearch/hermes-agent/blob/818c13be1dc4fd28987e1e881a9408224afd4535/gateway/platforms/webhook.py#L357-L366
repro: entries/webhook-cross-route-dedup/repro.sh
needs_credentials: false
confidence: source-verified
verified_on: []
last_reviewed: 2026-11-13
limits: The repro sends the two deliveries one after the other from one client, not from GitHub. Only the two pinned tags around the fix are checked.
credits: []
---

## Symptom

You add two GitHub webhooks for the same event, each to its own Hermes route, for example one that posts a notice and one that reviews pull requests. Each event runs on only one of them. The one that loses answers `200 {"status": "duplicate"}`, so GitHub shows the delivery as successful, and the gateway logs only `Skipping duplicate delivery`.

## Verified on

No CI run has been recorded yet. Every statement below is source reading.

## Reproduce

`repro.sh` boots a gateway with two routes, `notify` and `review`, both accepting `push` with the same secret. It posts one GitHub-signed payload to `notify` and then the same payload with the same `X-GitHub-Delivery` id to `review`, the way GitHub does when two hooks fire on one event. It prints `duplicate` when the second route answers 200 with `"duplicate"`, `both-accepted` when it answers 202, and `second-<status>` otherwise. A first route that does not answer 202 is a repro error.

## Expected vs actual

| Tag | `review` answers | Token |
| --- | --- | --- |
| v2026.9.24 | `200 {"status": "duplicate"}` | `duplicate` |
| v0.21.6 | `202 accepted` | `both-accepted` |

## Cause

Up to v2026.9.24 the gateway remembers deliveries in one map keyed by the delivery id alone ([webhook.py L316-L325](https://github.com/NousResearch/hermes-agent/blob/f97608f178d1ffeca59860195ab7da295f7c8e5f/gateway/platforms/webhook.py#L316-L325)), and a second request with a known id gets `200 {"status": "duplicate"}` ([L620-L623](https://github.com/NousResearch/hermes-agent/blob/f97608f178d1ffeca59860195ab7da295f7c8e5f/gateway/platforms/webhook.py#L620-L623)). GitHub sends the same `X-GitHub-Delivery` to every hook subscribed to the event, so whichever route the gateway receives first wins, and the other is dropped every time. It is not a timing window: the second request is dropped no matter how late it arrives within the idempotency window.

v0.21.6 keys the map on a `_WebhookDeliveryIdentity` of profile, route and delivery id ([v0.21.6 webhook.py L74-L84](https://github.com/NousResearch/hermes-agent/blob/818c13be1dc4fd28987e1e881a9408224afd4535/gateway/platforms/webhook.py#L74-L84) and [L357-L366](https://github.com/NousResearch/hermes-agent/blob/818c13be1dc4fd28987e1e881a9408224afd4535/gateway/platforms/webhook.py#L357-L366)), so each route deduplicates only its own retries. The change is commit [30f556d0](https://github.com/NousResearch/hermes-agent/commit/30f556d094dba84905a677b9b23ffcdef19c087e), "fix(gateway): scope webhook delivery identities", dated 2026-10-01.

## Workaround

- Upgrade to v0.21.6 or later.
- On an older image, use one GitHub hook and one route per event, and let that one route do both jobs.
- Or give the second hook a different event filter, so the two routes never share a delivery.

## Upstream status

Fixed in v0.21.6 by commit [30f556d0](https://github.com/NousResearch/hermes-agent/commit/30f556d094dba84905a677b9b23ffcdef19c087e), a cherry-pick with no linked pull request. No upstream issue reporting the cross-route drop was found on 2026-11-13; searched for webhook duplicate delivery with route, `X-GitHub-Delivery` and `_seen_deliveries`.

## Confidence and limits

Source-verified on v2026.9.24 and v0.21.6. A local run of `repro.sh` on 2026-11-13 printed `duplicate` on v2026.9.24; this becomes a stamped observation only once a CI run records it. The deliveries come from the repro, not from GitHub, and tags before v2026.9.24 are not checked here.
