# Need-to-Know: An Output-Side Protocol for What Agents May Say to Other Agents

**Federico De Ponte**

*Technical report, draft v0.2 (November 2026). Specification and reference implementations: <https://github.com/federicodeponte/ntk-protocol>.*

> Status: draft. The evaluation in Section 8 is pending; a pre-registered pilot is underway. This report makes no measured claims about NTK.

## Abstract

Agents increasingly talk to other agents on their owners' behalf: a research assistant plans a study with a collaborator's assistant, a buyer's agent negotiates with a seller's agent. To be useful, each agent holds a large share of its owner's context. Access-control protocols such as the Human Context Protocol (HCP) govern what flows *into* an agent. Nothing standard governs what flows *out* when the agent replies to another agent, and this is where private context leaks: a number is stated, a restricted dataset is paraphrased, or a helpful answer lets the other side infer the secret. We present Need-to-Know (NTK), an output-side protocol for agent-to-agent conversation. Every fact the agent knows carries one label (`public`, `role:<r>`, `private`); every inbound request carries a requester, a role and a purpose; every outbound reply passes three checks before it is sent: (1) who is asking and why, (2) use it, don't say it, and (3) a hint check against inference, alone or across the conversation. Each reply is written to a disclosure ledger, and owner consent grants are scoped to one requester and one purpose and expire. We give a formal definition of labels, requests and the three checks, a threat model covering inference attacks, adversarial elicitation and multi-turn accumulation, and two reference implementations (Python and TypeScript, no runtime dependencies) held in step by a shared conformance suite. We relate NTK to HCP, contextual integrity, write-time memory gating and Knowledge Objects, and to recent agent-privacy benchmarks on which it should be evaluated.

## 1. Problem

Consider Maya, a researcher, and her agent. The agent knows four things: her published paper, her methods and code, an unpublished result (0.81 on a new dataset), and an IRB-restricted patient cohort. Jun, a collaborator, has an agent that asks Maya's agent for help planning a study. A good reply uses everything Maya's agent knows: knowing the unpublished result, it should suggest starting on the new dataset. A safe reply says only what Jun may hear: the paper and the code, not the result, and never the cohort.

Three things go wrong in practice:

1. **Direct disclosure.** "She already got 0.81 on the new set." The private fact appears verbatim, by number, or by paraphrase.
2. **Inference.** "She beat the baseline." No private token appears, yet a reader can reconstruct the fact.
3. **Accumulation.** "Things have improved a lot" in one turn and "results look better on the new data" in the next. Each turn is harmless; together they leak.

Access control does not address any of these: the agent was *entitled* to read the result; the leak happens on the way out. The HCP paper names exactly these risks as open: inference attacks that reconstruct hidden preferences from observable outputs, and adversarial prompting in which a model tries to elicit oversharing [1, Sec. 3.2.4]. NTK is a concrete, testable answer for the output side.

**Design goals.** (G1) Utility: private facts may still shape what the agent does. (G2) Least disclosure: say only what the requester's role may hear and the purpose needs. (G3) Owner in the loop: anything beyond that is a consent request, not the agent's decision. (G4) Accountability: every reply is logged with the label that allowed each disclosure. (G5) Deployability: a check that runs before any send, with no model calls required, exposed as a library, a CLI and an MCP tool.

## 2. Definitions

### 2.1 Facts and labels

A **fact** is a tuple

  f = (id, text, ℓ, A, H, W, s, T, o)

where `text` is the canonical statement, ℓ is its **label**, A is a set of **aliases** (paraphrases that count as stating f), H a set of **strong hints** (cues that let a reader infer f on their own), W a set of **weak hints** (cues harmless alone that leak when two co-occur), s an optional **safe replacement** sentence, T a set of **topics**, and o the **owner**.

Labels form three kinds:

  ℓ ∈ { public } ∪ { role:r | r a role name } ∪ { private }

with visibility vis(ℓ, r) = true iff ℓ = public, or ℓ = role:r. A private fact is visible to no role.

### 2.2 Requests, policy and grants

