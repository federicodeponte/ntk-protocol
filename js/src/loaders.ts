/**
 * JSON in, JSON out: load facts, requests and policies; serialise decisions.
 * Same wire format as ntk/loaders.py (see SPEC.md, "Wire format").
 */

import { Decision, Fact, Grant, LedgerEntry, Policy, Request } from "./core.js";

const FACT_KEYS = ["id", "text", "label", "aliases", "hints", "weak_hints", "safe_say",
  "topics", "owner"];

function isObj(x: unknown): x is Record<string, unknown> {
  return x !== null && typeof x === "object" && !Array.isArray(x);
}

export function factFromDict(d: unknown): Fact {
  if (!isObj(d)) throw new TypeError(`fact must be an object: ${JSON.stringify(d)}`);
  const missing = ["id", "text", "label"].filter((k) => !(k in d));
  if (missing.length) throw new Error(`fact is missing ${missing.join(", ")}: ${JSON.stringify(d)}`);
  const unknown = Object.keys(d).filter((k) => !FACT_KEYS.includes(k)).sort();
  if (unknown.length) {
    throw new Error(`fact '${String(d.id)}' has unknown keys: ${JSON.stringify(unknown)}`);
  }
  for (const k of ["aliases", "hints", "weak_hints", "topics"]) {
    if (k in d && !Array.isArray(d[k])) throw new TypeError(`fact '${String(d.id)}': ${k} must be a list`);
  }
  return new Fact(d as never);
}

export function policyFromDict(d: unknown): Policy {
  const o = isObj(d) ? d : {};
  const p = new Policy({ purpose_needs: (o.purpose_needs ?? {}) as Record<string, string[]> });
  if ("grant_ttl" in o) p.grant_ttl = Number(o.grant_ttl);
  for (const g of (o.grants ?? []) as Record<string, unknown>[]) {
    for (const k of ["fact_id", "requester", "purpose", "expires_at"]) {
      if (!(k in g)) throw new Error(`grant is missing '${k}'`);
    }
    p.grants.push(new Grant(String(g.fact_id), String(g.requester), String(g.purpose),
      Number(g.expires_at), Boolean(g.revoked ?? false)));
  }
  return p;
}

/** Accept a list of facts or {"facts": [...], "policy": {...}}. */
export function loadFactsDoc(doc: unknown): [Fact[], Policy] {
  if (Array.isArray(doc)) return [doc.map(factFromDict), new Policy()];
  if (isObj(doc) && "facts" in doc && Array.isArray(doc.facts)) {
    return [doc.facts.map(factFromDict), policyFromDict(doc.policy)];
  }
  throw new Error("facts must be a list or an object with a 'facts' key");
}

export function requestFromDict(d: unknown): [Request, string[]] {
  if (!isObj(d)) throw new TypeError("request must be an object");
  const missing = ["requester", "role", "purpose"].filter((k) => !(k in d));
  if (missing.length) throw new Error(`request is missing ${missing.join(", ")}`);
  const thread = (d.thread ?? []) as unknown[];
  return [{ requester: String(d.requester), role: String(d.role), purpose: String(d.purpose) },
    thread.map((m) => (typeof m === "string" ? m : JSON.stringify(m)))];
}

export interface DecisionDict {
  allowed: boolean;
  send: string;
  reasons: string[];
  consent_requests: Decision["consent_requests"];
  ledger_entry?: LedgerEntry;
}

export function decisionToDict(d: Decision, entry?: LedgerEntry): DecisionDict {
  const out: DecisionDict = {
    allowed: d.allowed,
    send: d.rewritten,
    reasons: [...d.reasons],
    consent_requests: d.consent_requests.map((c) => ({ fact_id: c.fact_id, owner: c.owner,
      requester: c.requester, role: c.role, purpose: c.purpose, reason: c.reason })),
  };
  if (entry !== undefined) out.ledger_entry = { ...entry };
  return out;
}
