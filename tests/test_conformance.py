"""Cross-implementation conformance: the same cases run in js/test/conformance.test.mjs."""

import json
import os
import sys
import unittest

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "conformance"))

from generate import CASES, run_case  # noqa: E402


class TestConformance(unittest.TestCase):
    def test_all_cases(self):
        with open(CASES, encoding="utf-8") as fh:
            cases = json.load(fh)["cases"]
        self.assertGreaterEqual(len(cases), 20)
        for case in cases:
            with self.subTest(case["name"]):
                self.assertEqual(run_case(case), case["expect"])


if __name__ == "__main__":
    unittest.main()
