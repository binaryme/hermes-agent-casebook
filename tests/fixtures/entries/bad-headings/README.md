---
id: E1
slug: bad-headings
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
repro: entries/bad-headings/repro.sh
needs_credentials: false
confidence: source-verified
verified_on: []
last_reviewed: 2026-11-13
limits: Source reading only. Not run on any image yet.
credits: []
---

## Observation

Hypothesis below.

## Hypothesis

The example feature does nothing until its toolset is enabled.

## Results

### Runs

Nothing yet.

## Method

Run `entries/bad-headings/repro.sh` through the harness.

### Expected and observed

Expected `present`, actual `empty`.

## Recommendation

Enable the toolset.

## Analysis

The toolset gate in the example source.

## Related work

One open issue.

## Threats to validity

Source reading only.