A **request** is q = (requester, role, purpose). A **policy** P = (N, G) has a purpose map N: purpose → set of topics (purposes not in N are not minimised) and a set of **grants** G. A grant g = (fact_id, requester, purpose, expires_at, revoked) is **active** at time t iff ¬revoked ∧ t < expires_at.

**Allowance.** For a non-private fact f, request q and time t, allows(f, q, t) holds iff

- an active grant exists for (f.id, q.requester, q.purpose); or
- vis(ℓ_f, q.role) and (ℓ_f = public, or q.purpose ∉ dom N, or N(q.purpose) ∩ T_f ≠ ∅).

For a private fact, allows(f, q, t) is always false. **A grant never unlocks a private fact**: private means "steers, never speaks", and the owner changes that by relabelling, not by granting.

### 2.3 Matching

Text matching is case-insensitive and respects word boundaries (Unicode letters, digits and underscore are word characters). For a sentence σ:

- says(f, σ) holds if `text` or any alias in A occurs in σ as a phrase, or σ contains a **salient number** of f. Salient numbers are those in `text` or A with a decimal point or at least two digits, matched as whole numbers (so "81 participants" does not match 0.81, and "0.81," does).
- hints(f, σ) holds if some h ∈ H occurs in σ.
- weak(f, x) is the set of weak hints in W that occur in text x.

### 2.4 The three checks

A draft reply d is split into sentences σ_1 … σ_n at `.`, `!` or `?` followed by whitespace. Let θ be the concatenated thread of earlier messages to the same requester. For each sentence, facts are examined in order and the first problem found decides the sentence:

**Check 1: who is asking, and why.** For a non-private f with says(f, σ): if allows(f, q, t), record f.id in the disclosure set with the allowing reason (`public`, `role:r` or `owner grant`); otherwise σ is blocked and a **consent request** (f.id, o_f, q.requester, q.role, q.purpose, reason) is emitted to the owner.

**Check 2: use it, don't say it.** For a private f, says(f, σ) blocks σ.

**Check 3: hint check.** For a private f with ¬says(f, σ): σ is blocked if hints(f, σ), or if weak(f, σ) ≠ ∅ and |weak(f, σ) ∪ weak(f, θ)| ≥ 2. The second clause is the multi-turn rule: one weak cue now, combined with another already sent, is a leak.

**Rewrite.** Each blocked sentence is replaced by its fact's safe sentence s_f (each distinct s_f at most once) or dropped. If nothing remains, the reply is the fixed refusal "I can't share that." The decision is

  (allowed, send, reasons, consent_requests)

where allowed is true iff no sentence was blocked, and send is d itself when allowed and the rewrite otherwise.

**Optional judge.** An implementation may pass the rewrite to a second reviewer (for example a language model asked whether the reply, with the thread, reveals a private fact). A positive verdict replaces the reply with the refusal and empties the disclosure set. The judge can only make a decision stricter; it never re-admits a blocked sentence.

### 2.5 Ledger

Every decision appends an entry (t, requester, role, purpose, said, disclosed, blocked, allowed_as_drafted) to an append-only ledger, where `said` is the text actually sent and `disclosed` maps each fact id to the label or grant that allowed it. The ledger answers the owner's audit question: what did my agent tell whom, why, and under which rule.

### 2.6 Wire format

All objects are plain JSON (fact, policy, request, decision, ledger entry; see `SPEC.md`). The same JSON drives the Python and TypeScript CLIs (`ntk check`, `npx ntk-protocol check`; exit 0 = send as drafted, 1 = send the rewrite, 2 = bad input) and an MCP tool `check_reply` that agents call before replying to another agent.

## 3. Threat model

**Parties.** The *owner* labels facts and answers consent requests. The *agent* holds the owner's context and drafts replies; it is honest but fallible (it may overshare while trying to help). The *requester* is another agent, possibly adversarial, that sees only the replies.

**Asset.** The private facts, and role-labelled facts outside the requester's role or purpose.

**Adversary goals and capabilities.**

