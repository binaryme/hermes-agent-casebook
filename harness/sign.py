#!/usr/bin/env python3
import argparse
import hashlib
import hmac
import sys
import time
import uuid
from pathlib import Path

CHATWOOT_PREFIX = "sha256="
GITHUB_PREFIX = "sha256="


def hex_hmac(secret, data):
    return hmac.new(secret.encode("utf-8"), data, hashlib.sha256).hexdigest()


def current_timestamp(timestamp):
    return str(int(time.time()) if timestamp is None else int(timestamp))


def v2_headers(secret, body, timestamp=None):
    stamp = current_timestamp(timestamp)
    return {
        "X-Webhook-Timestamp": stamp,
        "X-Webhook-Signature-V2": hex_hmac(secret, stamp.encode("ascii") + b"." + body),
    }


def github_headers(secret, body, delivery_id, event="push"):
    return {
        "X-Hub-Signature-256": GITHUB_PREFIX + hex_hmac(secret, body),
        "X-GitHub-Event": event,
        "X-GitHub-Delivery": delivery_id,
    }


def chatwoot_headers(secret, body, timestamp=None, delivery_id=None):
    stamp = current_timestamp(timestamp)
    return {
        "X-Chatwoot-Timestamp": stamp,
        "X-Chatwoot-Signature": CHATWOOT_PREFIX + hex_hmac(secret, stamp.encode("ascii") + b"." + body),
        "X-Chatwoot-Delivery": delivery_id or str(uuid.uuid4()),
    }


def chatwoot_to_v2(headers):
    lowered = {name.lower(): value for name, value in headers.items()}
    signature = lowered.get("x-chatwoot-signature", "")
    timestamp = lowered.get("x-chatwoot-timestamp", "")
    if not signature or not timestamp:
        raise ValueError("Chatwoot signature and timestamp headers are required")
    mapped = {
        "X-Webhook-Timestamp": timestamp,
        "X-Webhook-Signature-V2": signature[len(CHATWOOT_PREFIX):] if signature.startswith(CHATWOOT_PREFIX) else signature,
    }
    delivery = lowered.get("x-chatwoot-delivery")
    if delivery:
        mapped["X-Request-ID"] = delivery
    return mapped


def build_parser():
    parser = argparse.ArgumentParser(description="Print webhook signature headers as 'Name: value' lines.")
    parser.add_argument("scheme", choices=("v2", "github", "chatwoot", "chatwoot-mapped"))
    parser.add_argument("secret")
    parser.add_argument("body_file")
    parser.add_argument("--timestamp", type=int)
    parser.add_argument("--delivery-id")
    parser.add_argument("--event", default="push")
    return parser


def headers_for(args, body):
    if args.scheme == "v2":
        return v2_headers(args.secret, body, args.timestamp)
    if args.scheme == "github":
        if not args.delivery_id:
            raise ValueError("--delivery-id is required for the github scheme")
        return github_headers(args.secret, body, args.delivery_id, args.event)
    headers = chatwoot_headers(args.secret, body, args.timestamp, args.delivery_id)
    return chatwoot_to_v2(headers) if args.scheme == "chatwoot-mapped" else headers


def main(argv=None):
    args = build_parser().parse_args(argv)
    try:
        body = Path(args.body_file).read_bytes()
        headers = headers_for(args, body)
    except (OSError, ValueError) as error:
        print(f"error: {error}", file=sys.stderr)
        return 2
    for name, value in headers.items():
        print(f"{name}: {value}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
