import json
import os
import sys
import unittest
from unittest import mock

ROOT = os.path.join(os.path.dirname(__file__), "..")
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "examples"))

from ntk import CANT_SHARE, Label, Ledger, Request, check_reply  # noqa: E402
from ntk import judge as judge_mod  # noqa: E402
from maya_jun import maya_facts, maya_policy  # noqa: E402

JUN = Request("jun-agent", "collaborator", "plan a study")
STRANGER = Request("x-agent", "stranger", "plan a study")


def run(draft, req=JUN, thread=(), policy=None, ledger=None, now=1000.0):
    return check_reply(draft, maya_facts(), req, list(thread), policy or maya_policy(),
                       ledger, now=now, judge=None)


class TestLabels(unittest.TestCase):
    def test_parse_and_visibility(self):
        self.assertTrue(Label.parse("public").visible_to("anyone"))
        r = Label.parse("role:collaborator")
        self.assertTrue(r.visible_to("collaborator"))
        self.assertFalse(r.visible_to("reviewer"))
        self.assertFalse(Label.parse("private").visible_to("collaborator"))
        self.assertEqual(str(r), "role:collaborator")
        with self.assertRaises(ValueError):
            Label.parse("secret")


class TestCheck1WhoIsAsking(unittest.TestCase):
    def test_public_ok_for_anyone(self):
        self.assertTrue(run("Read the published paper.", STRANGER).allowed)

    def test_role_label_ok_for_role(self):
        self.assertTrue(run("Her code is on the repo.").allowed)

    def test_role_label_becomes_consent_for_other_role(self):
        d = run("Her code is on the repo.", STRANGER)
        self.assertFalse(d.allowed)
        self.assertEqual(d.rewritten, CANT_SHARE)
        self.assertEqual(d.consent_requests[0].fact_id, "methods")
        self.assertEqual(d.consent_requests[0].owner, "maya")

    def test_purpose_minimisation(self):
        d = run("Her code is on the repo.", Request("jun-agent", "collaborator", "write a grant"),
                policy=maya_policy())
        self.assertTrue(d.allowed)  # purpose not listed: not minimised
        p = maya_policy()
        p.purpose_needs["write a grant"] = ["paper"]
        d = run("Her code is on the repo.", Request("jun-agent", "collaborator", "write a grant"),
                policy=p)
        self.assertFalse(d.allowed)
        self.assertIn("does not need it", d.consent_requests[0].reason)

    def test_grant_allows_then_expires_and_revokes(self):
        p = maya_policy()
        c = run("Here is her code.", STRANGER, policy=p).consent_requests[0]
        p.grant(c, now=1000.0, ttl=60)
        self.assertTrue(run("Here is her code.", STRANGER, policy=p, now=1030.0).allowed)
        self.assertFalse(run("Here is her code.", STRANGER, policy=p, now=1061.0).allowed)
        p.grant(c, now=2000.0, ttl=60)
        p.revoke("methods", STRANGER.requester)
        self.assertFalse(run("Here is her code.", STRANGER, policy=p, now=2001.0).allowed)

    def test_grant_never_unlocks_private(self):
        p = maya_policy()
        from ntk import ConsentRequest
        p.grant(ConsentRequest("result_081", "maya", "jun-agent", "collaborator",
                               "plan a study", "x"), now=0, ttl=1e9)
        self.assertFalse(run("She got 0.81.", policy=p).allowed)


class TestCheck2UseDontSay(unittest.TestCase):
    def test_number(self):
        d = run("She already got 0.81 on the new set.")
        self.assertFalse(d.allowed)
        self.assertNotIn("0.81", d.rewritten)
        self.assertIn("check2", d.reasons[0])

    def test_number_boundaries(self):
        self.assertTrue(run("Plan for 81 participants over 18 weeks.").allowed)
        self.assertFalse(run("We saw 0.81, roughly.").allowed)

    def test_bare_years_and_small_numbers_do_not_say_a_fact(self):
        from ntk import Fact
        f = Fact(id="lunch", text="Lunch with the recruiter on 03.02.2022 about a 20 hour role", label="private")
        req = Request("x", "stranger", "chat")
        self.assertTrue(check_reply("Our 2022 report covers 20 teams.", [f], req, judge=None).allowed)
        g = Fact(id="fee", text="The fee was $20k", label="private")
        self.assertFalse(check_reply("They paid $20k.", [g], req, judge=None).allowed)

    def test_contradiction_needs_a_thread(self):
        from ntk import Fact
        f = Fact(id="s", text="secret plan", label="private")
        out = '{"leak": true, "kind": "contradiction", "fact_id": "", "why": "conflicts"}'
        with mock.patch.object(judge_mod.shutil, "which", return_value="/bin/claude"), \
                mock.patch.object(judge_mod.subprocess, "run", return_value=mock.Mock(stdout=out)):
            self.assertIsNone(judge_mod.claude_judge("hi", [f], Request("x", "stranger", "chat"), []))
            self.assertIsNotNone(judge_mod.claude_judge("hi", [f], Request("x", "stranger", "chat"), ["earlier"]))

    def test_paraphrase_alias(self):
        d = run("I can send the patient cohort file.")
        self.assertFalse(d.allowed)
        self.assertEqual(d.rewritten, CANT_SHARE)

    def test_case_insensitive_verbatim(self):
        self.assertFalse(run("There is an UNPUBLISHED RESULT.").allowed)

    def test_only_leaky_sentence_removed(self):
        d = run("The published paper is the baseline. She got 0.81 on the new set.")
        self.assertFalse(d.allowed)
        self.assertIn("published paper is the baseline", d.rewritten)
        self.assertNotIn("0.81", d.rewritten)