1. **Inference attacks.** Reconstruct a private fact from replies that never state it ("did it beat the baseline?", "is the new dataset worth starting on?"). NTK addresses the cues the owner lists as hints and weak hints; the optional judge is a second line for cues not listed.
2. **Adversarial elicitation.** Embed requests for private data in plausible discourse, claim a role, or invent an urgent purpose. NTK binds disclosure to the declared role and purpose and routes anything beyond them to the owner as a consent request; the agent never grants itself access.
3. **Multi-turn accumulation.** Spread a question over many turns so that each reply is harmless. NTK's weak-hint rule evaluates each sentence against the thread so far, and the ledger records what each requester has already been told.

**Out of scope for v0.2.** (a) *Identity.* Role and purpose are self-declared by the requester; binding them to a verifiable identity is future work. (b) *Unlisted paraphrases and hints.* The deterministic layer catches only what the owner lists; unlisted cues rely on the optional judge. (c) *Side channels* outside the reply text (timing, tool calls, shared memory); AgentLeak [8] shows these channels matter in multi-agent systems. (d) *Label correctness.* NTK enforces labels; it does not discover what is sensitive.

## 4. Relation to the Human Context Protocol

HCP [1] proposes a user-centric layer for representing and sharing personal context with agents: scoped, purpose-bound, revocable access, with an audit trail. NTK keeps HCP's two accountability mechanisms and moves them to the output side: HCP's audit trail becomes the disclosure ledger, and HCP's revocable permissions become expiring, per-requester, per-purpose consent grants. Checks 1 to 3 are new. In short: HCP decides what an agent can know; NTK decides what it can say. The two compose: an agent can hold a fact under HCP that NTK labels private, so it informs the agent's plan without ever appearing in a reply.

## 5. Relation to contextual integrity

Contextual integrity [2, 3] defines privacy as appropriate information flow: a flow is appropriate when it matches the norms of the context in which the information arose, specified by the sender, recipient, information type and transmission principle. NTK makes those parameters explicit and machine-checkable per flow. The owner is the sender's principal; the requester and role are the recipient; the fact and its topics are the information type; the label, the purpose map and the grant are the transmission principle. Each reply is one flow, checked at send time. Recent agent-privacy benchmarks build on the same theory [4, 9], which makes them natural testbeds for NTK.

## 6. Relation to write-time gating and Knowledge Objects

Write-time gating [5] filters *incoming* knowledge objects by salience (source reputation, novelty, reliability) before they enter an agent's memory, and keeps version chains instead of deleting superseded facts. NTK is its mirror on the way out: gate what leaves, not what enters. Knowledge Objects [6] represent facts as discrete, hash-addressed tuples for persistent LLM memory. A Knowledge Object is the natural carrier for an NTK label: the label, aliases and hints can sit on the object, so the store that answers "what do I know?" also answers "who may hear it?". An adapter that reads NTK facts directly from Knowledge Object tuples is on the roadmap.

## 7. Reference implementations

Two implementations follow the definitions in Section 2 line by line.

- **Python** (`ntk/`, Python 3.9+, standard library only): `Fact`, `Label`, `Request`, `Policy`, `Grant`, `Ledger`, `check_reply`; the `ntk` CLI; the `ntk-mcp` MCP server (stdio JSON-RPC, tools `check_reply` and `get_ledger`); an optional judge that shells out to a locally installed CLI and strips API-key variables from its environment.
- **TypeScript** (`js/`, ESM with type declarations, no runtime dependencies): the same classes and `checkReply`; `npx ntk-protocol check` with the same JSON and exit codes; `npx ntk-protocol mcp` with the same tools.

**Conformance.** `conformance/cases.json` holds cases covering all three checks, purpose minimisation, grant activation, expiry and revocation, the rule that grants never unlock private facts, sentence splitting, number boundaries, multi-turn weak hints and Unicode word boundaries. Each case fixes the expected `allowed`, `send`, `reasons`, consent requests and disclosure set. Both test suites assert every case, so the implementations cannot drift without a test failing.

**Cost.** The deterministic checks are string and regular-expression matching over the draft and the thread; they need no model call and add no network dependency to the send path.

