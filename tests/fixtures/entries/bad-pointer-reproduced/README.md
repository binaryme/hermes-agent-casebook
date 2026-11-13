---
id: E1
slug: bad-pointer-reproduced
title: Enable the example toolset before relying on it
kind: pointer
status: fixed
affected:
  - v9.0.0
not_affected:
  - v9.1.0
fixed_in: v9.1.0
upstream:
  - https://example.com/org/repo/issues/1
evidence:
  - https://example.com/org/repo/blob/0123456789abcdef0123456789abcdef01234567/src/main.py#L10-L20
repro: null
needs_credentials: false
confidence: reproduced
verified_on:
  - tag: v9.0.0
    digest: sha256:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa
    date: 2026-11-13
    observed: empty
    run: https://example.com/runs/1
last_reviewed: 2026-11-13
limits: Source reading only. Not run on any image yet.
credits: []
---

## Symptom

The example feature does nothing until its toolset is enabled.

## Verified on

Nothing yet.

## Reproduce

Run `entries/bad-pointer-reproduced/repro.sh` through the harness.

## Expected vs actual

Expected `present`, actual `empty`.

## Cause

The toolset gate in the example source.

## Workaround

Enable the toolset.

## Upstream status

One open issue.

## Confidence and limits

Source reading only.
