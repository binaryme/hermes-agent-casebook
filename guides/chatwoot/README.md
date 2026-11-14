# Chatwoot to Hermes

How to send Chatwoot webhooks to a Hermes Agent webhook route so that every delivery is signed, verified and acted on. Hermes has no Chatwoot integration of its own; this guide closes the gap with a one-file relay that holds no secret.

Each claim is labeled:

- **Observed**: printed by a script in this repository against a pinned Hermes image. The scripts are [E3's repro](../../entries/chatwoot-signature-v2/repro.sh) and [e2e.sh](e2e.sh), and CI runs both.
- **Source-verified**: read in the source at the linked commit, not run.

Chatwoot itself is never run here. Everything about Chatwoot is source-verified.

## Versions

| Component | Version | Why |
| --- | --- | --- |
| Chatwoot | v4.11.2 or later | First release that signs webhooks ([trigger.rb at v4.11.2](https://github.com/chatwoot/chatwoot/blob/19683fae74f4d747b332b1fe6e9628da5f7e523d/lib/webhooks/trigger.rb#L44-L52)); v4.11.1 sends no signature ([trigger.rb at v4.11.1](https://github.com/chatwoot/chatwoot/blob/a08125e283b8e15b84b5073def1e785137b059ba/lib/webhooks/trigger.rb)). Source-verified. |
| Chatwoot, agent bots | v4.13.0 or later | Agent bots get a webhook secret from v4.13.0 ([agent_bot.rb at v4.13.0](https://github.com/chatwoot/chatwoot/blob/88ffa329eb6e18ae06b608d8b4bab96c0e1b8f44/app/models/agent_bot.rb)); at v4.12.0 the model has none ([agent_bot.rb at v4.12.0](https://github.com/chatwoot/chatwoot/blob/b6b856260f5c8869f179630f721180df5796c5a0/app/models/agent_bot.rb)). Source-verified. |
| Hermes | v2026.8.13 and v0.23.1 checked | The generic V2 signature check is the same on both. Observed. |

## How the pieces fit

```text
Chatwoot ── X-Chatwoot-Signature ──> relay.py ── X-Webhook-Signature-V2 ──> Hermes /webhooks/<route>
           X-Chatwoot-Timestamp                 X-Webhook-Timestamp
           X-Chatwoot-Delivery                  X-Request-ID
```

Chatwoot signs `"<timestamp>.<body>"` with HMAC-SHA256 and sends `sha256=<hex>`. Hermes' generic V2 check computes the same MAC but reads it, as bare hex, from different headers. Sent directly, Chatwoot's request gets `401`. With the headers renamed and the body unchanged, it gets `202`. Observed: [E3](../../entries/chatwoot-signature-v2/README.md) prints `401-202-401-401` for raw, mapped, tampered and stale requests on v2026.8.13 and v0.23.1.

## Set up the route

In `config.yaml` on the Hermes side:

```yaml
platforms:
  webhook:
    enabled: true
    extra:
      routes:
        chatwoot:
          secret: "<the Chatwoot webhook secret>"
          filters:
            - field: "event"
              equals: "message_created"
            - field: "message_type"
              equals: "incoming"
          prompt: |
            Draft a reply to this Chatwoot message. Do not send it.
            Conversation {conversation.id}: {content}
```

- Use the secret Chatwoot generated for this webhook or agent bot. It is a `has_secure_token` value created with the record ([webhook_secretable.rb at v4.19.1](https://github.com/chatwoot/chatwoot/blob/caab07a8f00032d5205b5a5d7e2eb0ba2f3d2d82/app/models/concerns/webhook_secretable.rb#L4-L7)). Source-verified.
- Chatwoot sends `message_created` for incoming, outgoing and template messages alike ([message_filter_helpers.rb L8-L10 at v4.19.1](https://github.com/chatwoot/chatwoot/blob/caab07a8f00032d5205b5a5d7e2eb0ba2f3d2d82/app/models/concerns/message_filter_helpers.rb#L8-L10)). Without the `filters` above, the agent drafts replies to your own agents' messages, and to its own once they are posted. Source-verified; `filters` is documented for routes at [webhooks.md L132-L163](https://github.com/NousResearch/hermes-agent/blob/3b421578588243f920886e6fe79a6faa87ea026e/website/docs/user-guide/messaging/webhooks.md?plain=1#L132-L163).
- A route that has a secret rejects any request whose signature it cannot verify. With the relay in front, that means only requests Chatwoot signed with this secret get through. Observed in E3 and e2e.sh.
- Payload fields are text from your customers. Hermes' docs call them untrusted even on an authenticated route ([webhooks.md L642](https://github.com/NousResearch/hermes-agent/blob/3b421578588243f920886e6fe79a6faa87ea026e/website/docs/user-guide/messaging/webhooks.md?plain=1#L642)). Keep the route's toolset small, and read [E1](../../entries/webhook-no-skills-index/README.md) before you add the `skills` toolset to it.

## Run the relay

```bash
python3 relay/relay.py --upstream http://hermes:8644/webhooks/chatwoot --host 0.0.0.0 --port 8645
```

Point the Chatwoot webhook, or the agent bot's outgoing URL, at the relay. What [relay.py](relay/relay.py) does:

- It renames the three headers, strips the `sha256=` prefix, and forwards the body byte for byte.
- It always forwards to the one `--upstream` URL given at startup; the request path cannot choose another route.
- It refuses, without forwarding, a request with no Chatwoot signature or timestamp, a body without `Content-Length`, a chunked body, and a body over 1 MiB (`--max-body-bytes`).
- It holds no secret. Hermes still checks the MAC and rejects timestamps more than 300 seconds off. That window limits a replay to five minutes; it does not prevent one, because the delivery id Hermes deduplicates on is not covered by the MAC. Keep the relay on a network an attacker cannot capture traffic from.
- It stops reading a request that stalls for 10 seconds.

Observed: [e2e.sh](e2e.sh) boots a pinned gateway, puts the relay in front of it, and gets `202` for a signed request, `401` for a body changed after signing, and `401` at the relay for an unsigned request, on v2026.8.13 and v0.23.1.

Run the relay on the same private network as Hermes. Expose only the relay, never the Hermes webhook port.

From v4.14.0, Chatwoot sends webhooks through its SSRF filter ([trigger.rb L43 at v4.19.1](https://github.com/chatwoot/chatwoot/blob/caab07a8f00032d5205b5a5d7e2eb0ba2f3d2d82/lib/webhooks/trigger.rb#L43); not present at [v4.13.0](https://github.com/chatwoot/chatwoot/blob/88ffa329eb6e18ae06b608d8b4bab96c0e1b8f44/lib/webhooks/trigger.rb)). It refuses private and loopback addresses unless `SAFE_FETCH_ALLOW_PRIVATE_NETWORK` is true ([safe_fetch.rb L36-L38](https://github.com/chatwoot/chatwoot/blob/caab07a8f00032d5205b5a5d7e2eb0ba2f3d2d82/lib/safe_fetch.rb#L36-L38) and [fetcher.rb L46-L50](https://github.com/chatwoot/chatwoot/blob/caab07a8f00032d5205b5a5d7e2eb0ba2f3d2d82/lib/safe_fetch/fetcher.rb#L46-L50)). Source-verified. A self-hosted Chatwoot pointed at a relay on a private address therefore fails every delivery until you either give the relay a public address, or set that variable. The variable turns the SSRF protection off for all of Chatwoot's outbound fetches, not just webhooks, so weigh it before you do.

## Retries and acknowledgements

What Chatwoot does when Hermes does not answer `2xx`, source-verified at v4.19.1:

| Chatwoot sends from | Retried on | Attempts | Source |
| --- | --- | --- | --- |
| An account webhook | never | 1 | [webhook_job.rb](https://github.com/chatwoot/chatwoot/blob/caab07a8f00032d5205b5a5d7e2eb0ba2f3d2d82/app/jobs/webhook_job.rb#L1-L7) |
| An agent bot | `429` and `500` only | 3, 3 seconds apart | [agent_bots/webhook_job.rb L3](https://github.com/chatwoot/chatwoot/blob/caab07a8f00032d5205b5a5d7e2eb0ba2f3d2d82/app/jobs/agent_bots/webhook_job.rb#L3) and [trigger.rb L3](https://github.com/chatwoot/chatwoot/blob/caab07a8f00032d5205b5a5d7e2eb0ba2f3d2d82/lib/webhooks/trigger.rb#L3) |

- Chatwoot waits 5 seconds for an answer unless `WEBHOOK_TIMEOUT` is set ([trigger.rb L118-L123](https://github.com/chatwoot/chatwoot/blob/caab07a8f00032d5205b5a5d7e2eb0ba2f3d2d82/lib/webhooks/trigger.rb#L118-L123)). Hermes answers `202` as soon as it has admitted the delivery and runs the agent afterwards ([webhook.py L747-L760 at v0.23.1](https://github.com/NousResearch/hermes-agent/blob/3b421578588243f920886e6fe79a6faa87ea026e/gateway/platforms/webhook.py#L747-L760)), so a slow model does not time the webhook out. Source-verified; the `202` itself is observed.
- When Hermes cannot admit a delivery, v0.23.1 answers `503` "Admission unavailable; retry this delivery" (same lines). Chatwoot does not retry a `503`, so that message is lost. Source-verified.
- When an agent bot delivery fails for good, Chatwoot moves a `pending` conversation to `open` and posts an activity message, unless the account keeps conversations pending on bot failure ([trigger.rb L65-L89](https://github.com/chatwoot/chatwoot/blob/caab07a8f00032d5205b5a5d7e2eb0ba2f3d2d82/lib/webhooks/trigger.rb#L65-L89)). Source-verified.
- A retry carries the same `X-Chatwoot-Delivery` id. The relay passes it as `X-Request-ID`, which Hermes uses as the delivery id for deduplication ([webhook.py L77-L80](https://github.com/NousResearch/hermes-agent/blob/3b421578588243f920886e6fe79a6faa87ea026e/gateway/platforms/webhook.py#L77-L80)). So a retried delivery that Hermes already admitted gets `200 duplicate`, not a second run, as long as the retry carries the same delivery id. Source-verified.

## Sending the reply back

Hermes has no Chatwoot delivery target: the route's `deliver` options do not include Chatwoot ([webhooks.md L89](https://github.com/NousResearch/hermes-agent/blob/3b421578588243f920886e6fe79a6faa87ea026e/website/docs/user-guide/messaging/webhooks.md?plain=1#L89)). Source-verified. A reply has to go back through Chatwoot's API, from a tool the agent can call or from a separate service. That part is outside this guide.

Whatever you build, keep a human between the draft and the customer. Have the agent draft, and let code send what a person approved. A draft built from a customer's message can be wrong in ways nobody catches until it is posted to the wrong conversation.

## Checklist

- [ ] Chatwoot is v4.11.2 or later, and v4.13.0 or later for agent bots.
- [ ] On Chatwoot v4.14.0 or later, the relay's address is reachable through Chatwoot's SSRF filter.
- [ ] The route only wakes the agent for incoming messages.
- [ ] The Hermes route has the Chatwoot secret.
- [ ] Only the relay is reachable from Chatwoot. The Hermes webhook port is not.
- [ ] The route's toolset is the smallest that works.
- [ ] Replies go out only after a human approves them.
