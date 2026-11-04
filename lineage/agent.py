"""
The learning agent: a frozen model plus a playbook it rewrites.

- `Playbook` is an ordered list of rules. Each rule remembers which edit and
  generation created it, which is what makes blame possible later.
- `triage()` labels a batch of issues using the playbook. Every decision names
  the rule ids it relied on, so a wrong call can be traced to a rule.
- `propose_edit()` shows the agent its mistakes and asks for ONE structured
  edit. Structured edits are what let the jury test, diff and reject them.
- `score()` is plain accuracy against the project's real labels.
"""

from __future__ import annotations

import copy
import json
from dataclasses import dataclass, field

from .data import Issue
from .llm import LLM

BATCH = 5  # issues per model call; keeps cost down without hurting accuracy


@dataclass
class Rule:
    id: str
    text: str
    gen: int
    edit_id: str | None = None


@dataclass
class Playbook:
    rules: list[Rule] = field(default_factory=list)
    next_id: int = 1

    @classmethod
    def seed(cls, kinds: list[str], areas: list[str]) -> "Playbook":
        """The starting playbook every lineage begins from: label definitions only."""
        pb = cls()
        pb.add(f"Kinds: {', '.join(kinds)}. Choose the single best kind.", gen=0)
        pb.add(f"Areas (owning teams): {', '.join(areas)}. Choose the single best area.", gen=0)
        pb.add("If a report describes incorrect behaviour of existing functionality, kind is bug.", gen=0)
        return pb

    def add(self, text: str, gen: int, edit_id: str | None = None) -> Rule:
        r = Rule(id=f"R{self.next_id}", text=text.strip(), gen=gen, edit_id=edit_id)
        self.next_id += 1
        self.rules.append(r)
        return r

    def get(self, rule_id: str) -> Rule | None:
        return next((r for r in self.rules if r.id == rule_id), None)

    def render(self) -> str:
        return "\n".join(f"[{r.id}] {r.text}" for r in self.rules)

    def to_dict(self) -> dict:
        return {"rules": [r.__dict__ for r in self.rules], "next_id": self.next_id}

    @classmethod
    def from_dict(cls, d: dict) -> "Playbook":
        pb = cls(next_id=d["next_id"])
        pb.rules = [Rule(**r) for r in d["rules"]]
        return pb

    def apply(self, edit: dict, gen: int, edit_id: str) -> "Playbook":
        """Return a NEW playbook with the edit applied. The original is untouched,
        so a rejected edit leaves no trace and rollback is just 'use the old one'."""
        pb = copy.deepcopy(self)
        op = edit["op"]
        if op == "add":
            pb.add(edit["text"], gen, edit_id)
        elif op == "change":
            r = pb.get(edit["rule_id"])
            if r is None:
                raise ValueError(f"no rule {edit['rule_id']}")
            r.text, r.gen, r.edit_id = edit["text"].strip(), gen, edit_id
        elif op == "delete":
            before = len(pb.rules)
            pb.rules = [r for r in pb.rules if r.id != edit["rule_id"]]
            if len(pb.rules) == before:
                raise ValueError(f"no rule {edit['rule_id']}")
        else:
            raise ValueError(f"unknown op {op}")
        return pb


TRIAGE_SYSTEM = """You are an issue-triage agent for the {repo} project.
For each issue, decide its kind and the area (owning team), following the PLAYBOOK rules strictly.
Return JSON: {{"decisions": [{{"id": "...", "kind": "...", "area": "...", "confidence": 0.0-1.0, "rule_ids": ["R1"]}}]}}
rule_ids lists the playbook rules you relied on for that decision."""


def triage_prompt(issues: list[Issue], playbook: Playbook, kinds: list[str], areas: list[str]) -> str:
    return (f"KINDS: {', '.join(kinds)}\nAREAS: {', '.join(areas)}\n\n"
            f"PLAYBOOK:\n{playbook.render()}\n\nTASK: triage\n\n"
            + "\n".join(i.prompt_block() for i in issues))


async def triage(llm: LLM, role: str, issues: list[Issue], playbook: Playbook,
                 kinds: list[str], areas: list[str], repo: str) -> tuple[list[dict], float]:
    """Label `issues` in batches. Returns (decisions, usd)."""
    decisions: list[dict] = []
    usd = 0.0
    import asyncio
    batches = [issues[i:i + BATCH] for i in range(0, len(issues), BATCH)]

    async def one(batch):
        data, meta = await llm.chat_json(role, TRIAGE_SYSTEM.format(repo=repo),
                                         triage_prompt(batch, playbook, kinds, areas),
                                         reasoning="low", max_tokens=4000)
        got = {str(d.get("id")): d for d in data.get("decisions", [])}
        out = []
        for iss in batch:
            d = got.get(iss.id, {})
            out.append({"id": iss.id, "kind": str(d.get("kind", "")).strip(),
                        "area": str(d.get("area", "")).strip(),
                        "confidence": float(d.get("confidence", 0) or 0),
                        "rule_ids": [str(x) for x in (d.get("rule_ids") or [])],
                        "true_kind": iss.kind, "true_areas": list(iss.areas)})
        return out, meta["usd"]

    for out, cost in await asyncio.gather(*(one(b) for b in batches)):
        decisions.extend(out)
        usd += cost
    return decisions, usd


def score(decisions: list[dict]) -> dict:
    """Accuracy on kind, on area, and on both at once (the headline number)."""
    n = max(len(decisions), 1)
    k = sum(d["kind"] == d["true_kind"] for d in decisions)
    a = sum(d["area"] in d["true_areas"] for d in decisions)
    b = sum(d["kind"] == d["true_kind"] and d["area"] in d["true_areas"] for d in decisions)
    return {"kind_acc": round(k / n, 4), "area_acc": round(a / n, 4), "both_acc": round(b / n, 4), "n": n}


PROPOSE_SYSTEM = """You are improving your own triage playbook from experience.
You will see a batch of issues, your decisions, and the correct labels.
Propose exactly ONE edit that would most reduce mistakes like these, as a general rule (never about a single issue).
Return JSON: {"op": "add" | "change" | "delete", "rule_id": "R3" or null, "text": "the rule", "reason": "one sentence"}
Rules must be specific and checkable, e.g. "Reports of kubelet or cgroup problems belong to area node."
Do not restate rules that already exist."""


async def propose_edit(llm: LLM, decisions: list[dict], issues: list[Issue],
                       playbook: Playbook) -> tuple[dict, float]:
    by_id = {i.id: i for i in issues}
    lines = []
    for d in decisions:
        iss = by_id[d["id"]]
        mark = "OK " if (d["kind"] == d["true_kind"] and d["area"] in d["true_areas"]) else "MISS"
        lines.append(f"{mark} #{iss.id} \"{iss.title[:100]}\" -> you said {d['kind']}/{d['area']}, "
                     f"correct {d['true_kind']}/{' or '.join(d['true_areas'])}")
    user = (f"PLAYBOOK:\n{playbook.render()}\n\nTASK: propose_edit\n\nRESULTS:\n" + "\n".join(lines))
    data, meta = await llm.chat_json("agent", PROPOSE_SYSTEM, user, reasoning="medium", max_tokens=6000)
    return data, meta["usd"]