"""Fast offline tests: run with `python -m pytest -q` (or `python -m unittest`)."""

import asyncio
import json
import unittest

from lineage.agent import Playbook, score
from lineage.data import build_dataset, make_synthetic, parse_issue
from lineage.jury import validate
from lineage.llm import MockLLM, extract_json


class TestJsonParsing(unittest.TestCase):
    def test_plain(self):
        self.assertEqual(extract_json('{"a": 1}'), {"a": 1})

    def test_wrapped_in_prose_and_fence(self):
        txt = 'Sure, here you go:\n```json\n{"decisions": [{"id": "1"}]}\n```\nDone.'
        self.assertEqual(extract_json(txt)["decisions"][0]["id"], "1")

    def test_braces_inside_strings(self):
        self.assertEqual(extract_json('{"t": "a } b"}'), {"t": "a } b"})


class TestPlaybook(unittest.TestCase):
    def test_apply_does_not_mutate_original(self):
        pb = Playbook.seed(["bug"], ["node"])
        new = pb.apply({"op": "add", "text": "Kubelet reports belong to area node."}, gen=1, edit_id="e1")
        self.assertEqual(len(pb.rules) + 1, len(new.rules))
        self.assertEqual(new.rules[-1].edit_id, "e1")

    def test_change_and_delete(self):
        pb = Playbook.seed(["bug"], ["node"])
        pb = pb.apply({"op": "add", "text": "Temporary rule for testing purposes."}, 1, "e1")
        rid = pb.rules[-1].id
        pb2 = pb.apply({"op": "change", "rule_id": rid, "text": "Changed rule for testing purposes."}, 2, "e2")
        self.assertEqual(pb2.get(rid).text, "Changed rule for testing purposes.")
        pb3 = pb2.apply({"op": "delete", "rule_id": rid}, 3, "e3")
        self.assertIsNone(pb3.get(rid))

    def test_roundtrip(self):
        pb = Playbook.seed(["bug", "feature"], ["node", "network"])
        self.assertEqual(Playbook.from_dict(json.loads(json.dumps(pb.to_dict()))).render(), pb.render())


class TestValidator(unittest.TestCase):
    def setUp(self):
        self.pb = Playbook.seed(["bug"], ["node"])

    def test_rejects_short_and_duplicate(self):
        self.assertFalse(validate({"op": "add", "text": "short"}, self.pb)[0])
        dup = {"op": "add", "text": self.pb.rules[0].text}
        self.assertFalse(validate(dup, self.pb)[0])

    def test_rejects_single_issue_rules_and_seed_deletes(self):
        self.assertFalse(validate({"op": "add", "text": "This issue #123 is a bug about kubelet."}, self.pb)[0])
        self.assertFalse(validate({"op": "delete", "rule_id": "R1"}, self.pb)[0])

    def test_accepts_good_rule(self):
        ok, why = validate({"op": "add", "text": "Reports mentioning kubelet belong to area node."}, self.pb)
        self.assertTrue(ok, why)


class TestData(unittest.TestCase):
    def test_parse_issue_filters(self):
        raw = {"number": 1, "title": "kubelet panics on restart", "body": "x",
               "labels": [{"name": "kind/bug"}, {"name": "sig/node"}], "html_url": "u"}
        self.assertEqual(parse_issue(raw).areas, ["node"])
        raw["labels"].append({"name": "sig/network"})
        self.assertEqual(parse_issue(raw).areas, ["network", "node"])   # two sigs: either counts
        raw["labels"].append({"name": "sig/storage"})
        self.assertIsNone(parse_issue(raw))           # three: too ambiguous
        self.assertIsNone(parse_issue({**raw, "pull_request": {}}))

    def test_splits_are_disjoint_and_deterministic(self):
        a = build_dataset(make_synthetic(), val_n=20, probe_n=20, test_n=30, min_per_label=5)
        b = build_dataset(make_synthetic(), val_n=20, probe_n=20, test_n=30, min_per_label=5)
        ids = lambda xs: {i.id for i in xs}
        self.assertEqual(ids(a.test), ids(b.test))
        self.assertTrue(ids(a.test).isdisjoint(ids(a.learn) | ids(a.val) | ids(a.probe)))


class TestScore(unittest.TestCase):
    def test_both_requires_both(self):
        d = [{"kind": "bug", "area": "node", "true_kind": "bug", "true_areas": ["net"]},
             {"kind": "bug", "area": "node", "true_kind": "bug", "true_areas": ["net", "node"]}]
        s = score(d)
        self.assertEqual((s["kind_acc"], s["area_acc"], s["both_acc"]), (1.0, 0.5, 0.5))


class TestMockEndToEnd(unittest.TestCase):
    def test_mock_llm_costs_nothing_real(self):
        llm = MockLLM()
        text, meta = asyncio.run(llm.chat("agent", "s", "TASK: triage\nISSUE 1: kubelet crashes"))
        self.assertIn("decisions", json.loads(text))
        self.assertLess(llm.usage.usd, 0.01)


if __name__ == "__main__":
    unittest.main()
