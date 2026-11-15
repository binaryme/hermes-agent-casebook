# Appendix E: evidence

Everything a statement of observation in this repository rests on, kept here because CI artifacts and logs expire after 90 days.

## E.1 CI runs

Each directory holds one CI run's results and transcripts, copied unchanged by `harness/stamp.py --run <id>`, with a `README.md` naming the run, its commit and its trigger, and a `SHA256SUMS` file. Check a copy with `sha256sum -c SHA256SUMS` from inside its directory.

| Run | Date | Entries and tags | Cited by |
| --- | --- | --- | --- |
| [43665652222](43665652222/README.md) | 2026-11-15 | 23 pairs, all `match` | every entry, [THESIS.md](../THESIS.md) |

Runs before 43665652222 are linked from the git history but their artifacts were not committed; nothing in the current text rests on them.

## E.2 Field observations

[field/2026-11-14.md](field/2026-11-14.md): read-only observations of the author's own install. Not reproducible by a reader, and no entry's confidence rests on them.
