# Need-to-Know (NTK)

**HCP decides what your agent can know. NTK decides what it can say.**

NTK is the output-side layer for agent-to-agent conversations. Every fact an agent knows carries a label (`public`, `role:<name>`, `private`), every inbound request carries `{requester, role, purpose}`, and every reply passes three checks before it is sent:

1. **Who's asking.** Role and purpose decide which labels may be shared. Anything beyond that becomes a consent request to the owner.
2. **Use, don't say.** Private facts may steer the plan but never appear in the reply, verbatim or paraphrased.
3. **Hint check.** If the requester could infer a private fact from the reply, alone or with the thread so far, the reply is rewritten or declined.

Every reply goes to a disclosure ledger, and consent grants expire.

Spec: [SPEC.md](SPEC.md). Deck: https://federicodeponte.github.io/need-to-know/

## Quickstart

```bash
git clone https://github.com/federicodeponte/ntk-protocol && cd ntk-protocol
python3 examples/maya_jun.py                 # Maya's agent answers Jun's agent
python3 -m unittest discover -s tests -v     # 22 tests, stdlib only
NTK_LLM=claude python3 examples/maya_jun.py  # optional: add the local `claude -p` judge
python3 -c "import ntk; print(ntk.__version__)"
```

## Flow

```
Jun's agent ──request{role:collaborator, purpose:plan study}──▶ Maya's agent
                                                                 │ 1. role + purpose → allowed labels
                                                                 │ 2. plan with everything, say only allowed
                                                                 │ 3. inference check
Jun's agent ◀──reply (+ ledger entry)────────────────────────────┘
```

## Use it

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

## How the checks work

- **Check 1 and the ledger are deterministic.** `Policy` maps purposes to the topics they need; a fact outside the role's labels or the purpose's needs yields a `ConsentRequest`. `Policy.grant()` creates a grant for one requester and one purpose with a TTL; `revoke()` ends it. Private facts are never unlocked by a grant.
- **Checks 2 and 3 run a deterministic layer first:** verbatim text, numbers, `aliases` (paraphrases that count as saying the fact), `hints` (cues that leak it alone) and `weak_hints` (cues that leak when two meet across the draft and the thread). Leaky sentences are replaced with the fact's `safe_say` or dropped; an empty result becomes "I can't share that."
- **Optional LLM judge.** With `NTK_LLM=claude`, the final reply is also reviewed by the local `claude -p` CLI on your Claude login. API-key variables are stripped from its environment; no pay-per-use API is ever called. Tests never call it.

Standard library only. Python 3.9+.

Built on the Human Context Protocol (HCP) paper (SSRN), sections 3.1 to 3.2.
