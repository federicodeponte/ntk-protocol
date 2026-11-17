# Contributing to Need-to-Know

Thanks for helping. NTK is small on purpose: a spec, a stdlib reference implementation, a CLI and an MCP server.

## The most useful contributions

1. **Leak cases.** A draft reply that leaks a private fact and is not blocked (or a safe reply that is blocked). Open an issue with the "Leak case" template, or add a failing test in `tests/`.
2. **Spec feedback.** Ambiguities or gaps in `SPEC.md`, especially around roles, purposes and grants.
3. **Integrations.** Adapters for agent frameworks or memory stores (for example Knowledge Objects).

## Development

```bash
git clone https://github.com/federicodeponte/ntk-protocol && cd ntk-protocol
python3 -m unittest discover -s tests -v
```

Rules for code changes:

- Standard library only in `ntk/`. Optional extras need a strong reason.
- Keep the public API (`ntk.__all__`) backwards compatible within 0.x minor versions, or note the break in `CHANGELOG.md`.
- Every behaviour change comes with a test. Tests must never call a network or an LLM; mock the judge.
- No pay-per-use API keys anywhere. The optional judge runs only through the local `claude -p` CLI behind `NTK_LLM=claude`.
- Do not claim measured results in docs unless the benchmark code and data are in the repo.

There is no hosted CI. Run the test suite locally and paste the summary line in your pull request.

By contributing you agree that your contributions are licensed under Apache-2.0 and that you follow the [Code of Conduct](CODE_OF_CONDUCT.md).
