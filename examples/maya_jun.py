"""Maya's agent answers Jun's agent under Need-to-Know.

Run:  python3 examples/maya_jun.py
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from ntk import CANT_SHARE, Fact, Ledger, Policy, Request, check_reply  # noqa: E402


def maya_facts():
    return [
        Fact("paper", "published paper", "public", owner="maya",
             aliases=["her paper", "the paper"], topics=["paper"]),
        Fact("methods", "methods and code", "role:collaborator", owner="maya",
             aliases=["her methods", "her code", "the code", "repo"], topics=["methods"]),
        Fact("result_081", "unpublished result 0.81", "private", owner="maya",
             aliases=["unpublished result", "new result"],
             hints=["beat the baseline", "beats the baseline", "outperform", "state of the art"],
             weak_hints=["better", "improved", "since the paper"],
             safe_say="Anything after publication I can't share yet."),
        Fact("cohort", "patient cohort data, IRB restricted", "private", owner="maya",
             aliases=["patient cohort", "cohort file", "patient data", "cohort data"],
             hints=["irb", "patient records"],
             safe_say=CANT_SHARE),
    ]


def maya_policy():
    return Policy(purpose_needs={"plan a study": ["paper", "methods"]})


def show(title, draft, d):
    print(f"\n--- {title}")
    print(f"draft:    {draft}")
    print(f"allowed:  {d.allowed}")
    print(f"sent:     {d.rewritten}")
    for r in d.reasons:
        print(f"reason:   {r}")
    for c in d.consent_requests:
        print(f"consent:  {c}")


def main():
    facts, policy, ledger = maya_facts(), maya_policy(), Ledger()
    jun = Request(requester="jun-agent", role="collaborator", purpose="plan a study")
    thread = []
    clock = iter(range(1_700_000_000, 1_700_000_100, 10))

    drafts = [
        ("leak 1: private number", "She already got 0.81 on the new set."),
        ("leak 2: restricted data", "I can send the patient cohort file."),
        ("leak 3: inference hint", "She beat the baseline."),
        ("allowed", "Her methods and code are on the shared repo, and the published paper "
                    "is the baseline to build on. I'd start the study on the new dataset."),
    ]
    for title, draft in drafts:
        d = check_reply(draft, facts, jun, thread, policy, ledger, now=next(clock))
        show(title, draft, d)
        thread.append(d.rewritten)

    # Check 1 + consent: a reviewer asks for the code. Not the agent's call.
    rev = Request(requester="rev-agent", role="reviewer", purpose="review the paper")
    draft = "Here is her code."
    d = check_reply(draft, facts, rev, [], policy, ledger, now=next(clock))
    show("check 1: reviewer asks for code", draft, d)
    t = next(clock)
    policy.grant(d.consent_requests[0], now=t, ttl=3600)  # Maya taps "allow" for 1 hour
    d = check_reply(draft, facts, rev, [], policy, ledger, now=t + 60)
    show("after Maya's one-tap grant", draft, d)
    d = check_reply(draft, facts, rev, [], policy, ledger, now=t + 7200)
    show("two hours later: grant expired", draft, d)

    print("\n--- ledger")
    print(ledger.to_jsonl())


if __name__ == "__main__":
    main()
