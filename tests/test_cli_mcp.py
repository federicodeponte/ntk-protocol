import contextlib
import io
import json
import os
import subprocess
import sys
import tempfile
import unittest

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, ROOT)

from ntk import cli  # noqa: E402
from ntk.loaders import fact_from_dict, load_facts_doc  # noqa: E402
from ntk.mcp_server import Server  # noqa: E402

FACTS = os.path.join(ROOT, "examples", "maya_facts.json")
REQUEST = os.path.join(ROOT, "examples", "jun_request.json")


def run_cli(*argv):
    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        code = cli.main(list(argv))
    return code, out.getvalue(), err.getvalue()


class TestLoaders(unittest.TestCase):
    def test_example_json_matches_python_example(self):
        sys.path.insert(0, os.path.join(ROOT, "examples"))
        from maya_jun import maya_facts
        with open(FACTS) as fh:
            facts, policy = load_facts_doc(json.load(fh))
        self.assertEqual([f.id for f in facts], [f.id for f in maya_facts()])
        self.assertEqual(policy.purpose_needs, {"plan a study": ["paper", "methods"]})

    def test_rejects_bad_fact(self):
        with self.assertRaises(ValueError):
            fact_from_dict({"id": "x", "text": "y"})
        with self.assertRaises(ValueError):
            fact_from_dict({"id": "x", "text": "y", "label": "private", "secret": 1})
        with self.assertRaises(ValueError):
            fact_from_dict({"id": "x", "text": "y", "label": "secret"})


class TestCLI(unittest.TestCase):
    def test_leak_is_rewritten_exit_1(self):
        code, out, _ = run_cli("check", "--facts", FACTS, "--request", REQUEST, "--now", "5",
                               "--no-judge", "She already got 0.81 on the new set.")
        self.assertEqual(code, 1)
        d = json.loads(out)
        self.assertFalse(d["allowed"])
        self.assertNotIn("0.81", d["send"])
        self.assertIn("check2", d["reasons"][0])
        self.assertEqual(d["ledger_entry"]["ts"], 5.0)

    def test_allowed_exit_0(self):
        code, out, _ = run_cli("check", "--facts", FACTS, "--request", REQUEST, "--no-judge",
                               "Her code is on the repo.")
        self.assertEqual(code, 0)
        d = json.loads(out)
        self.assertTrue(d["allowed"])
        self.assertEqual(d["ledger_entry"]["disclosed"], {"methods": "role:collaborator"})

    def test_consent_request_and_ledger_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            req = os.path.join(tmp, "req.json")
            led = os.path.join(tmp, "ledger.jsonl")
            with open(req, "w") as fh:
                json.dump({"requester": "rev-agent", "role": "reviewer",
                           "purpose": "review the paper"}, fh)
            code, out, _ = run_cli("check", "--facts", FACTS, "--request", req, "--ledger", led,
                                   "--no-judge", "Here is her code.")
            self.assertEqual(code, 1)
            self.assertEqual(json.loads(out)["consent_requests"][0]["fact_id"], "methods")
            with open(led) as fh:
                self.assertEqual(json.loads(fh.read().strip())["requester"], "rev-agent")

    def test_thread_from_request_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            req = os.path.join(tmp, "req.json")
            with open(req, "w") as fh:
                json.dump({"requester": "jun-agent", "role": "collaborator",
                           "purpose": "plan a study", "thread": ["It improved a lot."]}, fh)
            code, out, _ = run_cli("check", "--facts", FACTS, "--request", req, "--no-judge",
                                   "Results look better.")
        self.assertEqual(code, 1)
        self.assertIn("with thread", json.loads(out)["reasons"][0])

    def test_bad_input_exit_2(self):
        code, _, err = run_cli("check", "--facts", "/nonexistent.json", "--request", REQUEST,
                               "hi")
        self.assertEqual(code, 2)
        self.assertIn("error", json.loads(err))

    def test_module_entrypoint_reads_stdin(self):
        p = subprocess.run([sys.executable, "-m", "ntk", "check", "--facts", FACTS,
                            "--request", REQUEST, "--no-judge"],
                           input="She beat the baseline.", capture_output=True, text=True,
                           cwd=ROOT, env={**os.environ, "NTK_LLM": ""})
        self.assertEqual(p.returncode, 1, p.stderr)
        self.assertEqual(json.loads(p.stdout)["send"],
                         "Anything after publication I can't share yet.")


