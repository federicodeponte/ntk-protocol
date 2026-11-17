// Cross-implementation conformance: the same cases run in tests/test_conformance.py.
import { test } from "node:test";
import assert from "node:assert/strict";
import { join } from "node:path";
import { Ledger, checkReply, loadFactsDoc, policyFromDict } from "../dist/index.js";
import { ROOT, readJson } from "./helpers.mjs";

const { cases } = readJson(join(ROOT, "conformance", "cases.json"));

test("conformance file has cases", () => assert.ok(cases.length >= 20));

for (const c of cases) {
  test(c.name, () => {
    const doc = typeof c.facts === "string" ? readJson(join(ROOT, c.facts)) : c.facts;
    let [facts, policy] = loadFactsDoc(doc);
    if ("policy" in c) policy = policyFromDict(c.policy);
    const ledger = new Ledger();
    const d = checkReply(c.draft, facts, c.request,
      { thread: c.thread ?? [], policy, ledger, now: c.now ?? 1000, judge: null });
    assert.deepEqual({ allowed: d.allowed, send: d.rewritten, reasons: d.reasons,
      consent_fact_ids: d.consent_requests.map((x) => x.fact_id), disclosed: ledger.entries[0].disclosed },
    c.expect);
  });
}
