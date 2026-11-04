"""Quick diagnostics on a finished run.

    python -m lineage.diag --run full

Prints: probe-set accuracy per lineage over generations (less noisy than batch
accuracy), the edits proposed from the poisoned batch, how many edits each
lineage applied, and the model's own noise floor: the seed playbook scored on
the locked test set three times, with pairwise disagreement between passes.
"""

import argparse
import asyncio
import json
from collections import defaultdict
from pathlib import Path

from .agent import Playbook, score, triage
from .data import DATA_DIR, build_dataset, load_issues
from .llm import LLM
from .run import EventLog


async def noise_floor(ds, repo, passes=3):
    llm = LLM()
    pb = Playbook.seed(ds.kinds, ds.areas)
    runs = []
    for _ in range(passes):
        d, _ = await triage(llm, "agent", ds.test, pb, ds.kinds, ds.areas, repo)
        runs.append(d)
        print(f"  pass {len(runs)}: both={score(d)['both_acc']:.3f}")
    dis = []
    for i in range(passes):
        for j in range(i + 1, passes):
            a, b = runs[i], runs[j]
            dis.append(sum((x["kind"], x["area"]) != (y["kind"], y["area"]) for x, y in zip(a, b)) / len(a))
    print(f"  same playbook, same issues: passes disagree on {100 * sum(dis) / len(dis):.0f}% of cases (${llm.usage.usd:.2f})")
    return runs, dis


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--run", required=True)
    p.add_argument("--repo", default="kubernetes/kubernetes")
    p.add_argument("--no-noise", action="store_true")
    a = p.parse_args()
    ev = EventLog.read(Path("runs") / a.run / "events.jsonl")

    print("\nPROBE ACCURACY (fixed 50 issues) by generation")
    probes = defaultdict(dict)
    for e in ev:
        if e["type"] == "probe":
            probes[e["lineage"]][e["gen"]] = e["score"]["both_acc"]
    gens = sorted({g for v in probes.values() for g in v})
    print("lineage      " + " ".join(f"g{g:<4}" for g in gens))
    for ln, v in sorted(probes.items()):
        print(f"{ln:12} " + " ".join(f"{v.get(g, float('nan')):.2f} " for g in gens))

    print("\nEDITS APPLIED per lineage")
    for e in ev:
        if e["type"] == "state" and e["gen"] == max(x["gen"] for x in ev if x["type"] == "state"):
            print(f"  {e['lineage']:12} proposed {e['edits_proposed']:3}  applied {e['edits_applied']:3}  rules now {len(e['playbook']['rules'])}")

    print("\nEDITS PROPOSED FROM THE POISONED BATCH")
    for e in ev:
        if e["type"] == "edit" and e.get("poisoned_batch"):
            print(f"  {e['lineage']:12} {e['edit']['op']:6} -> {e['decision']:8} {e['reason'][:60]}")
            print(f"               \"{(e['edit'].get('text') or '')[:160]}\"")

    print("\nINVALID reasons")
    inv = defaultdict(int)
    for e in ev:
        if e["type"] == "edit" and e["decision"] == "invalid":
            inv[e["validator_reason"]] += 1
    for k, v in inv.items():
        print(f"  {v:3} {k}")

    if not a.no_noise:
        print("\nNOISE FLOOR: seed playbook on the locked test set, 3 passes")
        cfg = next(e for e in ev if e["type"] == "run_start")["config"]
        ds = build_dataset(load_issues(DATA_DIR / f"{a.repo.replace('/', '__')}.jsonl"),
                           val_n=cfg["val"], probe_n=cfg["probe_n"], test_n=cfg["test_n"], seed=cfg["seed"])
        asyncio.run(noise_floor(ds, a.repo))


if __name__ == "__main__":
    main()