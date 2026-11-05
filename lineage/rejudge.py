"""Re-judge specific edits from a finished run with the full jury.

    python -m lineage.rejudge --run full --edits ungated-2-g12 ungated-3-g12 gated-1-g2

Used when the second juror's provider was unavailable during the run: the
edited playbook is rebuilt from the log and judged again by Muse Spark and the
open-weights juror (wherever JUROR2_* points). Appends `rejudge` events.
"""

import argparse
import asyncio
from pathlib import Path

from .agent import Playbook
from .data import DATA_DIR, build_dataset, load_issues
from .jury import Jury
from .llm import LLM, ROLE_MODELS
from .run import EventLog


async def main_async(a):
    path = Path("runs") / a.run / "events.jsonl"
    ev = EventLog.read(path)
    cfg = next(e for e in ev if e["type"] == "run_start")["config"]
    ds = build_dataset(load_issues(DATA_DIR / f"{a.repo.replace('/', '__')}.jsonl"),
                       val_n=cfg["val"], probe_n=cfg["probe_n"], test_n=cfg["test_n"], seed=cfg["seed"])
    if cfg.get("convention"):
        from .run import apply_convention
        ds = apply_convention(ds, cfg["convention"])
    canary_ids = set(next(e for e in ev if e["type"] == "canaries")["ids"])
    canaries = [i for i in ds.val if i.id in canary_ids]
    llm = LLM()
    jury = Jury(llm, ds.val, canaries, ds.kinds, ds.areas, a.repo)
    print(f"juror 2: {ROLE_MODELS['juror_open'][0]} via {llm.juror2_host}")
    log = EventLog(path)
    for eid in a.edits:
        e = next((x for x in ev if x["type"] == "edit" and x["edit_id"] == eid), None)
        if not e or not e["valid"]:
            print(f"{eid}: not found or invalid"); continue
        old = Playbook.from_dict(e["before"])
        new = old.apply(e["edit"], e["gen"], eid)
        v = await jury.judge(old, new, e["edit"])
        print(f"{eid:16} original: {e['decision']:7} | full jury: {v.decision:7} {v.reason}")
        print(f"                 votes {v.votes}  canary {v.canary['correct']}/{v.canary['n']} (was {v.canary['before']})")
        log.write({"type": "rejudge", "edit_id": eid, "lineage": e["lineage"], "gen": e["gen"],
                   "original_decision": e["decision"], "decision": v.decision, "reason": v.reason,
                   "votes": v.votes, "scores": v.scores, "canary": v.canary, "arbiter": v.arbiter,
                   "juror2_model": ROLE_MODELS["juror_open"][0], "juror2_host": llm.juror2_host,
                   "usd": round(v.usd, 4)})
    print(f"total ${llm.usage.usd:.2f}")


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--run", required=True)
    p.add_argument("--edits", nargs="+", required=True)
    p.add_argument("--repo", default="kubernetes/kubernetes")
    asyncio.run(main_async(p.parse_args()))


if __name__ == "__main__":
    main()
