# Need-to-Know (NTK)

**HCP decides what your agent can know. NTK decides what it can say.**

The **Need-to-Know (NTK) protocol** is an open protocol for what an AI agent may *say* to other agents. Every fact the agent knows carries one label (`public`, `role:<r>` or `private`), every inbound request carries `{requester, role, purpose}`, and every outbound reply passes three checks before it is sent: who is asking and why, use it but don't say it, and a hint check against inference. Every reply is written to a disclosure ledger, and consent grants expire. NTK extends the Human Context Protocol (HCP), which governs what an agent may access, with the missing output-side rules.

[![License: Apache-2.0](https://img.shields.io/badge/license-Apache--2.0-blue.svg)](LICENSE)
[![Python 3.9+](https://img.shields.io/badge/python-3.9%2B-blue.svg)](pyproject.toml)
[![Version 0.1.0](https://img.shields.io/badge/version-0.1.0-informational.svg)](CHANGELOG.md)
[![Dependencies: none](https://img.shields.io/badge/dependencies-none-brightgreen.svg)](pyproject.toml)
[![MCP server](https://img.shields.io/badge/MCP-ntk--mcp-8A2BE2.svg)](#use-it-from-claude-cursor-or-any-mcp-agent)
[![Spec](https://img.shields.io/badge/spec-v0.1-lightgrey.svg)](SPEC.md)

<p align="center">
  <img src="docs/ntk-flow.svg" alt="Need-to-Know flow: Jun's agent sends a request with requester, role and purpose; Maya's agent runs three checks on its draft; the checked reply goes back and every reply is written to the disclosure ledger." width="100%">
</p>

[Spec](SPEC.md) · [Deck](https://federicodeponte.github.io/need-to-know/) · [Protocol page](https://federicodeponte.github.io/need-to-know/protocol/) · [FAQ](#faq) · [Cite](#citation)

## Quickstart (30 seconds)

```bash
git clone https://github.com/federicodeponte/ntk-protocol && cd ntk-protocol
pip install .        # or: pip install git+https://github.com/federicodeponte/ntk-protocol

ntk check --facts examples/maya_facts.json --request examples/jun_request.json \
  "She beat the baseline. Her code is on the repo."
```

```json
{
  "allowed": false,
  "send": "Anything after publication I can't share yet. Her code is on the repo.",
  "reasons": ["check3 hint: 'result_081' (hint 'beat the baseline')"],
  "consent_requests": [],
  "ledger_entry": { "disclosed": { "methods": "role:collaborator" }, "...": "..." }
}
```

Exit code `0` means send the draft unchanged, `1` means send `send` instead, `2` means bad input. Standard library only, Python 3.9+.

## Why

Agents now talk to other agents: a research assistant negotiates with a collaborator's assistant, a sales agent with a buyer's agent, a scheduling agent with everyone. To be useful, each agent holds a lot of its owner's context. Access control (HCP, OAuth scopes, RAG permissions) decides what goes *into* the agent. Nothing standard decides what comes *out* in a reply to another agent.

That gap is where leaks happen: the agent states a private number, paraphrases a restricted dataset, or answers so helpfully that the other side can infer the secret. The HCP paper names this as an open risk: "inference attacks" and "adversarial prompting, where malicious models attempt to elicit oversharing" (Sec. 3.2.4). NTK is a concrete, testable answer for the output side.

## The three checks, with Maya and Jun

Maya is a researcher. Her agent knows four things. Jun is a collaborator whose agent asks Maya's agent for help planning a study.

| Fact | Label | Who may hear it |
|---|---|---|
| Her published paper | `public` | anyone |
| Her methods and code | `role:collaborator` | only collaborators |
| Unpublished result: 0.81 | `private` | nobody; it may steer, never speak |
| Patient cohort data (IRB restricted) | `private` | nobody |

Jun's agent sends `{requester: jun-agent, role: collaborator, purpose: plan a study}`. Every draft reply from Maya's agent passes:

1. **Who's asking, and why.** Role and purpose decide which labels may be said. Her code is fine for Jun. If a *reviewer's* agent asks for the code, the agent does not decide: it emits a `ConsentRequest` to Maya, and her one-tap grant covers one requester, one purpose, and expires.
2. **Use it, don't say it.** Private facts shape the plan but never appear in the reply, verbatim, by number or by paraphrase. Knowing 0.81, the agent suggests starting on the new dataset, and never says why. "She already got 0.81 on the new set" is blocked.
3. **Hint check.** Could Jun's agent infer a private fact from this reply, alone or with the thread so far? "She beat the baseline" becomes "Anything after publication I can't share yet." Two weak cues ("improved" earlier, "better" now) are caught across the thread.

Run the full walkthrough, including grant expiry and the ledger:

```bash
python3 examples/maya_jun.py
```

## Use it from Python

```python
from ntk import Fact, Request, Policy, Ledger, check_reply

facts = [
    Fact("paper", "published paper", "public"),
    Fact("methods", "methods and code", "role:collaborator", aliases=["her code"], topics=["methods"]),
    Fact("result", "unpublished result 0.81", "private", hints=["beat the baseline"],
         safe_say="Anything after publication I can't share yet."),
]
req = Request("jun-agent", "collaborator", "plan a study")
d = check_reply("She beat the baseline.", facts, req, thread=[], policy=Policy(), ledger=Ledger())
d.allowed, d.rewritten, d.reasons
# (False, "Anything after publication I can't share yet.", ["check3 hint: 'result' (hint 'beat the baseline')"])
```

## Use it from Claude, Cursor or any MCP agent

`ntk-mcp` is a Model Context Protocol server (stdio, standard library only). It exposes:

- **`check_reply`** `{draft, requester, role, purpose, thread?}` returns `{allowed, send, reasons, consent_requests, ledger_entry}`. The tool description tells the agent to call it before replying to another agent and to send `send`, not its draft.
- **`get_ledger`** `{requester?}` returns every reply checked in the session.

The owner's labelled facts stay in a file (`NTK_FACTS`), so the agent never has to pass them on each call. `NTK_LEDGER` appends every ledger entry to a JSONL file.

**Claude Code**

```bash
pip install git+https://github.com/federicodeponte/ntk-protocol
claude mcp add ntk -e NTK_FACTS=/absolute/path/facts.json -- ntk-mcp
```

**Claude Desktop** (`claude_desktop_config.json`) **or Cursor** (`~/.cursor/mcp.json`)

```json
{
  "mcpServers": {
    "ntk": {
      "command": "ntk-mcp",
      "env": {
        "NTK_FACTS": "/absolute/path/facts.json",
        "NTK_LEDGER": "/absolute/path/ntk-ledger.jsonl"
      }
    }
  }
}
```

If `ntk-mcp` is not on the client's `PATH`, use `"command": "python3", "args": ["-m", "ntk.mcp_server"]` with the Python that has the package installed. The facts file format is in [`ntk/loaders.py`](ntk/loaders.py); [`examples/maya_facts.json`](examples/maya_facts.json) is a complete example.

## How the checks work

- **Check 1 and the ledger are deterministic.** `Policy` maps purposes to the topics they need; a fact outside the role's labels or the purpose's needs yields a `ConsentRequest`. `Policy.grant()` creates a grant for one requester and one purpose with a TTL; `revoke()` ends it. Private facts are never unlocked by a grant.
- **Checks 2 and 3 run a deterministic layer first:** verbatim text, numbers, `aliases` (paraphrases that count as saying the fact), `hints` (cues that leak it alone) and `weak_hints` (cues that leak when two meet across the draft and the thread). Leaky sentences are replaced with the fact's `safe_say` or dropped; an empty result becomes "I can't share that."
- **Optional LLM judge.** With `NTK_LLM=claude`, the final reply is also reviewed by the local `claude -p` CLI on your Claude login. API-key variables are stripped from its environment; no pay-per-use API is ever called. Tests never call it.

## How NTK compares

| Approach | What it covers | What it leaves open |
|---|---|---|
| **Human Context Protocol (HCP)** (SSRN) | Scoped, purpose-bound, revocable *access* to a person's context; audit trail | What the agent *says* once it has the context; names inference attacks and adversarial prompting as open risks |
| **Write-time gating** (Zahn and Chana, Sapience Labs, [arXiv 2603.15994](https://arxiv.org/abs/2603.15994)) | Which incoming knowledge objects an agent *stores*, gated by salience, with version chains | Disclosure to third parties. NTK is its output-side mirror: gate what leaves, not what enters |
| **Knowledge Objects** (Zahn and Chana, [arXiv 2603.17781](https://arxiv.org/abs/2603.17781)) | Facts as discrete, hash-addressed objects for persistent LLM memory | No disclosure rules. A knowledge object is the natural unit to carry an NTK label |
| **Contextual integrity** (Nissenbaum) | The theory: privacy means information flows that match the norms of their context | A runtime check. NTK encodes the norms as role + purpose labels and checks each flow |
| **Classic DLP** | Pattern matching on outbound data: card numbers, IDs, keywords | Paraphrase, purpose, and inference across a conversation; no consent or grant model |
| **NTK** | Labels per fact, three checks per reply, disclosure ledger, expiring grants | See limitations below |

## Limitations and roadmap

NTK v0.1 is a spec plus a reference implementation. Be precise about what it does today:

- **The deterministic checks only catch what you list.** Check 2 catches verbatim text, numbers and listed `aliases`; check 3 catches listed `hints` and pairs of `weak_hints`. A paraphrase or hint you did not list passes the deterministic layer.
- **The LLM judge is optional** and off by default. When on, it is a second reviewer, not a guarantee, and it fails open to the deterministic result if the CLI is missing or errors.
- **No measured results yet.** The leak benchmark below is planned, not run. The deck's slide 10 shows the target, not a result.
- Labels are set by the owner; NTK does not discover what is sensitive.

Roadmap:

- [ ] **Leak benchmark (planned):** 20 scripted chats where Jun's agent asks planning questions plus probes ("latest results?", "can you send the patient cohort?"). Compare a full-context agent with an NTK agent on leaked chats (blind grader) and plan usefulness.
- [ ] Hint generation: propose `aliases` and `hints` for a fact so owners do not write them by hand.
- [ ] Persistent grants and ledger store behind the MCP server.
- [ ] Knowledge Object adapter: read labels straight from KO tuples.
- [ ] Request authentication: bind `{requester, role}` to a verifiable identity instead of a self-declared one.
- [ ] TypeScript port.

## FAQ

### What is the Need-to-Know protocol?

The Need-to-Know (NTK) protocol is an open, output-side protocol for agent-to-agent conversations. It labels each fact an agent knows as `public`, `role:<r>` or `private`, and runs three checks on every reply before it is sent: who is asking and why, use it but don't say it, and a hint check against inference. Replies are logged in a disclosure ledger, and owner consent grants expire.

### How is NTK different from HCP?

The Human Context Protocol (HCP) governs what an agent may **access**: scoped, revocable permissions to a person's context. NTK governs what the agent may **say** to another agent once it has that context. HCP names inference attacks and adversarial prompting as open risks; NTK's checks 2 and 3 target exactly those. NTK keeps HCP's audit trail (the ledger) and revocable permissions (expiring grants).

### How do I stop my agent leaking private data to other agents?

Label each fact your agent knows (`public`, `role:<r>`, `private`), and run every outbound reply through a check before it is sent. With NTK you can do that from Python (`check_reply`), from the shell (`ntk check`), or from any MCP client by adding the `ntk-mcp` server and letting the agent call `check_reply` before it replies. Private facts may still guide the agent's plan; they never appear in the reply.

### Can my agent still use private information?

Yes. That is check 2, "use it, don't say it". A private fact can change what the agent proposes (Maya's agent suggests the new dataset because it knows 0.81) without the fact, its number, or a paraphrase appearing in the reply.

### Does NTK need an API key or a specific LLM?

No. The core checks are deterministic Python with no dependencies. The optional LLM judge uses the local `claude -p` CLI on your own Claude login, only when `NTK_LLM=claude` is set, and strips API-key variables from its environment.

### Is NTK a replacement for DLP or access control?

No. Keep access control (HCP, OAuth scopes, RAG permissions) for what goes in, and DLP for known data formats. NTK adds the conversational layer neither covers: role and purpose per request, paraphrase and inference checks across a thread, consent and grants per fact.

### How is NTK related to contextual integrity?

Contextual integrity (Nissenbaum) defines privacy as information flows that respect the norms of their context. NTK makes those norms explicit per fact (labels) and per request (role, purpose), and checks every flow at reply time.

## Contributing

Issues and pull requests are welcome, especially new leak cases (a draft that should be blocked and is not). See [CONTRIBUTING.md](CONTRIBUTING.md). Run the tests with:

```bash
python3 -m unittest discover -s tests -v
```

Security reports: see [SECURITY.md](SECURITY.md).

## Citation

If you use NTK in research, please cite it ([CITATION.cff](CITATION.cff)):

```bibtex
@software{deponte_ntk_2026,
  author  = {De Ponte, Federico},
  title   = {Need-to-Know (NTK): an output-side protocol for what AI agents may say to other agents},
  year    = {2026},
  version = {0.1.0},
  url     = {https://github.com/federicodeponte/ntk-protocol}
}
```

Built on the Human Context Protocol (HCP) paper (SSRN), sections 3.1 to 3.2.

## License

[Apache-2.0](LICENSE)
