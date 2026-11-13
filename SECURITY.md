# Security policy

This repository holds notes and test scripts about Hermes Agent. It does not ship Hermes Agent.

## Vulnerabilities in Hermes Agent

Report them to the upstream project, privately, through one of the channels in its own policy:

- [GitHub Security Advisories for NousResearch/hermes-agent](https://github.com/NousResearch/hermes-agent/security/advisories/new)
- The contact published in upstream's [SECURITY.md](https://github.com/NousResearch/hermes-agent/blob/main/SECURITY.md)

Do not open an issue in this repository, or a public issue upstream, for a security vulnerability. Read the scope sections of upstream's policy before you report: upstream defines which classes of reports it treats as vulnerabilities.

Upstream's policy states a coordinated disclosure window of 90 days from report, or until a fix is released, whichever comes first. Do not publish a vulnerability here before that window ends.

If a repro in this repository appears to show a security boundary of Hermes Agent being crossed, for example a credential reaching a process it should not reach, stop and do not publish it. Report it upstream first.

## What issues here are for

Issues in this repository are for entry errors and new entry proposals only. See [CONTRIBUTING.md](CONTRIBUTING.md).

## Security issues in this repository

Report a problem in this repository itself, such as a weakness in a workflow or a secret or private identifier that was committed, through [private vulnerability reporting](https://github.com/binaryme/hermes-agent-casebook/security/advisories/new). Use the Security tab, then Report a vulnerability. Do not open a public issue.

This repository does not run a bug bounty.
