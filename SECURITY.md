# Security policy

NTK is a privacy control, so a bypass is a security issue.

## What counts

- A reply that discloses a `private` fact (verbatim, by number, or through a listed alias or hint) and is allowed by `check_reply`.
- A `role:<r>` fact disclosed to another role without an active grant.
- A grant that unlocks a `private` fact, or that outlives its expiry or revocation.
- The optional judge reading API-key variables or calling a pay-per-use API.
- Crashes or injection in `ntk-mcp` caused by tool arguments.

Known limitation, not a vulnerability: the deterministic checks only catch aliases and hints that are listed for a fact. Unlisted paraphrases are a documented gap (see the README); improvements are welcome as normal issues.

## How to report

Use GitHub's private vulnerability reporting: **Security > Report a vulnerability** on this repository. Please do not open a public issue for a bypass. Expect a first reply within 7 days.

## Supported versions

| Version | Supported |
|---|---|
| 0.1.x | yes |
