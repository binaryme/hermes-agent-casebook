# hermes-agent-casebook

Reproducible operator notes for [Hermes Agent](https://github.com/NousResearch/hermes-agent), written as a thesis. Each entry states one behavior that surprises operators as a falsifiable hypothesis, names the image tags where it holds and where it does not, and ships a script that CI runs against those images, pinned by digest. The results and transcripts of the runs are committed with the text.

Independent work. Not affiliated with, endorsed by, or reviewed by Nous Research. "Hermes Agent" refers to github.com/NousResearch/hermes-agent (MIT).

**Read the thesis: [THESIS.md](THESIS.md)**, *Where Hermes Agent surprises its operators*, by Israel Ortiz, version 1.0.0. It has the abstract, the declaration of how it was made, the method, the discussion and the threats to validity. The entries below are the sections of its results chapter.

## The entries

| Id | Read this if you | Present on |
| --- | --- | --- |
| [E1](entries/webhook-no-skills-index/README.md) | added a skill and webhook runs never use it | every tested tag |
| [E2](entries/webhook-first-skill-only/README.md) | list more than one skill on a webhook route | every tested tag |
| [E3](entries/chatwoot-signature-v2/README.md) | point Chatwoot at Hermes and get 401 on every delivery | every tested tag |
| [E4](entries/skill-description-cut/README.md) | write long skill descriptions | every tested tag; word-boundary cut from v0.22.6 |
| [E6](entries/config-write-drops-comments/README.md) | keep comments in `config.yaml` | before v2026.9.24 |
| [E7](entries/login-shell-path/README.md) | see `ModuleNotFoundError` from the terminal tool | before v0.22.6 |
| [E9](entries/webhook-cross-route-dedup/README.md) | point two webhook routes at one GitHub event | before v0.21.6 |

Upstream changed its tag scheme in October 2026: v0.21.6 and later are newer than every v2026 tag. [INDEX.md](INDEX.md) has each entry's status and last verification, generated from the entries.

## Also here

| | |
| --- | --- |
| [evidence/](evidence/README.md) | Appendix E: results and transcripts of every cited CI run, with checksums, and the field observations. |
| [guides/chatwoot/](guides/chatwoot/README.md) | Appendix A: sending Chatwoot webhooks to a Hermes route, with a relay that holds no secret. |
| [POINTERS.md](POINTERS.md) | Appendix B: documented behaviors that still surprise operators. |
| [docs/entry-format.md](docs/entry-format.md) | Appendix C: the entry format and the rules CI enforces. |

## Reproduce a result

With Docker and Python 3 with PyYAML:

```sh
python3 harness/run_repro.py --entry webhook-no-skills-index --all-tags
```

The script pulls each pinned image by digest, runs the repro with no model credentials, and writes a result and a transcript under `results/`. Every week, `watch-upstream.yml` runs every entry against the newest stable Hermes release and opens an issue when a result changes.

## Corrections

A report that an entry is wrong is acknowledged within 72 hours and fixed, or marked disputed, within 7 days. The fix is made in place, recorded under Corrected in the [changelog](CHANGELOG.md), and credited to the reporter in the entry, the changelog and the commit, unless they ask otherwise. Open an [Entry is wrong](https://github.com/binaryme/hermes-agent-casebook/issues/new/choose) issue.

## Contributing

Propose an entry through the [issue forms](https://github.com/binaryme/hermes-agent-casebook/issues/new/choose) and read [CONTRIBUTING.md](CONTRIBUTING.md) first. Report vulnerabilities in Hermes Agent to the upstream project, privately; see [SECURITY.md](SECURITY.md).

## License

Prose is licensed under CC-BY-4.0 ([LICENSE](LICENSE)). Code is licensed under MIT ([LICENSE-CODE](LICENSE-CODE)): `harness/`, `tests/`, `guides/chatwoot/relay/`, `guides/chatwoot/e2e.sh` and every `entries/*/repro.sh`. To cite this work, see [CITATION.cff](CITATION.cff).
