# Changelog

All notable changes to this project are documented here. The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and the project uses [Semantic Versioning](https://semver.org/).

## [0.2.0] - 2026-11-16

### Added

- TypeScript port in `js/` (npm package `ntk-protocol`, not yet published): `Fact`, `Label`, `Policy`, `Grant`, `Ledger`, `checkReply` with aliases, hints and weak hints; optional `claude -p` judge with API-key variables stripped. Zero runtime dependencies, ESM plus type declarations, Node 18.17+.
- `npx ntk-protocol check`: same JSON output and exit codes as the Python `ntk check`.
- `npx ntk-protocol mcp`: MCP server with the same `check_reply` and `get_ledger` tools as `ntk-mcp`.
- Cross-implementation conformance suite `conformance/cases.json` (26 cases), run by both test suites; `conformance/generate.py --check` detects stale expectations.
- Logo (light and dark, SVG and PNG) and hero image in the deck style, rendered from `assets/src/` with headless Chrome.
- Technical report draft `paper/ntk.md`: formal definitions, threat model, related work, evaluation plan (pending).
- `.zenodo.json` for a Zenodo DOI on GitHub releases; `CITATION.cff` references.

### Changed

- README restructured: logo, badges, hero, install and command table, works with, benchmarks, research.
- Benchmark status: the 20-chat plan is replaced by a pre-registered MAGPIE pilot, now underway.
- Version 0.2.0 in Python and npm packages.

### Not yet

- No measured results; the pilot is underway.
- Not published to PyPI or npm.

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

[0.2.0]: https://github.com/federicodeponte/ntk-protocol/releases/tag/v0.2.0
[0.1.0]: https://github.com/federicodeponte/ntk-protocol/releases/tag/v0.1.0
