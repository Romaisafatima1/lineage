"""lineage bisect: find the generation that broke an agent.

    python -m lineage.bisect --run full2 --lineage ungated-3 --every 5

Git bisect finds the commit that broke the build; this scores a lineage's
playbook *as it stood at each generation* on the locked test set, so you can
see exactly when learning turned into damage. Every historical playbook is in
the event log already. Appends `bisect` events the dashboard can show.
"""

import argparse
import asyncio
from pathlib import Path

from .agent import Playbook, score, triage
from .data import DATA_DIR, build_dataset, load_issues
from .llm import LLM
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
    states = {e["gen"]: e["playbook"] for e in ev if e["type"] == "state" and e["lineage"] == a.lineage}
    gens = [0] + [g for g in sorted(states) if g % a.every == 0 or g == max(states)]
    gens = sorted(set(gens))
    poison = next((e["gen"] for e in ev if e["type"] == "generation" and e.get("poisoned")), None)
    llm = LLM()
    log = EventLog(path)
    print(f"{a.lineage}: scoring the playbook at generations {gens} on the locked test ({len(ds.test)} issues)")
    for g in gens:
        pb = Playbook.seed(ds.kinds, ds.areas) if g == 0 else Playbook.from_dict(states[g])
        d, usd = await triage(llm, "agent", ds.test, pb, ds.kinds, ds.areas, a.repo)
        s = score(d)
        mark = "  <- poisoned batch learned here" if poison and g >= poison and g - a.every < poison else ""
        print(f"  gen {g:3}  rules {len(pb.rules):2}  locked test {s['both_acc']:.3f}  (kind {s['kind_acc']:.2f} area {s['area_acc']:.2f}){mark}")
        log.write({"type": "bisect", "lineage": a.lineage, "gen": g, "score": s, "rules": len(pb.rules),
                   "poison_gen": poison, "usd": round(usd, 4)})
    print(f"total ${llm.usage.usd:.2f}")


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--run", required=True)
    p.add_argument("--lineage", required=True)
    p.add_argument("--every", type=int, default=5)
    p.add_argument("--repo", default="kubernetes/kubernetes")
    asyncio.run(main_async(p.parse_args()))


if __name__ == "__main__":
    main()
