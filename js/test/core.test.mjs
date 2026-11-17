// Mirrors tests/test_ntk.py.
import { test, describe } from "node:test";
import assert from "node:assert/strict";
import { CANT_SHARE, Label, Ledger, checkReply, claudeJudge, defaultJudge } from "../dist/index.js";
import { judgeEnv } from "../dist/judge.js";
import { mayaFacts, mayaPolicy } from "./helpers.mjs";

const JUN = { requester: "jun-agent", role: "collaborator", purpose: "plan a study" };
const STRANGER = { requester: "x-agent", role: "stranger", purpose: "plan a study" };

function run(draft, { req = JUN, thread = [], policy, ledger, now = 1000 } = {}) {
  return checkReply(draft, mayaFacts(), req, { thread, policy: policy ?? mayaPolicy(), ledger, now, judge: null });
}

describe("labels", () => {
  test("parse and visibility", () => {
    assert.ok(Label.parse("public").visibleTo("anyone"));
    const r = Label.parse("role:collaborator");
    assert.ok(r.visibleTo("collaborator"));
    assert.ok(!r.visibleTo("reviewer"));
    assert.ok(!Label.parse("private").visibleTo("collaborator"));
    assert.equal(String(r), "role:collaborator");
    assert.throws(() => Label.parse("secret"));
    assert.throws(() => Label.parse("role:"));
  });
});

describe("check 1: who is asking", () => {
  test("public ok for anyone", () => assert.ok(run("Read the published paper.", { req: STRANGER }).allowed));
  test("role label ok for role", () => assert.ok(run("Her code is on the repo.").allowed));
  test("role label becomes consent for other role", () => {
    const d = run("Her code is on the repo.", { req: STRANGER });
    assert.ok(!d.allowed);
    assert.equal(d.rewritten, CANT_SHARE);
    assert.equal(d.consent_requests[0].fact_id, "methods");
    assert.equal(d.consent_requests[0].owner, "maya");
  });
  test("purpose minimisation", () => {
    const req = { ...JUN, purpose: "write a grant" };
    assert.ok(run("Her code is on the repo.", { req }).allowed);
    const p = mayaPolicy();
    p.purpose_needs["write a grant"] = ["paper"];
    const d = run("Her code is on the repo.", { req, policy: p });
    assert.ok(!d.allowed);
    assert.match(d.consent_requests[0].reason, /does not need it/);
  });
  test("grant allows, then expires and revokes", () => {
    const p = mayaPolicy();
    const c = run("Here is her code.", { req: STRANGER, policy: p }).consent_requests[0];
    p.grant(c, 1000, 60);
    assert.ok(run("Here is her code.", { req: STRANGER, policy: p, now: 1030 }).allowed);
    assert.ok(!run("Here is her code.", { req: STRANGER, policy: p, now: 1061 }).allowed);
    p.grant(c, 2000, 60);
    p.revoke("methods", STRANGER.requester);
    assert.ok(!run("Here is her code.", { req: STRANGER, policy: p, now: 2001 }).allowed);
  });
  test("grant never unlocks private", () => {
    const p = mayaPolicy();
    p.grant({ fact_id: "result_081", owner: "maya", requester: "jun-agent", role: "collaborator",
      purpose: "plan a study", reason: "x" }, 0, 1e9);
    assert.ok(!run("She got 0.81.", { policy: p }).allowed);
  });
});

describe("check 2: use it, don't say it", () => {
  test("number", () => {
    const d = run("She already got 0.81 on the new set.");
    assert.ok(!d.allowed);
    assert.ok(!d.rewritten.includes("0.81"));
    assert.match(d.reasons[0], /check2/);
  });
  test("number boundaries", () => {
    assert.ok(run("Plan for 81 participants over 18 weeks.").allowed);
    assert.ok(!run("We saw 0.81, roughly.").allowed);
  });
  test("paraphrase alias", () => {
    const d = run("I can send the patient cohort file.");
    assert.ok(!d.allowed);
    assert.equal(d.rewritten, CANT_SHARE);
  });
  test("case-insensitive verbatim", () => assert.ok(!run("There is an UNPUBLISHED RESULT.").allowed));
  test("only the leaky sentence is removed", () => {
    const d = run("The published paper is the baseline. She got 0.81 on the new set.");
    assert.ok(!d.allowed);
    assert.ok(d.rewritten.includes("published paper is the baseline"));
    assert.ok(!d.rewritten.includes("0.81"));
  });
});

describe("check 3: hints", () => {
  test("strong hint alone", () => {
    const d = run("She beat the baseline.");
    assert.ok(!d.allowed);
    assert.match(d.reasons[0], /check3/);
    assert.equal(d.rewritten, "Anything after publication I can't share yet.");
  });
  test("weak hint alone is fine", () => assert.ok(run("A better plan is to start small.").allowed));
  test("weak hints combine with thread", () => {
    const d = run("Results look better on the new data.", { thread: ["Things have improved a lot for her."] });
    assert.ok(!d.allowed);
    assert.match(d.reasons[0], /with thread/);
  });
  test("thread objects accepted", () => {
    assert.ok(!run("Results look better.", { thread: [{ text: "it improved" }] }).allowed);
  });
});

describe("ledger", () => {
  test("every reply logged with labels", () => {
    const led = new Ledger();
    run("Her methods and code are on the repo. Read the published paper.", { ledger: led });
    run("She got 0.81.", { ledger: led, now: 2000 });
    assert.equal(led.entries.length, 2);
    const [e0, e1] = led.entries;
    assert.deepEqual(e0.disclosed, { methods: "role:collaborator", paper: "public" });
    assert.ok(e0.allowed_as_drafted);
    assert.ok(!e1.allowed_as_drafted);
    assert.ok(!e1.said.includes("0.81"));
    assert.deepEqual(led.disclosedTo("jun-agent"), new Set(["methods", "paper"]));
    const rows = led.toJsonl().split("\n").map((l) => JSON.parse(l));
    assert.equal(rows[1].ts, 2000);
    assert.ok(led.toJsonl().startsWith('{"allowed_as_drafted": true, "blocked": []'));
  });
});

describe("LLM judge", () => {
  test("off by default", () => {
    const saved = process.env.NTK_LLM;
    delete process.env.NTK_LLM;
    try {
      assert.equal(defaultJudge(), null);
      assert.ok(checkReply("Hello.", mayaFacts(), JUN, { policy: mayaPolicy() }).allowed);
    } finally {
      if (saved !== undefined) process.env.NTK_LLM = saved;
    }
  });
  test("on only with env", () => {
    const saved = process.env.NTK_LLM;
    process.env.NTK_LLM = "claude";
    try { assert.equal(defaultJudge(), claudeJudge); } finally {
      if (saved === undefined) delete process.env.NTK_LLM; else process.env.NTK_LLM = saved;
    }
  });
  test("judge verdict declines", () => {
    const d = checkReply("Hello.", mayaFacts(), JUN,
      { policy: mayaPolicy(), now: 0, judge: () => "'result_081' implies a new result" });
    assert.ok(!d.allowed);
    assert.equal(d.rewritten, CANT_SHARE);
  });
  test("judge child env strips API keys", () => {
    const env = judgeEnv({ ANTHROPIC_API_KEY: "k", ANTHROPIC_AUTH_TOKEN: "t", CLAUDE_API_KEY: "c", PATH: "/bin" });
    assert.deepEqual(env, { PATH: "/bin" });
  });
});
