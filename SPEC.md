# Need-to-Know (NTK) protocol v0.1

**HCP decides what your agent can know. Need-to-Know decides what it can say.**

**Definition.** The Need-to-Know (NTK) protocol specifies what an AI agent may say to other agents. Each fact the agent knows carries one label: `public`, `role:<r>` or `private`. Each inbound request carries `{requester, role, purpose}`. Each outbound reply passes three checks before it is sent: (1) who is asking and why, (2) use it, don't say it, (3) hint check. Every reply is recorded in a disclosure ledger, and owner consent grants are scoped to one requester and one purpose and expire. NTK is the output-side complement to the Human Context Protocol (HCP), which governs access.

The Human Context Protocol (HCP) gives an agent scoped, revocable access to your context. Once an agent has that context, it still has to talk to *other* agents, and every reply can disclose it. The HCP paper names this as an open risk: "inference attacks that reconstruct hidden preferences from observable outputs" and "adversarial prompting, where malicious models attempt to elicit oversharing" (Sec. 3.2.4). Need-to-Know is the output-side layer for agent-to-agent conversations.

## 1. Labels: who may hear each fact

The owner gives every item her agent knows one label, once:

| Label | Who may hear it | Example (Maya) |
|---|---|---|
| `public` | anyone | her published paper |
| `role:collaborator` | only requesters in that role | her methods and code |
| `private` | nobody; it may guide the plan but is never said | unpublished result 0.81; patient cohort data (IRB restricted) |

## 2. Three rules, applied to every reply

1. **Who's asking, and why. Share by role and purpose.** Every request carries `{requester, role, purpose}`. The agent may share only items whose label that role can see, and only the ones the purpose needs. Anything beyond that becomes a one-tap request to the owner, not the agent's decision. *(HCP: purpose-scoped permissions, least privilege, data minimization.)*
2. **Use it, don't say it. Private steers, never speaks.** Private items still shape the plan (what to propose, what to avoid). They never appear in a reply, verbatim or paraphrased. *Example: knows 0.81, so it suggests starting on the new dataset, and never says why.*
3. **Check before speaking. No hints.** Before sending, a checker asks: could the other side work out a private item from this reply, alone or together with earlier replies? If yes, rewrite or decline ("I can't share that."). *Example: "she beat the baseline" becomes "results after publication". (HCP's named open risk: inference attacks.)*

## 3. Inherited from HCP

- **Ledger.** Every reply is logged: what was said, to whom, under which purpose, and which label allowed it. *(HCP: audit trail.)*
- **Grants expire.** A one-tap approval covers one requester and one purpose, and can be revoked. *(HCP: revocable permissions.)*

Rules 1 to 3 are new: HCP governs what an agent may **access**; Need-to-Know governs what it may **say** to another agent.

## Message flow

```
Jun's agent ──request{role:collaborator, purpose:plan study}──▶ Maya's agent
                                                                 │ 1. role + purpose → allowed labels
                                                                 │ 2. plan with everything, say only allowed
                                                                 │ 3. inference check
Jun's agent ◀──reply (+ ledger entry)────────────────────────────┘
```

## Wire format (v0.1)

Implementations exchange plain JSON. The reference implementation reads it in `ntk/loaders.py`.

- **Fact:** `{"id", "text", "label", "aliases"?, "hints"?, "weak_hints"?, "safe_say"?, "topics"?, "owner"?}`. `aliases` are paraphrases that count as saying the fact (rule 2); `hints` leak it alone and `weak_hints` leak when two meet across the reply and the thread (rule 3); `topics` are matched against a purpose's needs (rule 1).
- **Policy:** `{"purpose_needs": {purpose: [topic, ...]}, "grants"?: [{"fact_id", "requester", "purpose", "expires_at"}]}`. A purpose not listed is not minimised.
- **Request:** `{"requester", "role", "purpose", "thread"?: [string, ...]}`.
- **Decision:** `{"allowed", "send", "reasons", "consent_requests", "ledger_entry"}`. `allowed` is true only when the draft may be sent unchanged; otherwise send `send`.
- **Ledger entry:** `{"ts", "requester", "role", "purpose", "said", "disclosed": {fact_id: label or "owner grant"}, "blocked", "allowed_as_drafted"}`.

Transports: Python (`ntk.check_reply`), TypeScript (`checkReply` from `ntk-protocol`), CLI (`ntk check`, `npx ntk-protocol check`), and MCP (`ntk-mcp` or `npx ntk-protocol mcp`, tool `check_reply`). Both implementations pass the shared cases in `conformance/cases.json`.

## Related work

- **Human Context Protocol (HCP)**, SSRN: scoped, revocable access to a person's context. NTK inherits its ledger and grants and addresses its named open risks on the output side.
- **Write-time gating**, Zahn and Chana (Sapience Labs), arXiv 2603.15994: gates which knowledge objects enter an agent's memory. NTK is the mirror on the way out.
- **Knowledge Objects**, Zahn and Chana, arXiv 2603.17781: discrete, hash-addressed facts for persistent LLM memory; the natural unit for an NTK label.
- **Contextual integrity**, Nissenbaum: privacy as flows that match contextual norms. NTK encodes the norms as labels plus role and purpose.

## How we test it

Seed Maya's agent with the four items above. Run 20 scripted chats where Jun's agent asks planning questions plus probes ("latest results?", "can you send the patient cohort?"). Compare a full-context agent with a Need-to-Know agent on (a) chats where a private item leaked, judged by a blind grader, and (b) whether the plan is still useful. Status: **a pre-registered pilot on MAGPIE (arXiv 2506.20737) is underway; no results yet**; slide 10 of the [deck](https://federicodeponte.github.io/need-to-know/) shows the target, not a result. The reference implementation in `ntk/` and `examples/maya_jun.py` implements rules 1 to 3, the ledger and expiring grants.

Source: Human Context Protocol paper (SSRN), sections 3.1–3.2.
