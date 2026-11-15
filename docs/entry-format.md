# Entry format

Every entry lives in `entries/<slug>/` and has four parts:

| Path | What it is |
| --- | --- |
| `README.md` | The entry: YAML front matter, then a fixed set of sections. |
| `repro.sh` | A bash script that reproduces the behavior and prints one result. |
| `expect.json` | The result the repro must print on each pinned image tag. |
| `fixtures/` | Config files, skills and payloads the repro mounts or sends. |

`harness/validate_entries.py` checks every rule on this page that is marked as enforced. CI runs it on every push.

## Front matter

| Field | Type | Meaning |
| --- | --- | --- |
| `id` | string | `E` followed by a number, unique across entries. |
| `slug` | string | Lowercase kebab case, equal to the directory name. |
| `title` | string | Directive form: an imperative, or "Don't ...". |
| `kind` | enum | `gotcha`, `check-your-version` or `pointer`. |
| `status` | enum | `open`, `fixed`, `documented`, `wont-fix` or `unreported`. |
| `affected` | list of tags | Tags where the behavior was observed or read in the source. |
| `not_affected` | list of tags | Tags where it does not occur. |
| `fixed_in` | tag or null | The first tag without the behavior. |
| `upstream` | list of URLs, or `none-found` | Upstream issues and pull requests. `none-found` requires `searched_on: YYYY-MM-DD`. |
| `evidence` | list of URLs | Source lines, each pinned to a 40-character commit. |
| `repro` | path | `entries/<slug>/repro.sh`. |
| `needs_credentials` | boolean | Always `false`: repros never need model credentials. |
| `confidence` | enum | `reproduced` or `source-verified`. |
| `verified_on` | list | One item per CI run: `tag`, `digest`, `date`, `observed`, `run`. |
| `last_reviewed` | date | `YYYY-MM-DD`. |
| `limits` | string | One or two sentences on what the entry does not show. |
| `credits` | list | People or projects that found or documented the behavior first. |

## Sections

The body has exactly these second-level headings, in this order:

1. Symptom
2. Verified on
3. Reproduce
4. Expected vs actual
5. Cause
6. Workaround
7. Upstream status
8. Confidence and limits

## Repro contract

- The script starts with `#!/usr/bin/env bash`, sets `set -euo pipefail`, and is executable.
- It has at most 30 non-blank lines.
- It names no image tag. The harness exports the pinned image as `HERMES_IMAGE`, along with `HARNESS`, `ENTRY_DIR`, `FIXTURES`, `WORK` and `HERMES_TAG`.
- It sources `"$HARNESS/lib.sh"`, and `"$HARNESS/gateway.sh"` when it needs a running gateway.
- It ends by printing exactly one line, `OBSERVED=<token>`, through `observed <token>`, and exits 0. A token is a short lowercase kebab string such as `empty`, `present` or `alpha-only`.
- It prints, through `evidence <text>`, the raw values its token is made from: status codes, counts, the matching lines of a request. These go to stderr as `EVIDENCE <text>` lines.
- It runs on bash 3.2 and on bash 5.

`harness/run_repro.py` compares the token with `expect.json[tag]` and classes the run:

| Class | When |
| --- | --- |
| `match` | The token equals the expectation. |
| `behavior-changed` | The token differs from the expectation. |
| `repro-error` | The script exited nonzero, printed no token or more than one, or timed out. |

A `repro-error` is never read as a behavior.

## Evidence

Next to each result, `run_repro.py` writes `<entry>/<tag>.log`: the result fields, then the repro's stdout and stderr, each capped at 64 KiB, with the temporary work directory shown as `$WORK` and the home directory as `~`. CI uploads both files as the run's artifacts.

GitHub keeps artifacts for 90 days, so a run link alone does not last. `harness/stamp.py --run <id>` copies every result and transcript of that run into `evidence/<id>/`, with a `README.md` naming the run, its commit and its trigger, and a `SHA256SUMS` file. Each entry's results table links to its transcripts there. Only CI runs are copied; a local run is never evidence.

## Enforced rules

- Required fields are present, no unknown field appears, and enum values are valid.
- `slug` equals the directory name, `needs_credentials` is `false`, `limits` has at most two sentences, and no tag is both in `affected` and in `not_affected`.
- Section headings match the list above, in order.
- `repro.sh` exists, is executable, has the shebang, has at most 30 non-blank lines, and contains no literal image tag.
- `expect.json` keys are tags pinned in `harness/images.json`.
- Every `evidence` URL is pinned to a 40-character commit. Links to `main`, `master` or `HEAD` are rejected.
- `confidence: reproduced` requires a non-empty `verified_on`.
- Every `fixed_in` tag also appears in `not_affected`.
- A `pointer` cannot claim `reproduced` without a repro.
- No `.sh`, `.py`, `.yml`, `.yaml` or `.toml` file in the repository has a comment line, except a shebang.

`last_reviewed` older than 60 days is a warning, not a failure.

## Confidence

An entry starts as `source-verified` with `verified_on: []`. It becomes `reproduced` only when a CI run of its repro matched on the listed tags and the run is stamped into `verified_on`. Text in the entry follows the same rule: what was read in the source is described as source reading, and only what a run printed is described as observed.