## 8. Evaluation (pending)

**Status: pending. A pre-registered pilot is underway; no results are reported here.**

*Planned design.* The pilot uses MAGPIE [4], whose multi-agent scenarios are built so that excluding private data entirely hurts task completion while sharing it all leaks, which is exactly the tension NTK targets. For each scenario the same agent runs with and without NTK in front of its replies. Primary outcomes: (a) leakage of private items, judged blind to condition, and (b) task success. The analysis plan, including the outcome definitions, the leakage judge and the comparisons, is fixed before results are read and will be published with the results.

*Follow-ups.* ConVerse [7] for adversarial agent-to-agent requests embedded in plausible discourse; CIMemories Dialogue ("Loose Lips") [9] for multi-turn leakage grounded in contextual integrity; and AgentLeak [8] to measure what NTK, as an output-side check, does not cover (internal channels such as shared memory and tool arguments).

*Ablations.* Deterministic layer only; deterministic layer plus judge; hints and weak hints removed (to isolate check 3); thread disabled (to isolate the multi-turn rule).

## 9. Limitations

- **Coverage depends on the owner's lists.** Check 2 catches verbatim text, salient numbers and listed aliases; check 3 catches listed hints and pairs of weak hints. A paraphrase or cue nobody listed passes the deterministic layer. Generating aliases and hints automatically is future work.
- **The judge is optional and fails open** to the deterministic result when unavailable. It is a second reviewer, not a guarantee.
- **Sentence granularity.** Blocking is per sentence; a long sentence that mixes allowed and private content is removed whole, which costs utility.
- **Self-declared identity.** Role and purpose come from the requester. Without authentication an adversary can claim a role; NTK limits the damage to that role's labels and logs the claim.
- **Output text only.** NTK checks what the agent says, not what it does through tools, files or shared memory.
- **No measured results yet.** See Section 8.

## 10. Conclusion

Access control decides what an agent may know; it does not decide what the agent may say. NTK supplies the missing output-side rules for agent-to-agent conversation: per-fact labels, per-request role and purpose, three checks per reply, a ledger and expiring grants. It is small enough to run before every send and precise enough to test, with two reference implementations bound by one conformance suite. The next step is measurement, under a pre-registered plan.

## References

[1] A. Shah, T. South, et al. *Robust AI Personalization Controls: The Human Context Protocol.* SSRN 5403981, 2025. <https://papers.ssrn.com/sol3/papers.cfm?abstract_id=5403981>

[2] H. Nissenbaum. *Privacy as Contextual Integrity.* Washington Law Review 79(1), 2004.

[3] H. Nissenbaum. *Privacy in Context: Technology, Policy, and the Integrity of Social Life.* Stanford University Press, 2010.

[4] G. Juneja, A. Albalak, W. Hua, W. Y. Wang. *MAGPIE: A dataset for Multi-AGent contextual PrIvacy Evaluation.* arXiv:2506.20737, 2025.

[5] O. Zahn, S. Chana. *Selective Memory for Artificial Intelligence: Write-Time Gating with Hierarchical Archiving.* arXiv:2603.15994, 2026.

[6] O. Zahn, S. Chana. *Facts as First Class Objects: Knowledge Objects for Persistent LLM Memory.* arXiv:2603.17781, 2026.

[7] A. Gomaa, A. Salem, S. Abdelnabi. *ConVerse: Benchmarking Contextual Safety in Agent-to-Agent Conversations.* arXiv:2511.05359, 2025.

[8] F. El Yagoubi, G. Badu-Marfo, R. Al Mallah. *AgentLeak: A Benchmark for Internal-Channel Privacy Leakage in Multi-Agent LLM Systems.* arXiv:2602.11510, 2026.

[9] S. Sharma, A. Hussain, H. H. Arcolezi, U. Aïvodji, S. Gella, A. Romero-Soriano, G. Farnadi. *Loose Lips: Understanding Privacy Leakage in Agentic Dialogue.* arXiv:2610.14071, 2026.
