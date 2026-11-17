"""JSON in, JSON out: load facts, requests and policies; serialise decisions.

Shared by the `ntk` CLI and the `ntk-mcp` server.

facts file: either a list of fact objects, or {"facts": [...], "policy": {...}}.
  fact:   {"id", "text", "label", "aliases"?, "hints"?, "weak_hints"?,
           "safe_say"?, "topics"?, "owner"?}
  policy: {"purpose_needs": {purpose: [topic, ...]}, "grants"?: [
           {"fact_id", "requester", "purpose", "expires_at"}]}
request file: {"requester", "role", "purpose", "thread"?: [str, ...]}
"""

from __future__ import annotations

import json
from dataclasses import asdict
from typing import Any, Optional

from .core import Decision, Fact, Grant, LedgerEntry, Policy, Request

_FACT_KEYS = ("id", "text", "label", "aliases", "hints", "weak_hints", "safe_say",
              "topics", "owner")


def fact_from_dict(d: dict) -> Fact:
    missing = [k for k in ("id", "text", "label") if k not in d]
    if missing:
        raise ValueError(f"fact is missing {', '.join(missing)}: {d!r}")
    unknown = set(d) - set(_FACT_KEYS)
    if unknown:
        raise ValueError(f"fact {d.get('id')!r} has unknown keys: {sorted(unknown)}")
    kw = dict(d)
    for k in ("aliases", "hints", "weak_hints", "topics"):
        if k in kw:
            kw[k] = list(kw[k])
    return Fact(**kw)


def policy_from_dict(d: Optional[dict]) -> Policy:
    d = d or {}
    p = Policy(purpose_needs=dict(d.get("purpose_needs", {})))
    if "grant_ttl" in d:
        p.grant_ttl = float(d["grant_ttl"])
    for g in d.get("grants", []):
        p.grants.append(Grant(g["fact_id"], g["requester"], g["purpose"],
                              float(g["expires_at"]), bool(g.get("revoked", False))))
    return p


def load_facts_doc(doc: Any) -> tuple[list[Fact], Policy]:
    """Accept a list of facts or {"facts": [...], "policy": {...}}."""
    if isinstance(doc, list):
        return [fact_from_dict(f) for f in doc], Policy()
    if isinstance(doc, dict) and "facts" in doc:
        return [fact_from_dict(f) for f in doc["facts"]], policy_from_dict(doc.get("policy"))
    raise ValueError("facts must be a list or an object with a 'facts' key")


def request_from_dict(d: dict) -> tuple[Request, list]:
    missing = [k for k in ("requester", "role", "purpose") if k not in d]
    if missing:
        raise ValueError(f"request is missing {', '.join(missing)}")
    return Request(d["requester"], d["role"], d["purpose"]), list(d.get("thread", []))


def read_json(path: str) -> Any:
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


def decision_to_dict(d: Decision, entry: Optional[LedgerEntry] = None) -> dict:
    out = {
        "allowed": d.allowed,
        "send": d.rewritten,
        "reasons": list(d.reasons),
        "consent_requests": [asdict(c) for c in d.consent_requests],
    }
    if entry is not None:
        out["ledger_entry"] = asdict(entry)
    return out
