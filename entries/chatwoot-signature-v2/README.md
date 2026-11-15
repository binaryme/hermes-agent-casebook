---
id: E3
slug: chatwoot-signature-v2
title: Map Chatwoot's signature headers before pointing Chatwoot at a Hermes webhook
kind: gotcha
status: unreported
affected:
- v2026.8.13
- v0.23.1
not_affected: []
fixed_in: null
upstream:
- https://github.com/NousResearch/hermes-agent/issues/84580
- https://github.com/NousResearch/hermes-agent/pull/85318
- https://github.com/NousResearch/hermes-agent/pull/90995
evidence:
- https://github.com/NousResearch/hermes-agent/blob/3b421578588243f920886e6fe79a6faa87ea026e/gateway/platforms/webhook.py#L886-L901
- https://github.com/NousResearch/hermes-agent/blob/3b421578588243f920886e6fe79a6faa87ea026e/gateway/platforms/webhook.py#L77-L80
- https://github.com/NousResearch/hermes-agent/blob/3b421578588243f920886e6fe79a6faa87ea026e/gateway/platforms/webhook.py#L70
- https://github.com/NousResearch/hermes-agent/blob/3b421578588243f920886e6fe79a6faa87ea026e/gateway/platforms/webhook.py#L550-L557
- https://github.com/NousResearch/hermes-agent/blob/f80f453ae0679347e38abc917c7f94f717bf96c5/gateway/platforms/webhook.py#L1108-L1149
- https://github.com/chatwoot/chatwoot/blob/19683fae74f4d747b332b1fe6e9628da5f7e523d/lib/webhooks/trigger.rb#L44-L52
- https://github.com/chatwoot/chatwoot/blob/caab07a8f00032d5205b5a5d7e2eb0ba2f3d2d82/lib/webhooks/trigger.rb#L54-L62
- https://github.com/chatwoot/chatwoot/blob/a08125e283b8e15b84b5073def1e785137b059ba/lib/webhooks/trigger.rb
repro: entries/chatwoot-signature-v2/repro.sh
needs_credentials: false
confidence: reproduced
verified_on:
- tag: v2026.8.13
  digest: sha256:68e15ae2a6d894d0ccbd9f8aacbbe13d4d28fa5dc9b6a303970b67bb2499b1a6
  date: '2026-11-14'
  observed: 401-202-401-401
  run: https://github.com/binaryme/hermes-agent-casebook/actions/runs/43544045802
- tag: v0.23.1
  digest: sha256:276d44685c65c0cb2a25f190b63c65c8906f9dc76486fb1c05ae71b5826bda08
  date: '2026-11-14'
  observed: 401-202-401-401
  run: https://github.com/binaryme/hermes-agent-casebook/actions/runs/43544045802
last_reviewed: '2026-11-14'
limits: Chatwoot's side is source reading of lib/webhooks/trigger.rb, not a running Chatwoot. The repro signs requests the way that file does.
credits: []
---

## Observation

