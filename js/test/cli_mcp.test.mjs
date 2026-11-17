// Mirrors tests/test_cli_mcp.py.
import { test, describe } from "node:test";
import assert from "node:assert/strict";
import { spawnSync } from "node:child_process";
import { mkdtempSync, readFileSync, writeFileSync, rmSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { factFromDict, loadFactsDoc, Server } from "../dist/index.js";
import { CLI, FACTS, REQUEST, readJson } from "./helpers.mjs";

const ENV = { ...process.env, NTK_LLM: "" };
const cli = (args, input) => spawnSync(process.execPath, [CLI, ...args], { input, encoding: "utf8", env: ENV });

describe("loaders", () => {
  test("example JSON loads with policy", () => {
    const [facts, policy] = loadFactsDoc(readJson(FACTS));
    assert.deepEqual(facts.map((f) => f.id), ["paper", "methods", "result_081", "cohort"]);
    assert.deepEqual(policy.purpose_needs, { "plan a study": ["paper", "methods"] });
  });
  test("rejects bad facts", () => {
    assert.throws(() => factFromDict({ id: "x", text: "y" }));
    assert.throws(() => factFromDict({ id: "x", text: "y", label: "private", secret: 1 }));
    assert.throws(() => factFromDict({ id: "x", text: "y", label: "secret" }));
  });
});

describe("CLI", () => {
  test("leak is rewritten, exit 1", () => {
    const p = cli(["check", "--facts", FACTS, "--request", REQUEST, "--now", "5", "--no-judge",
      "She already got 0.81 on the new set."]);
    assert.equal(p.status, 1);
    const d = JSON.parse(p.stdout);
    assert.equal(d.allowed, false);
    assert.ok(!d.send.includes("0.81"));
    assert.match(d.reasons[0], /check2/);
    assert.equal(d.ledger_entry.ts, 5);
  });
  test("allowed, exit 0", () => {
    const p = cli(["check", "--facts", FACTS, "--request", REQUEST, "--no-judge", "Her code is on the repo."]);
    assert.equal(p.status, 0);
    assert.deepEqual(JSON.parse(p.stdout).ledger_entry.disclosed, { methods: "role:collaborator" });
  });
  test("consent request and ledger file", () => {
    const tmp = mkdtempSync(join(tmpdir(), "ntk-"));
    try {
      const req = join(tmp, "req.json"), led = join(tmp, "ledger.jsonl");
      writeFileSync(req, JSON.stringify({ requester: "rev-agent", role: "reviewer", purpose: "review the paper" }));
      const p = cli(["check", "--facts", FACTS, "--request", req, "--ledger", led, "--no-judge", "Here is her code."]);
      assert.equal(p.status, 1);
      assert.equal(JSON.parse(p.stdout).consent_requests[0].fact_id, "methods");
      assert.equal(JSON.parse(readFileSync(led, "utf8").trim()).requester, "rev-agent");
    } finally { rmSync(tmp, { recursive: true, force: true }); }
  });
  test("thread from request file", () => {
    const tmp = mkdtempSync(join(tmpdir(), "ntk-"));
    try {
      const req = join(tmp, "req.json");
      writeFileSync(req, JSON.stringify({ requester: "jun-agent", role: "collaborator",
        purpose: "plan a study", thread: ["It improved a lot."] }));
      const p = cli(["check", "--facts", FACTS, "--request", req, "--no-judge", "Results look better."]);
      assert.equal(p.status, 1);
      assert.match(JSON.parse(p.stdout).reasons[0], /with thread/);
    } finally { rmSync(tmp, { recursive: true, force: true }); }
  });
  test("bad input, exit 2", () => {
    const p = cli(["check", "--facts", "/nonexistent.json", "--request", REQUEST, "hi"]);
    assert.equal(p.status, 2);
    assert.ok("error" in JSON.parse(p.stderr));
    assert.equal(cli(["check", "--request", REQUEST, "hi"]).status, 2);
    assert.equal(cli(["nope"]).status, 2);
  });
  test("reads the draft from stdin", () => {
    const p = cli(["check", "--facts", FACTS, "--request", REQUEST, "--no-judge"], "She beat the baseline.");
    assert.equal(p.status, 1, p.stderr);
    assert.equal(JSON.parse(p.stdout).send, "Anything after publication I can't share yet.");
  });
  test("version", () => assert.match(cli(["--version"]).stdout, /^ntk \d+\.\d+\.\d+/));
});

describe("MCP server", () => {
  const call = (s, name, args, id = 3) =>
    s.handle({ jsonrpc: "2.0", id, method: "tools/call", params: { name, arguments: args } }).result;

  test("initialize and list", () => {
    const s = new Server(FACTS, null, null);
    const r = s.handle({ jsonrpc: "2.0", id: 1, method: "initialize",
      params: { protocolVersion: "2025-03-26", capabilities: {}, clientInfo: { name: "t", version: "0" } } });
    assert.equal(r.result.protocolVersion, "2025-03-26");
    assert.equal(r.result.serverInfo.name, "ntk-mcp");
    assert.equal(s.handle({ jsonrpc: "2.0", method: "notifications/initialized" }), null);
    const tools = s.handle({ jsonrpc: "2.0", id: 2, method: "tools/list" }).result.tools;
    assert.deepEqual(tools.map((t) => t.name), ["check_reply", "get_ledger"]);
    assert.equal(s.handle({ jsonrpc: "2.0", id: 9, method: "nope" }).error.code, -32601);
  });
  test("check_reply and ledger", () => {
    const s = new Server(FACTS, null, null);
    const res = call(s, "check_reply", { draft: "I can send the patient cohort file.",
      requester: "jun-agent", role: "collaborator", purpose: "plan a study" });
    assert.equal(res.isError, false);
    assert.equal(res.structuredContent.allowed, false);
    assert.equal(JSON.parse(res.content[0].text).send, "I can't share that.");
    assert.equal(call(s, "get_ledger", { requester: "jun-agent" }).structuredContent.entries.length, 1);
  });
  test("inline facts and errors", () => {
    const s = new Server(null, null, null);
    assert.equal(call(s, "check_reply", { draft: "x", requester: "a", role: "b", purpose: "c" }).isError, true);
    const res = call(s, "check_reply", { draft: "The code word is bluebird.", requester: "a", role: "b",
      purpose: "c", facts: [{ id: "cw", text: "bluebird", label: "private" }] });
    assert.equal(res.structuredContent.allowed, false);
  });
  test("stdio subprocess roundtrip via `ntk-protocol mcp`", () => {
    const msgs = [
      { jsonrpc: "2.0", id: 1, method: "initialize", params: { protocolVersion: "2025-06-18",
        capabilities: {}, clientInfo: { name: "t", version: "0" } } },
      { jsonrpc: "2.0", method: "notifications/initialized" },
      { jsonrpc: "2.0", id: 2, method: "tools/call", params: { name: "check_reply", arguments: {
        draft: "She beat the baseline.", requester: "jun-agent", role: "collaborator", purpose: "plan a study" } } },
    ];
    const p = spawnSync(process.execPath, [CLI, "mcp"], { encoding: "utf8", timeout: 30000,
      env: { ...ENV, NTK_FACTS: FACTS }, input: msgs.map((m) => JSON.stringify(m)).join("\n") + "\n" });
    const lines = p.stdout.trim().split("\n").map((l) => JSON.parse(l));
    assert.deepEqual(lines.map((l) => l.id), [1, 2]);
    const out = lines[1].result.structuredContent;
    assert.equal(out.allowed, false);
    assert.match(out.reasons[0], /check3/);
  });
});
