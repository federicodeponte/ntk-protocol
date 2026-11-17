"""`ntk` command line.

    ntk check --facts facts.json --request request.json "draft reply"
    echo "draft reply" | ntk check --facts facts.json --request request.json

Prints the decision as JSON. Exit code 0 = send the draft unchanged,
1 = send the rewritten text in "send" instead, 2 = bad input.
"""

from __future__ import annotations

import argparse
import json
import sys
from typing import Optional, Sequence

from . import __version__
from .core import Ledger, check_reply
from .loaders import decision_to_dict, load_facts_doc, read_json, request_from_dict


def _parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="ntk", description="Need-to-Know: check what an agent may say to another agent.")
    p.add_argument("--version", action="version", version=f"ntk {__version__}")
    sub = p.add_subparsers(dest="cmd", required=True)
    c = sub.add_parser("check", help="run the three checks on one draft reply")
    c.add_argument("--facts", required=True, help="facts JSON (list, or {facts, policy})")
    c.add_argument("--request", required=True,
                   help="request JSON {requester, role, purpose, thread?}")
    c.add_argument("--policy", help="policy JSON; overrides a policy inside --facts")
    c.add_argument("--ledger", help="append the ledger entry to this JSONL file")
    c.add_argument("--now", type=float, help="clock override (unix seconds), for tests")
    c.add_argument("--no-judge", action="store_true",
                   help="skip the optional LLM judge even if NTK_LLM=claude")
    c.add_argument("draft", nargs="?", help="draft reply; read from stdin when omitted")
    return p


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = _parser().parse_args(argv)
    try:
        facts, policy = load_facts_doc(read_json(args.facts))
        if args.policy:
            from .loaders import policy_from_dict
            policy = policy_from_dict(read_json(args.policy))
        request, thread = request_from_dict(read_json(args.request))
    except (OSError, ValueError, KeyError, TypeError) as e:
        print(json.dumps({"error": str(e)}), file=sys.stderr)
        return 2
    draft = args.draft if args.draft is not None else sys.stdin.read()
    if not draft.strip():
        print(json.dumps({"error": "empty draft"}), file=sys.stderr)
        return 2
    ledger = Ledger()
    d = check_reply(draft, facts, request, thread, policy, ledger, now=args.now,
                    judge=None if args.no_judge else "auto")
    entry = ledger.entries[-1]
    if args.ledger:
        with open(args.ledger, "a", encoding="utf-8") as fh:
            fh.write(ledger.to_jsonl() + "\n")
    print(json.dumps(decision_to_dict(d, entry), indent=2, ensure_ascii=False))
    return 0 if d.allowed else 1


if __name__ == "__main__":
    sys.exit(main())