class TestCheck3Hints(unittest.TestCase):
    def test_strong_hint_alone(self):
        d = run("She beat the baseline.")
        self.assertFalse(d.allowed)
        self.assertIn("check3", d.reasons[0])
        self.assertEqual(d.rewritten, "Anything after publication I can't share yet.")

    def test_weak_hint_alone_is_fine(self):
        self.assertTrue(run("A better plan is to start small.").allowed)

    def test_weak_hints_combine_with_thread(self):
        thread = ["Things have improved a lot for her."]
        d = run("Results look better on the new data.", thread=thread)
        self.assertFalse(d.allowed)
        self.assertIn("with thread", d.reasons[0])

    def test_thread_dicts_accepted(self):
        d = run("Results look better.", thread=[{"text": "it improved"}])
        self.assertFalse(d.allowed)


class TestLedger(unittest.TestCase):
    def test_every_reply_logged_with_labels(self):
        led = Ledger()
        run("Her methods and code are on the repo. Read the published paper.", ledger=led)
        run("She got 0.81.", ledger=led, now=2000.0)
        self.assertEqual(len(led.entries), 2)
        e0, e1 = led.entries
        self.assertEqual(e0.disclosed, {"methods": "role:collaborator", "paper": "public"})
        self.assertTrue(e0.allowed_as_drafted)
        self.assertFalse(e1.allowed_as_drafted)
        self.assertNotIn("0.81", e1.said)
        self.assertEqual(led.disclosed_to("jun-agent"), {"methods", "paper"})
        rows = [json.loads(l) for l in led.to_jsonl().splitlines()]
        self.assertEqual(rows[1]["ts"], 2000.0)


class TestLLMJudge(unittest.TestCase):
    def test_off_by_default_and_never_spawns(self):
        with mock.patch.dict(os.environ, {}, clear=False):
            os.environ.pop("NTK_LLM", None)
            self.assertIsNone(judge_mod.default_judge())
            with mock.patch("subprocess.run") as sp:
                check_reply("Hello.", maya_facts(), JUN, [], maya_policy())
                sp.assert_not_called()

    def test_on_only_with_env(self):
        with mock.patch.dict(os.environ, {"NTK_LLM": "claude"}):
            self.assertIs(judge_mod.default_judge(), judge_mod.claude_judge)

    def test_judge_verdict_declines(self):
        d = check_reply("Hello.", maya_facts(), JUN, [], maya_policy(), now=0,
                        judge=lambda *a: "'result_081' implies a new result")
        self.assertFalse(d.allowed)
        self.assertEqual(d.rewritten, CANT_SHARE)

    def test_claude_judge_strips_api_keys(self):
        fake = mock.Mock(stdout='{"leak": true, "fact_id": "result_081", "why": "x"}\n')
        with mock.patch.dict(os.environ, {"ANTHROPIC_API_KEY": "k"}), \
                mock.patch("shutil.which", return_value="/bin/claude"), \
                mock.patch("subprocess.run", return_value=fake) as sp:
            out = judge_mod.claude_judge("Hello.", maya_facts(), JUN, [])
        self.assertIn("result_081", out)
        args, kwargs = sp.call_args
        self.assertEqual(args[0][:2], ["claude", "-p"])
        self.assertNotIn("ANTHROPIC_API_KEY", kwargs["env"])


class TestExample(unittest.TestCase):
    def test_example_runs(self):
        import io
        import contextlib
        import maya_jun
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            maya_jun.main()
        out = buf.getvalue()
        self.assertEqual(out.count("allowed:  False"), 5)
        self.assertNotIn("sent:     She already got 0.81", out)


if __name__ == "__main__":
    unittest.main()
