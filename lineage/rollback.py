"""
Blame and rollback, computed from the event log.

    python -m lineage.rollback --run full --lineage ungated-1 --blame 123456
    python -m lineage.rollback --run full --lineage ungated-1 --edit ungated-1-g12

--blame <issue id>  : which rule drove the lineage's final decision on that issue,
                      and which edit (generation, verdict) created the rule.
--edit <edit id>    : rebuild the lineage's playbook WITHOUT that edit, score both
                      playbooks on validation and the locked test set, and append a
                      `rollback` event the dashboard shows. Costs a few cents.
"""

from __future__ import annotations

import argparse
import asyncio
import json
from pathlib import Path

from .agent import Playbook, score, triage
from .data import DATA_DIR, build_dataset, load_issues
from .llm import LLM
from .run import EventLog


def applied_edits(events: list[dict], lineage: str) -> list[dict]:
    return [e for e in events if e["type"] == "edit" and e["lineage"] == lineage and e.get("applied")]


def rebuild(events: list[dict], lineage: str, kinds, areas, skip: str | None = None) -> Playbook:
    """Replay every applied edit from the seed playbook, optionally skipping one.
    Rule ids stay stable: a skipped 'add' still consumes its id."""
    pb = Playbook.seed(kinds, areas)
    for e in applied_edits(events, lineage):
        if e["edit_id"] == skip:
            if e["edit"]["op"] == "add":
                pb.next_id += 1
            continue
        try:
            pb = pb.apply(e["edit"], e["gen"], e["edit_id"])
        except ValueError:
            pass   # a later edit touched a rule the skipped edit created
    return pb


def blame(events: list[dict], lineage: str, issue_id: str) -> dict:
    final = next((e for e in events if e["type"] == "final_test" and e["lineage"] == lineage), None)
    if not final:
        raise SystemExit("no final_test event yet for that lineage")
    d = next((x for x in final["decisions"] if x["id"] == issue_id), None)
    if not d:
        raise SystemExit("issue not in the locked test set")
    pb = Playbook.from_dict(final["playbook"])
    edits = {e["edit_id"]: e for e in events if e["type"] == "edit"}
    trail = []
    for rid in d["rule_ids"]:
        r = pb.get(rid)
        if not r:
            continue
        e = edits.get(r.edit_id) if r.edit_id else None
        trail.append({"rule": rid, "text": r.text, "gen": r.gen, "edit_id": r.edit_id,
                      "verdict": e and e.get("decision"), "reason": e and e.get("reason"),
                      "poisoned_batch": e and e.get("poisoned_batch")})
    return {"issue": issue_id, "decision": {"kind": d["kind"], "area": d["area"]},
            "truth": {"kind": d["true_kind"], "areas": d["true_areas"]},
            "correct": d["kind"] == d["true_kind"] and d["area"] in d["true_areas"], "rules": trail}


async def rollback(run: str, lineage: str, edit_id: str, repo: str):
    path = Path("runs") / run / "events.jsonl"
    events = EventLog.read(path)
    cfg = next(e for e in events if e["type"] == "run_start")["config"]
    ds = build_dataset(load_issues(DATA_DIR / f"{repo.replace('/', '__')}.jsonl"),
                       val_n=cfg["val"], probe_n=cfg["probe_n"], test_n=cfg["test_n"], seed=cfg["seed"])
    with_edit = rebuild(events, lineage, ds.kinds, ds.areas)
    without = rebuild(events, lineage, ds.kinds, ds.areas, skip=edit_id)
    llm = LLM()
    out = {}
    for label, pb in (("with", with_edit), ("without", without)):
        dv, u1 = await triage(llm, "agent", ds.val, pb, ds.kinds, ds.areas, repo)
        dt, u2 = await triage(llm, "agent", ds.test, pb, ds.kinds, ds.areas, repo)
        out[label] = {"val": score(dv), "test": score(dt), "playbook": pb.to_dict()}
        print(f"{label:8} val={out[label]['val']['both_acc']:.3f} test={out[label]['test']['both_acc']:.3f}")
    EventLog(path).write({"type": "rollback", "lineage": lineage, "edit_id": edit_id, **out,
                          "usd": round(llm.usage.usd, 4)})
    print(f"rollback event written (${llm.usage.usd:.2f})")


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--run", required=True)
    p.add_argument("--lineage", required=True)
    p.add_argument("--repo", default="kubernetes/kubernetes")
    p.add_argument("--blame", help="issue id to explain")
    p.add_argument("--edit", help="edit id to roll back")
    a = p.parse_args()
    events = EventLog.read(Path("runs") / a.run / "events.jsonl")
    if a.blame:
        print(json.dumps(blame(events, a.lineage, a.blame), indent=2))
    elif a.edit:
        asyncio.run(rollback(a.run, a.lineage, a.edit, a.repo))
    else:
        for e in applied_edits(events, a.lineage):
            print(f"{e['edit_id']:16} g{e['gen']:02d} {e['edit']['op']:6} {e['edit'].get('text', '')[:80]}")


if __name__ == "__main__":
    main()