You point a Chatwoot webhook at a Hermes webhook route that has a secret, and every delivery gets `401`. The signing secret is the same on both sides. The gateway log says `Invalid signature for route <name>` ([v0.23.1 webhook.py L555-L557](https://github.com/NousResearch/hermes-agent/blob/3b421578588243f920886e6fe79a6faa87ea026e/gateway/platforms/webhook.py#L555-L557)), which reads like a wrong secret, so the natural next step is to rotate secrets that were never the problem.

## Hypothesis

Hermes' generic V2 signature check accepts a Chatwoot delivery only when Chatwoot's headers are mapped to the V2 header names and the `sha256=` prefix is dropped, because both sign `"{timestamp}.{body}"` with HMAC-SHA256; with Chatwoot's own header names the gateway answers 401, and it still rejects a changed body and a stale timestamp. The hypothesis is falsified if the unmapped delivery is accepted, or if the mapped one is refused.

## Method

`repro.sh` boots a gateway with one route, `chatwoot`, that has a secret and no `signature:` pin, and posts the same Chatwoot-style payload four ways:

| Mode | Headers | Body |
| --- | --- | --- |
| `raw` | `X-Chatwoot-Signature: sha256=<mac>`, `X-Chatwoot-Timestamp`, `X-Chatwoot-Delivery`, as Chatwoot sends them | as signed |
| `mapped` | the same MAC and timestamp under `X-Webhook-Signature-V2` and `X-Webhook-Timestamp`, prefix removed, delivery id as `X-Request-ID` | as signed |
| `tampered` | valid `mapped` headers | one byte appended |
| `stale` | `mapped` headers with a timestamp 15 minutes old | as signed |

It prints the four HTTP status codes joined by `-`.

## Results

### Runs

| Tag | Observed | Date | Digest | Run |
| --- | --- | --- | --- | --- |
| v2026.8.13 | `401-202-401-401` | 2026-11-14 | `sha256:68e15ae2a6d8` | [run](https://github.com/binaryme/hermes-agent-casebook/actions/runs/43544045802) |
| v0.23.1 | `401-202-401-401` | 2026-11-14 | `sha256:276d44685c65` | [run](https://github.com/binaryme/hermes-agent-casebook/actions/runs/43544045802) |

### Expected and observed

| Mode | Status |
| --- | --- |
| `raw` | `401` |
| `mapped` | `202` |
| `tampered` | `401` |
| `stale` | `401` |

`expect.json` records `401-202-401-401` on v2026.8.13 and v0.23.1. The `mapped` row is the point: Chatwoot's MAC is already a valid Hermes signature, only under other header names.

## Analysis

From v4.11.2 (released 2026-03-09), Chatwoot signs a webhook when it has a secret: `X-Chatwoot-Signature` is `sha256=` followed by the hex HMAC-SHA256 of `"<timestamp>.<body>"`, with the timestamp in `X-Chatwoot-Timestamp` ([trigger.rb L44-L52 at v4.11.2](https://github.com/chatwoot/chatwoot/blob/19683fae74f4d747b332b1fe6e9628da5f7e523d/lib/webhooks/trigger.rb#L44-L52); unchanged at [v4.19.1 L54-L62](https://github.com/chatwoot/chatwoot/blob/caab07a8f00032d5205b5a5d7e2eb0ba2f3d2d82/lib/webhooks/trigger.rb#L54-L62)). [v4.11.1](https://github.com/chatwoot/chatwoot/blob/a08125e283b8e15b84b5073def1e785137b059ba/lib/webhooks/trigger.rb) and v4.10.1 send no signature at all.

Hermes' generic V2 check computes exactly that MAC, as bare hex, but reads it from `X-Webhook-Signature-V2` and the timestamp from `X-Webhook-Timestamp`, within a 300-second window in either direction ([v0.23.1 webhook.py L886-L901](https://github.com/NousResearch/hermes-agent/blob/3b421578588243f920886e6fe79a6faa87ea026e/gateway/platforms/webhook.py#L886-L901) and [L70](https://github.com/NousResearch/hermes-agent/blob/3b421578588243f920886e6fe79a6faa87ea026e/gateway/platforms/webhook.py#L70); the same check at [v2026.8.13 L1108-L1149](https://github.com/NousResearch/hermes-agent/blob/f80f453ae0679347e38abc917c7f94f717bf96c5/gateway/platforms/webhook.py#L1108-L1149)). Hermes has no Chatwoot header family, so a raw Chatwoot request carries no signature it recognizes. Its delivery id falls back to `X-Request-ID` when no provider-specific id is present ([L77-L80](https://github.com/NousResearch/hermes-agent/blob/3b421578588243f920886e6fe79a6faa87ea026e/gateway/platforms/webhook.py#L77-L80)).

## Recommendation

Put a small relay between Chatwoot and Hermes that renames the headers and forwards the body byte for byte:

| Chatwoot sends | Hermes reads |
| --- | --- |
| `X-Chatwoot-Signature: sha256=<hex>` | `X-Webhook-Signature-V2: <hex>` |
| `X-Chatwoot-Timestamp` | `X-Webhook-Timestamp` |
| `X-Chatwoot-Delivery` | `X-Request-ID` |

The relay needs no copy of the secret: Hermes still verifies the MAC. It should refuse requests without a Chatwoot signature, so it never forwards unsigned traffic. The [Chatwoot guide](../../guides/chatwoot/README.md) has such a relay and the rest of the setup. Use Chatwoot v4.11.2 or later. Earlier versions do not sign at all, and a Hermes route refuses requests when it has no secret ([L550-L554](https://github.com/NousResearch/hermes-agent/blob/3b421578588243f920886e6fe79a6faa87ea026e/gateway/platforms/webhook.py#L550-L554)), so on those versions the relay itself would have to hold the secret and sign V2 requests, which the relay here deliberately does not. A deployment's version label can lag its code: check whether your installed `lib/webhooks/trigger.rb` contains `X-Chatwoot-Signature` before you decide.

## Related work

Unreported as such. A search on 2026-11-13 for chatwoot, `X-Chatwoot-Signature` and "chatwoot webhook" found related work but no report of this mismatch:

- [#84580](https://github.com/NousResearch/hermes-agent/issues/84580), open: a feature request for a documented pre-LLM ingress hook, with Chatwoot account webhooks as its concrete case. It lists Chatwoot's signature headers among the metadata such a hook should carry.
- [#85318](https://github.com/NousResearch/hermes-agent/pull/85318) and [#90995](https://github.com/NousResearch/hermes-agent/pull/90995): webhook refactors that described a declared `chatwoot` provider namespace. Both were closed without being merged.

## Threats to validity

Reproduced in CI on v2026.8.13 and v0.23.1 on 2026-11-14 ([run 43544045802](https://github.com/binaryme/hermes-agent-casebook/actions/runs/43544045802)), each against the digest pinned in `harness/images.json`. The causes are source-verified at the linked lines. Chatwoot itself is not run: the repro signs requests the way Chatwoot's `trigger.rb` does at the cited versions.
