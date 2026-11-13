# Contributing

This repository holds reproducible operator notes for Hermes Agent. One entry covers one behavior that surprised an operator. Everything is written in English.

## What fits

- A behavior of the official Docker image `nousresearch/hermes-agent` that you observed or can read in the source, on named tags.
- A repro that runs without model credentials and prints one result.
- A claim limited to the tags you tested. Say which tags are affected and which are not.

Behaviors that upstream already documents clearly are not entries. They may become a one-line pointer.

## Propose an entry

Open an issue with the [New entry form](https://github.com/binaryme/hermes-agent-casebook/issues/new/choose). The form asks for:

- The Hermes version or image tag.
- The install method and the operating system.
- A minimal repro: commands or a script of at most 30 non-blank lines.
- What you expected and what happened.
- The upstream issues you searched, with links, or the search terms you used if you found none.

Entries are written in a fixed format and verified by running the repro against pinned image digests. A maintainer turns an accepted proposal into an entry and credits you in it, unless you ask not to be credited.

## Evidence

- Link source lines at a full 40-character commit, never at `main`.
- Anything you read in the source but did not run is described as source reading, not as an observation.
- Do not write that something always or never happens unless a repro shows it on the tags you list.

## No private identifiers

Do not include company, product, customer, host, IP, channel or personal identifiers, or real tokens, secrets and conversation ids. Use `example.com` and obvious placeholder secrets. Redact logs before pasting them. If a repro needs a real identifier to work, it does not belong here.

## Report a wrong entry

Use the Entry is wrong form with the entry id, the tag and the output you observed. A correction is made in place and recorded in the changelog, and you are credited unless you ask otherwise.

## Pull requests

Pull requests are welcome for corrections and for entries that were discussed in an issue first. A pull request that adds or changes an entry links the CI run of the repro for that entry, states which AI tools were used, if any, and says what a human verified. The pull request template asks for all three.

## Vulnerabilities

Do not open an issue about a security vulnerability in Hermes Agent. See [SECURITY.md](SECURITY.md).

## Conduct

Participation is covered by the [Code of Conduct](CODE_OF_CONDUCT.md).

## License

Prose you contribute is licensed under CC-BY-4.0. Code you contribute is licensed under MIT.
