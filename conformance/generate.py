"""Regenerate the `expect` blocks in conformance/cases.json from the Python reference.

    python3 conformance/generate.py          # rewrite expectations
    python3 conformance/generate.py --check  # exit 1 if any expectation is stale

Both test suites (tests/test_conformance.py and js/test/conformance.test.mjs) assert
every case against the frozen `expect` block, so the Python and TypeScript
implementations cannot drift apart. Review the diff before committing.
"""

import json
import os
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, ROOT)

from ntk import Ledger, Request, check_reply  # noqa: E402
from ntk.loaders import load_facts_doc, policy_from_dict, read_json  # noqa: E402

CASES = os.path.join(ROOT, "conformance", "cases.json")


def run_case(case):
    facts_doc = case["facts"]
    if isinstance(facts_doc, str):
        facts_doc = read_json(os.path.join(ROOT, facts_doc))
    facts, policy = load_facts_doc(facts_doc)
    if "policy" in case:
        policy = policy_from_dict(case["policy"])
    r = case["request"]
    ledger = Ledger()
    d = check_reply(case["draft"], facts, Request(r["requester"], r["role"], r["purpose"]),
                    case.get("thread", []), policy, ledger, now=case.get("now", 1000.0),
                    judge=None)
    return {"allowed": d.allowed, "send": d.rewritten, "reasons": d.reasons,
            "consent_fact_ids": [c.fact_id for c in d.consent_requests],
            "disclosed": ledger.entries[0].disclosed}


def main():
    with open(CASES, encoding="utf-8") as fh:
        doc = json.load(fh)
    stale = 0
    for case in doc["cases"]:
        got = run_case(case)
        if case.get("expect") != got:
            stale += 1
            case["expect"] = got
    if "--check" in sys.argv:
        print(f"{stale} stale case(s)")
        return 1 if stale else 0
    with open(CASES, "w", encoding="utf-8") as fh:
        json.dump(doc, fh, indent=2, ensure_ascii=False)
        fh.write("\n")
    print(f"{len(doc['cases'])} cases, {stale} updated")
    return 0


if __name__ == "__main__":
    sys.exit(main())
