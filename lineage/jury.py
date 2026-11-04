"""
The gate: nothing changes the playbook until it passes here.

Three steps, each more expensive and rarer than the last:

1. validator  (code, free)     — malformed, empty, duplicate or self-referential edits
2. jury       (two models)     — run the EDITED playbook on validation cases the agent
                                 never learns from, with Muse Spark and Muse Spark Open,
                                 and compare with the current playbook's score. Also run
                                 the canary cases: things the agent already gets right
                                 must stay right.
3. arbiter    (Muse Wonder)    — only when the jurors split or the result is a wash;
                                 rules at high reasoning, and its ruling goes to the
                                 human review queue, where a person can override.

The gate is empirical: edits are judged on known answers, not on a model's
opinion of the edit. The second juror is a different deployment a team could
self-host, and we record how often the two jurors agree rather than assume it.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass

from .agent import Playbook, score, triage
from .data import Issue
from .llm import LLM

JURORS = ("juror_spark", "juror_open")


# ---------- step 1: validator ----------

def validate(edit: dict, playbook: Playbook) -> tuple[bool, str]:
    if not isinstance(edit, dict):
        return False, "edit is not an object"
    op = edit.get("op")
    if op not in ("add", "change", "delete"):
        return False, f"unknown op {op!r}"
    text = (edit.get("text") or "").strip()
    if op in ("add", "change"):
        if len(text) < 15:
            return False, "rule text too short to be checkable"
        if len(text) > 400:
            return False, "rule text too long"
        norm = text.lower()
        for r in playbook.rules:
            if r.text.lower() == norm:
                return False, f"duplicate of {r.id}"
        if any(w in norm for w in ("issue #", "this issue", "the above issue")):
            return False, "rule refers to a single issue, not a general pattern"
    if op in ("change", "delete"):
        rid = edit.get("rule_id")
        if not rid or playbook.get(rid) is None:
            return False, f"rule_id {rid!r} not in playbook"
        if playbook.get(rid).gen == 0 and op == "delete":
            return False, "seed rules cannot be deleted"
    if op == "delete" and len(playbook.rules) <= 2:
        return False, "playbook would be empty"
    return True, "ok"


# ---------- step 2: jury ----------

def pb_hash(pb: Playbook) -> str:
    return hashlib.sha1(pb.render().encode()).hexdigest()[:10]


@dataclass
class Verdict:
    decision: str            # accept | reject | review
    reason: str
    votes: dict              # juror -> accept/reject/neutral
    scores: dict             # juror -> {"old": .., "new": ..}
    canary: dict             # {"passed": bool, "correct": n, "n": n}
    arbiter: dict | None     # Wonder's ruling if it ran
    usd: float


class Jury:
    def __init__(self, llm: LLM, val: list[Issue], canary: list[Issue],
                 kinds: list[str], areas: list[str], repo: str):
        self.llm, self.val, self.canary = llm, val, canary
        self.kinds, self.areas, self.repo = kinds, areas, repo
        self._cache: dict[tuple[str, str], dict] = {}   # (juror, playbook hash) -> score
        self.agreements = {"agree": 0, "split": 0}

    async def _score(self, juror: str, pb: Playbook, cases: list[Issue]) -> tuple[dict, float]:
        key = (juror, pb_hash(pb), len(cases))
        if key in self._cache:
            return self._cache[key], 0.0
        decisions, usd = await triage(self.llm, juror, cases, pb, self.kinds, self.areas, self.repo)
        s = score(decisions)
        self._cache[key] = s
        return s, usd

    async def judge(self, old: Playbook, new: Playbook, edit: dict) -> Verdict:
        import asyncio
        usd = 0.0
        # Both jurors score old and new on the validation set. Old scores are cached,
        # so each edit costs roughly one validation pass per juror.
        tasks = []
        for j in JURORS:
            tasks.append(self._score(j, old, self.val))
            tasks.append(self._score(j, new, self.val))
        tasks.append(self._score("juror_spark", new, self.canary))
        results = await asyncio.gather(*tasks)
        usd += sum(r[1] for r in results)
        scores, votes = {}, {}
        for i, j in enumerate(JURORS):
            old_s, new_s = results[2 * i][0], results[2 * i + 1][0]
            scores[j] = {"old": old_s["both_acc"], "new": new_s["both_acc"]}
            d = new_s["both_acc"] - old_s["both_acc"]
            votes[j] = "accept" if d > 0 else ("reject" if d < 0 else "neutral")
        can = results[-1][0]
        canary = {"passed": can["both_acc"] >= 0.9, "correct": round(can["both_acc"] * can["n"]), "n": can["n"]}

        if votes[JURORS[0]] == votes[JURORS[1]]:
            self.agreements["agree"] += 1
        else:
            self.agreements["split"] += 1

        if not canary["passed"]:
            return Verdict("reject", f"canary regression: {canary['correct']}/{canary['n']} kept",
                           votes, scores, canary, None, usd)
        vs = set(votes.values())
        if vs == {"accept"}:
            return Verdict("accept", "both jurors improved on validation", votes, scores, canary, None, usd)
        if vs == {"reject"} or (vs == {"reject", "neutral"}):
            return Verdict("reject", "validation score dropped", votes, scores, canary, None, usd)
        # Split or a wash: escalate to the arbiter, then to the human queue.
        ruling, cost = await self.arbitrate(old, new, edit, scores, canary)
        usd += cost
        decision = "review" if {"accept", "reject"} <= vs else ruling["decision"]
        return Verdict(decision, ruling["reason"], votes, scores, canary, ruling, usd)

    # ---------- step 3: arbiter ----------

    ARBITER_SYSTEM = """You are the arbiter for a self-improving triage agent.
Two jurors scored a proposed playbook edit on held-out cases and did not clearly agree.
Decide whether the edit should be kept. Prefer rejecting edits whose gain is within noise
(one case on a 40-case set is 2.5 points) or that narrow a rule to a single situation.
Return JSON: {"decision": "accept" | "reject", "reason": "two sentences for a human reviewer"}"""

    async def arbitrate(self, old: Playbook, new: Playbook, edit: dict, scores: dict, canary: dict):
        user = (f"TASK: arbitrate\n\nPROPOSED EDIT:\n{json.dumps(edit)}\n\n"
                f"CURRENT PLAYBOOK:\n{old.render()}\n\nEDITED PLAYBOOK:\n{new.render()}\n\n"
                f"VALIDATION SCORES (accuracy on both labels):\n{json.dumps(scores)}\n"
                f"CANARY: {canary['correct']}/{canary['n']} kept\n")
        try:
            data, meta = await self.llm.chat_json("arbiter", self.ARBITER_SYSTEM, user,
                                                  reasoning="high", max_tokens=12000)
            dec = "accept" if str(data.get("decision", "")).lower().startswith("acc") else "reject"
            return {"decision": dec, "reason": str(data.get("reason", ""))[:500], "model": meta["model"]}, meta["usd"]
        except Exception as e:  # Wonder is in preview; never let it stall a run
            return {"decision": "reject", "reason": f"arbiter unavailable ({type(e).__name__}); defaulting to reject",
                    "model": "none"}, 0.0