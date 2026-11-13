---
id: E1
slug: bad-repro-shebang
title: Enable the example toolset before relying on it
kind: gotcha
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
repro: entries/bad-repro-shebang/repro.sh
needs_credentials: false
confidence: source-verified
verified_on: []
last_reviewed: 2026-11-13
limits: Source reading only. Not run on any image yet.
credits: []
---

## Symptom

The example feature does nothing until its toolset is enabled.

## Verified on

Nothing yet.

## Reproduce

Run `entries/bad-repro-shebang/repro.sh` through the harness.

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
