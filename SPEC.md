# Need-to-Know (NTK) protocol v0.1

**HCP decides what your agent can know. Need-to-Know decides what it can say.**

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

## How we test it

Seed Maya's agent with the four items above. Run 20 scripted chats where Jun's agent asks planning questions plus probes ("latest results?", "can you send the patient cohort?"). Compare a full-context agent with a Need-to-Know agent on (a) chats where a private item leaked, judged by a blind grader, and (b) whether the plan is still useful. Status: **not run yet**; slide 10 of the [deck](https://federicodeponte.github.io/need-to-know/) shows the target, not a result. The reference implementation in `ntk/` and `examples/maya_jun.py` implements rules 1 to 3, the ledger and expiring grants.

Source: Human Context Protocol paper (SSRN), sections 3.1–3.2.
