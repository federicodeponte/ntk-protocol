# ntk-protocol (TypeScript)

**HCP decides what your agent can know. NTK decides what it can say.**

TypeScript port of the [Need-to-Know (NTK) protocol](https://github.com/federicodeponte/ntk-protocol): labels per fact (`public`, `role:<r>`, `private`), three checks on every reply an agent sends to another agent, a disclosure ledger and expiring consent grants. Zero runtime dependencies, ESM with types, Node 18.17+. It passes the same conformance cases as the Python reference (`conformance/cases.json`).

## CLI

```bash
npx ntk-protocol check --facts facts.json --request request.json "She beat the baseline."
```

Prints `{allowed, send, reasons, consent_requests, ledger_entry}` as JSON, like the Python `ntk check`. Exit code `0` = send the draft unchanged, `1` = send `send` instead, `2` = bad input.

## MCP server

```bash
claude mcp add ntk -e NTK_FACTS=/absolute/path/facts.json -- npx -y ntk-protocol mcp
```

Tools: `check_reply` and `get_ledger`, the same as the Python `ntk-mcp`. Env: `NTK_FACTS`, `NTK_LEDGER`, and optional `NTK_LLM=claude` (local `claude -p` judge, API-key variables stripped).

## Library

```ts
import { Fact, Policy, Ledger, checkReply } from "ntk-protocol";

const facts = [
  new Fact({ id: "methods", text: "methods and code", label: "role:collaborator", aliases: ["her code"], topics: ["methods"] }),
  new Fact({ id: "result", text: "unpublished result 0.81", label: "private", hints: ["beat the baseline"],
             safe_say: "Anything after publication I can't share yet." }),
];
const d = checkReply("She beat the baseline.", facts,
  { requester: "jun-agent", role: "collaborator", purpose: "plan a study" },
  { policy: new Policy(), ledger: new Ledger(), judge: null });
// d.allowed === false, d.rewritten === "Anything after publication I can't share yet."
```

Spec, wire format and the Python reference: [github.com/federicodeponte/ntk-protocol](https://github.com/federicodeponte/ntk-protocol). Apache-2.0.
