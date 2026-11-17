# Changelog

All notable changes to this project are documented here. The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and the project uses [Semantic Versioning](https://semver.org/).

## [0.1.0] - 2026-11-16

### Added

- Need-to-Know protocol spec v0.1 (`SPEC.md`): labels (`public`, `role:<r>`, `private`), three checks per reply, disclosure ledger, expiring consent grants, JSON wire format, related work.
- Reference implementation `ntk` (Python 3.9+, standard library only): `Fact`, `Label`, `Request`, `Policy`, `Grant`, `Ledger`, `check_reply`.
- Optional LLM judge through the local `claude -p` CLI, enabled only with `NTK_LLM=claude`; API-key variables are stripped.
- `ntk check` CLI: prints the decision as JSON; exit code 0 (send), 1 (send the rewrite), 2 (bad input).
- `ntk-mcp` MCP server (stdio, standard library only) with `check_reply` and `get_ledger` tools.
- Packaging (`pyproject.toml`): `pip install git+https://github.com/federicodeponte/ntk-protocol`.
- Maya and Jun example (`examples/maya_jun.py`, `examples/maya_facts.json`), flow diagram, social preview.
- 34 unit tests.

### Not yet

- The 20-chat leak benchmark is planned and has not been run.

[0.1.0]: https://github.com/federicodeponte/ntk-protocol/releases/tag/v0.1.0
