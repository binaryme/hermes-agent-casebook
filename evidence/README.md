# Appendix E: evidence

Everything a statement of observation in an entry's Results rests on, kept here because CI artifacts and logs expire after 90 days. The field observations of E.2 are the exception: they come from the author's install, not from CI, and are labelled wherever they are used.

## E.1 CI runs

Each directory holds one CI run's results and transcripts, copied unchanged by `harness/stamp.py --run <id>`, with a `README.md` naming the run, its commit and its trigger, and a `SHA256SUMS` file. Check a copy with `sha256sum -c SHA256SUMS` from inside its directory.

| Run | Date | Entries and tags | Cited by |
| --- | --- | --- | --- |
| [43668393761](43668393761/README.md) | 2026-11-15 | 49 pairs, every entry on all seven pinned tags, all `match` | every entry and [THESIS.md](../THESIS.md) from 1.0.1 |
| [43665652222](43665652222/README.md) | 2026-11-15 | 23 pairs, all `match` | version 1.0.0 |

Runs before 43665652222 are linked from the git history but their artifacts were not committed; nothing in the current text rests on them.

## E.2 Field observations

[field/2026-11-14.md](field/2026-11-14.md): read-only observations of the author's own install. Not reproducible by a reader, and no entry's confidence rests on them.
