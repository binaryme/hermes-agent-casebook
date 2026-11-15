# Changelog

All notable changes to this repository are recorded here. The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and releases use [Semantic Versioning](https://semver.org/spec/v2.0.0.html): a new entry is a minor release and a correction is a patch.

Entries that are removed because they no longer apply to any supported tag are listed under Pruned, with the reason.

## [Unreleased]

## [1.0.1] - 2026-11-15

### Corrected

Found by a second review of 1.0.0, against the entries and the run transcripts.

- Every entry now runs on all seven pinned tags, not only on the tags where its behavior was expected to change: 49 entry and tag pairs, all matching, in a new run whose evidence replaces the 1.0.0 run's. E1, E2 and E3 are now shown present on all seven tags, and the "before" ranges of E6, E7 and E9 cover every pinned tag in between.
- E7: on v0.21.6 and v0.22.5 the login shell finds `/usr/local/bin/python3`, not `/usr/bin/python3`. The repro now checks whether that interpreter can import `openai`, a dependency only the image's virtualenv has, so "without Hermes' dependencies" is observed, not inferred. The `uv pip install --target` workaround names the right interpreter per tag.
- E6: the backup file names and the schema versions on every tag come from transcripts; they came from local runs before.
- E4 field observation: counted against the real 60-character limit, not 57, and checked against the index lines Hermes reports.
- Hypotheses: E1's falsification names the prompt-size case it tests, E3's covers the tampered and stale requests, and E7's no longer claims what the repro does not test.
- THESIS.md: the abstract no longer counts E4 as fixed; "fixed in" is the first fixed tag among the pinned ones; the declaration and section 3.8 say E3 was not compared with the author's install; RQ3 says which workarounds were exercised; the log claims are marked as source reading; the description advice matches E4.
- Field observations: context from the operator is marked as the operator's account, and a session count that showed traffic volume is removed.
- Result tables in E1 and E2 say "Observed", not "What the source does".

## [1.0.0] - 2026-11-15

### Added

- THESIS.md: the work as one document, with abstract, declaration, introduction and research questions, background, method, results, discussion, threats to validity, conclusion, references and appendices. README.md is now its title page.
- Seven entries, each a section of the results chapter: E1 webhook runs have no skills index, E2 a route's `skills:` loads only the first skill, E3 Chatwoot signatures need header mapping, E4 skill descriptions are cut at 60 characters, E6 config writers drop comments before v2026.9.24, E7 login shells lose the image's Python before v0.22.6, E9 two routes on one GitHub delivery deduplicate before v0.21.6.
- A Hypothesis section in every entry, with the result that would falsify it, and a Field observation subsection in six of them, from the author's own install.
- Repro transcripts: `run_repro.py` writes each repro's output next to its result, and every repro prints the raw values behind its token.
- `evidence/`: the results and transcripts of the cited CI run, with checksums, and the field observations.
- POINTERS.md: four documented behaviors that still surprise operators.
- The Chatwoot guide and a header-mapping relay that holds no secret, tested end to end in CI.
- A CI check of every commit message, and a weekly run of every entry against the newest stable Hermes release.

### Changed

- Entry headings follow a thesis results section: Observation, Hypothesis, Method, Results, Analysis, Recommendation, Related work, Threats to validity. The validator and `stamp.py` enforce and write the new layout.

### Corrected before release

- E6: the boot-time schema migration also drops comments on v2026.8.13 and v2026.9.21, not only `config set`.
- E9: upstream issue #7448 and pull requests #130692 and #129626 were missed; they are linked and credited.
- E1, E2, E4: the repros now test the configuration the entries recommend, read every request the model received, and accept only exact cut lengths.
- E3: the gateway does log a warning on a refused signature; the entry quotes it.

## [0.2.0] - 2026-11-13

### Added

- The repro harness: digest pins for seven Hermes tags, a stub model, a webhook gateway helper, request signing, the run classifier, `stamp.py` and the generated INDEX.md.

## [0.1.0] - 2026-11-13

### Added

- Licenses: CC-BY-4.0 for prose, MIT for code.
- Markdown, spelling and link checks in CI.
- Dependabot updates for pinned actions.
- Contributing guide, code of conduct and security policy.
- Issue forms for new entries and wrong entries, and a pull request template.
- Citation metadata and this changelog.

[Unreleased]: https://github.com/binaryme/hermes-agent-casebook/compare/v1.0.1...HEAD
[1.0.1]: https://github.com/binaryme/hermes-agent-casebook/compare/v1.0.0...v1.0.1
[1.0.0]: https://github.com/binaryme/hermes-agent-casebook/compare/v0.2.0...v1.0.0
[0.2.0]: https://github.com/binaryme/hermes-agent-casebook/compare/v0.1.0...v0.2.0
[0.1.0]: https://github.com/binaryme/hermes-agent-casebook/releases/tag/v0.1.0