class TestMCPServer(unittest.TestCase):
    def call(self, server, name, args, mid=3):
        r = server.handle({"jsonrpc": "2.0", "id": mid, "method": "tools/call",
                           "params": {"name": name, "arguments": args}})
        return r["result"]

    def test_initialize_and_list(self):
        s = Server(FACTS, judge=None)
        r = s.handle({"jsonrpc": "2.0", "id": 1, "method": "initialize",
                      "params": {"protocolVersion": "2025-03-26", "capabilities": {},
                                 "clientInfo": {"name": "t", "version": "0"}}})
        self.assertEqual(r["result"]["protocolVersion"], "2025-03-26")
        self.assertEqual(r["result"]["serverInfo"]["name"], "ntk-mcp")
        self.assertIsNone(s.handle({"jsonrpc": "2.0", "method": "notifications/initialized"}))
        tools = s.handle({"jsonrpc": "2.0", "id": 2, "method": "tools/list"})["result"]["tools"]
        self.assertEqual([t["name"] for t in tools], ["check_reply", "get_ledger"])
        self.assertEqual(s.handle({"jsonrpc": "2.0", "id": 9, "method": "nope"})["error"]["code"],
                         -32601)

    def test_check_reply_and_ledger(self):
        s = Server(FACTS, judge=None)
        res = self.call(s, "check_reply", {"draft": "I can send the patient cohort file.",
                                           "requester": "jun-agent", "role": "collaborator",
                                           "purpose": "plan a study"})
        self.assertFalse(res["isError"])
        self.assertFalse(res["structuredContent"]["allowed"])
        self.assertEqual(json.loads(res["content"][0]["text"])["send"], "I can't share that.")
        led = self.call(s, "get_ledger", {"requester": "jun-agent"})["structuredContent"]
        self.assertEqual(len(led["entries"]), 1)

    def test_inline_facts_and_errors(self):
        s = Server(None, judge=None)
        res = self.call(s, "check_reply", {"draft": "x", "requester": "a", "role": "b",
                                           "purpose": "c"})
        self.assertTrue(res["isError"])
        res = self.call(s, "check_reply", {
            "draft": "The code word is bluebird.", "requester": "a", "role": "b", "purpose": "c",
            "facts": [{"id": "cw", "text": "bluebird", "label": "private"}]})
        self.assertFalse(res["structuredContent"]["allowed"])

    def test_stdio_subprocess_roundtrip(self):
        msgs = [
            {"jsonrpc": "2.0", "id": 1, "method": "initialize",
             "params": {"protocolVersion": "2025-06-18", "capabilities": {},
                        "clientInfo": {"name": "t", "version": "0"}}},
            {"jsonrpc": "2.0", "method": "notifications/initialized"},
            {"jsonrpc": "2.0", "id": 2, "method": "tools/call",
             "params": {"name": "check_reply", "arguments": {
                 "draft": "She beat the baseline.", "requester": "jun-agent",
                 "role": "collaborator", "purpose": "plan a study"}}},
        ]
        env = {**os.environ, "NTK_FACTS": FACTS, "NTK_LLM": ""}
        p = subprocess.run([sys.executable, "-m", "ntk.mcp_server"], cwd=ROOT, env=env,
                           input="\n".join(json.dumps(m) for m in msgs) + "\n",
                           capture_output=True, text=True, timeout=30)
        lines = [json.loads(l) for l in p.stdout.splitlines()]
        self.assertEqual([l["id"] for l in lines], [1, 2])
        out = lines[1]["result"]["structuredContent"]
        self.assertFalse(out["allowed"])
        self.assertIn("check3", out["reasons"][0])


if __name__ == "__main__":
    unittest.main()
